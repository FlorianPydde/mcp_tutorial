# MCP Weather Server

A **Model Context Protocol (MCP)** server providing weather information tools using the National Weather Service API. Implements MCP best practices with support for multiple transport protocols.

## 🌟 Features

- **Multi-Transport Support** - stdio, SSE, and StreamableHTTP
- **Three Weather Tools** - alerts, forecasts, and current conditions
- **Production Ready** - Comprehensive error handling and logging
- **No API Keys Required** - Uses free National Weather Service API
- **Docker Support** - Containerized deployment ready
- **Health Monitoring** - Built-in health check endpoints

## 🛠️ Available Tools

### `get_alerts(state: str)`
Get active weather alerts for a US state.

**Parameters:**
- `state` (str): Two-letter US state code (e.g., "CA", "NY", "TX")

**Returns:**
- Formatted string with active weather alerts including severity, description, and instructions

**Example:**
```python
# Get alerts for California
result = await get_alerts("CA")
```

### `get_forecast(latitude: float, longitude: float)`
Get detailed weather forecast for coordinates.

**Parameters:**
- `latitude` (float): Latitude in decimal degrees (-90 to 90)
- `longitude` (float): Longitude in decimal degrees (-180 to 180)

**Returns:**
- Multi-day forecast with temperature, wind, and detailed conditions

**Example:**
```python
# Get forecast for San Francisco
result = await get_forecast(37.7749, -122.4194)
```

### `get_current_conditions(latitude: float, longitude: float)`
Get current weather observations for coordinates.

**Parameters:**
- `latitude` (float): Latitude in decimal degrees (-90 to 90)
- `longitude` (float): Longitude in decimal degrees (-180 to 180)

**Returns:**
- Current temperature, humidity, wind speed, and conditions

**Example:**
```python
# Get current conditions for New York
result = await get_current_conditions(40.7128, -74.0060)
```

## 📚 Available Resources

### `weather://service/info`
Comprehensive information about the weather service capabilities, supported areas, and usage notes.

### `weather://states/codes`
Complete reference of US state and territory codes for use with the `get_alerts` tool.

## 🚀 Quick Start

### Local Development

```bash
# Install dependencies
uv sync

# Run with stdio transport (for Claude Desktop, etc.)
uv run python weather.py

# Run with SSE transport (for web clients)
uv run python weather.py sse

# Run with StreamableHTTP transport (production recommended)
uv run python weather.py streamable-http
```

### Docker Deployment

```bash
# Build the image
docker build -t mcp-weather-server .

# Run with SSE transport
docker run -p 8000:8000 mcp-weather-server

# Run with StreamableHTTP transport
docker run -p 8000:8000 mcp-weather-server python weather.py streamable-http
```

## 🔌 Transport Protocols

### stdio Transport
```bash
python weather.py
```
**Use Case:** Local desktop integration (Claude Desktop, local scripts)
**Endpoint:** stdin/stdout communication

### SSE (Server-Sent Events) Transport
```bash
python weather.py sse
```
**Use Case:** Web applications requiring real-time updates
**Endpoint:** `http://localhost:8000/sse`
**Health Check:** `http://localhost:8000/health`

### StreamableHTTP Transport
```bash
python weather.py streamable-http
```
**Use Case:** Production web services and microservices
**Endpoint:** `http://localhost:8000/mcp`
**Health Check:** `http://localhost:8000/health`

## 🌐 API Endpoints (HTTP Transports)

When running with SSE or StreamableHTTP transport:

- **`GET /health`** - Health check with service status
- **`GET /sse`** - SSE transport endpoint (SSE mode only)
- **`POST /mcp`** - StreamableHTTP transport endpoint (StreamableHTTP mode only)

## 🔧 Configuration

### Environment Variables

All configuration is optional and uses sensible defaults:

- `HOST` - Server host (default: "0.0.0.0")
- `PORT` - Server port (default: "8000")
- `LOG_LEVEL` - Logging level (default: "INFO")

### Dependencies

