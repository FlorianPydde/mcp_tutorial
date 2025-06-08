import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp_client import MCPWebClient
from models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    SessionStatsResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MCP client instance
mcp_client: Optional[MCPWebClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    global mcp_client
    
    # Startup
    logger.info("Starting MCP Web Client application")
    try:
        mcp_client = MCPWebClient()
        await mcp_client.connect_to_server()
        logger.info("Successfully connected to MCP server")
    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {e}")
        # Continue startup even if MCP connection fails
        # Health endpoint will reflect the connection status
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP Web Client application")
    if mcp_client:
        await mcp_client.cleanup()


# Create FastAPI application
app = FastAPI(
    title="MCP Web Client",
    description="Web service client for MCP weather tutorial",
    version="0.1.0",
    lifespan=lifespan
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
            error="Internal server error",
            detail=str(exc)
        ).model_dump()
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        if mcp_client is None:
            return HealthResponse(
                status="unhealthy",
                mcp_connected=False,
                error="MCP client not initialized"
            )
        
        health_status = await mcp_client.health_check()
        return HealthResponse(**health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            mcp_connected=False,
            error=str(e)
        )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat query without session memory."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available"
            )
        
        response = await mcp_client.process_query(request.query)
        return ChatResponse(response=response)
        
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/chat/session/{session_id}", response_model=ChatResponse)
async def chat_with_session(session_id: str, request: ChatRequest):
    """Process a chat query with session-based conversation memory."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available"
            )
        
        response = await mcp_client.process_query(
            request.query, 
            session_id=session_id
        )
        return ChatResponse(response=response, session_id=session_id)
        
    except Exception as e:
        logger.error(f"Session chat processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available"
            )
        
        cleared = mcp_client.clear_session(session_id)
        if cleared:
            return {"message": f"Session {session_id} cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session clearing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/chat/session/{session_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(session_id: str):
    """Get conversation statistics for a session."""
    try:
        if mcp_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MCP client not available"
            )
        
        stats = mcp_client.get_session_stats(session_id)
        return SessionStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Session stats retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "MCP Web Client",
        "version": "0.1.0",
        "description": "Web service client for MCP weather tutorial",
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "session_chat": "/chat/session/{session_id}",
            "clear_session": "/chat/session/{session_id}",
            "session_stats": "/chat/session/{session_id}/stats"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
