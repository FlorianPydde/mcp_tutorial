"""
MCP Gateway Client - Simplified without authentication
"""
import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from openai import AzureOpenAI
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class MCPGatewayClient:
    """Simple client for interacting with the MCP Gateway."""

    def __init__(self, gateway_url: Optional[str] = None):
        """Initialize the MCP Gateway client.

        Args:
            gateway_url: MCP Gateway endpoint URL
        """
        # Configure gateway URL
        if gateway_url:
            self.gateway_url = gateway_url
        else:
            gateway_port = os.getenv("MCP_GATEWAY_PORT", "8080")
            self.gateway_url = f"http://localhost:{gateway_port}"
        
        # HTTP client for API calls
        self.http_client: Optional[httpx.AsyncClient] = None
        
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
                "Gateway client will work for direct tool calls, but chat functionality will be limited"
            )

        logger.info(f"Initialized MCP Gateway client for: {self.gateway_url}")

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

    async def connect(self) -> None:
        """Connect to the MCP Gateway."""
        try:
            logger.info(f"Connecting to MCP Gateway at {self.gateway_url}...")
            
            # Create HTTP client
            self.http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True
            )
            
            # Test connection by listing tools
            tools = await self.list_tools()
            logger.info("Connected to gateway successfully")
            logger.info(f"Available tools: {[tool['name'] for tool in tools]}")
            
        except Exception as e:
            logger.error(f"Failed to connect to gateway: {e}")
            raise

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for requests."""
        return {"Content-Type": "application/json"}

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from the gateway."""
        if not self.http_client:
            raise RuntimeError("Not connected. Call connect() first.")
            
        try:
            response = await self.http_client.get(
                f"{self.gateway_url}/tools",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["tools"]
            else:
                raise Exception(f"Failed to list tools: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            raise

    async def get_tools_summary(self) -> Dict[str, Any]:
        """Get tools summary from the gateway."""
        if not self.http_client:
            raise RuntimeError("Not connected. Call connect() first.")
            
        try:
            response = await self.http_client.get(
                f"{self.gateway_url}/tools/summary",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to get tools summary: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting tools summary: {e}")
            raise

    async def search_tools(self, query: str) -> List[Dict[str, Any]]:
        """Search tools by name or description."""
        if not self.http_client:
            raise RuntimeError("Not connected. Call connect() first.")
            
        try:
            response = await self.http_client.get(
                f"{self.gateway_url}/tools/search",
                params={"q": query},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["tools"]
            else:
                raise Exception(f"Failed to search tools: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error searching tools: {e}")
            raise

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a specific tool through the gateway."""
        if not self.http_client:
            raise RuntimeError("Not connected. Call connect() first.")
            
        try:
            response = await self.http_client.post(
                f"{self.gateway_url}/tools/{tool_name}/call",
                json={"arguments": arguments},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Tool call failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise

    async def call_mcp_method(
        self, 
        method: str, 
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Call an MCP method through the gateway."""
        if not self.http_client:
            raise RuntimeError("Not connected. Call connect() first.")
            
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        try:
            response = await self.http_client.post(
                f"{self.gateway_url}/mcp",
                json=mcp_request,
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return data["result"]
                elif "error" in data:
                    raise Exception(f"MCP error: {data['error']}")
                else:
                    raise Exception(f"Invalid MCP response: {data}")
            else:
                raise Exception(f"MCP call failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error calling MCP method {method}: {e}")
            raise

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all servers."""
        if not self.http_client:
            raise RuntimeError("Not connected. Call connect() first.")
            
        try:
            response = await self.http_client.get(
                f"{self.gateway_url}/health/servers",
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to get health status: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            raise

    def create_session(self, session_id: str) -> None:
        """Create a new conversation session."""
        if session_id not in self.conversation_sessions:
            self.conversation_sessions[session_id] = []
            logger.info(f"Created new session: {session_id}")

    def clear_session(self, session_id: str) -> bool:
        """Clear conversation history for a session."""
        if session_id in self.conversation_sessions:
            self.conversation_sessions[session_id] = []
            logger.info(f"Cleared session: {session_id}")
            return True
        return False

    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a conversation session."""
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
        """Process a query using Azure OpenAI and available tools."""
        if not self.http_client:
            raise RuntimeError("Not connected. Call connect() first.")

        if self.llm is None:
            raise RuntimeError(
                "Azure OpenAI not configured. Cannot process chat queries. "
                "Use direct tool calls instead via call_tool() method."
            )

        # Get or create conversation history
        if session_id:
            self.create_session(session_id)
            conversation_history = self.conversation_sessions[session_id]
        else:
            conversation_history = []

        # Add the new user message to conversation history
        conversation_history.append({"role": "user", "content": query})

        # Get available tools from the gateway
        tools_data = await self.list_tools()
        available_tools: List[Dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in tools_data
        ]

        # Initial Azure OpenAI API call with conversation history
        response = self.llm.chat.completions.create(
            messages=conversation_history,
            tools=available_tools,
            max_tokens=1000,
            temperature=0.7,
            model=self.deployment,
        )

        response_message = response.choices[0].message
        conversation_history.append(response_message)

        # Handle tool calls if any
        if response_message.tool_calls:
            # Execute tool calls through the gateway
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"Calling tool: {tool_name} with args: {tool_args}")

                try:
                    # Call tool through gateway
                    tool_result = await self.call_tool(tool_name, tool_args)
                    
                    # Add tool result to conversation
                    conversation_history.append({
                        "role": "tool",
                        "content": json.dumps(tool_result, default=str),
                        "tool_call_id": tool_call.id,
                    })
                    
                except Exception as e:
                    logger.error(f"Tool call failed: {e}")
                    conversation_history.append({
                        "role": "tool",
                        "content": f"Error: {str(e)}",
                        "tool_call_id": tool_call.id,
                    })

            # Get final response after tool calls
            final_response = self.llm.chat.completions.create(
                messages=conversation_history,
                tools=available_tools,
                max_tokens=1000,
                temperature=0.7,
                model=self.deployment,
            )

            final_message = final_response.choices[0].message
            conversation_history.append(final_message)

            # Store updated conversation history
            if session_id:
                self.conversation_sessions[session_id] = conversation_history

            return final_message.content or "No response generated"

        else:
            # Store conversation history
            if session_id:
                self.conversation_sessions[session_id] = conversation_history

            return response_message.content or "No response generated"

    async def disconnect(self) -> None:
        """Disconnect from the gateway."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
            logger.info("Disconnected from MCP Gateway")


# Maintain backward compatibility by aliasing the old class name
MCPWebClient = MCPGatewayClient
