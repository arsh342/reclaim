"""API routes."""

import asyncio
import time
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from backend.db.session import get_session_dependency
from backend.db.models import (
    Order,
    PaymentAttempt,
    RecoveryAction,
    AgentRun,
    AgentEvent,
    Merchant,
    Customer,
)
from backend.api.schemas import (
    IngestResult,
    OrderSummary,
    OrderDetail,
    PaymentAttemptSchema,
    RecoveryActionSchema,
    AgentRunSchema,
    AgentEventSchema,
    EvalSummary,
    PolicyMetrics,
    HealthResponse,
    SimulateWebhookRequest,
    MCPStatus,
    MCPTool,
    MCPActivity,
    CompleteRecoveryActionRequest,
    CompleteRecoveryActionResponse,
)
from backend.api.webhooks import ingest_webhook
from backend.policy.constraints import get_allowed_actions
from backend.evaluator.runner import run_evaluation
from backend.evaluator.baselines import AlwaysRetryPolicy, ReclaimPolicy
from backend.agent_runtime.orchestrator import run_agent
from backend.mcp_server.activity import get_recent_activity, activity_stream
from backend.executor.executor import complete_recovery_action
from backend.agent_runtime.state import AgentStage
from backend.core.config import settings


router = APIRouter()


# Create a separate engine for background tasks to avoid session conflicts
_bg_db_url = settings.DATABASE_URL
if not _bg_db_url.startswith("sqlite") and _bg_db_url.startswith("postgresql://"):
    _bg_db_url = _bg_db_url.replace("postgresql://", "postgresql+asyncpg://")
_background_engine = create_async_engine(_bg_db_url, pool_pre_ping=True)
_background_session_maker = async_sessionmaker(_background_engine, expire_on_commit=False)


async def run_agent_background(run_id: str, order_id: str):
    """Run agent in background with its own session."""
    async with _background_session_maker() as session:
        from backend.agent_runtime.orchestrator import run_agent
        try:
            await run_agent(session, order_id, run_id=run_id)
            await session.commit()
        except Exception as e:
            # Log error but don't crash background task
            print(f"Background agent run {run_id} failed: {e}")
            await session.rollback()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy")


@router.post("/webhooks/simulate", response_model=IngestResult)
async def simulate_webhook(
    webhook: SimulateWebhookRequest,
    session: AsyncSession = Depends(get_session_dependency),
):
    result = await ingest_webhook(session, webhook)
    return result


