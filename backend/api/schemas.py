"""Pydantic schemas for API responses — single source of truth for types.
These generate the OpenAPI spec which drives frontend type generation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class IngestResult(BaseModel):
    status: str
    event_id: str
    order_id: str
    action_id: Optional[int] = None


class PaymentAttemptSchema(BaseModel):
    payment_id: str
    attempt_number: int
    method: str
    status: str
    error_code: Optional[str] = None
    error_reason: Optional[str] = None
    created_at: Optional[datetime] = None


class RecoveryActionSchema(BaseModel):
    action_id: int
    action_type: str
    expected_value: float
    status: str
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    reason: Optional[str] = None
    explanation: Optional[str] = None
    explanation_model: Optional[str] = None


class OrderSummary(BaseModel):
    order_id: str
    amount: float
    currency: str
    status: str
    created_at: Optional[datetime] = None


class OrderDetail(BaseModel):
    order_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    created_at: Optional[datetime] = None
    payment_attempts: list[PaymentAttemptSchema] = []
    recovery_actions: list[RecoveryActionSchema] = []
    decision_analysis: "DecisionAnalysis"


class CandidateAction(BaseModel):
    action: str
    erv: float


class DecisionAnalysis(BaseModel):
    candidate_actions: list[CandidateAction] = []
    selected_action: Optional[str] = None


class PolicyMetrics(BaseModel):
    recovered_revenue: float
    total_revenue_at_risk: float
    recovery_rate: float
    unnecessary_interventions: int
    total_interventions: int


class EvalSummary(BaseModel):
    seed: int
    n_orders: int
    reclaim: PolicyMetrics
    always_retry: PolicyMetrics
    delta: dict[str, float]  # recovered_revenue, recovery_rate


# Update forward refs
OrderDetail.model_rebuild()
DecisionAnalysis.model_rebuild()