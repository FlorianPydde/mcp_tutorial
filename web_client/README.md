# MCP Web Client

A FastAPI-based web service that provides HTTP endpoints for interacting with MCP servers, following Model Context Protocol standards.

## Features

- RESTful API endpoints for MCP server interactions
- Support for both SSE and StreamableHTTP transports
- Conversation memory support with session management
- Azure OpenAI integration for intelligent responses
- Direct tool calling capabilities
- Health checks and monitoring

## API Endpoints

### Chat Endpoints
- `POST /chat` - Process a query without session memory
- `POST /chat/session/{session_id}` - Process query with session memory
- `DELETE /chat/session/{session_id}` - Clear session conversation
- `GET /chat/session/{session_id}/stats` - Get conversation statistics

### Tool Endpoints
- `GET /tools` - List all available tools from MCP server
- `POST /tools/{tool_name}/call` - Call a specific tool directly

### System Endpoints
- `GET /health` - Health check endpoint
- `GET /` - API information and available endpoints

## Environment Variables

### Required Azure OpenAI Configuration
- `AZURE_OPENAI_API_BASE` - Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
- `AZURE_OPENAI_API_VERSION` - API version (e.g., "2024-02-15-preview")
- `AZURE_OPENAI_DEPLOYMENT_NAME` - Deployment name

### MCP Server Configuration
- `MCP_SERVER_URL` - Explicit MCP server URL (optional)
- `MCP_SERVER_PORT` - MCP server port (default: 8000)
- `MCP_TRANSPORT_TYPE` - Transport type: "sse" or "streamable_http" (default: "sse")

## Usage

### Local Development

```bash
# Install dependencies
uv sync

# Run the server
uv run uvicorn main:app --reload --port 8080
```

### Docker Deployment

```bash
docker build -t mcp-web-client .
docker run -p 8080:8080 --env-file .env mcp-web-client
```

## API Examples

### Simple Query
```bash
curl -X POST "http://localhost:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in San Francisco?"}'
```

### Session-based Query
```bash
curl -X POST "http://localhost:8080/chat/session/user123" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in San Francisco?"}'
```

### Clear Session
```bash
curl -X DELETE "http://localhost:8080/chat/session/user123"
```
