# Multi-stage build for better caching and smaller final image
FROM python:3.12-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies in one layer
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Create non-root user early
RUN useradd --create-home --shell /bin/bash --uid 1000 app

# Dependency installation stage
FROM base AS deps

# Copy only dependency files for better caching
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev


# Copy only necessary application files (no COPY . .)
COPY main.py ./
COPY mcp_client.py ./
COPY mcp_gateway_client.py ./
COPY models.py ./

# Set proper ownership
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
