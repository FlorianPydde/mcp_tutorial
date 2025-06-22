FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files and README first (required by pyproject.toml)
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies
RUN uv sync --frozen

# Copy source code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash gateway && \
    chown -R gateway:gateway /app
USER gateway

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the gateway
CMD ["uv", "run", "-m", "mcp_gateway.main"]
