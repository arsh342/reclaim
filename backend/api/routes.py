"""API routes."""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from backend.api.webhooks import ingest_webhook
from backend.policy.constraints import get_allowed_actions
from backend.evaluator.runner import run_evaluation
from backend.evaluator.baselines import AlwaysRetryPolicy, ReclaimPolicy


router = APIRouter()


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
    stmt = select(Order).order_by(Order.created_at.desc()).offset(offset).limit(limit)
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
    )


@router.get("/eval/summary", response_model=EvalSummary)
async def get_eval_summary(
    n_orders: int = Query(2000, ge=100, le=5000),
    seed: int = Query(42, ge=0),
    session: AsyncSession = Depends(get_session_dependency),
):
    result = await run_evaluation(session, n_orders, seed)
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