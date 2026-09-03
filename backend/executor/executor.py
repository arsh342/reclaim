"""Safe executor with idempotency and policy re-check."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Order, RecoveryAction
from backend.policy.constraints import get_allowed_actions, RETRY_NOW, RETRY_DELAYED, PAYMENT_LINK, WHATSAPP_NUDGE, ALTERNATE_METHOD, NO_ACTION


@dataclass
class ActionResult:
    success: bool
    action_id: Optional[int] = None
    reason: Optional[str] = None
    scheduled_at: Optional[datetime] = None


async def cancel_pending_actions(session: AsyncSession, order_id: str, reason: str) -> int:
    """Cancel all pending recovery actions for an order."""
    stmt = select(RecoveryAction).where(
        RecoveryAction.order_id == order_id,
        RecoveryAction.status == "scheduled",
    )
    result = await session.execute(stmt)
    actions = result.scalars().all()
    
    count = 0
    for action in actions:
        action.status = "cancelled"
        action.cancelled_at = datetime.now(timezone.utc)
        action.reason = reason
        count += 1
    
    return count


async def get_pending_action(session: AsyncSession, order_id: str) -> Optional[RecoveryAction]:
    """Get pending recovery action for order."""
    stmt = select(RecoveryAction).where(
        RecoveryAction.order_id == order_id,
        RecoveryAction.status == "scheduled",
    ).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_recovery_action(
    session: AsyncSession,
    order_id: str,
    action_type: str,
    expected_value: Decimal,
) -> RecoveryAction:
    """Create a recovery action record (idempotent)."""
    # Check for existing pending action
    existing = await get_pending_action(session, order_id)
    if existing:
        return existing
    
    action = RecoveryAction(
        order_id=order_id,
        action_type=action_type,
        expected_value=expected_value,
        status="scheduled",
    )
    session.add(action)
    await session.flush()
    return action


async def execute_recovery_action(
    session: AsyncSession,
    order_id: str,
    action_type: str,
    delay_minutes: int = 0,
) -> ActionResult:
    """Execute a recovery action with safety checks.
    
    For immediate actions (delay_minutes=0), marks as executed.
    For delayed actions (delay_minutes>0), schedules for later execution.
    NO_ACTION is a no-op that always succeeds.
    """
    # NO_ACTION is a no-op - always succeeds without changing state
    if action_type == NO_ACTION:
        from backend.policy.scoring import calculate_expected_value
        expected_value = await calculate_expected_value(session, order_id, action_type)
        action = await create_recovery_action(session, order_id, action_type, expected_value)
        action.status = "executed"
        action.executed_at = datetime.now(timezone.utc)
        await session.flush()
        return ActionResult(
            success=True,
            action_id=action.action_id,
            reason="No action required",
            scheduled_at=action.scheduled_at,
        )

    # Re-check policy immediately before execution
    allowed = await get_allowed_actions(session, order_id)
    if action_type not in allowed:
        return ActionResult(
            success=False,
            reason=f"Policy rejection at execution: {action_type} not in allowed actions",
        )
    
    # Idempotency: check for existing pending action
    existing = await get_pending_action(session, order_id)
    if existing:
        return ActionResult(
            success=False,
            reason=f"Action already pending: {existing.action_type}",
            action_id=existing.action_id,
        )
    
    # Get order for amount
    order = await session.get(Order, order_id)
    if not order:
        return ActionResult(success=False, reason="Order not found")
    
    # Calculate expected value
    from backend.policy.scoring import calculate_expected_value
    expected_value = await calculate_expected_value(session, order_id, action_type)
    
    # Create recovery action
    action = await create_recovery_action(session, order_id, action_type, expected_value)
    
    if delay_minutes > 0:
        # Schedule for later execution
        action.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        action.status = "scheduled"
        await session.flush()
        
        return ActionResult(
            success=True,
            action_id=action.action_id,
            reason=f"Scheduled for execution in {delay_minutes} minutes",
            scheduled_at=action.scheduled_at,
        )
    else:
        # Execute immediately
        action.status = "executed"
        action.executed_at = datetime.now(timezone.utc)
        
        # Update order status to recovered and cancel other pending actions
        order = await session.get(Order, order_id)
        if order:
            order.status = "recovered"
        
        # Cancel other pending actions for this order
        await cancel_pending_actions(session, order_id, "Payment recovered via recovery action")
        
        await session.flush()
        
        return ActionResult(
            success=True,
            action_id=action.action_id,
            scheduled_at=action.scheduled_at,
        )


async def schedule_recovery_action(
    session: AsyncSession,
    order_id: str,
    action_type: str,
    delay_minutes: int = 0,
) -> ActionResult:
    """Schedule a recovery action for later execution."""
    if action_type == NO_ACTION:
        from backend.policy.scoring import calculate_expected_value
        expected_value = await calculate_expected_value(session, order_id, action_type)
        action = await create_recovery_action(session, order_id, action_type, expected_value)
        action.status = "executed"
        action.executed_at = datetime.now(timezone.utc)
        await session.flush()
        return ActionResult(
            success=True,
            action_id=action.action_id,
            reason="No action required",
            scheduled_at=action.scheduled_at,
        )

    allowed = await get_allowed_actions(session, order_id)
    if action_type not in allowed:
        return ActionResult(
            success=False,
            reason=f"Policy rejection: {action_type} not allowed",
        )
    
    existing = await get_pending_action(session, order_id)
    if existing:
        return ActionResult(
            success=False,
            reason=f"Action already pending: {existing.action_type}",
            action_id=existing.action_id,
        )
    
    from backend.policy.scoring import calculate_expected_value
    expected_value = await calculate_expected_value(session, order_id, action_type)
    
    action = await create_recovery_action(session, order_id, action_type, expected_value)
    
    if delay_minutes > 0:
        action.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    
    return ActionResult(
        success=True,
        action_id=action.action_id,
        scheduled_at=action.scheduled_at,
    )


async def complete_recovery_action(
    session: AsyncSession,
    action_id: int,
    success: bool = True,
    reason: Optional[str] = None,
) -> ActionResult:
    """Mark a recovery action as completed and update order status.
    
    If success=True, marks order as recovered and cancels other pending actions.
    If success=False, marks action as failed.
    """
    action = await session.get(RecoveryAction, action_id)
    if not action:
        return ActionResult(success=False, reason="Action not found")
    
    if success:
        action.status = "executed"
        action.executed_at = datetime.now(timezone.utc)
        action.reason = reason or "Recovery successful"
        
        # Update order status to recovered
        order = await session.get(Order, action.order_id)
        if order:
            order.status = "recovered"
        
        # Cancel other pending actions for this order
        await cancel_pending_actions(session, action.order_id, "Payment recovered via recovery action")
        
        await session.flush()
        
        return ActionResult(
            success=True,
            action_id=action.action_id,
            reason="Recovery completed successfully",
        )
    else:
        action.status = "failed"
        action.reason = reason or "Recovery failed"
        await session.flush()
        
        return ActionResult(
            success=False,
            action_id=action.action_id,
            reason=action.reason,
        )