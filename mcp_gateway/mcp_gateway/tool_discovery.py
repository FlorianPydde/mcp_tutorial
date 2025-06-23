"""
Tool discovery and management for MCP servers using proper Streamable HTTP protocol.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """Represents a discovered MCP tool."""

    name: str
    description: str
    server_name: str
    input_schema: Dict[str, Any]
    discovered_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "server_name": self.server_name,
            "input_schema": self.input_schema,
            "discovered_at": self.discovered_at,
        }


class ToolRegistry:
    """Registry for managing tools discovered from MCP servers."""

    def __init__(self):
        self.server_tools: Dict[str, Set[str]] = {}
        self.tool_schemas: Dict[str, Dict[str, Any]] = {}
        self.tools: Dict[str, Tool] = {}  # tool_name -> Tool object
        self.discovery_task: Optional[asyncio.Task] = None
        self.http_client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        """Start tool discovery service."""
        logger.info("Starting tool discovery service")

        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Initialize server tools tracking
        for server_name in settings.mcp_servers.keys():
            self.server_tools[server_name] = set()

        # Start discovery task
        self.discovery_task = asyncio.create_task(self._discovery_loop())

        # Do initial discovery
        await self.discover_all_tools()

    async def stop(self) -> None:
        """Stop tool discovery service."""
        logger.info("Stopping tool discovery service")

        if self.discovery_task:
            self.discovery_task.cancel()
            try:
                await self.discovery_task
            except asyncio.CancelledError:
                pass

        if self.http_client:
            await self.http_client.aclose()

    async def _discovery_loop(self) -> None:
        """Main discovery loop."""
        while True:
            try:
                await asyncio.sleep(settings.tool_discovery_interval)
                await self.discover_all_tools()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in tool discovery loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying

    async def discover_all_tools(self) -> None:
        """Discover tools from all configured servers."""
        tasks = []
        for server_name, config in settings.mcp_servers.items():
            if config.enabled:
                task = asyncio.create_task(
                    self._discover_server_tools(server_name, config)
                )
                tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    server_name = list(settings.mcp_servers.keys())[i]
                    logger.warning(f"Tool discovery failed for {server_name}: {result}")

    async def _discover_server_tools(self, server_name: str, config) -> None:
        """Discover tools from a specific MCP server using proper Streamable HTTP protocol."""
        logger.info(f"DEBUG: Starting discovery for {server_name}")

        try:
            # Build endpoint URL
            endpoint = f"http://{config.host}:{config.port}{config.mcp_endpoint}"
            logger.info(
                f"Attempting to discover tools from {server_name} at {endpoint}"
            )

            # Use proper MCP client
            async with streamablehttp_client(endpoint) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize session
                    logger.debug(f"Attempting to initialize session with {server_name}")
                    init_result = await session.initialize()
                    logger.info(
                        f"Successfully initialized session with {server_name}: {init_result}"
                    )
                    # List tools
                    logger.debug(f"Attempting to list tools from {server_name}")
                    tools_result = await session.list_tools()
                    logger.info(
                        f"Successfully retrieved tools from {server_name}: {len(tools_result.tools)} tools"
                    )
                    current_time = datetime.utcnow().isoformat()

                    # Clear existing tools for this server
                    old_tools = self.server_tools.get(server_name, set()).copy()
                    self.server_tools[server_name] = set()

                    # Process discovered tools
                    for tool_data in tools_result.tools:
                        tool_name = tool_data.name
                        if tool_name:
                            # Update server tools tracking
                            self.server_tools[server_name].add(tool_name)

                            # Store tool schema
                            tool_dict = {
                                "name": tool_data.name,
                                "description": tool_data.description or "",
                                "inputSchema": tool_data.inputSchema or {},
                            }
                            self.tool_schemas[f"{server_name}:{tool_name}"] = tool_dict

                            # Create Tool object
                            tool = Tool(
                                name=tool_name,
                                description=tool_data.description or "",
                                server_name=server_name,
                                input_schema=tool_data.inputSchema or {},
                                discovered_at=current_time,
                            )

                            # Store tool object
                            self.tools[f"{server_name}:{tool_name}"] = (
                                tool  # Remove tools that are no longer available
                            )
                    new_tools = self.server_tools[server_name]
                    for tool_name in old_tools:
                        if (
                            tool_name not in new_tools
                        ):  # Only remove if not in new tools
                            tool_key = f"{server_name}:{tool_name}"
                            if tool_key in self.tools:
                                del self.tools[tool_key]
                            if tool_key in self.tool_schemas:
                                del self.tool_schemas[tool_key]

                    logger.info(
                        f"Discovered {len(tools_result.tools)} tools from {server_name}: "
                        f"{list(self.server_tools[server_name])}"
                    )

        except Exception as e:
            logger.error(
                f"Failed to discover tools from {server_name}: {type(e).__name__}: {e}"
            )
            import traceback

            logger.debug(f"Full traceback for {server_name}: {traceback.format_exc()}")

    def get_all_tools(self) -> List[Tool]:
        """Get all discovered tools as Tool objects."""
        return list(self.tools.values())

    def get_server_tools(self, server_name: str) -> Set[str]:
        """Get tool names for a specific server."""
        return self.server_tools.get(server_name, set()).copy()

    def get_tool_schema(
        self, server_name: str, tool_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get tool schema for a specific tool."""
        return self.tool_schemas.get(f"{server_name}:{tool_name}")

    def get_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which server provides a specific tool."""
        for tool_key, tool in self.tools.items():
            if tool.name == tool_name:
                return tool.server_name
        return None

    def has_tool(self, server_name: str, tool_name: str) -> bool:
        """Check if a tool exists on a server."""
        return tool_name in self.server_tools.get(server_name, set())

    def search_tools(self, query: str) -> List[Tool]:
        """Search tools by name or description."""
        query_lower = query.lower()
        results = []

        for tool in self.tools.values():
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
            ):
                results.append(tool)

        return results

    def get_tools_summary(self) -> Dict[str, Any]:
        """Get summary of all discovered tools."""
        total_tools = len(self.tools)
        servers_with_tools = sum(1 for tools in self.server_tools.values() if tools)

        return {
            "total_tools": total_tools,
            "servers_with_tools": servers_with_tools,
            "servers": {
                server: len(tools) for server, tools in self.server_tools.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Call a tool on a specific server using proper Streamable HTTP protocol."""
        if arguments is None:
            arguments = {}

        if not self.has_tool(server_name, tool_name):
            raise ValueError(f"Tool {tool_name} not found on server {server_name}")

        config = settings.mcp_servers.get(server_name)
        if not config or not config.enabled:
            raise ValueError(f"Server {server_name} not configured or disabled")

        try:
            # Build endpoint URL
            endpoint = f"http://{config.host}:{config.port}{config.mcp_endpoint}"

            # Use proper MCP client
            async with streamablehttp_client(endpoint) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize session
                    await session.initialize()

                    # Call tool
                    result = await session.call_tool(tool_name, arguments)

                    logger.info(
                        f"Successfully called tool {tool_name} on {server_name}"
                    )

                    # Convert result to dictionary format
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
                        "isError": result.isError
                        if hasattr(result, "isError")
                        else False,
                    }

        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {server_name}: {e}")
            raise
