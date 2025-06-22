"""
Authentication and authorization for MCP Gateway
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)


class User(BaseModel):
    """User model."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: bool = False
    permissions: Set[str] = set()
    allowed_tools: Set[str] = set()
    allowed_servers: Set[str] = set()


class UserInDB(User):
    """User model with hashed password."""

    hashed_password: str


class Token(BaseModel):
    """Token model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data model."""

    username: Optional[str] = None


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()


class AuthManager:
    """Authentication and authorization manager."""

    def __init__(self) -> None:
        # In production, this would come from a database
        # For demo purposes, we'll use a simple in-memory store
        self.users_db: Dict[str, UserInDB] = {
            "admin": UserInDB(
                username="admin",
                email="admin@company.com",
                full_name="Administrator",
                hashed_password=self._get_password_hash("admin123"),
                permissions={"admin", "read", "write", "execute"},
                allowed_tools={"*"},  # All tools
                allowed_servers={"*"},  # All servers
            ),
            "team_a": UserInDB(
                username="team_a",
                email="team_a@company.com",
                full_name="Team A",
                hashed_password=self._get_password_hash("team_a123"),
                permissions={"read", "execute"},
                allowed_tools={"weather_*", "news_*"},
                allowed_servers={"weather", "news"},
            ),
            "team_b": UserInDB(
                username="team_b",
                email="team_b@company.com",
                full_name="Team B",
                hashed_password=self._get_password_hash("team_b123"),
                permissions={"read", "execute"},
                allowed_tools={"weather_*"},
                allowed_servers={"weather"},
            ),
        }

    def _get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get user by username."""
        return self.users_db.get(username)

    def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """Authenticate a user."""
        user = self.get_user(username)
        if not user:
            return None
        if not self._verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(
        self, data: Dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.auth.access_token_expire_minutes
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, settings.auth.secret_key, algorithm=settings.auth.algorithm
        )
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify a JWT token."""
        try:
            payload = jwt.decode(
                token, settings.auth.secret_key, algorithms=[settings.auth.algorithm]
            )
            username: str = payload.get("sub")
            if username is None:
                return None
            token_data = TokenData(username=username)
            return token_data
        except JWTError:
            return None

    def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from token."""
        token_data = self.verify_token(token)
        if token_data is None or token_data.username is None:
            return None

        user = self.get_user(username=token_data.username)
        if user is None:
            return None

        return User(**user.dict())

    def check_permission(self, user: User, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in user.permissions or "admin" in user.permissions

    def check_tool_access(self, user: User, tool_name: str) -> bool:
        """Check if user has access to a specific tool."""
        if "*" in user.allowed_tools or "admin" in user.permissions:
            return True

        # Check exact match
        if tool_name in user.allowed_tools:
            return True

        # Check wildcard patterns
        for allowed_pattern in user.allowed_tools:
            if allowed_pattern.endswith("*"):
                prefix = allowed_pattern[:-1]
                if tool_name.startswith(prefix):
                    return True

        return False

    def check_server_access(self, user: User, server_name: str) -> bool:
        """Check if user has access to a specific server."""
        if "*" in user.allowed_servers or "admin" in user.permissions:
            return True

        return server_name in user.allowed_servers

    def get_user_tools(self, user: User, available_tools: List[str]) -> List[str]:
        """Get list of tools user has access to."""
        if "*" in user.allowed_tools or "admin" in user.permissions:
            return available_tools

        allowed_tools = []
        for tool_name in available_tools:
            if self.check_tool_access(user, tool_name):
                allowed_tools.append(tool_name)

        return allowed_tools

    def get_user_servers(self, user: User, available_servers: List[str]) -> List[str]:
        """Get list of servers user has access to."""
        if "*" in user.allowed_servers or "admin" in user.permissions:
            return available_servers

        allowed_servers = []
        for server_name in available_servers:
            if self.check_server_access(user, server_name):
                allowed_servers.append(server_name)

        return allowed_servers


# Global auth manager instance
auth_manager = AuthManager()


def get_current_user_from_token(credentials: HTTPAuthorizationCredentials) -> User:
    """Get current user from authorization header."""
    if not settings.auth.enabled:
        # Return a default admin user when auth is disabled
        return User(
            username="anonymous",
            permissions={"admin", "read", "write", "execute"},
            allowed_tools={"*"},
            allowed_servers={"*"},
        )

    user = auth_manager.get_current_user(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(required_permission: str):
    """Decorator to require a specific permission."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be implemented as a FastAPI dependency
            # For now, we'll just return the function
            return func(*args, **kwargs)

        return wrapper

    return decorator
