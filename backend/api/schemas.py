"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class WebhookEventRequest(BaseModel):
    entity: str = Field(..., pattern="^event$")
    account_id: str
    event: str = Field(..., pattern="^(payment\\.failed|payment\\.captured)$")
    contains: List[str]
    payload: Dict[str, Any]

    @field_validator("entity")
    @classmethod
    def validate_entity(cls, v: str) -> str:
        if v != "event":
            raise ValueError("entity must be 'event'")
        return v


class PaymentEntity(BaseModel):
    id: str
    order_id: str
    amount: int
    currency: str
    method: str
    status: str
    attempt_number: int
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_reason: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None


class PaymentPayload(BaseModel):
    payment: PaymentEntity


class WebhookEventPayload(BaseModel):
    entity: str = "event"
    account_id: str
    event: str
    contains: List[str]
    payload: PaymentPayload


class IngestResult(BaseModel):
    status: str  # "processed" | "duplicate"
    event_id: str
    order_id: Optional[str] = None
    message: str


class OrderSummary(BaseModel):
    order_id: str
    merchant_id: str
    customer_id: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    latest_attempt_status: Optional[str] = None
    latest_attempt_reason: Optional[str] = None


class PaymentAttemptSchema(BaseModel):
    payment_id: str
    order_id: str
    attempt_number: int
    method: str
    status: str
    error_code: Optional[str] = None
    error_reason: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    created_at: datetime


class RecoveryActionSchema(BaseModel):
    action_id: int
    order_id: str
    action_type: str
    expected_value: Decimal
    status: str
    scheduled_at: datetime
    executed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    reason: Optional[str] = None


class AgentEventSchema(BaseModel):
    event_seq: int
    run_id: str
    order_id: str
    agent_stage: str
    event_type: str
    payload: Dict[str, Any]
    created_at: datetime


class AgentRunSchema(BaseModel):
    run_id: str
    order_id: str
    status: str
    current_stage: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    final_action: Optional[str] = None
    final_reason: Optional[str] = None


class CandidateAction(BaseModel):
    action: str
    probability: float
    expected_value: float
    intervention_cost: float
    friction_cost: float
    risk_penalty: float


class DecisionAnalysis(BaseModel):
    diagnosis: Dict[str, Any]
    candidates: List[CandidateAction]
    chosen_action: Optional[str] = None
    stop_conditions: List[str] = []


class PolicyMetrics(BaseModel):
    policy_name: str
    recovered_revenue: float
    recovery_rate: float
    total_revenue_at_risk: float
    unnecessary_interventions: int
    contact_count: int
    avg_time_to_resolution_hours: float
    policy_rejections: int


class EvalSummary(BaseModel):
    always_retry: PolicyMetrics
    reclaim: PolicyMetrics
    incremental_revenue: float
    incremental_recovery_rate: float
    total_orders: int
    seed: int


class OrderDetail(BaseModel):
    order: OrderSummary
    attempts: List[PaymentAttemptSchema]
    recovery_actions: List[RecoveryActionSchema]
    agent_runs: List[AgentRunSchema]
    decision_analysis: Optional[DecisionAnalysis] = None


class HealthResponse(BaseModel):
    status: str


class SimulateWebhookRequest(BaseModel):
    entity: str = "event"
    account_id: str
    event: str = Field(..., pattern="^(payment\\.failed|payment\\.captured)$")
    contains: List[str]
    payload: PaymentPayload