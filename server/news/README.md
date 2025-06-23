# News MCP Server

A **Model Context Protocol (MCP)** server providing news information tools using the NewsAPI.org service. Implements MCP best practices with support for multiple transport protocols.

## 🌟 Features

- **Multi-Transport Support** - stdio, SSE, and StreamableHTTP
- **Two News Tools** - headlines and search functionality
- **Production Ready** - Comprehensive error handling and logging
- **NewsAPI Integration** - Access to 80,000+ news sources worldwide
- **Docker Support** - Containerized deployment ready
- **Health Monitoring** - Built-in health check endpoints

## 🛠️ Available Tools

### `get_top_headlines(country: str, category: Optional[str])`
Get top headlines from a specific country and optional category.

**Parameters:**
- `country` (str): Two-letter country code (e.g., "us", "gb", "ca", "au")
- `category` (Optional[str]): News category - 'business', 'entertainment', 'general', 'health', 'science', 'sports', 'technology'

**Returns:**
- Formatted string with top headlines including title, source, description, and URL

**Example:**
```python
# Get US tech headlines
result = await get_top_headlines("us", "technology")
```

### `search_news(query: str, language: str, sort_by: str)`
Search for news articles based on keywords.

**Parameters:**
- `query` (str): Keywords or phrases to search for
- `language` (str): Language code (default: "en") - 'ar', 'de', 'en', 'es', 'fr', 'he', 'it', 'nl', 'no', 'pt', 'ru', 'sv', 'ud', 'zh'
- `sort_by` (str): Sort order - 'relevancy', 'popularity', 'publishedAt' (default)

**Returns:**
- Formatted string with search results including article details

**Example:**
```python
# Search for AI articles
result = await search_news("artificial intelligence", "en", "relevancy")
```

## 📚 Available Resources

### `news://service/info`
Comprehensive information about the news service capabilities, supported countries, categories, and usage notes.

## 🚀 Quick Start

### Prerequisites

1. **Get NewsAPI Key**
   - Sign up at [https://newsapi.org](https://newsapi.org)
   - Get your free API key (1,000 requests/day)

2. **Set Environment Variable**
   ```bash
   # Create environment file and add your API key
   NEWS_API_KEY=your_actual_api_key_here
   ```

### Local Development

```bash
# Install dependencies
uv sync

# Run with stdio transport (for Claude Desktop, etc.)
uv run python news.py

# Run with SSE transport (for web clients)
uv run python news.py sse

# Run with StreamableHTTP transport (production recommended)
uv run python news.py streamable-http
```

### Docker Deployment

```bash
# Build the image
docker build -t mcp-news-server .

# Run with SSE transport
docker run -p 8001:8001 --env-file .env mcp-news-server

# Run with StreamableHTTP transport
docker run -p 8001:8001 --env-file .env mcp-news-server python news.py streamable-http
```

## 🔌 Transport Protocols

### stdio Transport
```bash
python news.py
```
**Use Case:** Local desktop integration (Claude Desktop, local scripts)
**Endpoint:** stdin/stdout communication

### SSE (Server-Sent Events) Transport
```bash
python news.py sse
```
**Use Case:** Web applications requiring real-time updates
**Endpoint:** `http://localhost:8001/sse`
**Health Check:** `http://localhost:8001/health`

### StreamableHTTP Transport
```bash
python news.py streamable-http
```
**Use Case:** Production web services and microservices
**Endpoint:** `http://localhost:8001/mcp`
**Health Check:** `http://localhost:8001/health`

## 🌐 API Endpoints (HTTP Transports)

When running with SSE or StreamableHTTP transport:

- **`GET /health`** - Health check with API key status
- **`GET /sse`** - SSE transport endpoint (SSE mode only)
- **`POST /mcp`** - StreamableHTTP transport endpoint (StreamableHTTP mode only)

## 🔧 Configuration

### Environment Variables

- `NEWS_API_KEY` - **Required** - Your NewsAPI.org API key
- `HOST` - Server host (default: "0.0.0.0")
- `PORT` - Server port (default: "8001")
- `LOG_LEVEL` - Logging level (default: "INFO")

### Dependencies

Defined in `pyproject.toml`:
- `httpx` - HTTP client for NewsAPI calls
- `mcp[cli]` - Model Context Protocol framework
- `uvicorn` - ASGI server for HTTP transports
- `fastapi` - Web framework for HTTP endpoints

## 📊 Monitoring

### Health Checks

The server provides comprehensive health checks when running HTTP transports:

```bash
# Check server health
curl http://localhost:8001/health

# Response example
{
  "status": "healthy",
  "service": "news-mcp-server",
  "transport": "sse",
  "version": "1.0.0",
  "api_key_configured": true
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

## 🗺️ Supported Coverage

### Countries
The NewsAPI supports headlines from 54+ countries including:
- **Americas**: US, Canada, Brazil, Mexico, Argentina
- **Europe**: UK, Germany, France, Spain, Italy, Netherlands
- **Asia**: Japan, China, India, South Korea, Singapore
- **Oceania**: Australia, New Zealand
- **Africa**: South Africa, Egypt
- **Middle East**: Saudi Arabia, UAE, Israel

### Categories
- **business** - Business and financial news
- **entertainment** - Entertainment and celebrity news
- **general** - General news (default)
- **health** - Health and medical news
- **science** - Science and technology breakthroughs
- **sports** - Sports news and updates
- **technology** - Technology and startup news

### Languages
- **English** (en), **Spanish** (es), **French** (fr), **German** (de)
- **Chinese** (zh), **Japanese** (ja), **Arabic** (ar), **Russian** (ru)
- **Portuguese** (pt), **Italian** (it), **Dutch** (nl), **Hebrew** (he)
- **Norwegian** (no), **Swedish** (sv), **Urdu** (ud)

## 🔍 Error Handling

The server implements comprehensive error handling:

- **API Key Validation** - Checks for missing or invalid API keys
- **Input Validation** - Validates country codes, categories, and languages
- **Rate Limit Handling** - Graceful handling of API rate limits
- **Timeout Protection** - 30-second timeouts for external API calls
- **Logging** - Detailed error logging for debugging

## 🧪 Testing

### Manual Testing

```bash
# Test with MCP CLI tools
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python news.py

# Test with curl (HTTP transports)
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

### Example Queries

```bash
# Get US business headlines
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_top_headlines",
      "arguments": {"country": "us", "category": "business"}
    }
  }'

# Search for climate change news
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_news",
      "arguments": {"query": "climate change", "language": "en", "sort_by": "relevancy"}
    }
  }'
```

## 🚀 Production Deployment

### Performance Considerations

- **API Rate Limits** - Free tier: 1,000 requests/day, paid tiers available
- **Caching** - Consider implementing response caching for frequently requested data
- **Async Operations** - Non-blocking I/O for high concurrency
- **Connection Pooling** - Reuses HTTP connections to NewsAPI

### Security Best Practices

- **API Key Protection** - Store API key in environment variables
- **Input Validation** - All parameters validated before processing
- **Error Sanitization** - Internal errors not exposed to clients
- **Rate Limiting** - Consider implementing client-side rate limiting

## 📚 Further Reading

- [NewsAPI Documentation](https://newsapi.org/docs)
- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
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
