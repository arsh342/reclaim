"""MCP server adapters - delegates to Reclaim domain services."""

from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from backend.tools.registry import tool_registry
from backend.agent_runtime.orchestrator import run_agent
from backend.db.models import AgentRun, AgentEvent
from sqlalchemy import select
from backend.evaluator.runner import run_evaluation


async def get_order_context_adapter(order_id: str, session: AsyncSession) -> Dict[str, Any]:
    return await tool_registry.call("get_order_context", order_id=order_id, session=session)


async def get_allowed_actions_adapter(order_id: str, session: AsyncSession) -> List[str]:
    return await tool_registry.call("get_allowed_actions", order_id=order_id, session=session)


async def estimate_recovery_adapter(order_id: str, action: str, session: AsyncSession) -> Dict[str, Any]:
    return await tool_registry.call("estimate_recovery", order_id=order_id, action=action, session=session)


async def execute_recovery_action_adapter(order_id: str, action: str, session: AsyncSession) -> Dict[str, Any]:
    return await tool_registry.call("execute_recovery_action", order_id=order_id, action=action, session=session)


async def cancel_pending_action_adapter(order_id: str, session: AsyncSession) -> Dict[str, Any]:
    return await tool_registry.call("cancel_pending_action", order_id=order_id, session=session)


async def start_recovery_run_adapter(order_id: str, session: AsyncSession) -> Dict[str, Any]:
    state = await run_agent(session, order_id)
    return {
        "run_id": state.run_id,
        "order_id": state.order_id,
        "status": state.status,
        "final_action": state.final_action,
        "final_reason": state.final_reason,
    }


async def get_agent_run_adapter(run_id: str, session: AsyncSession) -> Dict[str, Any]:
    run = await session.get(AgentRun, run_id)
    if not run:
        return {"error": "Agent run not found"}
    return {
        "run_id": run.run_id,
        "order_id": run.order_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "final_action": run.final_action,
        "final_reason": run.final_reason,
    }


async def get_agent_events_adapter(run_id: str, session: AsyncSession) -> List[Dict[str, Any]]:
    stmt = select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.event_seq)
    result = await session.execute(stmt)
    events = result.scalars().all()
    return [
        {
            "event_seq": e.event_seq,
            "run_id": e.run_id,
            "order_id": e.order_id,
            "agent_stage": e.agent_stage,
            "event_type": e.event_type,
            "payload": e.payload,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


async def get_evaluation_summary_adapter(session: AsyncSession) -> Dict[str, Any]:
    result = await run_evaluation(session, n_orders=2000, seed=42)
    return {
        "always_retry": result.always_retry.model_dump(),
        "reclaim": result.reclaim.model_dump(),
        "incremental_revenue": result.incremental_revenue,
        "incremental_recovery_rate": result.incremental_recovery_rate,
        "total_orders": result.total_orders,
        "seed": result.seed,
    }