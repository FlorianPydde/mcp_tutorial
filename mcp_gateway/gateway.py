"""
Main MCP Gateway Service

This service acts as both an MCP client (to backend servers) and MCP server
(to frontend clients), providing routing, authentication, and health monitoring.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from .auth import User, auth_manager, get_current_user_from_token, security
from .config import settings
from .health import HealthMonitor
from .tool_discovery import ToolRegistry

logger = logging.getLogger(__name__)


class MCPRequest(BaseModel):
    """MCP JSON-RPC request model."""

    jsonrpc: str = "2.0"
    id: Any
    method: str
    params: Dict = {}


class MCPResponse(BaseModel):
    """MCP JSON-RPC response model."""

    jsonrpc: str = "2.0"
    id: Any
    result: Optional[Dict] = None
    error: Optional[Dict] = None


class ToolCallRequest(BaseModel):
    """Tool call request model."""

    name: str
    arguments: Dict = {}


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str


class MCPGateway:
    """Main MCP Gateway service."""

    def __init__(self) -> None:
        self.app = FastAPI(
            title="MCP Gateway",
            description="Enterprise MCP Gateway for routing tool calls to multiple MCP servers",
            version="1.0.0",
            docs_url="/docs" if settings.debug else None,
            redoc_url="/redoc" if settings.debug else None,
        )

        # Initialize components
        self.health_monitor = HealthMonitor()
        self.tool_registry = ToolRegistry()
        self.http_client: Optional[httpx.AsyncClient] = None

        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Setup routes
        self._setup_routes()

        # Setup startup and shutdown
        self.app.add_event_handler("startup", self.startup)
        self.app.add_event_handler("shutdown", self.shutdown)

    def _setup_routes(self) -> None:
        """Setup FastAPI routes."""

        # Authentication routes
        @self.app.post("/auth/login")
        async def login(request: LoginRequest):
            """Authenticate user and return access token."""
            user = auth_manager.authenticate_user(request.username, request.password)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            access_token = auth_manager.create_access_token(data={"sub": user.username})
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "permissions": list(user.permissions),
                },
            }

        # Health and status routes
        @self.app.get("/health")
        async def health_check():
            """Gateway health check."""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
            }

        @self.app.get("/health/servers")
        async def servers_health(
            current_user: User = Depends(get_current_user_from_token),
        ):
            """Get health status of all MCP servers."""
            if not auth_manager.check_permission(current_user, "read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            return self.health_monitor.get_all_health()

        @self.app.get("/health/servers/{server_name}")
        async def server_health(
            server_name: str, current_user: User = Depends(get_current_user_from_token)
        ):
            """Get health status of a specific MCP server."""
            if not auth_manager.check_permission(current_user, "read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            if not auth_manager.check_server_access(current_user, server_name):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No access to server {server_name}",
                )

            health = self.health_monitor.get_server_health(server_name)
            if health is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Server {server_name} not found",
                )

            return health.to_dict()

        # Tool discovery routes
        @self.app.get("/tools")
        async def list_tools(current_user: User = Depends(get_current_user_from_token)):
            """List all available tools (filtered by user permissions)."""
            if not auth_manager.check_permission(current_user, "read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            all_tools = self.tool_registry.get_all_tools()
            tool_names = [tool.name for tool in all_tools]
            allowed_tools = auth_manager.get_user_tools(current_user, tool_names)

            filtered_tools = [
                tool.to_dict() for tool in all_tools if tool.name in allowed_tools
            ]

            return {
                "tools": filtered_tools,
                "total": len(filtered_tools),
                "timestamp": datetime.utcnow().isoformat(),
            }

        @self.app.get("/tools/summary")
        async def tools_summary(
            current_user: User = Depends(get_current_user_from_token),
        ):
            """Get tools summary."""
            if not auth_manager.check_permission(current_user, "read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            return self.tool_registry.get_tools_summary()

        @self.app.get("/tools/search")
        async def search_tools(
            q: str, current_user: User = Depends(get_current_user_from_token)
        ):
            """Search tools by name or description."""
            if not auth_manager.check_permission(current_user, "read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            found_tools = self.tool_registry.search_tools(q)
            tool_names = [tool.name for tool in found_tools]
            allowed_tools = auth_manager.get_user_tools(current_user, tool_names)

            filtered_tools = [
                tool.to_dict() for tool in found_tools if tool.name in allowed_tools
            ]

            return {
                "tools": filtered_tools,
                "query": q,
                "total": len(filtered_tools),
                "timestamp": datetime.utcnow().isoformat(),
            }

        # MCP protocol routes
        @self.app.post("/mcp")
        async def mcp_endpoint(
            request: MCPRequest,
            current_user: User = Depends(get_current_user_from_token),
        ):
            """Main MCP protocol endpoint."""
            try:
                if request.method == "tools/list":
                    return await self._handle_tools_list(request, current_user)
                elif request.method == "tools/call":
                    return await self._handle_tools_call(request, current_user)
                elif request.method == "resources/list":
                    return await self._handle_resources_list(request, current_user)
                elif request.method == "resources/read":
                    return await self._handle_resources_read(request, current_user)
                else:
                    return MCPResponse(
                        id=request.id,
                        error={
                            "code": -32601,
                            "message": f"Method not found: {request.method}",
                        },
                    )
            except Exception as e:
                logger.error(f"MCP request error: {e}")
                return MCPResponse(
                    id=request.id,
                    error={"code": -32603, "message": f"Internal error: {str(e)}"},
                )

        # Tool execution route
        @self.app.post("/tools/{tool_name}/call")
        async def call_tool(
            tool_name: str,
            request: ToolCallRequest,
            current_user: User = Depends(get_current_user_from_token),
        ):
            """Execute a specific tool."""
            if not auth_manager.check_permission(current_user, "execute"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to execute tools",
                )

            if not auth_manager.check_tool_access(current_user, tool_name):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No access to tool {tool_name}",
                )

            return await self._execute_tool(tool_name, request.arguments)

    async def _handle_tools_list(self, request: MCPRequest, user: User) -> MCPResponse:
        """Handle MCP tools/list request."""
        all_tools = self.tool_registry.get_all_tools()
        tool_names = [tool.name for tool in all_tools]
        allowed_tools = auth_manager.get_user_tools(user, tool_names)

        tools_list = []
        for tool in all_tools:
            if tool.name in allowed_tools:
                tools_list.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                )

        return MCPResponse(id=request.id, result={"tools": tools_list})

    async def _handle_tools_call(self, request: MCPRequest, user: User) -> MCPResponse:
        """Handle MCP tools/call request."""
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        if not tool_name:
            return MCPResponse(
                id=request.id, error={"code": -32602, "message": "Missing tool name"}
            )

        if not auth_manager.check_tool_access(user, tool_name):
            return MCPResponse(
                id=request.id,
                error={"code": -32603, "message": f"Access denied to tool {tool_name}"},
            )

        try:
            result = await self._execute_tool(tool_name, arguments)
            return MCPResponse(id=request.id, result=result)
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error={"code": -32603, "message": f"Tool execution error: {str(e)}"},
            )

    async def _handle_resources_list(
        self, request: MCPRequest, user: User
    ) -> MCPResponse:
        """Handle MCP resources/list request."""
        # For now, return empty resources list
        # In a full implementation, you might expose server health, logs, etc.
        return MCPResponse(id=request.id, result={"resources": []})

    async def _handle_resources_read(
        self, request: MCPRequest, user: User
    ) -> MCPResponse:
        """Handle MCP resources/read request."""
        return MCPResponse(
            id=request.id,
            error={"code": -32601, "message": "Resource reading not implemented"},
        )

    async def _execute_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Execute a tool on the appropriate server."""
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        # Find which server provides this tool
        server_name = self.tool_registry.get_server_for_tool(tool_name)
        if not server_name:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool {tool_name} not found",
            )

        # Check if server is healthy
        if not self.health_monitor.is_server_healthy(server_name):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Server {server_name} is not healthy",
            )

        # Get server configuration
        server_config = settings.mcp_servers.get(server_name)
        if not server_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server {server_name} configuration not found",
            )

        # Make MCP tools/call request to the server
        url = f"http://{server_config.host}:{server_config.port}{server_config.mcp_endpoint}"

        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        try:
            response = await self.http_client.post(
                url,
                json=mcp_request,
                headers={"Content-Type": "application/json"},
                timeout=server_config.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return data["result"]
                elif "error" in data:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Server error: {data['error'].get('message', 'Unknown error')}",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Invalid response from server",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Server returned HTTP {response.status_code}",
                )

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Timeout calling server {server_name}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error connecting to server {server_name}: {str(e)}",
            )

    async def startup(self) -> None:
        """Initialize gateway services."""
        logger.info("Starting MCP Gateway")

        # Create HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

        # Start health monitoring
        await self.health_monitor.start()

        # Start tool discovery
        await self.tool_registry.start()

        logger.info("MCP Gateway started successfully")

    async def shutdown(self) -> None:
        """Cleanup gateway services."""
        logger.info("Shutting down MCP Gateway")

        # Stop services
        await self.health_monitor.stop()
        await self.tool_registry.stop()

        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()

        logger.info("MCP Gateway shutdown complete")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    gateway = MCPGateway()
    return gateway.app


def main() -> None:
    """Run the gateway server."""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()), format=settings.log_format
    )

    # Create and run the app
    app = create_app()

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=settings.debug,
    )


if __name__ == "__main__":
    main()
