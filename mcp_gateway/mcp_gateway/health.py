"""
Health monitoring for MCP servers
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import MCPServerConfig, settings

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ServerHealth:
    """Server health information."""

    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        self.status = HealthStatus.UNKNOWN
        self.last_check: Optional[datetime] = None
        self.last_healthy: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.response_time: Optional[float] = None
        self.consecutive_failures = 0

    def update_healthy(self, response_time: float) -> None:
        """Update health status to healthy."""
        self.status = HealthStatus.HEALTHY
        self.last_check = datetime.utcnow()
        self.last_healthy = datetime.utcnow()
        self.response_time = response_time
        self.error_message = None
        self.consecutive_failures = 0

    def update_unhealthy(self, error_message: str) -> None:
        """Update health status to unhealthy."""
        self.status = HealthStatus.UNHEALTHY
        self.last_check = datetime.utcnow()
        self.error_message = error_message
        self.consecutive_failures += 1

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "server_name": self.server_name,
            "status": self.status.value,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_healthy": self.last_healthy.isoformat()
            if self.last_healthy
            else None,
            "error_message": self.error_message,
            "response_time": self.response_time,
            "consecutive_failures": self.consecutive_failures,
        }


class HealthMonitor:
    """Health monitoring service for MCP servers."""

    def __init__(self) -> None:
        self.server_health: Dict[str, ServerHealth] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self.http_client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        """Start health monitoring."""
        logger.info("Starting health monitoring service")

        # Initialize health objects for all configured servers
        for server_name in settings.mcp_servers:
            self.server_health[server_name] = ServerHealth(server_name)

        # Create HTTP client for health checks
        self.http_client = httpx.AsyncClient(
            timeout=settings.health_timeout, follow_redirects=True
        )

        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self) -> None:
        """Stop health monitoring."""
        logger.info("Stopping health monitoring service")

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        if self.http_client:
            await self.http_client.aclose()

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while True:
            try:
                await self._check_all_servers()
                await asyncio.sleep(settings.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying

    async def _check_all_servers(self) -> None:
        """Check health of all configured servers."""
        tasks = []
        for server_name, config in settings.mcp_servers.items():
            if config.enabled:
                task = asyncio.create_task(
                    self._check_server_health(server_name, config)
                )
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_server_health(
        self, server_name: str, config: MCPServerConfig    ) -> None:
        """Check health of a single server."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # First try HTTP health endpoint
            success = await self._check_http_health(config)

            if success:
                # If HTTP health check passes, try MCP protocol check
                success = await self._check_mcp_health(config)

            if success:
                response_time = asyncio.get_event_loop().time() - start_time
                self.server_health[server_name].update_healthy(response_time)
                logger.debug(f"Server {server_name} is healthy")
            else:
                self.server_health[server_name].update_unhealthy("Health check failed")
        except Exception as e:
            error_msg = f"Health check error: {str(e)}"
            self.server_health[server_name].update_unhealthy(error_msg)
            logger.warning(f"Health check failed for {server_name}: {error_msg}")

    async def _check_http_health(self, config: MCPServerConfig) -> bool:
        """Check HTTP health endpoint."""
        if not self.http_client:
            return False

        try:
            url = f"http://{config.host}:{config.port}{config.health_endpoint}"
            response = await self.http_client.get(url)
            return response.status_code in [200, 406]  # 406 is OK for MCP streamable endpoints
        except Exception as e:
            logger.debug(f"HTTP health check failed for {config.name}: {e}")
            return False

    async def _check_mcp_health(self, config: MCPServerConfig) -> bool:
        """Check MCP protocol health."""
        try:
            # For now, we'll do a simple connection test
            # In a real implementation, you might want to send a capabilities
            # request or list tools
            url = f"http://{config.host}:{config.port}{config.mcp_endpoint}"

            if not self.http_client:
                return False            # Try to connect to MCP endpoint
            response = await self.http_client.get(url)
            return response.status_code in [200, 404, 406]  # 406 is OK for MCP streamable endpoints
        except Exception as e:
            logger.debug(f"MCP health check failed for {config.name}: {e}")
            return False

    def get_server_health(self, server_name: str) -> Optional[ServerHealth]:
        """Get health status for a specific server."""
        return self.server_health.get(server_name)

    def get_all_health(self) -> Dict[str, Dict]:
        """Get health status for all servers."""
        return {name: health.to_dict() for name, health in self.server_health.items()}

    def is_server_healthy(self, server_name: str) -> bool:
        """Check if a server is healthy."""
        health = self.get_server_health(server_name)
        return health is not None and health.status == HealthStatus.HEALTHY

    def get_healthy_servers(self) -> List[str]:
        """Get list of healthy server names."""
        return [
            name
            for name, health in self.server_health.items()
            if health.status == HealthStatus.HEALTHY
        ]
