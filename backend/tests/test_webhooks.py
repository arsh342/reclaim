"""Tests for webhook ingestion."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.webhooks import ingest_webhook
from backend.api.schemas import SimulateWebhookRequest, PaymentPayload, PaymentEntity
from backend.db.models import Order, PaymentAttempt, WebhookEvent


@pytest.mark.asyncio
async def test_ingest_payment_failed(db_session: AsyncSession):
    """Test ingesting a payment.failed webhook."""
    webhook = SimulateWebhookRequest(
        entity="event",
        account_id="acc_test",
        event="payment.failed",
        contains=["payment"],
        payload=PaymentPayload(
            payment=PaymentEntity(
                id="pay_001",
                order_id="order_001",
                amount=500000,  # 5000 INR in paise
                currency="INR",
                method="card",
                status="failed",
                attempt_number=1,
                error_code="BAD_REQUEST_PAYMENT_FAILED",
                error_description="Payment failed",
                error_reason="issuer_timeout",
                error_source="customer",
                error_step="payment_authentication",
            )
        ),
    )
    
    result = await ingest_webhook(db_session, webhook)
    
    assert result.status == "processed"
    assert result.event_id == "pay_001"
    assert result.order_id == "order_001"
    
    # Verify order created
    order = await db_session.get(Order, "order_001")
    assert order is not None
    assert order.amount == 5000
    assert order.status == "failed"
    
    # Verify payment attempt created
    attempt = await db_session.get(PaymentAttempt, "pay_001")
    assert attempt is not None
    assert attempt.attempt_number == 1
    assert attempt.status == "failed"
    assert attempt.error_reason == "issuer_timeout"
    
    # Verify webhook event recorded
    event = await db_session.get(WebhookEvent, "pay_001")
    assert event is not None
    assert event.event_type == "payment.failed"


@pytest.mark.asyncio
async def test_duplicate_webhook_ignored(db_session: AsyncSession):
    """Test that duplicate event_id is ignored."""
    webhook = SimulateWebhookRequest(
        entity="event",
        account_id="acc_test",
        event="payment.failed",
        contains=["payment"],
        payload=PaymentPayload(
            payment=PaymentEntity(
                id="pay_002",
                order_id="order_002",
                amount=300000,
                currency="INR",
                method="upi",
                status="failed",
                attempt_number=1,
                error_reason="insufficient_funds",
            )
        ),
    )
    
    # First ingest
    result1 = await ingest_webhook(db_session, webhook)
    assert result1.status == "processed"
    
    # Second ingest with same event_id
    result2 = await ingest_webhook(db_session, webhook)
    assert result2.status == "duplicate"
    assert "ignored" in result2.message.lower()


@pytest.mark.asyncio
async def test_payment_captured_cancels_pending_actions(db_session: AsyncSession):
    """Test that payment.captured cancels pending recovery actions."""
    from backend.executor.executor import create_recovery_action
    from backend.policy.constraints import RETRY_DELAYED
    from decimal import Decimal
    
    # First, create a failed payment
    webhook_failed = SimulateWebhookRequest(
        entity="event",
        account_id="acc_test",
        event="payment.failed",
        contains=["payment"],
        payload=PaymentPayload(
            payment=PaymentEntity(
                id="pay_003",
                order_id="order_003",
                amount=1000000,
                currency="INR",
                method="card",
                status="failed",
                attempt_number=1,
                error_reason="issuer_timeout",
            )
        ),
    )
    await ingest_webhook(db_session, webhook_failed)
    
    # Create a pending recovery action
    action = await create_recovery_action(db_session, "order_003", RETRY_DELAYED, Decimal("5000"))
    assert action.status == "scheduled"
    
    # Now ingest payment.captured
    webhook_captured = SimulateWebhookRequest(
        entity="event",
        account_id="acc_test",
        event="payment.captured",
        contains=["payment"],
        payload=PaymentPayload(
            payment=PaymentEntity(
                id="pay_004",
                order_id="order_003",
                amount=1000000,
                currency="INR",
                method="card",
                status="captured",
                attempt_number=2,
            )
        ),
    )
    result = await ingest_webhook(db_session, webhook_captured)
    
    assert result.status == "processed"
    
    # Verify order status changed to recovered
    order = await db_session.get(Order, "order_003")
    assert order.status == "recovered"
    
    # Verify recovery action was cancelled
    await db_session.refresh(action)
    assert action.status == "cancelled"
    assert "captured" in (action.reason or "").lower()


@pytest.mark.asyncio
async def test_webhook_creates_merchant_and_customer(db_session: AsyncSession):
    """Test that webhook ingestion creates merchant and customer if not exist."""
    webhook = SimulateWebhookRequest(
        entity="event",
        account_id="acc_new",
        event="payment.failed",
        contains=["payment"],
        payload=PaymentPayload(
            payment=PaymentEntity(
                id="pay_new_001",
                order_id="order_new_001",
                amount=250000,
                currency="INR",
                method="netbanking",
                status="failed",
                attempt_number=1,
                error_reason="network_error",
            )
        ),
    )
    
    result = await ingest_webhook(db_session, webhook)
    
    assert result.status == "processed"
    
    # Verify merchant created (default)
    from backend.db.models import Merchant, Customer
    merchant = await db_session.get(Merchant, "merchant_default")
    assert merchant is not None
    assert merchant.max_retries == 3
    
    # Verify customer created
    customer = await db_session.get(Customer, "cust_order_new_001")
    assert customer is not None
    assert customer.recovery_propensity == 0.5