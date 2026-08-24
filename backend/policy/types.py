"""Policy engine — shared types.

`PolicyContext` is the small seam between policy modules and the rest of
the app. It carries everything a constraint check or score needs in one
immutable bundle. Callers build it; policy code reads from it.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

ActionType = Literal[
    "retry_now",
    "retry_delayed",
    "payment_link",
    "whatsapp_nudge",
    "alternate_method",
    "no_action",
    "human_review",
]

ALL_ACTIONS: tuple[ActionType, ...] = (
    "retry_now",
    "retry_delayed",
    "payment_link",
    "whatsapp_nudge",
    "alternate_method",
)


@dataclass(frozen=True)
class Merchant:
    merchant_id: str
    max_retries: int
    contact_budget_per_day: int


@dataclass(frozen=True)
class OrderView:
    order_id: str
    amount: Decimal
    status: str  # pending | recovered | lost


@dataclass(frozen=True)
class AttemptView:
    attempt_number: int
    method: str
    error_reason: str | None = None


@dataclass(frozen=True)
class CustomerView:
    recovery_propensity: float
    contact_count_today: int = 0


@dataclass(frozen=True)
class PolicyContext:
    order: OrderView
    attempt: AttemptView
    merchant: Merchant
    customer: CustomerView

    @property
    def is_terminal(self) -> bool:
        return self.order.status in ("recovered", "lost")
