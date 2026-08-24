from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.api.fixtures import WebhookPayload
from backend.api.webhooks import IngestResult, ingest_webhook
from backend.api.schemas import (
    OrderDetail,
    OrderSummary,
    EvalSummary,
    IngestResult,
    PolicyMetrics,
    PaymentAttemptSchema,
    RecoveryActionSchema,
    CandidateAction,
    DecisionAnalysis,
)
from backend.agent.query_repo import QueryRepository
from backend.db.models import Order, PaymentAttempt, RecoveryAction, Merchant as MerchantModel, Customer
from backend.policy.select import select_action
from backend.policy.types import PolicyContext, OrderView, AttemptView, Merchant as MerchantView, CustomerView
from backend.db.session import get_db
from backend.eval.runner import run_evaluation
from backend.agent.tools import get_order_context, get_allowed_actions, estimate_recovery

router = APIRouter()


@router.post("/webhooks/simulate", response_model=IngestResult)
def simulate_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db),
) -> IngestResult:
    return ingest_webhook(db, payload)


@router.get("/orders", response_model=list[OrderSummary])
def list_orders(db: Session = Depends(get_db)) -> list[OrderSummary]:
    rows = db.execute(select(Order).order_by(Order.created_at.desc()).limit(100)).scalars().all()
    return [
        OrderSummary(
            order_id=o.order_id,
            amount=float(o.amount),
            currency=o.currency,
            status=o.status,
            created_at=o.created_at,
        )
        for o in rows
    ]


@router.get("/orders/{order_id}", response_model=OrderDetail)
def get_order(order_id: str, db: Session = Depends(get_db)) -> OrderDetail:
    order = db.execute(
        select(Order)
        .where(Order.order_id == order_id)
        .options(
            selectinload(Order.payment_attempts),
            selectinload(Order.recovery_actions),
        )
    ).scalar_one_or_none()

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")

    # Build candidate-action ERV breakdown by re-running the policy decision
    # to get the full ranked alternatives (stored on the latest recovery action
    # or recomputed for display)
    erv_breakdown = []
    selected_action = None
    try:
        repo = QueryRepository(db)
        policy_ctx = repo.build_estimate_recovery_policy_ctx(order_id)
        decision = select_action(policy_ctx)
        selected_action = decision.selected_action
        erv_breakdown = [
            {"action": action, "erv": round(erv, 2)}
            for action, erv in decision.ranked
        ]
    except Exception:
        # If recomputation fails, fall back to stored recovery actions
        erv_breakdown = [
            {"action": r.action_type, "erv": float(r.expected_value)}
            for r in order.recovery_actions
        ]

    recovery_actions = sorted(
        order.recovery_actions,
        key=lambda action: action.action_id,
        reverse=True,
    )
    latest_action = recovery_actions[0] if recovery_actions else None
    if selected_action is None and latest_action:
        selected_action = latest_action.action_type

    return OrderDetail(
        order_id=order.order_id,
        merchant_id=order.merchant_id,
        customer_id=order.customer_id,
        amount=float(order.amount),
        currency=order.currency,
        status=order.status,
        created_at=order.created_at,
        payment_attempts=[
            PaymentAttemptSchema(
                payment_id=a.payment_id,
                attempt_number=a.attempt_number,
                method=a.method,
                status=a.status,
                error_code=a.error_code,
                error_reason=a.error_reason,
                created_at=a.created_at,
            )
            for a in order.payment_attempts
        ],
        recovery_actions=[
            RecoveryActionSchema(
                action_id=r.action_id,
                action_type=r.action_type,
                expected_value=float(r.expected_value),
                status=r.status,
                scheduled_at=r.scheduled_at,
                executed_at=r.executed_at,
                cancelled_at=r.cancelled_at,
                reason=r.reason,
                explanation=r.explanation,
                explanation_model=r.explanation_model,
            )
            for r in recovery_actions
        ],
        decision_analysis=DecisionAnalysis(
            candidate_actions=[
                CandidateAction(action=a["action"], erv=a["erv"])
                for a in erv_breakdown
            ],
            selected_action=selected_action,
        ),
    )


@router.get("/eval/summary", response_model=EvalSummary)
def eval_summary(
    n_orders: int = 2000,
    seed: int = 42,
) -> EvalSummary:
    result = run_evaluation(n_orders=n_orders, seed=seed)
    return EvalSummary(
        seed=result.seed,
        n_orders=result.n_orders,
        reclaim=PolicyMetrics(
            recovered_revenue=float(result.reclaim.recovered_revenue),
            total_revenue_at_risk=float(result.reclaim.total_revenue_at_risk),
            recovery_rate=result.reclaim.recovery_rate,
            unnecessary_interventions=result.reclaim.unnecessary_interventions,
            total_interventions=result.reclaim.total_interventions,
        ),
        always_retry=PolicyMetrics(
            recovered_revenue=float(result.always_retry.recovered_revenue),
            total_revenue_at_risk=float(result.always_retry.total_revenue_at_risk),
            recovery_rate=result.always_retry.recovery_rate,
            unnecessary_interventions=result.always_retry.unnecessary_interventions,
            total_interventions=result.always_retry.total_interventions,
        ),
        delta={
            "recovered_revenue": float(result.delta_recovered_revenue()),
            "recovery_rate": result.delta_recovery_rate(),
        },
    )
