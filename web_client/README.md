# MCP Web Client

A FastAPI-based web service that provides HTTP endpoints for interacting with the MCP weather server.

## Features

- RESTful API endpoints for weather queries
- Conversation memory support
- Session management
- Azure OpenAI integration
- SSE connection to MCP server
- Health checks and monitoring

## API Endpoints

- `POST /chat` - Process a weather query
- `POST /chat/session/{session_id}` - Process query with session memory
- `DELETE /chat/session/{session_id}` - Clear session conversation
- `GET /chat/session/{session_id}/stats` - Get conversation statistics
- `GET /health` - Health check endpoint

## Environment Variables

Required environment variables:
- `AZURE_OPENAI_API_BASE` - Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
- `AZURE_OPENAI_API_VERSION` - API version (e.g., "2024-02-15-preview")
- `AZURE_OPENAI_DEPLOYMENT_NAME` - Deployment name
- `MCP_SERVER_URL` - MCP server SSE endpoint (default: "http://localhost:8000/sse")

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
