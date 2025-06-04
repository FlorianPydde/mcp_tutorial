import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AzureOpenAI

load_dotenv()  # load environment variables from .env

class MCPSSEClient:
    def __init__(self, server_url: str = "http://localhost:8000/sse"):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.server_url = server_url
        
        # Initialize conversation memory
        self.conversation_history: List[Dict[str, Any]] = []
        
        # Validate Azure OpenAI configuration
        azure_endpoint = os.getenv("AZURE_OPENAI_API_BASE", "")
        api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "")
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
        
        missing_vars = []
        if not azure_endpoint:
            missing_vars.append("AZURE_OPENAI_API_BASE")
        if not api_key:
            missing_vars.append("AZURE_OPENAI_API_KEY")
        if not api_version:
            missing_vars.append("AZURE_OPENAI_API_VERSION")
        if not deployment_name:
            missing_vars.append("AZURE_OPENAI_DEPLOYMENT_NAME")
        
        if missing_vars:
            raise ValueError(f"Missing required Azure OpenAI environment variables: {', '.join(missing_vars)}")
        
        self.llm = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self.deployment = deployment_name
    
    def clear_conversation_history(self):
        """Clear the conversation history"""
        self.conversation_history = []
    
    def get_conversation_length(self) -> int:
        """Get the number of messages in conversation history"""
        return len(self.conversation_history)
    
    def show_conversation_stats(self):
        """Show conversation statistics"""
        print(f"Conversation length: {len(self.conversation_history)} messages")

    async def connect_to_server(self) -> str | None:
        """Connect to an MCP server via SSE
        
        Args:
            server_url: URL of the SSE MCP server endpoint
        """
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
            print(f"\nConnected to SSE server at {self.server_url}")
            print("Available tools:", [tool.name for tool in tools])
            
        except Exception as e:
            print(f"Failed to connect to SSE server: {e}")
            raise

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and available tools"""
        if self.session is None:
            raise RuntimeError("Not connected to MCP server. Call connect_to_server() first.")
        
        # Add the new user message to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })

        response = await self.session.list_tools()
        available_tools: List[Dict[str, Any]] = [{ 
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in response.tools]

        # Initial Azure API call with conversation history
        response = self.llm.chat.completions.create(
            messages=self.conversation_history,
            tools=available_tools,
            max_tokens=1000,
            temperature=0.7,
            model=self.deployment
        )

        # Process response and handle tool calls
        tool_results = []
        final_text = []

        message = response.choices[0].message
        
        if message.content:
            final_text.append(message.content)
            
        if message.tool_calls:
            # Add assistant message with tool calls to history
            self.conversation_history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call.model_dump() for tool_call in message.tool_calls]
            })
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                
                # Execute tool call
                result = await self.session.call_tool(tool_name, eval(tool_args))
                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Convert result content to string if it's a list
                result_content = result.content
                if isinstance(result_content, list):
                    result_content = str(result_content)
                    
                # Add tool result to conversation history
                self.conversation_history.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id,
                    "content": result_content
                })

            # Get next response from OpenAI with updated conversation history
            response = self.llm.chat.completions.create(
                messages=self.conversation_history,
                tools=available_tools,
                max_tokens=1000,
                temperature=0.7,
                model=self.deployment
            )

            if response.choices[0].message.content:
                final_text.append(response.choices[0].message.content)
                # Add final assistant response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content
                })
        else:
            # Add assistant response to history when no tool calls
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content
            })

        return "\n".join(final_text)
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP SSE Client Started with Conversation Memory!")
        print("Commands:")
        print("- Type your queries to chat")
        print("- Type 'clear' to clear conversation history")
        print("- Type 'stats' to show conversation statistics")
        print("- Type 'quit' to exit")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                elif query.lower() == 'clear':
                    self.clear_conversation_history()
                    print("Conversation history cleared!")
                    continue
                elif query.lower() == 'stats':
                    self.show_conversation_stats()
                    continue
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    import sys
    
    # Allow custom server URL as command line argument
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/sse"
    
    client = MCPSSEClient(server_url)
    try:
        await client.connect_to_server()
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
