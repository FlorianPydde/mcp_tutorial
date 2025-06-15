# MCP Weather Tutorial: Complete Implementation Guide

A comprehensive, step-by-step guide to building a production-ready Model Context Protocol (MCP) weather service with Azure OpenAI integration.

## 🎯 Learning Objectives

By completing this tutorial, you will learn:

- **MCP Architecture** - Server-client protocol implementation
- **Multi-Transport Support** - stdio, SSE, and StreamableHTTP transports
- **Production Deployment** - Docker containers and Azure Container Apps
- **AI Integration** - Azure OpenAI with intelligent tool calling
- **Modern Python Practices** - uv, type hints, proper error handling

## 📋 Prerequisites

- **Python 3.12+** with `uv` package manager
- **Azure OpenAI** service (for chat functionality)
- **Docker** (for containerized deployment)
- **Azure CLI** (for cloud deployment)

## 🏗️ Part 1: Understanding MCP Architecture

### What is Model Context Protocol?

MCP is a protocol that allows AI models to securely access external tools and data sources. Think of it as a standardized way for AI assistants to:

- Call functions (tools)
- Access data (resources)
- Maintain context across interactions

### Our Weather Service Architecture

```
┌─────────────┐    MCP Protocol    ┌──────────────┐    HTTP API    ┌─────────────┐
│   AI Model  │◄─────────────────►│ MCP Server   │◄──────────────►│ Weather.gov │
│ (OpenAI)    │                   │ (weather.py) │                │     API     │
└─────────────┘                   └──────────────┘                └─────────────┘
```

The MCP server acts as a bridge between AI models and external APIs, providing structured access to weather data.

## 🔧 Part 2: Building the MCP Server

### Step 1: Server Setup

Create the server foundation:

```python
# server/weather.py
import logging
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    name="weather-service",
    dependencies=["httpx"]
)

logger = logging.getLogger(__name__)
```

### Step 2: Define Tools

MCP tools are functions that AI models can call:

```python
@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.
    
    Args:
        state: Two-letter US state code (e.g., 'CA', 'NY')
    
    Returns:
        Formatted string with active weather alerts
    """
    # Validate input
    if not state or len(state) != 2:
        return "Error: Please provide a valid two-letter US state code"
    
    # Make API request to weather.gov
    url = f"{NWS_API_BASE}/alerts/active/area/{state.upper()}"
    data = await make_nws_request(url)
    
    # Process and format results
    # ... (see full implementation in weather.py)
```

### Step 3: Add Resources

Resources provide contextual information to AI models:

```python
@mcp.resource("weather://service/info")
def get_service_info() -> str:
    """Provide information about the weather service capabilities."""
    return """Weather MCP Server Information
    
Available Tools:
- get_alerts(state): Get active weather alerts for a US state
- get_forecast(latitude, longitude): Get detailed weather forecast
- get_current_conditions(latitude, longitude): Get current weather
"""
```

### Step 4: Multi-Transport Support

Support different connection methods:

```python
def create_sse_app():
    """Create SSE transport for HTTP connections."""
    app = mcp.sse_app()
    # Add health endpoint for monitoring
    return app

def create_streamable_http_app():
    """Create StreamableHTTP transport (production recommended)."""
    app = mcp.streamable_http_app()
    return app

if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    
    if transport == "sse":
        app = create_sse_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    elif transport == "streamable-http":
        app = create_streamable_http_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        mcp.run(transport="stdio")
```

## 🌐 Part 3: Building the Web Client

### Step 1: MCP Client Implementation

Create a client that connects to your MCP server:

```python
# web_client/mcp_client.py
from mcp import ClientSession
from mcp.client.sse import sse_client

class MCPWebClient:
    def __init__(self, server_url: str, transport_type: str = "sse"):
        self.server_url = server_url
        self.session = None
        self.conversation_sessions = {}  # Session memory

    async def connect_to_server(self):
        """Establish persistent connection to MCP server."""
        if self.transport_type == "sse":
            transport = await sse_client(url=self.server_url)
            self.read, self.write = transport
        
        self.session = ClientSession(self.read, self.write)
        await self.session.initialize()
```

### Step 2: FastAPI Web Service

Expose the MCP client through REST endpoints:

```python
# web_client/main.py
from fastapi import FastAPI
from mcp_client import MCPWebClient

app = FastAPI(title="MCP Web Client")
mcp_client = None

@app.post("/chat")
async def chat(request: ChatRequest):
    """Process a chat query using MCP tools."""
    if mcp_client is None:
        raise HTTPException(status_code=503, detail="MCP client not available")
    
    response = await mcp_client.process_query(request.query)
    return ChatResponse(response=response)

@app.post("/chat/session/{session_id}")
async def chat_with_session(session_id: str, request: ChatRequest):
    """Process query with conversation memory."""
    response = await mcp_client.process_query(
        request.query, 
        session_id=session_id
    )
    return ChatResponse(response=response, session_id=session_id)
```

### Step 3: Azure OpenAI Integration

Connect the MCP client to Azure OpenAI for intelligent responses:

