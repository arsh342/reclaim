#!/usr/bin/env python3
"""Seed demo data for Reclaim demo.

Usage:
    PYTHONPATH=. python scripts/seed_demo.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import init_db, get_session
from backend.db.models import (
    Merchant,
    Customer,
    Order,
    PaymentAttempt,
    AgentRun,
    AgentEvent,
    RecoveryAction,
)


DEMO_MERCHANTS = [
    {
        "merchant_id": "merch_acme_corp",
        "max_retries": 3,
        "contact_budget_per_day": 2,
    },
    {
        "merchant_id": "merch_global_pay",
        "max_retries": 2,
        "contact_budget_per_day": 1,
    },
]

DEMO_CUSTOMERS = [
    {
        "customer_id": "cust_vip_001",
        "recovery_propensity": 0.85,
        "payment_method_preference": "card",
        "historical_success_rate": 0.78,
        "customer_value": 25000,
    },
    {
        "customer_id": "cust_regular_001",
        "recovery_propensity": 0.55,
        "payment_method_preference": "upi",
        "historical_success_rate": 0.45,
        "customer_value": 8000,
    },
    {
        "customer_id": "cust_new_001",
        "recovery_propensity": 0.35,
        "payment_method_preference": "card",
        "historical_success_rate": None,
        "customer_value": 3000,
    },
]

DEMO_ORDERS = [
    {
        "order_id": "order_demo_soft_decline",
        "merchant_id": "merch_acme_corp",
        "customer_id": "cust_vip_001",
        "amount": 5000,
        "currency": "INR",
        "status": "failed",
    },
    {
        "order_id": "order_demo_hard_decline",
        "merchant_id": "merch_acme_corp",
        "customer_id": "cust_regular_001",
        "amount": 3000,
        "currency": "INR",
        "status": "failed",
    },
    {
        "order_id": "order_demo_insufficient_funds",
        "merchant_id": "merch_global_pay",
        "customer_id": "cust_new_001",
        "amount": 1500,
        "currency": "INR",
        "status": "failed",
    },
    {
        "order_id": "order_demo_recovered",
        "merchant_id": "merch_acme_corp",
        "customer_id": "cust_vip_001",
        "amount": 10000,
        "currency": "INR",
        "status": "recovered",
    },
    {
        "order_id": "order_demo_lost",
        "merchant_id": "merch_global_pay",
        "customer_id": "cust_new_001",
        "amount": 2000,
        "currency": "INR",
        "status": "lost",
    },
]

DEMO_ATTEMPTS = [
    # Soft decline - issuer_timeout (retryable)
    {
        "payment_id": "pay_demo_001",
        "order_id": "order_demo_soft_decline",
        "attempt_number": 1,
        "method": "card",
        "status": "failed",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_reason": "issuer_timeout",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    # Hard decline - card_blocked (NOT retryable)
    {
        "payment_id": "pay_demo_002",
        "order_id": "order_demo_hard_decline",
        "attempt_number": 1,
        "method": "card",
        "status": "failed",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_reason": "card_blocked",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    # Insufficient funds (retryable with different method)
    {
        "payment_id": "pay_demo_003",
        "order_id": "order_demo_insufficient_funds",
        "attempt_number": 1,
        "method": "upi",
        "status": "failed",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_reason": "insufficient_funds",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    # Recovered order - captured
    {
        "payment_id": "pay_demo_004",
        "order_id": "order_demo_recovered",
        "attempt_number": 1,
        "method": "card",
        "status": "failed",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_reason": "issuer_timeout",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    {
        "payment_id": "pay_demo_005",
        "order_id": "order_demo_recovered",
        "attempt_number": 2,
        "method": "card",
        "status": "captured",
        "error_code": None,
        "error_reason": None,
        "error_source": None,
        "error_step": None,
    },
    # Lost order - max retries exceeded
    {
        "payment_id": "pay_demo_006",
        "order_id": "order_demo_lost",
        "attempt_number": 1,
        "method": "card",
        "status": "failed",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_reason": "issuer_timeout",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    {
        "payment_id": "pay_demo_007",
        "order_id": "order_demo_lost",
        "attempt_number": 2,
        "method": "card",
        "status": "failed",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_reason": "issuer_timeout",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
    {
        "payment_id": "pay_demo_008",
        "order_id": "order_demo_lost",
        "attempt_number": 3,
        "method": "card",
        "status": "failed",
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_reason": "issuer_timeout",
        "error_source": "customer",
        "error_step": "payment_authentication",
    },
]

DEMO_ACTIONS = [
    # Soft decline - delayed retry scheduled
    {
        "action_id": 1,
        "order_id": "order_demo_soft_decline",
        "action_type": "RETRY_DELAYED",
        "expected_value": 3800,
        "status": "scheduled",
        "scheduled_at": datetime.now(timezone.utc) + timedelta(minutes=30),
        "reason": "Soft decline (issuer_timeout), retry with 30min delay",
    },
    # Hard decline - payment link instead of retry
    {
        "action_id": 2,
        "order_id": "order_demo_hard_decline",
        "action_type": "PAYMENT_LINK",
        "expected_value": 1800,
        "status": "executed",
        "scheduled_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "executed_at": datetime.now(timezone.utc) - timedelta(minutes=45),
        "reason": "Hard decline (card_blocked), payment link sent",
    },
    # Insufficient funds - alternate method
    {
        "action_id": 3,
        "order_id": "order_demo_insufficient_funds",
        "action_type": "ALTERNATE_METHOD",
        "expected_value": 900,
        "status": "scheduled",
        "scheduled_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "reason": "Insufficient funds, try card instead of UPI",
    },
]


async def seed_demo_data(session: AsyncSession):
    """Seed the database with demo data."""
    print("Seeding demo data...")

    # Clear existing data
    await session.execute(RecoveryAction.__table__.delete())
    await session.execute(AgentEvent.__table__.delete())
    await session.execute(AgentRun.__table__.delete())
    await session.execute(PaymentAttempt.__table__.delete())
    await session.execute(Order.__table__.delete())
    await session.execute(Customer.__table__.delete())
    await session.execute(Merchant.__table__.delete())
    await session.commit()

    # Insert merchants
    for m in DEMO_MERCHANTS:
        session.add(Merchant(**m))
    print(f"  Added {len(DEMO_MERCHANTS)} merchants")

    # Insert customers
    for c in DEMO_CUSTOMERS:
        session.add(Customer(**c))
    print(f"  Added {len(DEMO_CUSTOMERS)} customers")

    await session.flush()

    # Insert orders
    for o in DEMO_ORDERS:
        session.add(Order(**o))
    print(f"  Added {len(DEMO_ORDERS)} orders")

    await session.flush()

    # Insert payment attempts
    for a in DEMO_ATTEMPTS:
        session.add(PaymentAttempt(**a))
    print(f"  Added {len(DEMO_ATTEMPTS)} payment attempts")

    await session.flush()

    # Insert recovery actions
    for a in DEMO_ACTIONS:
        session.add(RecoveryAction(**a))
    print(f"  Added {len(DEMO_ACTIONS)} recovery actions")

    # Update order status for orders with executed recovery actions
    executed_actions = [a for a in DEMO_ACTIONS if a.get("status") == "executed"]
    for action in executed_actions:
        order = await session.get(Order, action["order_id"])
        if order:
            order.status = "recovered"
            print(f"  Updated order {action['order_id']} status to recovered")

    await session.commit()

    print("Demo data seeded successfully!")


async def main():
    await init_db()
    async with get_session() as session:
        await seed_demo_data(session)


if __name__ == "__main__":
    asyncio.run(main())