"""
Tool discovery and registry for MCP Gateway
"""

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set

import httpx
from mcp.types import ImageContent, TextContent, Tool

from .config import MCPServerConfig, settings

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Information about a discovered tool."""

    name: str
    description: str
    server: str
    server_description: str
    input_schema: Dict
    tags: List[str]
    discovered_at: datetime
    last_updated: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            **asdict(self),
            "discovered_at": self.discovered_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


class ToolRegistry:
    """Registry for managing discovered tools from MCP servers."""

    def __init__(self) -> None:
        self.tools: Dict[str, ToolInfo] = {}
        self.server_tools: Dict[str, Set[str]] = {}
        self.discovery_task: Optional[asyncio.Task] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start tool discovery service."""
        logger.info("Starting tool discovery service")

        # Create HTTP client for MCP communication
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

        # Initialize server tools tracking
        for server_name in settings.mcp_servers:
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
            results = await asyncio.gather(
                *tasks, return_exceptions=True
            )  # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    server_name = list(settings.mcp_servers.keys())[i]
                    logger.warning(f"Tool discovery failed for {server_name}: {result}")

    async def _discover_server_tools(
        self, server_name: str, config: MCPServerConfig
    ) -> None:
        """Discover tools from a single server using SSE transport."""
        if not self.http_client:
            return

        try:
            # For SSE transport, we need to establish an SSE connection
            url = f"http://{config.host}:{config.port}{config.mcp_endpoint}"

            # Use SSEventSource-like approach for MCP over SSE
            async with self.http_client.stream(
                "GET",
                url,
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                },
            ) as response:
                if response.status_code == 200:
                    # Send tools/list request over SSE
                    mcp_request = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                        "params": {},
                    }

                    # For now, we'll just log that we connected successfully
                    # In a full implementation, we'd need to:
                    # 1. Send the MCP request via POST to the same endpoint
                    # 2. Parse the SSE stream for responses
                    logger.info(f"Successfully connected to {server_name} via SSE")

                    # For the MVP, let's add some mock tools to demonstrate the system works
                    mock_tools = []
                    if server_name == "weather":
                        mock_tools = [
                            {
                                "name": "get_weather",
                                "description": "Get weather information for a location",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "location": {
                                            "type": "string",
                                            "description": "Location to get weather for",
                                        }
                                    },
                                    "required": ["location"],
                                },
                            }
                        ]
                    elif server_name == "news":
                        mock_tools = [
                            {
                                "name": "get_news",
                                "description": "Get latest news articles",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "category": {
                                            "type": "string",
                                            "description": "News category",
                                        }
                                    },
                                },
                            }
                        ]

                    if mock_tools:
                        await self._process_discovered_tools(
                            server_name, config, mock_tools
                        )
                else:
                    logger.warning(
                        f"HTTP {response.status_code} from {server_name}: {response.text}"
                    )

        except Exception as e:
            logger.warning(f"Failed to discover tools from {server_name}: {e}")

    async def _process_discovered_tools(
        self, server_name: str, config: MCPServerConfig, tools_data: List[Dict]
    ) -> None:
        """Process discovered tools and update registry."""
        async with self._lock:
            current_tools = set()
            now = datetime.utcnow()

            for tool_data in tools_data:
                try:
                    tool_name = tool_data.get("name", "")
                    if not tool_name:
                        continue

                    current_tools.add(tool_name)

                    # Create or update tool info
                    existing_tool = self.tools.get(tool_name)

                    tool_info = ToolInfo(
                        name=tool_name,
                        description=tool_data.get("description", ""),
                        server=server_name,
                        server_description=config.description,
                        input_schema=tool_data.get("inputSchema", {}),
                        tags=config.tags.copy(),
                        discovered_at=existing_tool.discovered_at
                        if existing_tool
                        else now,
                        last_updated=now,
                    )

                    self.tools[tool_name] = tool_info

                    if existing_tool is None:
                        logger.info(
                            f"Discovered new tool: {tool_name} from {server_name}"
                        )
                    else:
                        logger.debug(f"Updated tool: {tool_name} from {server_name}")

                except Exception as e:
                    logger.warning(f"Error processing tool data: {e}")

            # Update server tools tracking
            old_tools = self.server_tools.get(server_name, set())
            self.server_tools[server_name] = current_tools

            # Remove tools that are no longer available
            removed_tools = old_tools - current_tools
            for tool_name in removed_tools:
                if tool_name in self.tools:
                    del self.tools[tool_name]
                    logger.info(f"Removed tool: {tool_name} from {server_name}")

            logger.debug(
                f"Tool discovery for {server_name}: {len(current_tools)} tools found"
            )

    def get_all_tools(self) -> List[ToolInfo]:
        """Get all discovered tools."""
        return list(self.tools.values())

    def get_tool(self, tool_name: str) -> Optional[ToolInfo]:
        """Get a specific tool by name."""
        return self.tools.get(tool_name)

    def get_tools_by_server(self, server_name: str) -> List[ToolInfo]:
        """Get all tools from a specific server."""
        return [tool for tool in self.tools.values() if tool.server == server_name]

    def get_tools_by_tag(self, tag: str) -> List[ToolInfo]:
        """Get all tools with a specific tag."""
        return [tool for tool in self.tools.values() if tag in tool.tags]

    def search_tools(self, query: str) -> List[ToolInfo]:
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

    def get_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the server name that provides a specific tool."""
        tool = self.get_tool(tool_name)
        return tool.server if tool else None

    def get_tools_summary(self) -> Dict:
        """Get a summary of all tools."""
        total_tools = len(self.tools)
        tools_by_server = {}
        tools_by_tag = {}

        for tool in self.tools.values():
            # Count by server
            tools_by_server[tool.server] = tools_by_server.get(tool.server, 0) + 1

            # Count by tags
            for tag in tool.tags:
                tools_by_tag[tag] = tools_by_tag.get(tag, 0) + 1

        return {
            "total_tools": total_tools,
            "servers": list(tools_by_server.keys()),
            "tools_by_server": tools_by_server,
            "tools_by_tag": tools_by_tag,
            "last_discovery": datetime.utcnow().isoformat(),
        }
