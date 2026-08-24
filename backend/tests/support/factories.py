"""Factories for test rows.

Tests compose fixtures like `merchant + customer + order + recovery_action`
to set up the exact state they need before invoking the API.
"""

from decimal import Decimal

from backend.db.models import (
    Customer,
    Merchant,
    Order,
    RecoveryAction,
)


def make_merchant(
    db,
    merchant_id: str = "merch_test",
    max_retries: int = 3,
    contact_budget_per_day: int = 2,
) -> Merchant:
    m = Merchant(
        merchant_id=merchant_id,
        max_retries=max_retries,
        contact_budget_per_day=contact_budget_per_day,
    )
    db.add(m)
    db.flush()
    return m


def make_customer(
    db,
    customer_id: str = "cust_test",
    recovery_propensity: Decimal = Decimal("0.5"),
    customer_value: Decimal = Decimal("1000"),
) -> Customer:
    c = Customer(
        customer_id=customer_id,
        recovery_propensity=recovery_propensity,
        payment_method_preference="card",
        historical_success_rate=Decimal("0.5"),
        customer_value=customer_value,
    )
    db.add(c)
    db.flush()
    return c


def make_order(
    db,
    order_id: str = "order_test",
    merchant_id: str = "merch_test",
    customer_id: str = "cust_test",
    amount: Decimal = Decimal("25000"),
    status: str = "pending",
) -> Order:
    o = Order(
        order_id=order_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        amount=amount,
        currency="INR",
        status=status,
    )
    db.add(o)
    db.flush()
    return o


def make_recovery_action(
    db,
    order_id: str,
    action_type: str = "RETRY_DELAYED",
    expected_value: Decimal = Decimal("500"),
    status: str = "scheduled",
) -> RecoveryAction:
    a = RecoveryAction(
        order_id=order_id,
        action_type=action_type,
        expected_value=expected_value,
        status=status,
    )
    db.add(a)
    db.flush()
    return a