Defined in `pyproject.toml`:
- `httpx` - HTTP client for Weather Service API calls
- `mcp[cli]` - Model Context Protocol framework
- `uvicorn` - ASGI server for HTTP transports
- `fastapi` - Web framework for HTTP endpoints

## 📊 Monitoring

### Health Checks

The server provides comprehensive health checks when running HTTP transports:

```bash
# Check server health
curl http://localhost:8000/health

# Response example
{
  "status": "healthy",
  "service": "weather-mcp-server",
  "transport": "sse",
  "version": "1.0.0"
}
```

### Logging

Structured logging with configurable levels:

```python
import logging

# Configure logging level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## 🗺️ Supported Areas

The National Weather Service API covers:

- **United States** - All 50 states
- **US Territories** - Puerto Rico, Guam, US Virgin Islands, American Samoa
- **Northern Mariana Islands**
- **Washington D.C.**

### State Codes Reference

Use these two-letter codes with `get_alerts`:

```
AL - Alabama     AK - Alaska      AZ - Arizona     AR - Arkansas
CA - California  CO - Colorado    CT - Connecticut DE - Delaware
FL - Florida     GA - Georgia     HI - Hawaii      ID - Idaho
IL - Illinois    IN - Indiana     IA - Iowa        KS - Kansas
KY - Kentucky    LA - Louisiana   ME - Maine       MD - Maryland
MA - Massachusetts MI - Michigan  MN - Minnesota   MS - Mississippi
MO - Missouri    MT - Montana     NE - Nebraska    NV - Nevada
NH - New Hampshire NJ - New Jersey NM - New Mexico NY - New York
NC - North Carolina ND - North Dakota OH - Ohio     OK - Oklahoma
OR - Oregon      PA - Pennsylvania RI - Rhode Island SC - South Carolina
SD - South Dakota TN - Tennessee  TX - Texas       UT - Utah
VT - Vermont     VA - Virginia    WA - Washington  WV - West Virginia
WI - Wisconsin   WY - Wyoming

Territories:
AS - American Samoa       DC - District of Columbia
GU - Guam                MP - Northern Mariana Islands
PR - Puerto Rico         VI - US Virgin Islands
```

## 🔍 Error Handling

The server implements comprehensive error handling:

- **Input Validation** - Validates state codes and coordinate ranges
- **HTTP Error Handling** - Graceful handling of API failures
- **Timeout Protection** - 30-second timeouts for external API calls
- **Logging** - Detailed error logging for debugging

## 🧪 Testing

### Manual Testing

```bash
# Test with MCP CLI tools
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python weather.py

# Test with curl (HTTP transports)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

### Integration Testing

```bash
# Test all transports
uv run pytest tests/

# Test specific transport
uv run pytest tests/test_sse_transport.py
```

## 🐳 Docker Configuration

### Dockerfile Features

- **Python 3.12** base image for modern Python features
- **uv** for fast dependency management
- **Health checks** built-in
- **Non-root user** for security
- **Optimized layers** for efficient builds

### Docker Compose Integration

```yaml
services:
  weather-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 🚀 Production Deployment

### Performance Considerations

- **Connection Pooling** - Reuses HTTP connections to Weather Service
- **Async Operations** - Non-blocking I/O for high concurrency
- **Timeout Handling** - Prevents hanging requests
- **Resource Cleanup** - Proper cleanup of HTTP clients

### Security Best Practices

- **Input Validation** - All parameters validated before processing
- **No Secrets** - Uses public APIs, no sensitive data
- **Error Sanitization** - Internal errors not exposed to clients
- **User-Agent** - Proper identification to Weather Service

## 📚 Further Reading

- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [National Weather Service API](https://www.weather.gov/documentation/services-web-api)
- [FastMCP Library](https://github.com/modelcontextprotocol/fastmcp)

## 🤝 Contributing

This server follows Python best practices:
- **Type hints** throughout
- **Async/await** for I/O operations
- **Comprehensive logging**
- **Error handling** with user-friendly messages
- **Documentation** for all public functions

## 📄 License

Open source - adapt for your own MCP server implementations!