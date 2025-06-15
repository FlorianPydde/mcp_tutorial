# MCP Architecture Deep Dive

A technical overview of the Model Context Protocol implementation patterns used in this weather tutorial project.

## 🏗️ MCP Protocol Overview

The Model Context Protocol (MCP) is a standardized way for AI models to interact with external tools and data sources. It defines:

- **Tools** - Functions that can be called by AI models
- **Resources** - Data sources that provide context
- **Prompts** - Reusable prompt templates
- **Transports** - Communication channels (stdio, SSE, HTTP)

## 📡 Transport Layer Architecture

### stdio Transport
```
┌─────────────┐    stdin/stdout    ┌─────────────┐
│ AI Client   │◄─────────────────►│ MCP Server  │
│ (Claude)    │                   │ (weather.py)│
└─────────────┘                   └─────────────┘
```
**Use Case**: Desktop integration (Claude Desktop, etc.)
**Benefits**: Simple, direct connection
**Limitations**: Single client, local only

### SSE (Server-Sent Events) Transport
```
┌─────────────┐    HTTP/SSE    ┌─────────────┐
│ Web Client  │◄──────────────►│ MCP Server  │
│ (Browser)   │                │ (Uvicorn)   │
└─────────────┘                └─────────────┘
```
**Use Case**: Web applications, real-time updates
**Benefits**: HTTP-compatible, firewall-friendly
**Limitations**: One-way streaming, connection overhead

### StreamableHTTP Transport
```
┌─────────────┐    HTTP/JSON    ┌─────────────┐
│ Web Service │◄───────────────►│ MCP Server  │
│ (FastAPI)   │                │ (Uvicorn)   │
└─────────────┘                └─────────────┘
```
**Use Case**: Production web services, microservices
**Benefits**: Standard HTTP, load balancer compatible
**Limitations**: Request/response pattern (no streaming)

## 🔧 Tool Implementation Patterns

### Basic Tool Pattern

```python
@mcp.tool()
async def simple_tool(param: str) -> str:
    """Tool description for AI model."""
    # Input validation
    if not param:
        return "Error: Parameter required"
    
    # Processing logic
    result = process_data(param)
    
    # Formatted output
    return f"Result: {result}"
```

### Advanced Tool with Error Handling

```python
@mcp.tool()
async def robust_tool(latitude: float, longitude: float) -> str:
    """Get weather data with comprehensive error handling."""
    
    # Input validation
    if not (-90 <= latitude <= 90):
        return f"Error: Latitude must be between -90 and 90. Got: {latitude}"
    
    if not (-180 <= longitude <= 180):
        return f"Error: Longitude must be between -180 and 180. Got: {longitude}"
    
    try:
        # External API call with timeout
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.weather.gov/points/{latitude},{longitude}",
                headers={"User-Agent": "weather-app/1.0"},
                timeout=30.0
            )
            response.raise_for_status()
            
            data = response.json()
            return format_weather_data(data)
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e}")
        return f"Weather service temporarily unavailable (HTTP {e.response.status_code})"
        
    except httpx.TimeoutException:
        logger.error("Request timeout")
        return "Request timed out. Please try again."
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "An unexpected error occurred. Please try again."
```

## 📚 Resource Implementation Patterns

### Static Information Resource

```python
@mcp.resource("weather://service/info")
def get_service_info() -> str:
    """Provide static service information."""
    return """Weather MCP Server Information
    
Available Tools:
- get_alerts(state): Active weather alerts
- get_forecast(lat, lon): Weather forecast
- get_conditions(lat, lon): Current conditions

Data Source: National Weather Service API
Coverage: United States and territories
"""
```

### Dynamic Data Resource

```python
@mcp.resource("weather://cache/stats")
async def get_cache_stats() -> str:
    """Provide dynamic cache statistics."""
    stats = await get_redis_stats()
    return f"""Cache Statistics
    
Hit Rate: {stats.hit_rate:.2%}
Total Requests: {stats.total_requests:,}
Cache Size: {stats.size_mb:.1f} MB
Last Updated: {stats.last_updated}
"""
```

## 🌐 Web Service Integration Patterns

### Persistent MCP Client Pattern

```python
class MCPWebClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()  # Manage async resources
        
    async def connect_to_server(self):
        """Establish persistent connection for web service lifecycle."""
        try:
            # Create transport
            transport = await self.exit_stack.enter_async_context(
                sse_client(url=self.server_url, timeout=60)
            )
            self.read, self.write = transport
            
            # Create session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read, self.write)
            )
            
            await self.session.initialize()
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise
            
    async def cleanup(self):
        """Properly cleanup all resources."""
        await self.exit_stack.aclose()
```

### Session Management Pattern

```python
class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, List[Dict[str, Any]]] = {}
        
    def create_session(self, session_id: str) -> None:
        """Create new conversation session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
            
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add message to session history."""
        self.create_session(session_id)
        self.sessions[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for session."""
        return self.sessions.get(session_id, [])
        
    def clear_session(self, session_id: str) -> bool:
        """Clear session history."""
        if session_id in self.sessions:
            self.sessions[session_id] = []
            return True
        return False
```

