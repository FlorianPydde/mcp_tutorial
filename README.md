# MCP Tutorial - Enterprise Gateway Architecture

This project demonstrates an enterprise-ready MCP (Model Context Protocol) Gateway architecture that allows multiple teams to connect to various MCP servers through a single endpoint.

## Architecture Overview

```
┌─────────────────────┐
│   Web Client        │
│   (Port 3000)       │
│   - Team Interface  │
│   - Chat & Tools    │
└─────────────────────┘
         │
         ▼ HTTP/JSON
┌─────────────────────┐
│   MCP Gateway       │
│   (Port 8080)       │
│   - Tool Discovery  │
│   - Health Monitor  │
│   - Request Routing │
└─────────────────────┘
         │
         ▼ MCP Protocol
┌─────────────────────┐    ┌─────────────────────┐
│  Weather Server     │    │   News Server       │
│  (Port 8001)        │    │   (Port 8002)       │
│  - Weather tools    │    │   - News tools      │
└─────────────────────┘    └─────────────────────┘
```

## Components

### MCP Gateway (`mcp_gateway/`)
- **Central routing service** that connects to multiple MCP servers
- **Dynamic tool discovery** and health monitoring
- **MCP protocol compliant** - acts as both client and server
- **Simplified without authentication** for easy setup

### Web Client (`web_client/`)
- **Team-facing web interface** that connects to the gateway
- **RESTful API** for easy integration
- **Chat functionality** with Azure OpenAI integration
- **Session management** for conversation context

### MCP Servers
- **Weather Server** (`server/`) - provides weather information tools
- **News Server** (`server/news/`) - provides news and article tools
- Easily extensible to add more servers

## Quick Start

### 1. Using Docker Compose (Recommended)

```bash
# Start all services
docker-compose up --build

# Services will be available at:
# - Web Client: http://localhost:3000
# - MCP Gateway: http://localhost:8080
# - Weather Server: http://localhost:8001
# - News Server: http://localhost:8002
```

### 2. Manual Setup

#### Start the MCP Servers

```bash
# Terminal 1: Weather Server
cd server
uv pip install -e .
python weather.py

# Terminal 2: News Server  
cd server/news
uv pip install -e .
python news.py
```

#### Start the Gateway

```bash
# Terminal 3: MCP Gateway
cd mcp_gateway
uv pip install -e .
python -m mcp_gateway.main
```

#### Start the Web Client

```bash
# Terminal 4: Web Client
cd web_client
uv pip install -e .
python main.py
```

## Usage Examples

### Direct API Calls

```bash
# List available tools
curl http://localhost:8080/tools

# Call weather tool
curl -X POST http://localhost:8080/tools/get_weather/call \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"location": "London"}}'

# Call news tool
curl -X POST http://localhost:8080/tools/get_news/call \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"category": "technology"}}'
```

### Web Client Interface

```bash
# Chat with AI (requires Azure OpenAI configuration)
curl -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in London and latest tech news?"}'

# Direct tool calls through web client
curl -X POST http://localhost:3000/tools/get_weather/call \
  -H "Content-Type: application/json" \
  -d '{"location": "Paris"}'
```

### Health Monitoring

```bash
# Gateway health
curl http://localhost:8080/health

# All servers health
curl http://localhost:8080/health/servers

# Web client health  
curl http://localhost:3000/health
```

## Configuration

### Gateway Configuration (`.env`)

```bash
# Server settings
HOST=0.0.0.0
PORT=8080
DEBUG=false

# Health monitoring
HEALTH_CHECK_INTERVAL=30
TOOL_DISCOVERY_INTERVAL=60

# MCP servers (automatically configured in docker-compose)
MCP_SERVERS__WEATHER__HOST=localhost
MCP_SERVERS__WEATHER__PORT=8001
MCP_SERVERS__NEWS__HOST=localhost  
MCP_SERVERS__NEWS__PORT=8002
```

### Web Client Configuration (`.env`)

```bash
# Gateway connection
MCP_GATEWAY_URL=http://localhost:8080

# Optional: Azure OpenAI for chat
AZURE_OPENAI_API_BASE=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment
```

## Features

### ✅ Implemented
- **MCP Gateway** with tool routing and health monitoring
- **Multiple MCP Servers** (weather and news)
- **Dynamic Tool Discovery** and real-time updates
- **Health Monitoring** of all backend services
- **Web Client** with REST API and chat interface
- **Docker Compose** deployment
- **MCP Protocol Compliance** for all components

### 🔄 Simplified (Authentication Removed)
- No JWT authentication or role-based access control
- All endpoints publicly accessible
- Simplified configuration and setup

## Adding New MCP Servers

1. **Create the server** following MCP protocol standards
2. **Add to docker-compose.yml**:
```yaml
new-server:
  build: ./path/to/new/server
  ports:
    - "8003:8000"
  networks:
    - mcp-network
```

3. **Update gateway configuration**:
```bash
MCP_SERVERS__NEWSERVER__HOST=new-server
MCP_SERVERS__NEWSERVER__PORT=8000
MCP_SERVERS__NEWSERVER__ENABLED=true
```

4. **Restart services** - gateway will automatically discover new tools

## Development

### Code Quality
- **Type hints** throughout the codebase
- **Comprehensive logging** for debugging
- **Error handling** and graceful degradation
- **Modular architecture** for easy maintenance

### Testing
```bash
# Run tests for each component
cd mcp_gateway && pytest
cd web_client && pytest  
cd server && pytest
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 3000, 8080, 8001, 8002 are available
2. **Docker issues**: Run `docker-compose down && docker-compose up --build`
3. **Tool discovery**: Check server health endpoints are responding
4. **Connection errors**: Verify all services are running and accessible

### Debug Mode

Enable debug logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Health Checks

All services include health check endpoints:
- Gateway: `http://localhost:8080/health`
- Web Client: `http://localhost:3000/health`
- Weather Server: `http://localhost:8001/health`
- News Server: `http://localhost:8002/health`

## License

This project is licensed under the MIT License.
