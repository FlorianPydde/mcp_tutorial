import asyncio
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AzureOpenAI

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
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
        
    # methods will go here

    async def connect_to_server(self, server_script_path: str) -> str | None:
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])


    async def process_query(self, query: str) -> str:
        """Process a query using Openai and available tools"""
        if self.session is None:
            raise RuntimeError("Not connected to MCP server. Call connect_to_server() first.")
            
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        available_tools: List[Dict[str, Any]] = [{ 
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in response.tools]

        # Initial Azure API call
        response = self.llm.chat.completions.create(
            messages=messages,
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
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                
                # Execute tool call
                result = await self.session.call_tool(tool_name, eval(tool_args))
                tool_results.append({"call": tool_name, "result": result})
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                # Continue conversation with tool results
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call.model_dump()]
                })
                
                # Convert result content to string if it's a list
                result_content = result.content
                if isinstance(result_content, list):
                    result_content = str(result_content)
                    
                messages.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id,
                    "content": result_content
                })

                # Get next response from OpenAI
                response = self.llm.chat.completions.create(
                    messages=messages,
                    tools=available_tools,
                    max_tokens=1000,
                    temperature=0.7,
                    model=self.deployment
                )

                if response.choices[0].message.content:
                    final_text.append(response.choices[0].message.content)

        return "\n".join(final_text)
    

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())