"""Seeded synthetic data generation.

Two RNGs, both derived from the same base seed:
  - generation RNG: drives merchant/customer/order/attempt creation.
  - outcome RNG: created lazily inside `simulate_outcome` from a separate
    seed stream so outcome sampling never leaks into generation state.

Same seed → identical dataset AND identical outcomes. Two callers running
in parallel with the same seed produce the same world.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal

from backend.simulator.config_loader import load_config

_REASONS = ("insufficient_funds", "issuer_timeout", "card_blocked", "invalid_card", "network_error")
_METHODS = ("card", "upi", "netbanking")


@dataclass(frozen=True)
class SimulatedMerchant:
    merchant_id: str
    max_retries: int
    contact_budget_per_day: int


@dataclass(frozen=True)
class SimulatedCustomer:
    customer_id: str
    recovery_propensity: float
    payment_method_preference: str
    historical_success_rate: float
    customer_value: Decimal


@dataclass(frozen=True)
class SimulatedOrder:
    order_id: str
    merchant_id: str
    customer_id: str
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class SimulatedAttempt:
    payment_id: str
    order_id: str
    attempt_number: int
    method: str
    status: str
    error_code: str
    error_reason: str
    error_source: str
    error_step: str


@dataclass(frozen=True)
class SimulatedWorld:
    merchants: list[SimulatedMerchant]
    customers: list[SimulatedCustomer]
    orders: list[SimulatedOrder]
    attempts: list[SimulatedAttempt]

    def attempts_for_order(self, order_id: str) -> list[SimulatedAttempt]:
        return [a for a in self.attempts if a.order_id == order_id]


def _make_rng(seed: int) -> random.Random:
    return random.Random(seed)


def generate_world(
    n_orders: int,
    seed: int,
    *,
    n_merchants: int = 50,
    n_customers: int = 500,
    attempts_per_order: int = 1,
) -> SimulatedWorld:
    """Generate a reproducible synthetic world.

    Order of generation is deterministic: merchants, customers, orders, attempts.
    """
    if n_orders <= 0:
        raise ValueError("n_orders must be > 0")
    rng = _make_rng(seed)

    merchants: list[SimulatedMerchant] = [
        SimulatedMerchant(
            merchant_id=f"merch_{i:05d}",
            max_retries=rng.randint(1, 5),
            contact_budget_per_day=rng.randint(1, 4),
        )
        for i in range(n_merchants)
    ]

    customers: list[SimulatedCustomer] = [
        SimulatedCustomer(
            customer_id=f"cust_{i:06d}",
            recovery_propensity=rng.random(),
            payment_method_preference=rng.choice(_METHODS),
            historical_success_rate=rng.uniform(0.2, 0.9),
            customer_value=Decimal(rng.randint(500, 50000)),
        )
        for i in range(n_customers)
    ]

    orders: list[SimulatedOrder] = []
    attempts: list[SimulatedAttempt] = []
    for i in range(n_orders):
        merchant = merchants[rng.randrange(n_merchants)]
        customer = customers[rng.randrange(n_customers)]
        order_id = f"order_{seed:08d}_{i:06d}"
        order = SimulatedOrder(
            order_id=order_id,
            merchant_id=merchant.merchant_id,
            customer_id=customer.customer_id,
            amount=Decimal(rng.randint(500, 100000)),
            currency="INR",
        )
        orders.append(order)
        for attempt_no in range(1, attempts_per_order + 1):
            attempts.append(
                SimulatedAttempt(
                    payment_id=f"pay_{seed:08d}_{i:06d}_{attempt_no}",
                    order_id=order_id,
                    attempt_number=attempt_no,
                    method=customer.payment_method_preference,
                    status="failed",
                    error_code="BAD_REQUEST_PAYMENT_FAILED",
                    error_reason=rng.choice(_REASONS),
                    error_source=rng.choice(("customer", "issuer", "network")),
                    error_step="payment_authentication",
                )
            )

    return SimulatedWorld(
        merchants=merchants,
        customers=customers,
        orders=orders,
        attempts=attempts,
    )


def simulate_outcome(
    *,
    reason: str,
    method: str,
    action: str,
    propensity: float,
    rng: random.Random,
    alternate_method: str | None = None,
) -> bool:
    """Sample whether the recovery action succeeds for the given context.

    The probability comes from `SimulatorConfig.probability(...)`. The RNG
    is passed in so outcome sampling stays independent of generation.
    """
    cfg = load_config()
    p = cfg.probability(
        reason,
        method,
        action,
        propensity,
        alternate_method=alternate_method,
    )
    return rng.random() < p
