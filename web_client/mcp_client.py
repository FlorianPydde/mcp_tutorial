import json
import logging
import os
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from openai import AzureOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class MCPWebClient:
    """Web service client for MCP server interactions following tutorial standards."""

    def __init__(self, server_url: Optional[str] = None, transport_type: str = "sse"):
        """Initialize the MCP web client.

        Args:
            server_url: MCP server endpoint URL
            transport_type: Transport type ('sse' or 'streamable_http')
        """
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()  # For persistent web service connections
        self.transport_type = transport_type

        # Configure server URL based on transport type
        if server_url:
            self.server_url = server_url
        else:
            server_port = os.getenv("MCP_SERVER_PORT", "8000")
            if transport_type == "streamable_http":
                self.server_url = f"http://localhost:{server_port}/mcp"
            else:  # Default to SSE
                self.server_url = f"http://localhost:{server_port}/sse"

        # Initialize conversation memory for sessions
        self.conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}

        # Try to initialize Azure OpenAI client, but don't fail if not configured
        self.llm = None
        self.deployment = None

        try:
            self._validate_azure_config()

            # Initialize Azure OpenAI client
            self.llm = AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_API_BASE"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            )
            self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            logger.info("Azure OpenAI client initialized successfully")

        except Exception as e:
            logger.warning(f"Azure OpenAI not configured: {e}")
            logger.info(
                "MCP client will work for direct tool calls, but chat functionality will be limited"
            )

        logger.info(
            f"Initialized MCP client for server: {self.server_url} "
            f"(transport: {transport_type})"
        )

    def _validate_azure_config(self) -> None:
        """Validate required Azure OpenAI environment variables."""
        required_vars = [
            "AZURE_OPENAI_API_BASE",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_API_VERSION",
            "AZURE_OPENAI_DEPLOYMENT_NAME",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(
                f"Missing required Azure OpenAI environment variables: "
                f"{', '.join(missing_vars)}"
            )

    async def connect_to_server(self) -> None:
        """Connect to the MCP server using configured transport.

        Uses AsyncExitStack to maintain persistent connections for web service.
        Unlike CLI apps that connect->work->exit, web apps need persistent connections.
        """
        try:
            logger.info(f"Attempting to connect to {self.server_url}...")

            if self.transport_type == "streamable_http":
                logger.info("Opening StreamableHTTP transport connection...")
                transport = await self.exit_stack.enter_async_context(
                    streamablehttp_client(
                        url=self.server_url, timeout=timedelta(seconds=60)
                    )
                )
                self.read, self.write, self.get_session_id = transport
            else:  # SSE transport
                logger.info("Opening SSE transport connection...")
                transport = await self.exit_stack.enter_async_context(
                    sse_client(url=self.server_url, timeout=60)
                )
                self.read, self.write = transport
                self.get_session_id = None

            # Initialize persistent session for the web service lifecycle
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
            )

            logger.info("Starting session initialization...")
            await self.session.initialize()
            logger.info("Session initialization complete!")

            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            logger.info(f"Connected to server at {self.server_url}")
            logger.info(f"Available tools: {[tool.name for tool in tools]}")

            if hasattr(self, "get_session_id") and self.get_session_id:
                session_id = self.get_session_id()
                if session_id:
                    logger.info(f"Session ID: {session_id}")

        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            raise

    def create_session(self, session_id: str) -> None:
        """Create a new conversation session.

        Args:
            session_id: Unique identifier for the session
        """
        if session_id not in self.conversation_sessions:
            self.conversation_sessions[session_id] = []
            logger.info(f"Created new session: {session_id}")

    def clear_session(self, session_id: str) -> bool:
        """Clear conversation history for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session existed and was cleared, False otherwise
        """
        if session_id in self.conversation_sessions:
            self.conversation_sessions[session_id] = []
            logger.info(f"Cleared session: {session_id}")
            return True
        return False

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a conversation session.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session statistics
        """
        if session_id not in self.conversation_sessions:
            return {"exists": False}

        history = self.conversation_sessions[session_id]
        return {
            "exists": True,
            "message_count": len(history),
            "user_messages": len([m for m in history if m["role"] == "user"]),
            "assistant_messages": len([m for m in history if m["role"] == "assistant"]),
            "tool_calls": len([m for m in history if m["role"] == "tool"]),
        }

    async def process_query(self, query: str, session_id: Optional[str] = None) -> str:
        """Process a query using OpenAI and available tools.

        Args:
            query: User query to process
            session_id: Optional session ID for conversation memory

        Returns:
            Processed response string
        """
        if self.session is None:
            raise RuntimeError(
                "Not connected to MCP server. Call connect_to_server() first."
            )

        if self.llm is None:
            raise RuntimeError(
                "Azure OpenAI not configured. Cannot process chat queries. "
                "Use direct tool calls instead via /tools/{tool_name}/call endpoints."
            )

        # Get or create conversation history
        if session_id:
            self.create_session(session_id)
            conversation_history = self.conversation_sessions[session_id]
        else:
            conversation_history = []

        # Add the new user message to conversation history
        conversation_history.append({"role": "user", "content": query})

        # Get available tools from MCP server
        response = await self.session.list_tools()
        available_tools: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in response.tools
        ]

        # Initial Azure OpenAI API call with conversation history
        response = self.llm.chat.completions.create(
            messages=conversation_history,
            tools=available_tools,
            max_tokens=1000,
            temperature=0.7,
            model=self.deployment,
        )

        # Process response and handle tool calls
        final_text = []
        message = response.choices[0].message

        if message.content:
            final_text.append(message.content)

        if message.tool_calls:
            # Add assistant message with tool calls to history
            conversation_history.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        tool_call.model_dump() for tool_call in message.tool_calls
                    ],
                }
            )

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments

                try:
                    # Parse tool arguments safely
                    if isinstance(tool_args, str):
                        try:
                            parsed_args = json.loads(tool_args)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse tool arguments as JSON: {e}")
                            final_text.append(
                                f"[Tool call {tool_name} failed: Invalid JSON arguments]"
                            )
                            continue
                    else:
                        parsed_args = tool_args
                    # Execute tool call
                    result = await self.session.call_tool(tool_name, parsed_args)

                    # Process result content similar to tutorial pattern
                    result_text = []
                    if hasattr(result, "content"):
                        for content in result.content:
                            if hasattr(content, "type") and content.type == "text":
                                result_text.append(content.text)
                            else:
                                result_text.append(str(content))
                    else:
                        result_text.append(str(result))

                    result_content = "\n".join(result_text)
                    final_text.append(f"[Called {tool_name}]: {result_content}")

                    # Add tool result to conversation history
                    conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_content,
                        }
                    )

                except Exception as e:
                    logger.error(f"Tool call failed: {e}")
                    final_text.append(f"[Tool call {tool_name} failed: {str(e)}]")

            # Get next response from OpenAI with updated conversation history
            response = self.llm.chat.completions.create(
                messages=conversation_history,
                tools=available_tools,
                max_tokens=1000,
                temperature=0.7,
                model=self.deployment,
            )

            if response.choices[0].message.content:
                final_text.append(response.choices[0].message.content)
                # Add final assistant response to history
                conversation_history.append(
                    {
                        "role": "assistant",
                        "content": response.choices[0].message.content,
                    }
                )
        else:
            # Add assistant response to history when no tool calls
            conversation_history.append(
                {"role": "assistant", "content": message.content}
            )

        return (
            conversation_history[-1]["content"]
            if "content" in conversation_history[-1]
            else "\n".join(final_text)
        )

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the MCP client.

        Returns:
            Health status dictionary with detailed configuration info
        """
        try:
            if self.session is None:
                return {
                    "status": "unhealthy",
                    "mcp_connected": False,
                    "server_url": self.server_url,
                    "transport_type": self.transport_type,
                    "azure_openai_configured": self.llm is not None,
                    "error": "Not connected to MCP server",
                }

            # Try to list tools to verify connection
            response = await self.session.list_tools()
            return {
                "status": "healthy",
                "mcp_connected": True,
                "server_url": self.server_url,
                "transport_type": self.transport_type,
                "available_tools": len(response.tools),
                "active_sessions": len(self.conversation_sessions),
                "azure_openai_configured": self.llm is not None,
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "mcp_connected": False,
                "server_url": self.server_url,
                "transport_type": self.transport_type,
                "azure_openai_configured": self.llm is not None,
                "error": str(e),
            }

    async def cleanup(self) -> None:
        """Clean up resources.

        Web service cleanup: Properly close all async context managers
        that were opened during the service lifecycle.
        """
        try:
            await self.exit_stack.aclose()
            logger.info("MCP client cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server.

        Returns:
            List of available tools with their information
        """
        if self.session is None:
            raise RuntimeError(
                "Not connected to MCP server. Call connect_to_server() first."
            )

        try:
            result = await self.session.list_tools()
            if hasattr(result, "tools") and result.tools:
                tools_info = []
                for tool in result.tools:
                    tool_info = {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    }
                    tools_info.append(tool_info)
                return tools_info
            else:
                return []
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            raise

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> str:
        """Call a specific tool directly.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool result as string
        """
        if self.session is None:
            raise RuntimeError(
                "Not connected to MCP server. Call connect_to_server() first."
            )

        try:
            result = await self.session.call_tool(tool_name, arguments or {})

            # Process result content similar to tutorial pattern
            result_text = []
            if hasattr(result, "content"):
                for content in result.content:
                    if hasattr(content, "type") and content.type == "text":
                        result_text.append(content.text)
                    else:
                        result_text.append(str(content))
            else:
                result_text.append(str(result))

            return "\n".join(result_text)

        except Exception as e:
            logger.error(f"Failed to call tool '{tool_name}': {e}")
            raise
