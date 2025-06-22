"""
MCP Gateway Service Configuration
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPServerConfig(BaseModel):
    """Configuration for an individual MCP server."""

    name: str = Field(..., description="Server name identifier")
    description: str = Field(..., description="Server description")
    host: str = Field(..., description="Server host")
    port: int = Field(..., description="Server port")
    health_endpoint: str = Field(
        default="/health", description="HTTP health check endpoint"
    )
    mcp_endpoint: str = Field(default="/mcp", description="MCP protocol endpoint")
    enabled: bool = Field(default=True, description="Whether server is enabled")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_attempts: int = Field(
        default=3, description="Number of retry attempts for failed requests"
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorizing tools"
    )


class AuthConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = Field(default=True, description="Whether auth is enabled")
    secret_key: str = Field(..., description="JWT secret key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration time"
    )


class GatewaySettings(BaseSettings):
    """Main gateway configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Gateway host")
    port: int = Field(default=8080, description="Gateway port")
    debug: bool = Field(default=False, description="Debug mode")

    # Health monitoring
    health_check_interval: int = Field(
        default=30, description="Health check interval in seconds"
    )
    health_timeout: int = Field(
        default=10, description="Health check timeout in seconds"
    )

    # Tool discovery
    tool_discovery_interval: int = Field(
        default=60, description="Tool discovery interval in seconds"
    )

    # Auth settings
    auth: AuthConfig = Field(
        default_factory=lambda: AuthConfig(
            enabled=True,
            secret_key="your-secret-key-change-in-production",
        )
    )

    # MCP servers configuration
    mcp_servers: Dict[str, MCPServerConfig] = Field(
        default_factory=lambda: {
            "weather": MCPServerConfig(
                name="weather",
                description="Weather information service",
                host="localhost",
                port=8001,
                tags=["weather", "forecast"],
            ),
            "news": MCPServerConfig(
                name="news",
                description="News and articles service",
                host="localhost",
                port=8002,
                tags=["news", "articles"],
            ),
        }
    )

    # CORS settings
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"], description="Allowed CORS origins"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format",
    )


# Global settings instance
settings = GatewaySettings()
