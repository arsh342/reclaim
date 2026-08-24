"""Razorpay-shaped webhook payload fixtures.

Field names mirror `razorpay.com/docs/webhooks` exactly. Two event types
are modeled: `payment.failed` and `payment.captured`. The third documented
type, `order.paid`, is the higher-level "any attempt on this order was
captured" signal — Reclaim derives that from a captured attempt + order
status flip, not from a separate webhook payload.

Tests and the live-demo script (build-plan §7) import from here so the
wire shape never drifts from the docs.
"""

from typing import Literal

from pydantic import BaseModel, Field


class PaymentEntity(BaseModel):
    id: str
    order_id: str
    amount: int
    currency: str = "INR"
    method: str
    status: str
    attempt_number: int = Field(default=1, alias="attempt_number")
    error_code: str | None = None
    error_description: str | None = None
    error_reason: str | None = None
    error_source: str | None = None
    error_step: str | None = None

    model_config = {"populate_by_name": True}


class WebhookPayload(BaseModel):
    entity: Literal["event"]
    account_id: str
    event: Literal["payment.failed", "payment.captured"]
    contains: list[str] = Field(default_factory=lambda: ["payment"])
    payload: dict


def payment_failed(
    *,
    event_id: str,
    payment_id: str,
    order_id: str,
    amount: float,  # rupees (e.g., 25000.0 for ₹25,000)
    method: str = "card",
    attempt_number: int = 1,
    error_code: str = "BAD_REQUEST_PAYMENT_FAILED",
    error_reason: str = "issuer_timeout",
    error_source: str = "customer",
    error_step: str = "payment_authentication",
) -> WebhookPayload:
    amount_paise = int(round(amount * 100))
    payment = PaymentEntity(
        id=payment_id,
        order_id=order_id,
        amount=amount_paise,
        method=method,
        status="failed",
        attempt_number=attempt_number,
        error_code=error_code,
        error_description="Payment failed",
        error_reason=error_reason,
        error_source=error_source,
        error_step=error_step,
    )
    return WebhookPayload(
        entity="event",
        account_id="acc_test",
        event="payment.failed",
        payload={"payment": {"entity": payment.model_dump(by_alias=True)}},
    )


def payment_captured(
    *,
    event_id: str,
    payment_id: str,
    order_id: str,
    amount: float,  # rupees (e.g., 25000.0 for ₹25,000)
    method: str = "card",
    attempt_number: int = 1,
) -> WebhookPayload:
    amount_paise = int(round(amount * 100))
    payment = PaymentEntity(
        id=payment_id,
        order_id=order_id,
        amount=amount_paise,
        method=method,
        status="captured",
        attempt_number=attempt_number,
    )
    return WebhookPayload(
        entity="event",
        account_id="acc_test",
        event="payment.captured",
        payload={"payment": {"entity": payment.model_dump(by_alias=True)}},
    )