## 🤖 AI Integration Patterns

### Tool Calling with Azure OpenAI

```python
async def process_with_tools(self, query: str, session_id: str = None) -> str:
    """Process query with intelligent tool selection."""
    
    # Get conversation context
    history = self.get_session_history(session_id) if session_id else []
    history.append({"role": "user", "content": query})
    
    # Get available tools from MCP server
    tools_response = await self.session.list_tools()
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools_response.tools
    ]
    
    # Initial completion with tools
    response = self.openai_client.chat.completions.create(
        messages=history,
        tools=openai_tools,
        temperature=0.7,
        model=self.deployment_name
    )
    
    message = response.choices[0].message
    
    # Handle tool calls
    if message.tool_calls:
        # Add assistant message with tool calls
        history.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [tc.model_dump() for tc in message.tool_calls]
        })
        
        # Execute each tool call
        for tool_call in message.tool_calls:
            try:
                # Parse arguments
                args = json.loads(tool_call.function.arguments)
                
                # Call MCP tool
                result = await self.session.call_tool(
                    tool_call.function.name, 
                    args
                )
                
                # Extract result text
                result_text = self.extract_result_text(result)
                
                # Add tool result to history
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text
                })
                
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Error: {str(e)}"
                })
        
        # Get final response with tool results
        final_response = self.openai_client.chat.completions.create(
            messages=history,
            tools=openai_tools,
            temperature=0.7,
            model=self.deployment_name
        )
        
        final_content = final_response.choices[0].message.content
        history.append({"role": "assistant", "content": final_content})
        
        return final_content
    
    else:
        # No tool calls needed
        history.append({"role": "assistant", "content": message.content})
        return message.content
```

## 🐳 Deployment Architecture Patterns

### Multi-Stage Docker Pattern

```dockerfile
# Build stage
FROM python:3.12-slim as builder

WORKDIR /app
RUN pip install uv

# Copy dependencies
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -e .

# Runtime stage
FROM python:3.12-slim as runtime

WORKDIR /app

# Copy from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY . .

# Non-root user
RUN useradd --create-home app && chown -R app:app /app
USER app

CMD ["python", "weather.py", "sse"]
```

### Container Orchestration Pattern

```yaml
# Production docker-compose.yml
version: '3.8'

services:
  mcp-server:
    build: ./server
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    networks:
      - mcp-network

  mcp-client:
    build: ./web_client
    ports:
      - "8080:8080"
    environment:
      - MCP_SERVER_URL=http://mcp-server:8000/sse
    env_file:
      - .env
    depends_on:
      mcp-server:
        condition: service_healthy
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    networks:
      - mcp-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - mcp-client
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
```

## 📊 Monitoring and Observability Patterns

### Health Check Pattern

```python
@app.get("/health")
async def comprehensive_health_check():
    """Multi-layer health check."""
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Check MCP connection
    try:
        await mcp_client.session.list_tools()
        health_data["checks"]["mcp_server"] = "healthy"
    except Exception as e:
        health_data["checks"]["mcp_server"] = f"unhealthy: {e}"
        health_data["status"] = "unhealthy"
    
    # Check Azure OpenAI
    try:
        test_response = await openai_client.chat.completions.create(
            messages=[{"role": "user", "content": "test"}],
            model=deployment_name,
            max_tokens=1
        )
        health_data["checks"]["azure_openai"] = "healthy"
    except Exception as e:
        health_data["checks"]["azure_openai"] = f"unhealthy: {e}"
        health_data["status"] = "degraded"
    
    # Check external API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.weather.gov/")
            if response.status_code == 200:
                health_data["checks"]["weather_api"] = "healthy"
            else:
                health_data["checks"]["weather_api"] = f"unhealthy: HTTP {response.status_code}"
    except Exception as e:
        health_data["checks"]["weather_api"] = f"unhealthy: {e}"
    
    return health_data
```

### Structured Logging Pattern

```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info("Processing request", 
           user_id="user123", 
           tool_name="get_forecast", 
           latitude=37.7749, 
           longitude=-122.4194)
```

## 🔐 Security Patterns

### Input Validation Pattern

```python
from pydantic import BaseModel, Field, validator

class WeatherRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    
    @validator('latitude')
    def validate_latitude(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError('Latitude must be a number')
        return v
    
    @validator('longitude')
    def validate_longitude(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError('Longitude must be a number')
        return v

class StateAlertRequest(BaseModel):
    state: str = Field(..., min_length=2, max_length=2, description="Two-letter US state code")
    
    @validator('state')
    def validate_state(cls, v):
        if not v.isalpha():
            raise ValueError('State code must contain only letters')
        return v.upper()
```

### Rate Limiting Pattern

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/chat")
@limiter.limit("10/minute")  # 10 requests per minute
async def chat(request: Request, chat_request: ChatRequest):
    """Rate-limited chat endpoint."""
    # ... implementation
```

This architecture document provides the foundation for building robust, scalable MCP implementations. Each pattern addresses specific challenges in production deployments while maintaining clean, maintainable code.
