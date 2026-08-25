"""SQLAlchemy models for Reclaim."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    contact_budget_per_day: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="merchant")


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    recovery_propensity: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    payment_method_preference: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    historical_success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    customer_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String, ForeignKey("merchants.merchant_id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("customers.customer_id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)  # pending, recovered, lost
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    merchant: Mapped["Merchant"] = relationship(back_populates="orders")
    customer: Mapped["Customer"] = relationship(back_populates="orders")
    payment_attempts: Mapped[list["PaymentAttempt"]] = relationship(back_populates="order", order_by="PaymentAttempt.attempt_number")
    recovery_actions: Mapped[list["RecoveryAction"]] = relationship(back_populates="order")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="order")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    payment_id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.order_id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # failed, captured, pending
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_step: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="payment_attempts")

    __table_args__ = (
        UniqueConstraint("order_id", "attempt_number", name="uq_order_attempt"),
        Index("ix_payment_attempts_order_id", "order_id"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_webhook_events_processed_at", "processed_at"),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: f"run_{uuid.uuid4().hex[:12]}")
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.order_id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)  # running, completed, failed
    current_stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    final_action: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    final_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="agent_runs")
    events: Mapped[list["AgentEvent"]] = relationship(back_populates="run", order_by="AgentEvent.event_seq")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    event_seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("agent_runs.run_id"), nullable=False)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.order_id"), nullable=False)
    agent_stage: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run: Mapped["AgentRun"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_agent_events_run_id", "run_id"),
        Index("ix_agent_events_order_id", "order_id"),
        Index("ix_agent_events_created_at", "created_at"),
    )


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    action_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.order_id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    expected_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, default="scheduled", nullable=False)  # scheduled, executed, cancelled
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="recovery_actions")

    __table_args__ = (
        Index("ix_recovery_actions_order_id", "order_id"),
        Index("ix_recovery_actions_status", "status"),
    )