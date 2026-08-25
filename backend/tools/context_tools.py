"""Context tools."""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Order, PaymentAttempt, Merchant, Customer
from backend.tools.registry import tool_registry


async def get_order_context(order_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Get full order context including customer, merchant, and attempts."""
    order = await session.get(Order, order_id)
    if not order:
        return {"error": "Order not found"}
    
    # Get attempts
    stmt = select(PaymentAttempt).where(PaymentAttempt.order_id == order_id).order_by(PaymentAttempt.attempt_number)
    result = await session.execute(stmt)
    attempts = result.scalars().all()
    
    # Get merchant
    merchant = await session.get(Merchant, order.merchant_id)
    
    # Get customer
    customer = await session.get(Customer, order.customer_id)
    
    return {
        "order": {
            "order_id": order.order_id,
            "merchant_id": order.merchant_id,
            "customer_id": order.customer_id,
            "amount": float(order.amount),
            "currency": order.currency,
            "status": order.status,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        },
        "attempts": [
            {
                "payment_id": a.payment_id,
                "attempt_number": a.attempt_number,
                "method": a.method,
                "status": a.status,
                "error_code": a.error_code,
                "error_reason": a.error_reason,
                "error_source": a.error_source,
                "error_step": a.error_step,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in attempts
        ],
        "merchant": {
            "merchant_id": merchant.merchant_id if merchant else None,
            "max_retries": merchant.max_retries if merchant else 3,
            "contact_budget_per_day": merchant.contact_budget_per_day if merchant else 2,
        } if merchant else None,
        "customer": {
            "customer_id": customer.customer_id if customer else None,
            "recovery_propensity": float(customer.recovery_propensity) if customer else 0.5,
            "payment_method_preference": customer.payment_method_preference if customer else None,
            "historical_success_rate": float(customer.historical_success_rate) if customer else None,
            "customer_value": float(customer.customer_value) if customer else 10000,
        } if customer else None,
        "latest_error": attempts[-1].error_reason if attempts else None,
    }


async def get_customer_history(customer_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Get customer recovery history."""
    customer = await session.get(Customer, customer_id)
    if not customer:
        return {"error": "Customer not found"}
    
    # Get customer's orders
    stmt = select(Order).where(Order.customer_id == customer_id)
    result = await session.execute(stmt)
    orders = result.scalars().all()
    
    return {
        "customer_id": customer.customer_id,
        "recovery_propensity": float(customer.recovery_propensity),
        "payment_method_preference": customer.payment_method_preference,
        "historical_success_rate": float(customer.historical_success_rate) if customer.historical_success_rate else None,
        "customer_value": float(customer.customer_value),
        "order_count": len(orders),
    }


# Register tools
tool_registry.register(
    "get_order_context",
    get_order_context,
    "Get order, customer, merchant, and payment attempt context",
    read_only=True,
    financial_side_effect=False,
)

tool_registry.register(
    "get_customer_history",
    get_customer_history,
    "Get customer recovery profile and history",
    read_only=True,
    financial_side_effect=False,
)