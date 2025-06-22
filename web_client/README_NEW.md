# MCP Gateway Web Client

Enterprise-ready web client that connects to the MCP Gateway to access multiple MCP servers through a single endpoint. This client demonstrates how teams can integrate with the MCP Gateway to get access to various tools and services.

## Features

- **Gateway Integration**: Connects to MCP Gateway instead of individual servers
- **Authentication**: JWT-based authentication with role-based access
- **Multi-tool Access**: Access to weather, news, and other tools through single endpoint
- **Session Management**: Persistent conversation sessions
- **Health Monitoring**: Real-time health status of backend services
- **Azure OpenAI Integration**: Optional chat functionality with tool calling
- **RESTful API**: Easy-to-use REST endpoints for integration

## Quick Start

### 1. Install Dependencies

```bash
# Install using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### 2. Configuration

Copy and configure the environment file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# MCP Gateway connection
MCP_GATEWAY_URL=http://localhost:8080
MCP_USERNAME=team_a
MCP_PASSWORD=team_a123

# Optional: Azure OpenAI for chat
AZURE_OPENAI_API_BASE=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment
```

### 3. Run the Client

```bash
# Start the web client
python main.py

# Or with uvicorn
uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

The client will be available at `http://localhost:3000`

## API Endpoints

### Health Check
- `GET /health` - Check client health and gateway connection status

### Chat & Queries
- `POST /chat` - Send a query and get AI response with tool calls
- `POST /sessions/{session_id}/chat` - Chat with session context
- `GET /sessions/{session_id}/stats` - Get session statistics  
- `DELETE /sessions/{session_id}` - Clear session history

### Direct Tool Calls
- `POST /tools/{tool_name}/call` - Call a specific tool directly
- `GET /tools` - List available tools
- `GET /tools/search?q={query}` - Search tools

### Gateway Information
- `GET /gateway/health` - Get health status of all backend servers
- `GET /gateway/tools/summary` - Get tools summary from gateway

## Authentication

The client authenticates with the gateway using the configured credentials. Different users have different permissions:

- **team_a**: Access to weather and news tools
- **team_b**: Access to weather tools only  
- **admin**: Full access to all tools and servers

## Usage Examples

### Chat with AI

```bash
curl -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current weather in London?"}'
```

### Direct Tool Call

```bash
curl -X POST http://localhost:3000/tools/get_weather/call \
  -H "Content-Type: application/json" \
  -d '{"location": "London"}'
```

### Session-based Chat

```bash
# Start a conversation in session
curl -X POST http://localhost:3000/sessions/my-session/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in London?"}'

# Continue conversation
curl -X POST http://localhost:3000/sessions/my-session/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "How about in Paris?"}'

# Check session stats
curl http://localhost:3000/sessions/my-session/stats
```

### Get Available Tools

```bash
curl http://localhost:3000/tools
```

### Search Tools

```bash
curl "http://localhost:3000/tools/search?q=weather"
```

### Check Gateway Health

```bash
curl http://localhost:3000/gateway/health
```

## Development

### Running in Development

```bash
# With auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 3000

# With debug logging
LOG_LEVEL=DEBUG uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

### Team Configurations

The client can be configured for different teams by changing the credentials:

```bash
# Team A (weather + news access)
MCP_USERNAME=team_a
MCP_PASSWORD=team_a123

# Team B (weather only)
MCP_USERNAME=team_b  
MCP_PASSWORD=team_b123

# Admin (full access)
MCP_USERNAME=admin
MCP_PASSWORD=admin123
```

## Architecture

```
┌─────────────────────┐
│   Web Client API    │
│   (Port 3000)       │
│   - REST endpoints  │
│   - Session mgmt    │
│   - Auth handling   │
└─────────────────────┘
         │
         ▼ HTTP/JSON
┌─────────────────────┐
│   MCP Gateway       │
│   (Port 8080)       │
│   - Authentication  │
│   - Tool routing    │
│   - Health monitor  │
└─────────────────────┘
         │
         ▼ MCP Protocol
┌─────────────────────┐
│  Backend MCP        │
│  Servers            │
│  - Weather (8001)   │
│  - News (8002)      │
│  - Others...        │
└─────────────────────┘
```

## Error Handling

The client includes comprehensive error handling:

- **Gateway Connection Errors**: Graceful handling of gateway connectivity issues
- **Authentication Errors**: Clear error messages for auth failures
- **Tool Execution Errors**: Proper error propagation from backend servers
- **Session Management**: Robust session state management

## Docker Support

```bash
# Build image
docker build -t mcp-gateway-client .

# Run container
docker run -p 3000:3000 \
  -e MCP_GATEWAY_URL=http://gateway:8080 \
  -e MCP_USERNAME=team_a \
  -e MCP_PASSWORD=team_a123 \
  mcp-gateway-client
```

## Integration Examples

### Python Integration

```python
import httpx

async def call_weather_tool():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3000/tools/get_weather/call",
            json={"location": "London"}
        )
        return response.json()

# Usage
weather_data = await call_weather_tool()
```

### JavaScript Integration

```javascript
// Fetch weather data
const response = await fetch('http://localhost:3000/tools/get_weather/call', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ location: 'London' })
});

const weatherData = await response.json();
```

## Monitoring

The client provides monitoring capabilities:

- Health check endpoint for load balancers
- Session statistics for usage analytics
- Gateway health status forwarding
- Structured logging for debugging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the existing code patterns
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License.
