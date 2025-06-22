"""
Simplified MCP Web Client using direct MCP protocol connections.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp_client import DirectMCPClient
from models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MCP client instance
mcp_client: Optional[DirectMCPClient] = None
startup_error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    global mcp_client, startup_error

    # Startup
    logger.info("Starting MCP Web Client application (Direct MCP mode)")
    try:
        mcp_client = DirectMCPClient()
        await mcp_client.connect()
        logger.info("Successfully connected to MCP servers")
        startup_error = None
    except Exception as e:
        error_msg = f"Failed to connect to MCP servers: {str(e)}"
        logger.error(error_msg)
        startup_error = error_msg
        mcp_client = None

    yield

    # Shutdown
    logger.info("Shutting down MCP Web Client application")
    if mcp_client:
        await mcp_client.disconnect()


# Initialize FastAPI application
app = FastAPI(
    title="MCP Web Client",
    description="Web interface for Model Context Protocol servers",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            details=str(exc),
        ).model_dump(),
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "MCP Web Client",
        "version": "1.0.0",
        "description": "Web interface for Model Context Protocol servers",
        "endpoints": {
            "/health": "Health check endpoint",
            "/config": "Server configuration information",
            "/tools": "List all available MCP tools",
            "/tools/call": "Call a specific MCP tool",
        },
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if startup_error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unavailable: {startup_error}",
        )

    if not mcp_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP client not initialized",
        )

    return HealthResponse(
        status="healthy",
        mcp_connected=mcp_client.connected,
        message="MCP Web Client is running",
    )


@app.get("/config")
async def get_config():
    """Get server configuration."""
    if not mcp_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP client not initialized",
        )

    return mcp_client.get_server_info()


@app.get("/tools")
async def get_tools():
    """Get all available tools from MCP servers."""
    if not mcp_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP client not initialized",
        )

    try:
        tools = await mcp_client.get_tools()
        return {
            "tools": tools,
            "total": len(tools),
        }
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tools: {str(e)}",
        )


@app.post("/tools/call")
async def call_tool(request: dict):
    """Call a specific tool."""
    if not mcp_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP client not initialized",
        )

    try:
        server_name = request.get("server_name")
        tool_name = request.get("tool_name")
        arguments = request.get("arguments", {})

        if not server_name or not tool_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="server_name and tool_name are required",
            )

        result = await mcp_client.call_tool(server_name, tool_name, arguments)
        return result

    except Exception as e:
        logger.error(f"Error calling tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to call tool: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))

    logger.info(f"Starting MCP Web Client on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