```python
async def process_query(self, query: str, session_id: Optional[str] = None):
    """Process query using OpenAI and available MCP tools."""
    
    # Get conversation history
    conversation_history = self.conversation_sessions.get(session_id, [])
    conversation_history.append({"role": "user", "content": query})
    
    # Get available tools from MCP server
    response = await self.session.list_tools()
    available_tools = [
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
    
    # Call Azure OpenAI with tools
    response = self.llm.chat.completions.create(
        messages=conversation_history,
        tools=available_tools,
        model=self.deployment
    )
    
    # Execute any tool calls
    if response.choices[0].message.tool_calls:
        for tool_call in response.choices[0].message.tool_calls:
            result = await self.session.call_tool(
                tool_call.function.name,
                json.loads(tool_call.function.arguments)
            )
            # Process result and get final response
    
    return final_response
```

## 🐳 Part 4: Containerization

### Server Dockerfile

```dockerfile
# server/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy and install dependencies
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -e .

# Copy application
COPY weather.py ./

EXPOSE 8000
CMD ["python", "weather.py", "sse"]
```

### Docker Compose

```yaml
# docker_deployment/docker-compose.yml
services:
  mcp-weather-server:
    build: ../server
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s

  mcp-web-client:
    build: ../web_client
    ports:
      - "8080:8080"
    environment:
      - MCP_SERVER_URL=http://mcp-weather-server:8000/sse
    depends_on:
      mcp-weather-server:
        condition: service_healthy
```

## ☁️ Part 5: Azure Deployment

### Container Apps Deployment

```bash
# Create Azure resources
az group create --name mcp-tutorial-rg --location westeurope

# Create container registry
az acr create --resource-group mcp-tutorial-rg --name mcptutorialacr --sku Basic

# Build and push images
az acr build --registry mcptutorialacr --image weather-server ./server
az acr build --registry mcptutorialacr --image web-client ./web_client

# Create container apps environment
az containerapp env create \
  --name mcp-tutorial-env \
  --resource-group mcp-tutorial-rg \
  --location westeurope

# Deploy MCP server
az containerapp create \
  --name mcp-weather-server \
  --resource-group mcp-tutorial-rg \
  --environment mcp-tutorial-env \
  --image mcptutorialacr.azurecr.io/weather-server:latest \
  --target-port 8000 \
  --ingress external

# Deploy web client
az containerapp create \
  --name mcp-web-client \
  --resource-group mcp-tutorial-rg \
  --environment mcp-tutorial-env \
  --image mcptutorialacr.azurecr.io/web-client:latest \
  --target-port 8080 \
  --ingress external \
  --env-vars MCP_SERVER_URL=https://mcp-weather-server.app/sse
```

## 🧪 Part 6: Testing Your Implementation

### Test MCP Server Directly

```bash
# Start server
cd server
uv run python weather.py stdio

# Test with MCP CLI tools or directly via HTTP
curl http://localhost:8000/health
```

### Test Web Client API

```bash
# Test health endpoint
curl http://localhost:8080/health

# Test chat functionality
curl -X POST "http://localhost:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the weather alerts for California?"}'

# Test session-based chat
curl -X POST "http://localhost:8080/chat/session/user123" \
  -H "Content-Type: application/json" \
  -d '{"query": "What about the forecast for San Francisco?"}'
```

### Test Direct Tool Calls

```bash
# List available tools
curl http://localhost:8080/tools

# Call a tool directly
curl -X POST "http://localhost:8080/tools/get_alerts/call" \
  -H "Content-Type: application/json" \
  -d '{"state": "CA"}'
```

## 📊 Part 7: Monitoring and Observability

### Health Checks

Both services include comprehensive health checks:

```python
@app.get("/health")
async def health_check():
    """Health check with detailed status information."""
    try:
        if mcp_client is None:
            return HealthResponse(
                status="unhealthy",
                mcp_connected=False,
                error="MCP client not initialized"
            )
        
        health_status = await mcp_client.health_check()
        return HealthResponse(**health_status)
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            error=str(e)
        )
```

### Logging Best Practices

```python
import logging

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.info("Starting MCP server...")
logger.warning("Connection timeout, retrying...")
logger.error(f"Failed to process request: {error}")
```

## 🚀 Part 8: Production Considerations

### Security

- Use environment variables for sensitive configuration
- Implement proper CORS policies
- Add authentication/authorization as needed
- Validate all inputs thoroughly

### Performance

- Use connection pooling for HTTP clients
- Implement request timeouts
- Add caching for frequently accessed data
- Monitor resource usage

### Reliability

- Implement retry logic for external API calls
- Use circuit breakers for failing services
- Add graceful shutdown handling
- Monitor health endpoints

## 🎓 Next Steps

Congratulations! You've built a complete MCP implementation. Consider extending it with:

- **Additional Weather Tools** - Severe weather notifications, historical data
- **Other Data Sources** - News APIs, financial data, etc.
- **Advanced AI Features** - RAG (Retrieval-Augmented Generation), memory
- **Enterprise Features** - Authentication, rate limiting, audit logging

## 📚 Additional Resources

- [MCP Official Documentation](https://modelcontextprotocol.io/)
- [FastMCP Library](https://github.com/modelcontextprotocol/fastmcp)
- [Azure OpenAI Documentation](https://docs.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure Container Apps](https://docs.microsoft.com/en-us/azure/container-apps/)

## 🐛 Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure MCP server is running on the expected port
2. **Tool Not Found**: Check tool registration and naming
3. **Authentication Errors**: Verify Azure OpenAI credentials
4. **CORS Issues**: Configure CORS middleware properly
5. **Container Issues**: Check Docker networking and port mapping

### Debug Mode

Enable detailed logging:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or modify logging configuration
logging.basicConfig(level=logging.DEBUG)
```

Happy building! 🎉
