"""Webhook ingestion.

Idempotency contract:
  - `webhook_events.event_id` is the primary key. The first thing every
    handler does is INSERT a row with that event_id. If the insert
    fails on PK conflict, the event is a replay — return early.
  - All downstream work for a captured payment runs in one transaction
    with `SELECT ... FOR UPDATE` on the parent `orders` row, so a
    captured webhook and an in-flight recovery action can't race.

Source of truth for behavior: docs/reclaim-build-plan.md §2 and
docs/reclaim-system-design.md §5.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api.fixtures import PaymentEntity, WebhookPayload
from backend.agent.router import run_agent
from backend.agent.explain import explain_decision
from backend.agent.tools import cancel_pending_action
from backend.db.models import (
    Order,
    PaymentAttempt,
    RecoveryAction,
    WebhookEvent,
)


@dataclass(frozen=True)
class IngestResult:
    status: str
    event_id: str
    order_id: str
    action_id: int | None = None


def _extract_payment(payload: WebhookPayload) -> PaymentEntity:
    raw = payload.payload["payment"]["entity"]
    return PaymentEntity.model_validate(raw)


def _event_id_for(payload: WebhookPayload, payment: PaymentEntity) -> str:
    return f"{payload.event}:{payment.id}:{payment.attempt_number}"


def ingest_webhook(db: Session, payload: WebhookPayload) -> IngestResult:
    payment = _extract_payment(payload)
    event_id = _event_id_for(payload, payment)

    event = WebhookEvent(
        event_id=event_id,
        event_type=payload.event,
        payload=payload.model_dump(by_alias=True),
        processed_at=None,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return IngestResult(
            status="duplicate",
            event_id=event_id,
            order_id=payment.order_id,
        )

    action_id = None
    if payload.event == "payment.failed":
        _record_failed_attempt(db, payment)
        db.flush()  # ensure order is visible to agent query

        # A late failure cannot create a new recovery decision after the
        # order is already resolved. Keep the event for auditability, but do
        # not send a terminal order through the policy agent.
        order = db.execute(
            select(Order).where(Order.order_id == payment.order_id)
        ).scalar_one()
        if order.status in ("recovered", "lost"):
            db.execute(
                update(WebhookEvent)
                .where(WebhookEvent.event_id == event_id)
                .values(processed_at=datetime.now(timezone.utc))
            )
            db.commit()
            return IngestResult(
                status="processed",
                event_id=event_id,
                order_id=payment.order_id,
            )

        # Run the router agent to decide and schedule a recovery action
        agent_decision = run_agent(db, payment.order_id)
        action_id = agent_decision.action_id

        # Generate explanation via LLM and persist to recovery action
        if action_id:
            # Build a Decision-like object for explain_decision
            from backend.policy.select import Decision
            decision_for_explanation = Decision(
                selected_action=agent_decision.selected_action,
                expected_value=agent_decision.expected_value,
                ranked=list(agent_decision.alternatives.items()),
                constraints_applied=agent_decision.constraints_applied,
                reasons=agent_decision.reasons,
            )
            explanation_result = explain_decision(decision_for_explanation)
            action = db.execute(
                select(RecoveryAction).where(RecoveryAction.action_id == action_id)
            ).scalar_one_or_none()
            if action:
                action.explanation = explanation_result.explanation
                action.explanation_model = explanation_result.model
                db.flush()
    elif payload.event == "payment.captured":
        _recover_order(db, payment)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported event: {payload.event}",
        )

    db.execute(
        update(WebhookEvent)
        .where(WebhookEvent.event_id == event_id)
        .values(processed_at=datetime.now(timezone.utc))
    )
    db.commit()

    return IngestResult(
        status="processed",
        event_id=event_id,
        order_id=payment.order_id,
        action_id=action_id,
    )


def _record_failed_attempt(db: Session, payment: PaymentEntity) -> None:
    order = db.execute(
        select(Order).where(Order.order_id == payment.order_id).with_for_update()
    ).scalar_one_or_none()

    if order is None:
        db.add(
            Order(
                order_id=payment.order_id,
                amount=payment.amount / 100,
                currency=payment.currency,
                status="pending",
            )
        )

    # Idempotent: check if payment attempt already exists
    existing = db.execute(
        select(PaymentAttempt).where(PaymentAttempt.payment_id == payment.id)
    ).scalar_one_or_none()

    if existing and existing.order_id != payment.order_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"payment_id {payment.id} already belongs to order {existing.order_id}",
        )

    if existing is None:
        db.add(
            PaymentAttempt(
                payment_id=payment.id,
                order_id=payment.order_id,
                attempt_number=payment.attempt_number,
                method=payment.method,
                status="failed",
                error_code=payment.error_code,
                error_description=payment.error_description,
                error_reason=payment.error_reason,
                error_source=payment.error_source,
                error_step=payment.error_step,
            )
        )


def _recover_order(db: Session, payment: PaymentEntity) -> None:
    order = db.execute(
        select(Order).where(Order.order_id == payment.order_id).with_for_update()
    ).scalar_one_or_none()

    def add_attempt_if_new():
        existing = db.execute(
            select(PaymentAttempt).where(PaymentAttempt.payment_id == payment.id)
        ).scalar_one_or_none()
        if existing and existing.order_id != payment.order_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"payment_id {payment.id} already belongs to order {existing.order_id}",
            )
        if existing is None:
            db.add(
                PaymentAttempt(
                    payment_id=payment.id,
                    order_id=payment.order_id,
                    attempt_number=payment.attempt_number,
                    method=payment.method,
                    status="captured",
                )
            )

    if order is None:
        add_attempt_if_new()
        db.add(
            Order(
                order_id=payment.order_id,
                amount=payment.amount / 100,
                currency=payment.currency,
                status="recovered",
            )
        )
        return

    if order.status in ("recovered", "lost"):
        add_attempt_if_new()
        return

    add_attempt_if_new()
    order.status = "recovered"

    cancel_pending_action(db, payment.order_id)
