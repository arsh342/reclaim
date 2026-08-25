"""SSE event streaming for agent runs."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session_dependency
from backend.db.models import AgentEvent


router = APIRouter()


async def event_stream_generator(run_id: str, session: AsyncSession):
    """Generate SSE events for an agent run."""
    last_seq = 0
    
    while True:
        stmt = select(AgentEvent).where(
            AgentEvent.run_id == run_id,
            AgentEvent.event_seq > last_seq
        ).order_by(AgentEvent.event_seq)
        result = await session.execute(stmt)
        events = result.scalars().all()
        
        for event in events:
            last_seq = event.event_seq
            yield f"data: {event.payload}\n\n"
        
        # Check if run is completed
        from backend.db.models import AgentRun
        run = await session.get(AgentRun, run_id)
        if run and run.status in ("completed", "failed"):
            break
        
        import asyncio
        await asyncio.sleep(0.5)


@router.get("/agent-runs/{run_id}/events")
async def stream_agent_events(
    run_id: str,
    session: AsyncSession = Depends(get_session_dependency),
):
    """Stream agent events via SSE."""
    return StreamingResponse(
        event_stream_generator(run_id, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )