# Project Configuration & Best Practices

## Development Environment Setup

### Prerequisites
```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Docker and Docker Compose
# Follow official Docker installation guide for your OS
```

### Project Setup
```bash
# Clone and setup
git clone <repository-url>
cd mcp_tutorial

# Setup each component
cd server && uv sync && cd ..
cd web_client && uv sync && cd ..
cd client && uv sync && cd ..

# Copy environment templates
cp web_client/.env.example web_client/.env
# Edit .env with your Azure OpenAI credentials
```

## Dependency Management Best Practices

### Using uv for Package Management
```bash
# Add new dependency
uv add package-name

# Add development dependency
uv add --dev pytest

# Update dependencies
uv sync --upgrade

# Lock dependencies
uv lock

# Install from lock file
uv sync --frozen
```

### Recommended Development Dependencies
```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
    "pre-commit>=3.5.0",
]
```

## Code Quality Standards

### Pre-commit Configuration
Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

### Ruff Configuration
Add to each `pyproject.toml`:
```toml
[tool.ruff]
line-length = 82
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## Testing Strategy

### Test Organization
```
tests/
├── unit/
│   ├── test_mcp_client.py
│   ├── test_models.py
│   └── test_weather_server.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_mcp_integration.py
└── conftest.py
```

### Pytest Configuration
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = [
    "--cov=src",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--strict-markers",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow running tests",
]
```

### Test Examples
```python
# tests/unit/test_mcp_client.py
import pytest
from unittest.mock import AsyncMock, patch
from mcp_client import MCPWebClient

@pytest.fixture
async def mcp_client():
    """Create test MCP client."""
    with patch.dict('os.environ', {
        'AZURE_OPENAI_API_BASE': 'https://test.openai.azure.com/',
        'AZURE_OPENAI_API_KEY': 'test-key',
        'AZURE_OPENAI_API_VERSION': '2024-02-15-preview',
        'AZURE_OPENAI_DEPLOYMENT_NAME': 'test-deployment',
    }):
        client = MCPWebClient()
        yield client

@pytest.mark.asyncio
async def test_process_query_success(mcp_client):
    """Test successful query processing."""
    with patch.object(mcp_client, 'session') as mock_session:
        mock_session.list_tools.return_value = AsyncMock()
        # Add more test logic
        pass
```

## Docker Best Practices

### Multi-stage Dockerfile Pattern
```dockerfile
# Build stage
FROM python:3.12-slim as builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Production stage
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Security: non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["python", "main.py"]
```

### Docker Compose Development
```yaml
# docker-compose.override.yml (auto-loaded in dev)
version: '3.8'

services:
  mcp-weather-server:
    volumes:
      - ./server:/app
    environment:
      - LOG_LEVEL=DEBUG
    
  mcp-web-client:
    volumes:
      - ./web_client:/app
    environment:
      - LOG_LEVEL=DEBUG
      - RELOAD=true
```

## Security Hardening

### Environment Variable Management
```bash
# Production: Use Azure Key Vault
az keyvault secret set \
  --vault-name mcp-tutorial-kv \
  --name "azure-openai-key" \
  --value "actual-key"

# Development: Use .env files (gitignored)
echo "AZURE_OPENAI_API_KEY=dev-key" >> .env
```

### Input Validation
```python
from pydantic import BaseModel, Field, validator

class ChatRequest(BaseModel):
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="User query"
    )
    
    @validator('query')
    def validate_query(cls, v):
        # Additional validation logic
        if not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()
```

### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    # Implementation
    pass
```

## Monitoring & Observability

### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# In your code
logger.info(
    "Processing query",
    session_id=session_id,
    query_length=len(query),
    user_id=user_id
)
```

### Health Check Implementation
```python
@app.get("/health")
async def health_check():
    """Comprehensive health check."""
    checks = {
        "database": await check_database(),
        "mcp_server": await check_mcp_connection(),
        "azure_openai": await check_azure_openai(),
    }
    
    healthy = all(checks.values())
    status_code = 200 if healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

### Metrics Collection
```python
from prometheus_client import Counter, Histogram

request_count = Counter('requests_total', 'Total requests')
request_duration = Histogram('request_duration_seconds', 'Request duration')

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    request_count.inc()
    request_duration.observe(duration)
    
    return response
```

## CI/CD Pipeline

### GitHub Actions Workflow
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
          
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
        
      - name: Install dependencies
        run: uv sync
        
      - name: Run tests
        run: uv run pytest --cov
        
      - name: Run linting
        run: uv run ruff check .
        
      - name: Run type checking
        run: uv run mypy .

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build Docker images
        run: |
          docker build -t mcp-server ./server
          docker build -t mcp-web-client ./web_client
```

## Performance Optimization

### Connection Pooling
```python
# In mcp_client.py
import httpx

class MCPWebClient:
    def __init__(self):
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20
            )
        )
```

### Caching Strategy
```python
from functools import lru_cache
from typing import Dict, Any
import asyncio

class WeatherCache:
    def __init__(self, ttl: int = 300):  # 5 minutes
        self.cache: Dict[str, Any] = {}
        self.ttl = ttl
    
    async def get_or_fetch(self, key: str, fetch_func):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
        
        data = await fetch_func()
        self.cache[key] = (data, time.time())
        return data
```

## Production Deployment Checklist

### Pre-deployment
- [ ] All tests passing
- [ ] Security scan completed
- [ ] Performance testing done
- [ ] Documentation updated
- [ ] Environment variables configured
- [ ] Monitoring setup complete

### Deployment
- [ ] Blue-green deployment strategy
- [ ] Database migrations applied
- [ ] Health checks passing
- [ ] Rollback plan ready

### Post-deployment
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Verify functionality
- [ ] Update status page

This configuration guide ensures your MCP tutorial project follows industry best practices for maintainability, security, and scalability.
