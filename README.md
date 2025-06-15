# MCP Weather Tutorial

A comprehensive **Model Context Protocol (MCP)** implementation demonstrating weather services with multiple transport options, Azure OpenAI integration, and deployment on Azure Container Apps.

## 🏗️ Architecture Overview

```
┌─────────────────┐    HTTP/REST    ┌──────────────────┐    MCP Protocol    ┌─────────────────┐
│   Web Client    │◄──────────────►│   Web Service    │◄─────────────────►│  Weather Server │
│  (Frontend)     │                │  (FastAPI)       │  (SSE/HTTP)        │   (MCP Server)  │
└─────────────────┘                └──────────────────┘                    └─────────────────┘
                                             │                                       │
                                             ▼                                       ▼
                                    ┌─────────────────┐                  ┌─────────────────┐
                                    │  Azure OpenAI   │                  │  Weather.gov    │
                                    │    Service      │                  │      API        │
                                    └─────────────────┘                  └─────────────────┘
```

## 📦 Project Structure

```
mcp_tutorial/
├── server/                     # MCP Weather Server
│   ├── weather.py             # Main MCP server implementation
│   ├── pyproject.toml         # Server dependencies
│   └── Dockerfile             # Server container config
├── web_client/                # FastAPI Web Service
│   ├── main.py               # FastAPI application
│   ├── mcp_client.py         # MCP client implementation
│   ├── models.py             # Pydantic models
│   ├── pyproject.toml        # Client dependencies
│   └── Dockerfile            # Client container config
├── docker_deployment/         # Container orchestration
│   └── docker-compose.yml    # Local multi-service setup
├── azure_deployment/          # Cloud deployment
│   └── azure-deploy.ps1      # Azure Container Apps deployment
└── doc/                      # Documentation (this folder)
```

## 🚀 Quick Start

### Local Development (Recommended)

1. **Prerequisites**
   ```bash
   # Install uv (modern Python package manager)
   pip install uv
   
   # Verify Python 3.12+
   python --version
   ```

2. **Start MCP Weather Server**
   ```bash
   cd server
   uv sync
   uv run python weather.py sse  # SSE transport on :8000
   ```

3. **Configure Azure OpenAI** (Create `web_client/.env`)
   ```env
   AZURE_OPENAI_API_BASE=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-api-key
   AZURE_OPENAI_API_VERSION=2024-02-15-preview
   AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
   MCP_SERVER_URL=http://localhost:8000/sse
   ```

4. **Start Web Client**
   ```bash
   cd web_client
   uv sync
   uv run uvicorn main:app --reload --port 8080
   ```

5. **Test the Setup**
   ```bash
   curl -X POST "http://localhost:8080/chat" \
     -H "Content-Type: application/json" \
     -d '{"query": "What are the weather alerts for California?"}'
   ```

### Docker Deployment

```bash
cd docker_deployment
docker-compose up --build
```

## 🛠️ Available Tools

The MCP weather server provides three main tools:

- **`get_alerts(state)`** - Get active weather alerts for US states
- **`get_forecast(latitude, longitude)`** - Get detailed weather forecasts
- **`get_current_conditions(latitude, longitude)`** - Get current weather observations

## 🔌 MCP Transports Supported

- **stdio** - Local desktop integration (Claude Desktop, etc.)
- **SSE (Server-Sent Events)** - HTTP-based streaming
- **StreamableHTTP** - Production-recommended HTTP transport

## 🌐 API Endpoints (Web Client)

### Chat & Sessions
- `POST /chat` - Process queries without memory
- `POST /chat/session/{id}` - Process queries with conversation memory
- `DELETE /chat/session/{id}` - Clear session history

### Direct Tool Access
- `GET /tools` - List available MCP tools
- `POST /tools/{tool_name}/call` - Call tools directly

### System
- `GET /health` - Health check with detailed status
- `GET /config` - Configuration and environment info

## 🚢 Azure Deployment

### Azure Container Apps (Recommended)

```bash
cd azure_deployment
# Edit azure-deploy.ps1 with your settings
.\azure-deploy.ps1
```

```bash
cd azure_deployment
# Edit azure-deploy.ps1 with your settings
.\azure-deploy.sh
```

### Docker Compose (Local)

```bash
cd docker_deployment
docker-compose -f docker-compose.yml up -d
```

## 🔧 Configuration

### Environment Variables

**Server** (Optional - uses defaults):
- No configuration required for basic operation

**Web Client** (Required for chat functionality):
- `AZURE_OPENAI_API_BASE` - Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY` - API key
- `AZURE_OPENAI_API_VERSION` - API version
- `AZURE_OPENAI_DEPLOYMENT_NAME` - Model deployment name
- `MCP_SERVER_URL` - MCP server endpoint
- `MCP_TRANSPORT_TYPE` - `sse` or `streamable_http`

## 📚 Key Features

- **Multi-Transport Support** - Works with stdio, SSE, and StreamableHTTP
- **Production Ready** - Health checks, logging, error handling
- **Session Management** - Conversation memory for web interactions
- **Azure OpenAI Integration** - Intelligent responses with tool calling
- **Container Ready** - Docker and Azure Container Apps support
- **Type Safety** - Full type annotations and Pydantic models

## 🧪 Testing

```bash
# Server tests
cd server
uv run pytest

# Client tests  
cd web_client
uv run pytest
```

## 📖 Further Reading

- See `doc/TUTORIAL_GUIDE.md` for step-by-step implementation guide
- See `web_client/DEPLOYMENT.md` for detailed Azure deployment instructions
- Visit [MCP Documentation](https://modelcontextprotocol.io/) for protocol details

## 🤝 Contributing

This project follows modern Python practices:
- **uv** for dependency management
- **pytest** for testing
- **Conventional commits** for version control
- **PEP 8** code style with 82-character line limits
- **Type annotations** throughout

## 📄 License

Open source - feel free to adapt for your own MCP implementations!
