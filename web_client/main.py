import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp_gateway_client import MCPGatewayClient
from models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    SessionStatsResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MCP gateway client instance and startup error tracking
mcp_client: Optional[MCPGatewayClient] = None
startup_error: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    global mcp_client, startup_error  # Startup
    logger.info("Starting MCP Web Client application (Gateway mode)")
    try:
        # Get gateway configuration from environment
        gateway_url = os.getenv("MCP_GATEWAY_URL")

        logger.info("Initializing MCP Gateway client")
        logger.info(f"Target gateway URL: {gateway_url or 'localhost:8080'}")

        mcp_client = MCPGatewayClient(gateway_url=gateway_url)
        await mcp_client.connect()
        logger.info("Successfully connected to MCP Gateway")
        startup_error = None  # Clear any previous errors
    except Exception as e:
        error_msg = f"Failed to initialize/connect to MCP Gateway: {str(e)}"
        logger.error(error_msg)
        startup_error = error_msg
        mcp_client = None
        # Continue startup even if MCP connection fails
        # Health endpoint will reflect the connection status

    yield  # Shutdown
    logger.info("Shutting down MCP Web Client application")
    if mcp_client:
        await mcp_client.disconnect()


# Create FastAPI application
app = FastAPI(
    title="MCP Gateway Web Client",
    description="Web service client for MCP Gateway - Enterprise ready team client",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error", detail=str(exc)
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with detailed startup error information."""
    try:
        if mcp_client is None:
            # Provide detailed information about why the client wasn't initialized
            error_detail = startup_error or "MCP client not initialized"
            logger.warning(f"Health check: MCP client is None - {error_detail}")

            return HealthResponse(
                status="unhealthy",
                mcp_connected=False,
                server_url=os.getenv("MCP_SERVER_URL"),
                error=error_detail,
            )

        # Try to get health status from the MCP client
        health_status = await mcp_client.health_check()
        logger.info(f"Health check result: {health_status}")
        return HealthResponse(**health_status)

    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(error_msg)
        return HealthResponse(
            status="unhealthy",
            mcp_connected=False,
            server_url=os.getenv("MCP_SERVER_URL"),
            error=error_msg,
        )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat query without session memory."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available",
            )

        response = await mcp_client.process_query(request.query)
        return ChatResponse(response=response)

    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post("/chat/session/{session_id}", response_model=ChatResponse)
async def chat_with_session(session_id: str, request: ChatRequest):
    """Process a chat query with session-based conversation memory."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available",
            )

        response = await mcp_client.process_query(request.query, session_id=session_id)
        return ChatResponse(response=response, session_id=session_id)

    except Exception as e:
        logger.error(f"Session chat processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available",
            )

        cleared = mcp_client.clear_session(session_id)
        if cleared:
            return {"message": f"Session {session_id} cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session clearing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/chat/session/{session_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(session_id: str):
    """Get conversation statistics for a session."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available",
            )

        stats = mcp_client.get_session_stats(session_id)
        return SessionStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Session stats retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/tools")
async def list_available_tools():
    """List all available tools from the MCP server."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available",
            )

        tools = await mcp_client.list_tools()
        return {"tools": tools}

    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post("/tools/{tool_name}/call")
async def call_tool_directly(tool_name: str, request: dict = None):
    """Call a specific tool directly with arguments."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available",
            )

        # Extract arguments from request body, default to empty dict
        arguments = request or {}

        result = await mcp_client.call_tool(tool_name, arguments)
        return {"tool_name": tool_name, "arguments": arguments, "result": result}

    except Exception as e:
        logger.error(f"Failed to call tool {tool_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "MCP Web Client",
        "version": "0.1.0",
        "description": "Web service client for MCP weather tutorial",
        "transport_type": os.getenv("MCP_TRANSPORT_TYPE", "sse"),
        "endpoints": {
            "health": "/health",
            "config": "/config",
            "chat": "/chat",
            "session_chat": "/chat/session/{session_id}",
            "clear_session": "/chat/session/{session_id}",
            "session_stats": "/chat/session/{session_id}/stats",
            "list_tools": "/tools",
            "call_tool": "/tools/{tool_name}/call",
        },
    }


@app.get("/config")
async def get_configuration():
    """Get current configuration and environment info for debugging."""
    return {
        "mcp_server_url": os.getenv("MCP_SERVER_URL"),
        "mcp_transport_type": os.getenv("MCP_TRANSPORT_TYPE", "sse"),
        "mcp_server_port": os.getenv("MCP_SERVER_PORT", "8000"),
        "azure_openai_configured": bool(os.getenv("AZURE_OPENAI_API_BASE")),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "client_initialized": mcp_client is not None,
        "startup_error": startup_error,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True, log_level="info")
