"""MCP activity tracking for live dashboard."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from contextvars import ContextVar


@dataclass
class MCPActivity:
    timestamp: str
    tool: str
    duration_ms: int
    status: str
    order_id: Optional[str] = None
    error: Optional[str] = None


_activity_log: List[MCPActivity] = []
_max_log_size = 100
_subscribers: List[asyncio.Queue] = []


def log_mcp_activity(
    tool: str,
    duration_ms: int,
    status: str,
    order_id: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Log an MCP tool call."""
    activity = MCPActivity(
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool=tool,
        duration_ms=duration_ms,
        status=status,
        order_id=order_id,
        error=error,
    )
    _activity_log.append(activity)
    if len(_activity_log) > _max_log_size:
        _activity_log.pop(0)
    
    # Notify subscribers
    for queue in _subscribers:
        try:
            queue.put_nowait(activity)
        except asyncio.QueueFull:
            pass


def get_recent_activity(limit: int = 50) -> List[MCPActivity]:
    """Get recent MCP activity."""
    return _activity_log[-limit:]


async def activity_stream():
    """Async generator for SSE streaming of MCP activity."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)
    
    # Send initial recent activity
    for activity in get_recent_activity(20):
        yield activity
    
    try:
        while True:
            activity = await queue.get()
            yield activity
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)


class MCPActivityTracker:
    """Context manager for tracking MCP tool calls."""
    
    def __init__(self, tool_name: str, order_id: Optional[str] = None):
        self.tool_name = tool_name
        self.order_id = order_id
        self.start_time = 0
    
    async def __aenter__(self):
        self.start_time = time.perf_counter()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.perf_counter() - self.start_time) * 1000)
        if exc_type is not None:
            log_mcp_activity(self.tool_name, duration_ms, "ERROR", self.order_id, str(exc_val))
        else:
            log_mcp_activity(self.tool_name, duration_ms, "OK", self.order_id)
        return False