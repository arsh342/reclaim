"""Query Repository — centralized database queries for the agent tools.

Eliminates duplicated query logic across get_order_context, get_allowed_actions,
estimate_recovery, and execute_recovery_action.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Customer, Merchant, Order, PaymentAttempt
from backend.policy.types import (
    ActionType,
    AttemptView,
    CustomerView,
    Merchant as MerchantView,
    OrderView,
    PolicyContext,
)


class QueryRepository:
    """Centralized read-only queries for agent tools."""

    def __init__(self, db: Session):
        self.db = db

    # --- Core entity lookups ---

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.db.execute(
            select(Order).where(Order.order_id == order_id)
        ).scalar_one_or_none()

    def get_order_locked(self, order_id: str) -> Optional[Order]:
        """Row-lock the order for update."""
        return self.db.execute(
            select(Order).where(Order.order_id == order_id).with_for_update()
        ).scalar_one_or_none()

    def get_merchant(self, merchant_id: Optional[str]) -> Optional[Merchant]:
        if not merchant_id:
            return None
        return self.db.execute(
            select(Merchant).where(Merchant.merchant_id == merchant_id)
        ).scalar_one_or_none()

    def get_customer(self, customer_id: Optional[str]) -> Optional[Customer]:
        if not customer_id or not customer_id.strip():
            return None
        result = self.db.execute(
            select(Customer).where(Customer.customer_id == customer_id)
        ).scalars().all()
        if len(result) > 1:
            raise ValueError(f"Multiple customers found for customer_id={customer_id}")
        return result[0] if result else None

    def get_latest_attempt(self, order_id: str) -> Optional[PaymentAttempt]:
        return self.db.execute(
            select(PaymentAttempt)
            .where(PaymentAttempt.order_id == order_id)
            .order_by(PaymentAttempt.attempt_number.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_all_attempts(self, order_id: str) -> list[PaymentAttempt]:
        return self.db.execute(
            select(PaymentAttempt)
            .where(PaymentAttempt.order_id == order_id)
            .order_by(PaymentAttempt.attempt_number)
        ).scalars().all()

    # --- Composite queries for tool contexts ---

    def get_order_context(self, order_id: str):
        """Full context for Tool 1: get_order_context."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"order {order_id} not found")

        merchant = self.get_merchant(order.merchant_id)
        customer = self.get_customer(order.customer_id)
        attempts = self.get_all_attempts(order_id)

        return {
            "order": order,
            "merchant": merchant,
            "customer": customer,
            "attempts": attempts,
        }

    def get_allowed_actions_context(self, order_id: str):
        """Context for Tool 2: get_allowed_actions."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"order {order_id} not found")

        merchant = self.get_merchant(order.merchant_id)
        customer = self.get_customer(order.customer_id)
        attempt = self.get_latest_attempt(order_id)

        if not attempt:
            raise ValueError(f"no payment attempts for order {order_id}")

        return {
            "order": order,
            "merchant": merchant,
            "customer": customer,
            "attempt": attempt,
        }

    def get_estimate_recovery_context(self, order_id: str):
        """Context for Tool 3: estimate_recovery."""
        order = self.get_order(order_id)
        if order is None:
            raise ValueError(f"order {order_id} not found")

        merchant = self.get_merchant(order.merchant_id)
        customer = self.get_customer(order.customer_id)
        attempt = self.get_latest_attempt(order_id)

        if not attempt:
            raise ValueError(f"no payment attempts for order {order_id}")

        return {
            "order": order,
            "merchant": merchant,
            "customer": customer,
            "attempt": attempt,
        }

    def get_execute_recovery_context(self, order_id: str, lock: bool = False):
        """Context for Tool 4: execute_recovery_action."""
        getter = self.get_order_locked if lock else self.get_order
        order = getter(order_id)
        if order is None:
            raise ValueError(f"order {order_id} not found")

        merchant = self.get_merchant(order.merchant_id)
        customer = self.get_customer(order.customer_id)
        attempt = self.get_latest_attempt(order_id)

        if not attempt:
            raise ValueError(f"no payment attempts for order {order_id}")

        return {
            "order": order,
            "merchant": merchant,
            "customer": customer,
            "attempt": attempt,
        }

    # --- PolicyContext builders ---

    def build_allowed_actions_policy_ctx(self, order_id: str) -> PolicyContext:
        """Build PolicyContext for get_allowed_actions."""
        ctx = self.get_allowed_actions_context(order_id)
        return self._build_policy_ctx(ctx["order"], ctx["merchant"], ctx["customer"], ctx["attempt"])

    def build_estimate_recovery_policy_ctx(self, order_id: str) -> PolicyContext:
        """Build PolicyContext for estimate_recovery."""
        ctx = self.get_estimate_recovery_context(order_id)
        return self._build_policy_ctx(ctx["order"], ctx["merchant"], ctx["customer"], ctx["attempt"])

    def build_execute_recovery_policy_ctx(self, order_id: str, lock: bool = False) -> PolicyContext:
        """Build PolicyContext for execute_recovery_action."""
        ctx = self.get_execute_recovery_context(order_id, lock=lock)
        return self._build_policy_ctx(ctx["order"], ctx["merchant"], ctx["customer"], ctx["attempt"])

    def _build_policy_ctx(
        self,
        order: Order,
        merchant: Optional[Merchant],
        customer: Optional[Customer],
        attempt: PaymentAttempt,
    ) -> PolicyContext:
        return PolicyContext(
            order=OrderView(
                order_id=order.order_id,
                amount=order.amount,
                status=order.status,
            ),
            attempt=AttemptView(
                attempt_number=attempt.attempt_number,
                method=attempt.method,
                error_reason=attempt.error_reason,
            ),
            merchant=MerchantView(
                merchant_id=merchant.merchant_id if merchant else "unknown",
                max_retries=merchant.max_retries if merchant else 3,
                contact_budget_per_day=merchant.contact_budget_per_day if merchant else 2,
            ),
            customer=CustomerView(
                recovery_propensity=float(customer.recovery_propensity) if customer else 0.5,
                contact_count_today=0,
            ),
        )