@router.get("/orders", response_model=List[OrderSummary])
async def list_orders(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session_dependency),
):
    # Filter out evaluation orders (merchant_eval_*)
    from sqlalchemy import not_
    stmt = select(Order).where(not_(Order.merchant_id.like("merchant_eval%"))).order_by(Order.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    orders = result.scalars().all()
    
    summaries = []
    for order in orders:
        # Get latest attempt
        attempt_stmt = (
            select(PaymentAttempt)
            .where(PaymentAttempt.order_id == order.order_id)
            .order_by(PaymentAttempt.attempt_number.desc())
            .limit(1)
        )
        attempt_result = await session.execute(attempt_stmt)
        latest = attempt_result.scalar_one_or_none()
        
        summaries.append(OrderSummary(
            order_id=order.order_id,
            merchant_id=order.merchant_id,
            customer_id=order.customer_id,
            amount=order.amount,
            currency=order.currency,
            status=order.status,
            created_at=order.created_at,
            latest_attempt_status=latest.status if latest else None,
            latest_attempt_reason=latest.error_reason if latest else None,
        ))
    
    return summaries


@router.get("/orders/{order_id}", response_model=OrderDetail)
async def get_order(
    order_id: str,
    session: AsyncSession = Depends(get_session_dependency),
):
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get attempts
    attempt_stmt = select(PaymentAttempt).where(PaymentAttempt.order_id == order_id).order_by(PaymentAttempt.attempt_number)
    attempt_result = await session.execute(attempt_stmt)
    attempts = attempt_result.scalars().all()
    
    # Get recovery actions
    action_stmt = select(RecoveryAction).where(RecoveryAction.order_id == order_id)
    action_result = await session.execute(action_stmt)
    actions = action_result.scalars().all()
    
    # Get agent runs
    run_stmt = select(AgentRun).where(AgentRun.order_id == order_id).order_by(AgentRun.started_at.desc())
    run_result = await session.execute(run_stmt)
    runs = run_result.scalars().all()
    
    # Build decision analysis from latest agent run
    decision_analysis = None
    if runs:
        latest_run = runs[0]
        event_stmt = select(AgentEvent).where(AgentEvent.run_id == latest_run.run_id).order_by(AgentEvent.event_seq)
        event_result = await session.execute(event_stmt)
        events = event_result.scalars().all()
        
        # Extract diagnosis, candidates, and chosen action from events
        diagnosis = {}
        candidates = []
        chosen_action = None
        stop_conditions = []
        
        for event in events:
            payload = event.payload
            if event.event_type == "agent.stage.completed" and event.agent_stage == "DIAGNOSING":
                diagnosis = payload.get("diagnosis", {})
            elif event.event_type == "agent.stage.completed" and event.agent_stage == "GENERATING_CANDIDATES":
                candidates = payload.get("candidates", [])
            elif event.event_type == "agent.stage.completed" and event.agent_stage == "PLANNING":
                chosen_action = payload.get("chosen_action")
            elif event.event_type == "agent.policy.rejected":
                stop_conditions.append(payload.get("reason", "Policy rejection"))
        
        if diagnosis or candidates or chosen_action:
            decision_analysis = {
                "diagnosis": diagnosis,
                "candidates": candidates,
                "chosen_action": chosen_action,
                "stop_conditions": stop_conditions,
            }
    
    return OrderDetail(
        order=OrderSummary(
            order_id=order.order_id,
            merchant_id=order.merchant_id,
            customer_id=order.customer_id,
            amount=order.amount,
            currency=order.currency,
            status=order.status,
            created_at=order.created_at,
        ),
        attempts=[
            PaymentAttemptSchema(
                payment_id=a.payment_id,
                order_id=a.order_id,
                attempt_number=a.attempt_number,
                method=a.method,
                status=a.status,
                error_code=a.error_code,
                error_reason=a.error_reason,
                error_source=a.error_source,
                error_step=a.error_step,
                created_at=a.created_at,
            )
            for a in attempts
        ],
        recovery_actions=[
            RecoveryActionSchema(
                action_id=a.action_id,
                order_id=a.order_id,
                action_type=a.action_type,
                expected_value=a.expected_value,
                status=a.status,
                scheduled_at=a.scheduled_at,
                executed_at=a.executed_at,
                cancelled_at=a.cancelled_at,
                reason=a.reason,
            )
            for a in actions
        ],
        agent_runs=[
            AgentRunSchema(
                run_id=r.run_id,
                order_id=r.order_id,
                status=r.status,
                current_stage=r.current_stage,
                started_at=r.started_at,
                completed_at=r.completed_at,
                final_action=r.final_action,
                final_reason=r.final_reason,
            )
            for r in runs
        ],
        decision_analysis=decision_analysis,
    )


# In-memory cache for eval summary
_eval_cache: dict[str, tuple[EvalSummary, float]] = {}
_EVAL_CACHE_TTL = 300  # 5 minutes

@router.get("/eval/summary", response_model=EvalSummary)
async def get_eval_summary(
    n_orders: int = Query(200, ge=50, le=500),  # Reduced default from 2000
    seed: int = Query(42, ge=0),
    session: AsyncSession = Depends(get_session_dependency),
):
    cache_key = f"{n_orders}:{seed}"
    now = time.time()
    
    # Check cache
    if cache_key in _eval_cache:
        cached_result, cached_time = _eval_cache[cache_key]
        if now - cached_time < _EVAL_CACHE_TTL:
            return cached_result
    
    result = await run_evaluation(session, n_orders, seed)
    
    # Cache result
    _eval_cache[cache_key] = (result, now)
    
    return result


@router.get("/agent-runs", response_model=List[AgentRunSchema])
async def list_agent_runs(
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(get_session_dependency),
):
    stmt = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
    result = await session.execute(stmt)
    runs = result.scalars().all()
    
    return [
        AgentRunSchema(
            run_id=r.run_id,
            order_id=r.order_id,
            status=r.status,
            current_stage=r.current_stage,
            started_at=r.started_at,
            completed_at=r.completed_at,
            final_action=r.final_action,
            final_reason=r.final_reason,
        )
        for r in runs
    ]


@router.get("/agent-runs/{run_id}", response_model=AgentRunSchema)
async def get_agent_run(
    run_id: str,
    session: AsyncSession = Depends(get_session_dependency),
):
    run = await session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    
    return AgentRunSchema(
        run_id=run.run_id,
        order_id=run.order_id,
        status=run.status,
        current_stage=run.current_stage,
        started_at=run.started_at,
        completed_at=run.completed_at,
        final_action=run.final_action,
        final_reason=run.final_reason,
    )


@router.get("/agent-runs/{run_id}/events", response_model=List[AgentEventSchema])
async def get_agent_events(
    run_id: str,
    session: AsyncSession = Depends(get_session_dependency),
):
    stmt = select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.event_seq)
    result = await session.execute(stmt)
    events = result.scalars().all()
    
    return [
        AgentEventSchema(
            event_seq=e.event_seq,
            run_id=e.run_id,
            order_id=e.order_id,
            agent_stage=e.agent_stage,
            event_type=e.event_type,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.post("/agent-runs/{order_id}/start", response_model=AgentRunSchema)
async def start_agent_run(
    order_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_dependency),
):
    """Start an agent run for an order (runs in background)."""
    # Create agent run record
    import uuid
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    agent_run = AgentRun(
        run_id=run_id,
        order_id=order_id,
        status="running",
        current_stage=AgentStage.RECEIVED.value,
    )
    session.add(agent_run)
    await session.flush()
    await session.commit()
    
    # Run agent in background
    background_tasks.add_task(run_agent_background, run_id, order_id)
    
    return AgentRunSchema(
        run_id=run_id,
        order_id=order_id,
        status="running",
        current_stage=AgentStage.RECEIVED.value,
        started_at=agent_run.started_at,
        completed_at=None,
        final_action=None,
        final_reason=None,
    )


@router.post("/agent-runs/{run_id}/replay", response_model=AgentRunSchema)
async def replay_agent_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session_dependency),
):
    """Replay an agent run for demo purposes (runs in background)."""
    # Get the original run to find the order
    original_run = await session.get(AgentRun, run_id)
    if not original_run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    
    # Create new agent run record
    import uuid
    new_run_id = f"run_{uuid.uuid4().hex[:12]}"
    agent_run = AgentRun(
        run_id=new_run_id,
        order_id=original_run.order_id,
        status="running",
        current_stage=AgentStage.RECEIVED.value,
    )
    session.add(agent_run)
    await session.flush()
    await session.commit()
    
    # Run agent in background
    background_tasks.add_task(run_agent_background, new_run_id, original_run.order_id)
    
    return AgentRunSchema(
        run_id=new_run_id,
        order_id=original_run.order_id,
        status="running",
        current_stage=AgentStage.RECEIVED.value,
        started_at=agent_run.started_at,
        completed_at=None,
        final_action=None,
        final_reason=None,
    )


