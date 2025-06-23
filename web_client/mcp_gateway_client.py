"""
MCP Gateway Client for connecting to the centralized MCP Gateway.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class MCPGatewayClient:
    """Client for connecting to the MCP Gateway instead of individual MCP servers."""

    def __init__(self, gateway_url: str = "http://mcp-gateway:8080"):
        """Initialize the MCP Gateway client.

        Args:
            gateway_url: URL of the MCP Gateway service
        """
        self.gateway_url = gateway_url.rstrip("/")
        self.http_client: Optional[httpx.AsyncClient] = None
        self.tools: Dict[str, Any] = {}
        self.connected = False

    async def connect(self) -> None:
        """Connect to the MCP Gateway and discover available tools."""
        logger.info(f"Connecting to MCP Gateway at {self.gateway_url}...")

        self.http_client = httpx.AsyncClient(timeout=30.0)

        try:
            # Test connection to gateway
            health_response = await self.http_client.get(f"{self.gateway_url}/health")
            health_response.raise_for_status()
            logger.info("Successfully connected to MCP Gateway")

            # Discover tools
            await self._discover_tools()
            self.connected = True

        except Exception as e:
            logger.error(f"Failed to connect to MCP Gateway: {e}")
            if self.http_client:
                await self.http_client.aclose()
                self.http_client = None
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP Gateway."""
        logger.info("Disconnecting from MCP Gateway...")
        self.connected = False

        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    async def _discover_tools(self) -> None:
        """Discover tools available through the gateway."""
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        try:
            response = await self.http_client.get(f"{self.gateway_url}/tools")
            response.raise_for_status()
            data = response.json()

            self.tools = {}
            tools_list = data.get("tools", [])

            for tool in tools_list:
                tool_name = tool.get("name")
                if tool_name:
                    self.tools[tool_name] = {
                        "name": tool_name,
                        "description": tool.get("description", ""),
                        "server_name": tool.get("server_name", "unknown"),
                        "server_url": tool.get("server_url", ""),
                        "input_schema": tool.get("input_schema", {}),
                    }

            logger.info(f"Discovered {len(self.tools)} tools from MCP Gateway")

        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            raise

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools."""
        if not self.connected:
            raise RuntimeError("Not connected to MCP Gateway")

        return list(self.tools.values())

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool through the MCP Gateway.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        if not self.connected or not self.http_client:
            raise RuntimeError("Not connected to MCP Gateway")

        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")

        try:
            # Use the REST API endpoint for tool calls
            url = f"{self.gateway_url}/tools/{tool_name}/call"
            payload = {"arguments": arguments}

            response = await self.http_client.post(url, json=payload)
            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Tool '{tool_name}' not found on gateway")
            else:
                raise RuntimeError(f"Tool call failed: {e.response.text}")
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise RuntimeError(f"Tool call failed: {str(e)}")

    async def get_gateway_health(self) -> Dict[str, Any]:
        """Get gateway health status."""
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        try:
            response = await self.http_client.get(f"{self.gateway_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get gateway health: {e}")
            raise

    async def get_servers_health(self) -> Dict[str, Any]:
        """Get health status of all MCP servers through the gateway."""
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        try:
            response = await self.http_client.get(f"{self.gateway_url}/health/servers")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get servers health: {e}")
            raise

    def get_server_info(self) -> Dict[str, Any]:
        """Get server configuration information."""
        return {
            "gateway_url": self.gateway_url,
            "connected": self.connected,
            "tools_count": len(self.tools),
            "available_tools": list(self.tools.keys()),
        }
