"""Webhook ingestion service."""

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    Merchant,
    Customer,
    Order,
    PaymentAttempt,
    WebhookEvent,
    RecoveryAction,
)
from backend.api.schemas import WebhookEventRequest, IngestResult, SimulateWebhookRequest
from backend.policy.constraints import get_allowed_actions
from backend.executor.executor import cancel_pending_actions


async def ingest_webhook(
    session: AsyncSession,
    webhook: SimulateWebhookRequest,
) -> IngestResult:
    """Ingest a webhook event with idempotency."""
    # Access payment entity from Pydantic model
    payment = webhook.payload.payment
    event_id = payment.id
    
    if not event_id:
        # Fallback: generate from payload
        import hashlib
        import json
        event_id = hashlib.sha256(json.dumps(webhook.payload.model_dump(), sort_keys=True).encode()).hexdigest()[:24]
    
    # Try to insert webhook event (idempotency via PK)
    stmt = insert(WebhookEvent).values(
        event_id=event_id,
        event_type=webhook.event,
        payload=webhook.payload.model_dump(),
        processed_at=None,
    ).on_conflict_do_nothing(index_elements=["event_id"])
    
    result = await session.execute(stmt)
    
    if result.rowcount == 0:
        return IngestResult(
            status="duplicate",
            event_id=event_id,
            message="Duplicate event_id ignored",
        )
    
    # Process the event
    order_id = payment.order_id
    
    # Ensure merchant exists
    merchant_id = "merchant_default"
    merchant = await session.get(Merchant, merchant_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=merchant_id,
            max_retries=3,
            contact_budget_per_day=2,
        )
        session.add(merchant)
    
    # Ensure customer exists
    customer_id = f"cust_{order_id}"
    customer = await session.get(Customer, customer_id)
    if not customer:
        customer = Customer(
            customer_id=customer_id,
            recovery_propensity=Decimal("0.5"),
            customer_value=Decimal("10000"),
        )
        session.add(customer)
    
    # Ensure order exists
    order = await session.get(Order, order_id)
    if not order:
        order = Order(
            order_id=order_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount=Decimal(str(payment.amount)) / Decimal("100"),
            currency=payment.currency,
            status="pending",
        )
        session.add(order)
    
    if webhook.event == "payment.failed":
        # Create payment attempt
        attempt = PaymentAttempt(
            payment_id=payment.id,
            order_id=order_id,
            attempt_number=payment.attempt_number,
            method=payment.method,
            status="failed",
            error_code=payment.error_code,
            error_description=payment.error_description,
            error_reason=payment.error_reason,
            error_source=payment.error_source,
            error_step=payment.error_step,
        )
        session.add(attempt)
        
        # Update order status to reflect failed payment
        if order.status == "pending":
            order.status = "failed"
        
    elif webhook.event == "payment.captured":
        # Update payment attempt
        attempt = await session.get(PaymentAttempt, payment.id)
        if attempt:
            attempt.status = "captured"
        
        # Update order status
        order.status = "recovered"
        
        # Cancel pending recovery actions
        await cancel_pending_actions(session, order_id, "Payment captured")
    
    # Mark webhook as processed
    webhook_event = await session.get(WebhookEvent, event_id)
    if webhook_event:
        from datetime import datetime, timezone
        webhook_event.processed_at = datetime.now(timezone.utc)
    
    await session.flush()
    
    return IngestResult(
        status="processed",
        event_id=event_id,
        order_id=order_id,
        message="Event processed successfully",
    )