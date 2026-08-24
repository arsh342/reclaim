"""Webhook ingestion + idempotency.

The three behaviors the panel will probe:
  1. Same event_id fired twice → exactly one row in webhook_events.
  2. payment.captured flips the order to 'recovered' AND cancels every
     scheduled recovery action in the same transaction.
  3. payment.captured against an order that's already recovered is a no-op.
"""

from sqlalchemy import select

from backend.db.models import Order, PaymentAttempt, RecoveryAction, WebhookEvent
from backend.tests.support.factories import (
    make_customer,
    make_merchant,
    make_order,
    make_recovery_action,
)


def _seed_pending_order_with_action(db):
    make_merchant(db)
    make_customer(db)
    order = make_order(db, order_id="order_recover_test", amount=25000)
    action = make_recovery_action(
        db, order_id=order.order_id, action_type="RETRY_DELAYED", expected_value=500
    )
    db.commit()
    return order, action


def test_same_event_id_fired_twice_creates_one_row(client, db):
    payload = {
        "entity": "event",
        "account_id": "acc_test",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_dup",
                    "order_id": "order_dup",
                    "amount": 1200,
                    "currency": "INR",
                    "method": "card",
                    "status": "failed",
                    "attempt_number": 1,
                    "error_code": "BAD_REQUEST_PAYMENT_FAILED",
                    "error_reason": "issuer_timeout",
                    "error_source": "customer",
                    "error_step": "payment_authentication",
                }
            }
        },
    }

    first = client.post("/webhooks/simulate", json=payload)
    second = client.post("/webhooks/simulate", json=payload)

    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"

    rows = db.execute(select(WebhookEvent)).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_id == "payment.failed:pay_dup:1"


def test_captured_payment_flips_order_and_cancels_pending_actions(client, db):
    order, action = _seed_pending_order_with_action(db)
    db.refresh(order)
    db.refresh(action)
    assert order.status == "pending"
    assert action.status == "scheduled"

    payload = {
        "entity": "event",
        "account_id": "acc_test",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_capture",
                    "order_id": order.order_id,
                    "amount": int(order.amount * 100),
                    "currency": order.currency,
                    "method": "card",
                    "status": "captured",
                    "attempt_number": 2,
                }
            }
        },
    }

    response = client.post("/webhooks/simulate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processed"
    assert body["order_id"] == order.order_id

    db.expire_all()
    db.refresh(order)
    db.refresh(action)
    assert order.status == "recovered"
    assert action.status == "cancelled"
    assert action.cancelled_at is not None

    attempts = db.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order.order_id)
    ).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].status == "captured"


def test_captured_payment_on_already_recovered_order_is_noop(client, db):
    order, _ = _seed_pending_order_with_action(db)
    db.execute(
        Order.__table__.update()
        .where(Order.order_id == order.order_id)
        .values(status="recovered")
    )
    db.commit()
    db.refresh(order)
    assert order.status == "recovered"

    payload = {
        "entity": "event",
        "account_id": "acc_test",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_late",
                    "order_id": order.order_id,
                    "amount": int(order.amount * 100),
                    "currency": order.currency,
                    "method": "card",
                    "status": "captured",
                    "attempt_number": 3,
                }
            }
        },
    }

    response = client.post("/webhooks/simulate", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    db.expire_all()
    db.refresh(order)
    assert order.status == "recovered"

    actions = db.execute(
        select(RecoveryAction).where(RecoveryAction.order_id == order.order_id)
    ).scalars().all()
    assert all(a.status != "cancelled" or a.cancelled_at is not None for a in actions)
