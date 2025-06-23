# MCP Gateway

Enterprise-ready MCP (Model Context Protocol) Gateway that provides a centralized routing layer for multiple MCP servers. The gateway acts as both an MCP client (to backend servers) and MCP server (to frontend clients), enabling teams to connect to a single endpoint while providing robust health monitoring and tool discovery.

## Features

- **Centralized Routing**: Single endpoint for multiple MCP servers
- **Dynamic Tool Discovery**: Automatic discovery and registration of tools from backend servers
- **Health Monitoring**: Real-time health checks of all backend MCP servers
- **MCP Protocol Compliant**: Fully compliant with MCP protocol specifications
- **Real-time Updates**: Tool registry updates and health status monitoring
- **Enterprise Ready**: Logging, monitoring, and deployment-ready
- **Simplified Architecture**: No authentication required for easy setup and testing

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Team Client   │    │   Team Client   │    │   Team Client   │
│     (Web App)   │    │  (Desktop App)  │    │   (CLI Tool)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    MCP Gateway          │
                    │  - Tool Discovery       │
                    │  - Health Monitor       │
                    │  - Request Routing      │
                    │  - Protocol Translation │
                    └─────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Weather Server │    │   News Server   │    │ Custom Server   │
│     (Port 8001) │    │   (Port 8002)   │    │   (Port 8003)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
# Install using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### 2. Configuration

Create and configure settings for your environment:

```bash
# Server settings
HOST=0.0.0.0
PORT=8080
DEBUG=false

# MCP Servers to connect to
MCP_SERVERS__WEATHER__HOST=localhost
MCP_SERVERS__WEATHER__PORT=8001
MCP_SERVERS__WEATHER__TAGS=weather,forecast,location

MCP_SERVERS__NEWS__HOST=localhost
MCP_SERVERS__NEWS__PORT=8002
MCP_SERVERS__NEWS__TAGS=news,headlines,search

# Health monitoring settings
HEALTH_CHECK_INTERVAL=30
HEALTH_TIMEOUT=10
```

### 3. Run the Gateway

```bash
# Using uv
uv run python -m mcp_gateway.main

# Or using python directly
python -m mcp_gateway.main

# Or using the entry point
mcp-gateway
```

The gateway will start on `http://localhost:8080` by default.

## API Endpoints

### Health Monitoring

- `GET /health` - Gateway health check
- `GET /health/servers` - Health status of all MCP servers
- `GET /health/servers/{server_name}` - Health status of specific server

### Tool Discovery

- `GET /tools` - List all available tools from all servers
- `GET /tools/summary` - Get tools summary and statistics
- `GET /tools/search?q={query}` - Search tools by name or description
- `POST /tools/{tool_name}/call` - Execute a specific tool

### MCP Protocol

- `POST /mcp` - Main MCP JSON-RPC endpoint
  - Supports `tools/list`, `tools/call`, `resources/list`, `resources/read`

## Authentication

## Example Usage

### List Available Tools

```bash
# Get all available tools
curl http://localhost:8080/tools
```

### Check Health Status

```bash
# Check gateway health
curl http://localhost:8080/health

# Check all server health
curl http://localhost:8080/health/servers
```
  -d '{"arguments": {"location": "London"}}'
```

## MCP Protocol Usage

The gateway is fully MCP protocol compliant:

```bash
# List available tools
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'

# Call a weather tool
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_forecast",
      "arguments": {"latitude": 37.7749, "longitude": -122.4194}
    }
  }'

# Call a news tool  
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "search_news",
      "arguments": {"query": "artificial intelligence", "language": "en"}
    }
  }'
```

## Configuration

### Environment Variables

Key configuration options:

```bash
# Server
HOST=0.0.0.0
PORT=8080
DEBUG=false

# Authentication
AUTH__ENABLED=true
AUTH__SECRET_KEY=your-secret-key
AUTH__ACCESS_TOKEN_EXPIRE_MINUTES=30

# Health Monitoring
HEALTH_CHECK_INTERVAL=30
HEALTH_TIMEOUT=10

# Tool Discovery  
TOOL_DISCOVERY_INTERVAL=60

# MCP Servers
MCP_SERVERS__WEATHER__HOST=localhost
MCP_SERVERS__WEATHER__PORT=8001
MCP_SERVERS__WEATHER__ENABLED=true
```

### Adding New Servers

To add a new MCP server:

1. Add server configuration to `.env`:
```bash
MCP_SERVERS__BILLING__NAME=billing
MCP_SERVERS__BILLING__DESCRIPTION=Billing service
MCP_SERVERS__BILLING__HOST=localhost
MCP_SERVERS__BILLING__PORT=8003
MCP_SERVERS__BILLING__ENABLED=true
MCP_SERVERS__BILLING__TAGS=["billing", "finance"]
```

2. Update user permissions in `auth.py` to grant access to the new server.

3. Restart the gateway - it will automatically discover tools from the new server.

## Development

### Running in Development Mode

```bash
# Set debug mode (Unix/Linux/macOS)
DEBUG=true

# Set debug mode (Windows PowerShell)
$env:DEBUG="true"

# Run with auto-reload
uvicorn mcp_gateway.gateway:create_app --reload --host 0.0.0.0 --port 8080
```

### Testing

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Manual testing with curl
curl http://localhost:8080/health
curl http://localhost:8080/tools
```

### Code Quality

```bash
# Format code
black mcp_gateway/
isort mcp_gateway/

# Lint code
flake8 mcp_gateway/
mypy mcp_gateway/
```

## Docker Deployment

### Build Image

```bash
docker build -t mcp-gateway .
```

### Run Container

```bash
docker run -p 8080:8080 \
  -e AUTH__SECRET_KEY=your-production-secret \
  -e MCP_SERVERS__WEATHER__HOST=weather-server \
  -e MCP_SERVERS__NEWS__HOST=news-server \
  mcp-gateway
```

### Docker Compose

See the main project's `docker-compose.yml` for a complete multi-service setup.

## Monitoring

The gateway provides several monitoring endpoints:

- `/health` - Basic health check
- `/health/servers` - Detailed health of all backend servers
- `/tools/summary` - Tool discovery statistics

Health checks include:
- HTTP connectivity to backend servers
- MCP protocol validation
- Response time monitoring
- Consecutive failure tracking

## Security

- JWT-based authentication with configurable expiration
- Role-based access control for tools and servers
- CORS protection
- Input validation on all endpoints
- Secure password hashing with bcrypt

## Logging

Structured logging with configurable levels:

```python
# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Custom log format
LOG_FORMAT="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## Troubleshooting

### Common Issues

1. **Server Not Found**: Check server configuration in `.env`
2. **Authentication Failed**: Verify JWT secret and token expiration
3. **Tool Discovery Issues**: Check server health and MCP endpoints
4. **Permission Denied**: Verify user permissions in `auth.py`

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Unix/Linux/macOS
DEBUG=true
LOG_LEVEL=DEBUG

# Windows PowerShell
$env:DEBUG="true"
$env:LOG_LEVEL="DEBUG"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following the coding standards
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License.
