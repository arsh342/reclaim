from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base


class Merchant(Base):
    __tablename__ = "merchants"

    merchant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    contact_budget_per_day: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="merchant")


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(Text, primary_key=True)
    recovery_propensity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    payment_method_preference: Mapped[str | None] = mapped_column(Text)
    historical_success_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    customer_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    merchant_id: Mapped[str | None] = mapped_column(Text, ForeignKey("merchants.merchant_id"))
    customer_id: Mapped[str | None] = mapped_column(Text, ForeignKey("customers.customer_id"))
    amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(Text, default="INR", nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    merchant: Mapped[Merchant | None] = relationship(back_populates="orders")
    customer: Mapped[Customer | None] = relationship(back_populates="orders")
    payment_attempts: Mapped[list["PaymentAttempt"]] = relationship(back_populates="order")
    recovery_actions: Mapped[list["RecoveryAction"]] = relationship(back_populates="order")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    payment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.order_id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_description: Mapped[str | None] = mapped_column(Text)
    error_reason: Mapped[str | None] = mapped_column(Text)
    error_source: Mapped[str | None] = mapped_column(Text)
    error_step: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order: Mapped[Order] = relationship(back_populates="payment_attempts")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    action_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(Text, ForeignKey("orders.order_id"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="scheduled", nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    explanation_model: Mapped[str | None] = mapped_column(Text)

    order: Mapped[Order] = relationship(back_populates="recovery_actions")
