"""Agent event emission and persistence."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AgentEvent
from backend.agent_runtime.state import AGENT_EVENT_TYPES, AgentStage


async def emit_event(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    stage: AgentStage,
    event_type: str,
    payload: Dict[str, Any],
) -> AgentEvent:
    """Emit and persist an agent event."""
    event = AgentEvent(
        run_id=run_id,
        order_id=order_id,
        agent_stage=stage.value,
        event_type=event_type,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    await session.flush()
    return event


async def emit_stage_started(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    stage: AgentStage,
    input_summary: Dict[str, Any],
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        stage,
        AGENT_EVENT_TYPES["stage_started"],
        {"input": input_summary},
    )


async def emit_stage_completed(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    stage: AgentStage,
    output_summary: Dict[str, Any],
    latency_ms: int,
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        stage,
        AGENT_EVENT_TYPES["stage_completed"],
        {"output": output_summary, "latency_ms": latency_ms},
    )


async def emit_tool_called(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    stage: AgentStage,
    tool_name: str,
    tool_input: Dict[str, Any],
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        stage,
        AGENT_EVENT_TYPES["tool_called"],
        {"tool": tool_name, "input": tool_input},
    )


async def emit_tool_completed(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    stage: AgentStage,
    tool_name: str,
    tool_output: Dict[str, Any],
    latency_ms: int,
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        stage,
        AGENT_EVENT_TYPES["tool_completed"],
        {"tool": tool_name, "output": tool_output, "latency_ms": latency_ms},
    )


async def emit_policy_rejected(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    action: str,
    reason: str,
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        AgentStage.SAFETY_CHECK,
        AGENT_EVENT_TYPES["policy_rejected"],
        {"action": action, "reason": reason},
    )


async def emit_plan_created(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    plan: Dict[str, Any],
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        AgentStage.PLANNING,
        AGENT_EVENT_TYPES["plan_created"],
        {"plan": plan},
    )


async def emit_action_executed(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    action: str,
    result: Dict[str, Any],
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        AgentStage.EXECUTING,
        AGENT_EVENT_TYPES["action_executed"],
        {"action": action, "result": result},
    )


async def emit_replan_started(
    session: AsyncSession,
    run_id: str,
    order_id: str,
    reason: str,
) -> AgentEvent:
    return await emit_event(
        session,
        run_id,
        order_id,
        AgentStage.REPLANNING,
        AGENT_EVENT_TYPES["replan_started"],
        {"reason": reason},
    )