# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml uv.lock* ./

# Install uv for faster dependency management
RUN pip install uv

# Install project and dependencies using uv pip install
RUN uv pip install --system -e .

# Copy application code
COPY news.py ./

# Expose port (different from weather server)
EXPOSE 8001

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=8001

# Run the MCP server with SSE transport using Python directly
CMD ["python", "news.py", "sse"]
