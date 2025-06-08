import json
import logging
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AzureOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class MCPWebClient:
    """Web service client for MCP server interactions."""
    
    def __init__(self, server_url: Optional[str] = None):
        """Initialize the MCP web client.
        
        Args:
            server_url: MCP server SSE endpoint URL
        """
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.server_url = server_url or os.getenv(
            "MCP_SERVER_URL", 
            "http://localhost:8000/sse"
        )
        
        # Initialize conversation memory for sessions
        self.conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}
        
        # Validate Azure OpenAI configuration
        self._validate_azure_config()
        
        # Initialize Azure OpenAI client
        self.llm = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_API_BASE"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        logger.info(f"Initialized MCP client for server: {self.server_url}")

    def _validate_azure_config(self) -> None:
        """Validate required Azure OpenAI environment variables."""
        required_vars = [
            "AZURE_OPENAI_API_BASE",
            "AZURE_OPENAI_API_KEY", 
            "AZURE_OPENAI_API_VERSION",
            "AZURE_OPENAI_DEPLOYMENT_NAME"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(
                f"Missing required Azure OpenAI environment variables: "
                f"{', '.join(missing_vars)}"
            )

    async def connect_to_server(self) -> None:
        """Connect to the MCP server via SSE."""
        try:
            # Connect to SSE server
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(self.server_url)
            )
            self.read, self.write = sse_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
            )
            
            await self.session.initialize()
            
            # List available tools
            response = await self.session.list_tools()
            tools = response.tools
            logger.info(f"Connected to SSE server at {self.server_url}")
            logger.info(f"Available tools: {[tool.name for tool in tools]}")
            
        except Exception as e:
            logger.error(f"Failed to connect to SSE server: {e}")
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
            "tool_calls": len([m for m in history if m["role"] == "tool"])
        }

    async def process_query(
        self, 
        query: str, 
        session_id: Optional[str] = None
    ) -> str:
        """Process a query using OpenAI and available tools.
        
        Args:
            query: User query to process
            session_id: Optional session ID for conversation memory
            
        Returns:
            Processed response string
        """
        if self.session is None:
            raise RuntimeError("Not connected to MCP server. Call connect_to_server() first.")
        
        # Get or create conversation history
        if session_id:
            self.create_session(session_id)
            conversation_history = self.conversation_sessions[session_id]
        else:
            conversation_history = []
        
        # Add the new user message to conversation history
        conversation_history.append({
            "role": "user",
            "content": query
        })

        # Get available tools from MCP server
        response = await self.session.list_tools()
        available_tools: List[Dict[str, Any]] = [{ 
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in response.tools]

        # Initial Azure OpenAI API call with conversation history
        response = self.llm.chat.completions.create(
            messages=conversation_history,
            tools=available_tools,
            max_tokens=1000,
            temperature=0.7,
            model=self.deployment
        )

        # Process response and handle tool calls
        final_text = []
        message = response.choices[0].message
        
        if message.content:
            final_text.append(message.content)
            
        if message.tool_calls:
            # Add assistant message with tool calls to history
            conversation_history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call.model_dump() for tool_call in message.tool_calls]
            })
            
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
                            final_text.append(f"[Tool call {tool_name} failed: Invalid JSON arguments]")
                            continue
                    else:
                        parsed_args = tool_args
                    
                    # Execute tool call
                    result = await self.session.call_tool(tool_name, parsed_args)
                    final_text.append(f"[Called {tool_name} with args {tool_args}]")

                    # Convert result content to string if it's a list
                    result_content = result.content
                    if isinstance(result_content, list):
                        result_content = str(result_content)
                        
                    # Add tool result to conversation history
                    conversation_history.append({
                        "role": "tool", 
                        "tool_call_id": tool_call.id,
                        "content": result_content
                    })
                    
                except Exception as e:
                    logger.error(f"Tool call failed: {e}")
                    final_text.append(f"[Tool call {tool_name} failed: {str(e)}]")

            # Get next response from OpenAI with updated conversation history
            response = self.llm.chat.completions.create(
                messages=conversation_history,
                tools=available_tools,
                max_tokens=1000,
                temperature=0.7,
                model=self.deployment
            )

            if response.choices[0].message.content:
                final_text.append(response.choices[0].message.content)
                # Add final assistant response to history
                conversation_history.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content
                })
        else:
            # Add assistant response to history when no tool calls
            conversation_history.append({
                "role": "assistant",
                "content": message.content
            })

        return "\n".join(final_text)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the MCP client.
        
        Returns:
            Health status dictionary
        """
        try:
            if self.session is None:
                return {
                    "status": "unhealthy",
                    "mcp_connected": False,
                    "error": "Not connected to MCP server"
                }
                
            # Try to list tools to verify connection
            response = await self.session.list_tools()
            return {
                "status": "healthy",
                "mcp_connected": True,
                "server_url": self.server_url,
                "available_tools": len(response.tools),
                "active_sessions": len(self.conversation_sessions)
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "mcp_connected": False,
                "error": str(e)
            }

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.exit_stack.aclose()
            logger.info("MCP client cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
