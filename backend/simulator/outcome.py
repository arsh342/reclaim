"""Simulator outcome calculation."""

from decimal import Decimal
from typing import Dict, Optional

import yaml

from backend.db.models import Order, PaymentAttempt
from backend.simulator.config_loader import load_config


async def simulate_recovery_probability(
    order: Order,
    attempt: PaymentAttempt,
    action: str,
) -> Decimal:
    """Calculate P(recovery | context, action) using simulator config."""
    config = load_config()
    
    # Base rate for error reason
    error_reason = attempt.error_reason or "unknown"
    base_rate = config.base_rate.get(error_reason, 0.3)
    
    # Method factor
    method_factor = config.method_factor.get(attempt.method, 1.0)
    
    # Action fit
    action_fit = config.action_fit.get(error_reason, {}).get(action, 1.0)
    
    # Calculate probability
    probability = base_rate * method_factor * action_fit
    
    # Clip to [0, 0.95]
    probability = max(0.0, min(0.95, probability))
    
    return Decimal(str(probability))


def simulate_outcome(
    order: Order,
    attempt: PaymentAttempt,
    action: str,
    seed: Optional[int] = None,
) -> bool:
    """Simulate whether recovery succeeds (for evaluation)."""
    import random
    
    # Use local Random instance to avoid affecting global state
    rng = random.Random(seed) if seed is not None else random
    
    config = load_config()
    error_reason = attempt.error_reason or "unknown"
    base_rate = config.base_rate.get(error_reason, 0.3)
    method_factor = config.method_factor.get(attempt.method, 1.0)
    action_fit = config.action_fit.get(error_reason, {}).get(action, 1.0)
    
    probability = base_rate * method_factor * action_fit
    probability = max(0.0, min(0.95, probability))
    
    return rng.random() < probability