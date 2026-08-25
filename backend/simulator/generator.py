"""Order generator for evaluation."""

from decimal import Decimal
from typing import List, Optional

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Merchant, Customer, Order, PaymentAttempt
from backend.core.config import settings


MERCHANT_ID = "merchant_default"


async def get_or_create_merchant(session: AsyncSession) -> Merchant:
    merchant = await session.get(Merchant, MERCHANT_ID)
    if not merchant:
        merchant = Merchant(
            merchant_id=MERCHANT_ID,
            max_retries=3,
            contact_budget_per_day=2,
        )
        session.add(merchant)
        await session.flush()
    return merchant


ERROR_REASONS = [
    "insufficient_funds",
    "issuer_timeout",
    "card_blocked",
    "invalid_card",
    "network_error",
]

ERROR_REASON_WEIGHTS = [0.35, 0.25, 0.10, 0.05, 0.25]

METHODS = ["card", "upi", "netbanking"]
METHOD_WEIGHTS = [0.6, 0.25, 0.15]


async def generate_orders(
    session: AsyncSession,
    n: int,
    seed: int = 42,
) -> List[Order]:
    """Generate n orders with payment attempts."""
    random.seed(seed)
    
    merchant = await get_or_create_merchant(session)
    
    orders = []
    for i in range(n):
        order_id = f"order_{i:04d}"
        customer_id = f"cust_{i:04d}"
        
        # Create customer
        customer = await session.get(Customer, customer_id)
        if not customer:
            customer = Customer(
                customer_id=customer_id,
                recovery_propensity=Decimal(str(round(random.uniform(0.2, 0.8), 2))),
                payment_method_preference=random.choice(METHODS),
                historical_success_rate=Decimal(str(round(random.uniform(0.3, 0.9), 2))),
                customer_value=Decimal(str(round(random.uniform(1000, 50000), 2))),
            )
            session.add(customer)
        
        # Create order
        amount = Decimal(str(round(random.uniform(500, 25000), 2)))
        order = Order(
            order_id=order_id,
            merchant_id=MERCHANT_ID,
            customer_id=customer_id,
            amount=amount,
            currency="INR",
            status="pending",
        )
        session.add(order)
        await session.flush()
        
        # Generate 1-3 payment attempts
        n_attempts = random.randint(1, 3)
        for attempt_num in range(1, n_attempts + 1):
            method = random.choices(METHODS, weights=METHOD_WEIGHTS)[0]
            error_reason = random.choices(ERROR_REASONS, weights=ERROR_REASON_WEIGHTS)[0]
            
            if attempt_num == n_attempts and random.random() < 0.3:
                # Some final attempts succeed
                status = "captured"
                error_reason = None
                order.status = "recovered"
            else:
                status = "failed"
            
            attempt = PaymentAttempt(
                payment_id=f"pay_{order_id}_{attempt_num}",
                order_id=order_id,
                attempt_number=attempt_num,
                method=method,
                status=status,
                error_reason=error_reason,
                error_source="customer" if error_reason != "network_error" else "network",
                error_step="payment_authentication",
            )
            session.add(attempt)
        
        orders.append(order)
    
    await session.commit()
    return orders