@router.post("/recovery-actions/{action_id}/complete", response_model=CompleteRecoveryActionResponse)
async def complete_recovery_action_endpoint(
    action_id: int,
    request: CompleteRecoveryActionRequest,
    session: AsyncSession = Depends(get_session_dependency),
):
    """Mark a recovery action as completed (success or failure) and update order status."""
    result = await complete_recovery_action(
        session,
        request.action_id,
        success=request.success,
        reason=request.reason,
    )
    
    return CompleteRecoveryActionResponse(
        success=result.success,
        action_id=result.action_id,
        reason=result.reason,
    )


@router.get("/mcp/status", response_model=MCPStatus)
async def get_mcp_status():
    """Get MCP server status."""
    return MCPStatus(
        status="online",
        endpoint="/mcp",
        transport="Streamable HTTP",
        protocol="MCP v2",
        tools_count=9,
    )


@router.get("/mcp/tools", response_model=List[MCPTool])
async def get_mcp_tools():
    """Get MCP tool catalog."""
    return [
        MCPTool(
            name="reclaim_get_order_context",
            description="Retrieve order, customer, merchant, and payment attempts",
            read_only=True,
            financial_side_effect=False,
        ),
        MCPTool(
            name="reclaim_get_allowed_actions",
            description="Retrieve actions allowed by policy",
            read_only=True,
            financial_side_effect=False,
        ),
        MCPTool(
            name="reclaim_estimate_recovery",
            description="Calculate recovery probability and expected recovery value",
            read_only=True,
            financial_side_effect=False,
        ),
        MCPTool(
            name="reclaim_get_agent_run",
            description="Retrieve an agent run",
            read_only=True,
            financial_side_effect=False,
        ),
        MCPTool(
            name="reclaim_get_agent_events",
            description="Retrieve agent execution events",
            read_only=True,
            financial_side_effect=False,
        ),
        MCPTool(
            name="reclaim_get_evaluation_summary",
            description="Retrieve baseline comparison metrics",
            read_only=True,
            financial_side_effect=False,
        ),
        MCPTool(
            name="reclaim_start_recovery_run",
            description="Start a bounded recovery workflow",
            read_only=False,
            financial_side_effect=True,
        ),
        MCPTool(
            name="reclaim_execute_recovery_action",
            description="Execute a permitted recovery action",
            read_only=False,
            financial_side_effect=True,
        ),
        MCPTool(
            name="reclaim_cancel_pending_action",
            description="Cancel a scheduled action",
            read_only=False,
            financial_side_effect=True,
        ),
    ]


@router.get("/mcp/activity", response_model=List[MCPActivity])
async def get_mcp_activity(limit: int = 50):
    """Get recent MCP activity."""
    from backend.mcp_server.activity import get_recent_activity
    activities = get_recent_activity(limit)
    return [
        MCPActivity(
            timestamp=a.timestamp,
            tool=a.tool,
            duration_ms=a.duration_ms,
            status=a.status,
            order_id=a.order_id,
            error=a.error,
        )
        for a in activities
    ]


@router.get("/mcp/activity/stream")
async def stream_mcp_activity():
    """Stream MCP activity via SSE."""
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        async for activity in activity_stream():
            yield f"data: {activity.model_dump_json()}\n\n"


@router.post("/seed")
async def seed_demo_data(db: AsyncSession = Depends(get_session_dependency)):
    """Seed demo data for testing (idempotent)."""
    from scripts.seed_demo import main as seed_main
    import sys
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    # Capture output
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            await seed_main(db)
        return {
            "status": "success",
            "message": "Demo data seeded",
            "stdout": stdout_capture.getvalue(),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
        }
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )