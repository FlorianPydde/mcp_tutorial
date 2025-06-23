"""
MCP Web Client using MCP Gateway for centralized tool access.
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

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
from openai import AsyncAzureOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MCP client instance
mcp_client: Optional[MCPGatewayClient] = None
startup_error: Optional[str] = None

# Azure OpenAI client
azure_client: Optional[AsyncAzureOpenAI] = None

# Session storage (in production, use Redis or database)
chat_sessions: Dict[str, List[Dict[str, str]]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    global mcp_client, startup_error, azure_client

    # Startup
    logger.info("Starting MCP Web Client application (Gateway mode)")
    try:
        # Get gateway URL from environment or use default
        gateway_url = os.getenv("MCP_GATEWAY_URL", "http://mcp-gateway:8080")
        mcp_client = MCPGatewayClient(gateway_url)
        await mcp_client.connect()
        logger.info("Successfully connected to MCP Gateway")

        # Initialize Azure OpenAI client
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")

        if api_key and azure_endpoint:
            azure_client = AsyncAzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=azure_endpoint,
            )
            logger.info("Azure OpenAI client initialized successfully")
        else:
            logger.warning(
                "Azure OpenAI credentials not found. Chat functionality will be limited."
            )

        startup_error = None
    except Exception as e:
        error_msg = f"Failed to connect to MCP Gateway: {str(e)}"
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
            "/chat": "Chat with Azure OpenAI using MCP tools",
            "/chat/session/{session_id}": "Chat in a specific session",
            "/sessions/{session_id}/stats": "Get session statistics",
            "/sessions": "List all active sessions",
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
        available_tools=len(await mcp_client.get_tools())
        if mcp_client.connected
        else None,
        active_sessions=len(chat_sessions),
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
        tool_name = request.get("tool_name")
        arguments = request.get("arguments", {})

        if not tool_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tool_name is required",
            )

        result = await mcp_client.call_tool(tool_name, arguments)
        return result

    except Exception as e:
        logger.error(f"Error calling tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to call tool: {str(e)}",
        )


async def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get existing session or create new one."""
    if session_id and session_id in chat_sessions:
        return session_id

    new_session_id = session_id or str(uuid.uuid4())
    chat_sessions[new_session_id] = []
    return new_session_id


async def call_azure_openai_with_tools(messages: List[dict], session_id: str) -> str:
    """Call Azure OpenAI with available MCP tools."""
    if not azure_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI client not available. Please configure AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.",
        )

    if not mcp_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP client not initialized",
        )

    # Get available tools
    tools = await mcp_client.get_tools()  # Convert MCP tools to OpenAI function format
    openai_tools = []
    for tool in tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool[
                        "name"
                    ],  # Use tool name directly, gateway handles routing
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
        )

    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    # Call Azure OpenAI
    response = await azure_client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        tools=openai_tools if openai_tools else None,
        tool_choice="auto" if openai_tools else None,
        temperature=0.7,
        max_tokens=1000,
    )

    assistant_message = response.choices[0].message

    # Handle tool calls
    if assistant_message.tool_calls:
        # Add assistant message with tool calls to conversation
        chat_sessions[session_id].append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in assistant_message.tool_calls
                ],
            }
        )  # Execute tool calls
        for tool_call in assistant_message.tool_calls:
            try:
                # Tool name (gateway handles server routing automatically)
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                # Call the tool through gateway
                tool_result = await mcp_client.call_tool(tool_name, arguments)

                # Add tool result to conversation
                tool_content = ""
                if isinstance(tool_result, dict) and "content" in tool_result:
                    if isinstance(tool_result["content"], list):
                        tool_content = "\n".join(
                            [
                                item.get("text", str(item))
                                for item in tool_result["content"]
                                if isinstance(item, dict)
                            ]
                        )
                    else:
                        tool_content = str(tool_result["content"])
                else:
                    tool_content = str(tool_result)

                chat_sessions[session_id].append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_content,
                    }
                )

            except Exception as e:
                logger.error(f"Error executing tool {tool_call.function.name}: {e}")
                chat_sessions[session_id].append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Error executing tool: {str(e)}",
                    }
                )

        # Get final response from OpenAI with tool results
        final_response = await azure_client.chat.completions.create(
            model=deployment_name,
            messages=chat_sessions[session_id],
            temperature=0.7,
            max_tokens=1000,
        )

        final_content = final_response.choices[0].message.content
        chat_sessions[session_id].append(
            {"role": "assistant", "content": final_content}
        )

        return final_content
    else:
        # No tool calls, just return the response
        chat_sessions[session_id].append(
            {"role": "assistant", "content": assistant_message.content}
        )
        return assistant_message.content


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint without session."""
    session_id = await get_or_create_session()

    # Add user message to session
    chat_sessions[session_id].append({"role": "user", "content": request.query})

    try:
        response = await call_azure_openai_with_tools(
            chat_sessions[session_id], session_id
        )

        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}",
        )


@app.post("/chat/session/{session_id}", response_model=ChatResponse)
async def chat_with_session(session_id: str, request: ChatRequest):
    """Chat endpoint with specific session."""
    session_id = await get_or_create_session(session_id)

    # Add user message to session
    chat_sessions[session_id].append({"role": "user", "content": request.query})

    try:
        response = await call_azure_openai_with_tools(
            chat_sessions[session_id], session_id
        )

        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        logger.error(f"Error in chat with session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}",
        )


@app.get("/sessions/{session_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(session_id: str):
    """Get statistics for a specific session."""
    if session_id not in chat_sessions:
        return SessionStatsResponse(exists=False)

    messages = chat_sessions[session_id]
    user_messages = sum(1 for msg in messages if msg["role"] == "user")
    assistant_messages = sum(1 for msg in messages if msg["role"] == "assistant")
    tool_calls = sum(1 for msg in messages if msg["role"] == "tool")

    return SessionStatsResponse(
        exists=True,
        message_count=len(messages),
        user_messages=user_messages,
        assistant_messages=assistant_messages,
        tool_calls=tool_calls,
    )


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {"sessions": list(chat_sessions.keys()), "total": len(chat_sessions)}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session."""
    if session_id in chat_sessions:
        del chat_sessions[session_id]
        return {"message": f"Session {session_id} deleted"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "3000"))

    logger.info(f"Starting MCP Web Client on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
