from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoints."""
    
    query: str = Field(
        ..., 
        description="User query to process",
        min_length=1,
        max_length=1000
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""
    
    response: str = Field(
        ...,
        description="Processed response from the MCP client"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID if session-based chat was used"
    )


class SessionStatsResponse(BaseModel):
    """Response model for session statistics."""
    
    exists: bool = Field(
        ...,
        description="Whether the session exists"
    )
    message_count: Optional[int] = Field(
        None,
        description="Total number of messages in the session"
    )
    user_messages: Optional[int] = Field(
        None,
        description="Number of user messages"
    )
    assistant_messages: Optional[int] = Field(
        None,
        description="Number of assistant messages"
    )
    tool_calls: Optional[int] = Field(
        None,
        description="Number of tool call messages"
    )


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(
        ...,
        description="Health status: 'healthy' or 'unhealthy'"
    )
    mcp_connected: bool = Field(
        ...,
        description="Whether connected to MCP server"
    )
    server_url: Optional[str] = Field(
        None,
        description="MCP server URL"
    )
    available_tools: Optional[int] = Field(
        None,
        description="Number of available tools"
    )
    active_sessions: Optional[int] = Field(
        None,
        description="Number of active conversation sessions"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if unhealthy"
    )


class ErrorResponse(BaseModel):
    """Response model for errors."""
    
    error: str = Field(
        ...,
        description="Error message"
    )
    detail: Optional[str] = Field(
        None,
        description="Additional error details"
    )
