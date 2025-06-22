"""
Direct MCP Client for connecting to MCP servers using streamable HTTP protocol.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class DirectMCPClient:
    """Direct MCP client that connects to multiple MCP servers using streamable HTTP protocol."""

    def __init__(self):
        """Initialize the direct MCP client."""
        self.servers = self._get_server_config()
        self.tools: Dict[str, Any] = {}
        self.connected = False

    def _get_server_config(self) -> Dict[str, Dict[str, Any]]:
        """Get server configuration from environment variables."""
        return {
            "weather": {
                "url": os.getenv(
                    "WEATHER_SERVER_URL", "http://weather-server:8000/mcp"
                ),
                "enabled": True,
            },
            "news": {
                "url": os.getenv("NEWS_SERVER_URL", "http://news-server:8000/mcp"),
                "enabled": True,
            },
        }

    async def connect(self) -> None:
        """Connect to all MCP servers and discover tools."""
        logger.info("Connecting to MCP servers...")
        self.tools = {}

        for server_name, config in self.servers.items():
            if not config["enabled"]:
                continue

            try:
                logger.info(f"Connecting to {server_name} at {config['url']}")
                await self._discover_server_tools(server_name, config["url"])
                logger.info(f"Successfully connected to {server_name}")
            except Exception as e:
                logger.error(f"Failed to connect to {server_name}: {e}")

        self.connected = True
        logger.info(
            f"Connected to MCP servers. Total tools discovered: {len(self.tools)}"
        )

    async def _discover_server_tools(self, server_name: str, server_url: str) -> None:
        """Discover tools from a specific MCP server."""
        async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize session
                await session.initialize()

                # List available tools
                tools_result = await session.list_tools()

                # Store tools with server information
                for tool in tools_result.tools:
                    tool_key = f"{server_name}:{tool.name}"
                    self.tools[tool_key] = {
                        "name": tool.name,
                        "description": tool.description or "",
                        "server_name": server_name,
                        "server_url": server_url,
                        "input_schema": tool.inputSchema or {},
                    }

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools."""
        if not self.connected:
            await self.connect()
        return list(self.tools.values())

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call a tool on a specific server."""
        if not self.connected:
            await self.connect()

        # Find server configuration
        server_config = self.servers.get(server_name)
        if not server_config:
            raise ValueError(f"Unknown server: {server_name}")

        # Connect to server and call tool
        async with streamablehttp_client(server_config["url"]) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize session
                await session.initialize()

                # Call the tool
                result = await session.call_tool(tool_name, arguments)

                # Convert result to dictionary
                return {
                    "content": [
                        {
                            "type": content.type,
                            "text": content.text
                            if hasattr(content, "text")
                            else str(content),
                        }
                        for content in result.content
                    ],
                    "isError": getattr(result, "isError", False),
                }

    async def disconnect(self) -> None:
        """Disconnect from all servers."""
        self.connected = False
        logger.info("Disconnected from MCP servers")

    def get_server_info(self) -> Dict[str, Any]:
        """Get information about configured servers."""
        return {
            "servers": {
                name: {"url": config["url"], "enabled": config["enabled"]}
                for name, config in self.servers.items()
            },
            "total_tools": len(self.tools),
            "connected": self.connected,
        }
