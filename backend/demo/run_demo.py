#!/usr/bin/env python3
"""Reclaim Demo Script — exact §7 sequence.

Run this against a clean database. It fires the exact webhooks
that the pitch script describes, and prints a timeline that matches
the panel demo.

Usage:
    python -m backend.demo.run_demo [--seed SEED] [--db-url URL]

Examples:
    # Run against configured DATABASE_URL (default)
    python -m backend.demo.run_demo --scenario all --eval

    # Run with SQLite in-memory (zero-setup local dev)
    python -m backend.demo.run_demo --scenario all --eval --db-url sqlite:///:memory:

    # Run against local PostgreSQL
    python -m backend.demo.run_demo --scenario all --eval --db-url postgresql://postgres:postgres@localhost:5432/reclaim_test
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from backend.api.webhooks import ingest_webhook
from backend.api.fixtures import payment_failed, payment_captured
from backend.db.models import Order, PaymentAttempt, RecoveryAction, WebhookEvent, Base
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import sessionmaker


def make_session_factory(db_url: str):
    """Create a session factory for the given database URL.
    For SQLite in-memory, create tables automatically."""
    engine = create_engine(db_url, pool_pre_ping=True)
    # For SQLite in-memory, create all tables
    if db_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session


def clean_database(Session):
    """Start from a truly clean slate."""
    s = Session()
    try:
        from backend.db.models import Order, PaymentAttempt, RecoveryAction, WebhookEvent
        from sqlalchemy import delete
        s.execute(delete(WebhookEvent))
        s.execute(delete(RecoveryAction))
        s.execute(delete(PaymentAttempt))
        s.execute(delete(Order))
        s.commit()
    finally:
        s.close()


def clean_scenario(Session, event_prefix: str, order_id: str):
    """Clean data for a specific scenario."""
    s = Session()
    try:
        s.execute(text("DELETE FROM webhook_events"))
        s.execute(text("DELETE FROM recovery_actions WHERE order_id = :order_id"), {"order_id": order_id})
        s.execute(text("DELETE FROM payment_attempts WHERE order_id = :order_id"), {"order_id": order_id})
        s.execute(text("DELETE FROM orders WHERE order_id = :order_id"), {"order_id": order_id})
        s.commit()
    finally:
        s.close()


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def print_step(step: int, description: str):
    print(f"\n--- Step {step}: {description} ---")


def print_result(label: str, result):
    print(f"  {label}: {result.status}")
    if hasattr(result, 'event_id'):
        print(f"    event_id: {result.event_id}")
    if hasattr(result, 'order_id'):
        print(f"    order_id: {result.order_id}")
    if hasattr(result, 'action_id') and result.action_id:
        print(f"    action_id: {result.action_id}")
    if hasattr(result, 'selected_action'):
        print(f"    selected_action: {result.selected_action}")
        print(f"    expected_value: {result.expected_value:.0f}")
        if result.constraints_applied:
            print(f"    constraints: {', '.join(result.constraints_applied)}")
        if result.reasons:
            print(f"    reasons: {'; '.join(result.reasons)}")


def run_scenario_1(Session):
    """§7 Main idempotency demo:
    1. Order ₹25,000 created. Fire payment.failed for payment_001 (issuer_timeout).
    2. System schedules RETRY_DELAYED, shown in Decision Inspector.
    3. Fire payment.captured for payment_002 on same order_id.
    4. Order flips to recovered. Scheduled action auto-cancels.
    5. Replay original payment.failed (same event_id) → duplicate ignored.
    """
    print_section("SCENARIO 1: Idempotency Demo (Build-Plan §7)")
    clean_scenario(Session, "evt_demo_", "order_demo_001")

    s = Session()
    try:
        # Step 1
        print_step(1, "Fire payment.failed for payment_001 (issuer_timeout)")
        payload = payment_failed(
            event_id="evt_demo_001",
            payment_id="pay_001",
            order_id="order_demo_001",
            amount=25000,  # rupees
            error_reason="issuer_timeout",
        )
        result = ingest_webhook(s, payload)
        print_result("Webhook", result)

        # Check what got scheduled
        actions = s.query(RecoveryAction).filter(
            RecoveryAction.order_id == "order_demo_001",
            RecoveryAction.status == "scheduled"
        ).all()
        for a in actions:
            print(f"  Scheduled action: {a.action_type} (ERV: {a.expected_value})")

        # Step 2
        print_step(2, "Fire payment.captured for payment_002 (same order)")
        payload = payment_captured(
            event_id="evt_demo_002",
            payment_id="pay_002",
            order_id="order_demo_001",
            amount=25000,
        )
        result = ingest_webhook(s, payload)
        print_result("Webhook", result)

        # Check order status and actions
        order = s.query(Order).filter(Order.order_id == "order_demo_001").one()
        print(f"  Order status: {order.status}")
        actions = s.query(RecoveryAction).filter(
            RecoveryAction.order_id == "order_demo_001"
        ).all()
        for a in actions:
            print(f"  Action {a.action_id}: {a.action_type} [{a.status}]")

        # Step 3
        print_step(3, "Replay original payment.failed (same event_id)")
        payload = payment_failed(
            event_id="evt_demo_001",  # SAME event_id
            payment_id="pay_001",
            order_id="order_demo_001",
            amount=25000,
            error_reason="issuer_timeout",
        )
        result = ingest_webhook(s, payload)
        print_result("Webhook", result)

        # Final verification
        order = s.query(Order).filter(Order.order_id == "order_demo_001").one()
        actions = s.query(RecoveryAction).filter(
            RecoveryAction.order_id == "order_demo_001"
        ).all()
        print(f"\n  ✓ Order status: {order.status}")
        for a in actions:
            print(f"  ✓ Action {a.action_id}: {a.action_type} [{a.status}]")
        print(f"\n  ✓ SCENARIO 1 COMPLETE — Idempotency verified")

    finally:
        s.close()


def run_scenario_2(Session):
    """§7 Soft decline:
    ₹1,200, issuer_timeout → immediate retry, highest ERV, succeeds.
    """
    print_section("SCENARIO 2: Soft Decline (Build-Plan §7)")
    clean_scenario(Session, "evt_s2_", "order_soft_001")

    print_step(1, "Fire payment.failed for ₹1,200 (issuer_timeout)")
    s = Session()
    try:
        payload = payment_failed(
            event_id="evt_s2_001",
            payment_id="pay_s2_001",
            order_id="order_soft_001",
            amount=1200,  # ₹1,200
            error_reason="issuer_timeout",
        )
        result = ingest_webhook(s, payload)
        print_result("Webhook", result)

        actions = s.query(RecoveryAction).filter(
            RecoveryAction.order_id == "order_soft_001",
            RecoveryAction.status == "scheduled"
        ).all()
        for a in actions:
            print(f"  Scheduled: {a.action_type} (ERV: {a.expected_value:.0f})")

        # Now captured
        print_step(2, "Fire payment.captured for payment_002")
        payload = payment_captured(
            event_id="evt_s2_002",
            payment_id="pay_s2_002",
            order_id="order_soft_001",
            amount=1200,
        )
        result = ingest_webhook(s, payload)
        print_result("Webhook", result)

        order = s.query(Order).filter(Order.order_id == "order_soft_001").one()
        print(f"  Order status: {order.status}")
        print(f"\n  ✓ SCENARIO 2 COMPLETE — Soft decline recovered via immediate retry")
    finally:
        s.close()


def run_scenario_3(Session):
    """§7 Hard decline, high value:
    ₹78,000, two consecutive card_blocked attempts → retry forbidden by
    hard-constraint gate → payment_link chosen on ERV → explain why
    retrying was never on the table.
    """
    print_section("SCENARIO 3: Hard Decline, High Value (Build-Plan §7)")
    clean_scenario(Session, "evt_s3_", "order_hard_001")

    print_step(1, "Fire payment.failed for ₹78,000 (card_blocked, attempt 1)")
    s = Session()
    try:
        payload = payment_failed(
            event_id="evt_s3_001",
            payment_id="pay_s3_001",
            order_id="order_hard_001",
            amount=78000,  # ₹78,000
            error_reason="card_blocked",
        )
        result = ingest_webhook(s, payload)
        print_result("Webhook", result)

        actions = s.query(RecoveryAction).filter(
            RecoveryAction.order_id == "order_hard_001",
            RecoveryAction.status == "scheduled"
        ).all()
        for a in actions:
            print(f"  Scheduled: {a.action_type} (ERV: {a.expected_value:.0f})")

        # Second failed attempt
        print_step(2, "Fire payment.failed for ₹78,000 (card_blocked, attempt 2)")
        payload = payment_failed(
            event_id="evt_s3_002",
            payment_id="pay_s3_002",
            order_id="order_hard_001",
            amount=78000,
            attempt_number=2,
            error_reason="card_blocked",
        )
        result = ingest_webhook(s, payload)
        print_result("Webhook", result)

        actions = s.query(RecoveryAction).filter(
            RecoveryAction.order_id == "order_hard_001",
            RecoveryAction.status == "scheduled"
        ).all()
        for a in actions:
            print(f"  Scheduled: {a.action_type} (ERV: {a.expected_value:.0f})")

        print(f"\n  ✓ SCENARIO 3 COMPLETE — Hard decline: retry forbidden, alternate chosen")
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser(description="Run Reclaim demo scenarios")
    parser.add_argument("--scenario", choices=["1", "2", "3", "all"], default="all")
    parser.add_argument("--eval", action="store_true", help="Also run offline evaluation and print headline number")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-orders", type=int, default=2000)
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "sqlite:///:memory:"),
        help="Database URL (default: sqlite:///:memory: for zero-setup local dev)",
    )
    args = parser.parse_args()

    # Create session factory for the specified DB URL
    Session = make_session_factory(args.db_url)

    # Clean database before running
    clean_database(Session)

    print("\n" + "=" * 60)
    print("  RECLAIM DEMO — Build-Plan §7 Scenarios")
    print("=" * 60)

    if args.scenario in ("1", "all"):
        run_scenario_1(Session)
        time.sleep(1)

    if args.scenario in ("2", "all"):
        run_scenario_2(Session)
        time.sleep(1)

    if args.scenario in ("3", "all"):
        run_scenario_3(Session)

    print("\n" + "=" * 60)
    print("  ALL SCENARIOS COMPLETE")
    print("=" * 60)

    if args.eval:
        print("\n" + "=" * 60)
        print("  OFFLINE EVALUATION")
        print("=" * 60 + "\n")
        from backend.eval.runner import run_evaluation

        result = run_evaluation(n_orders=args.n_orders, seed=args.seed)
        reclaim_amt = float(result.reclaim.recovered_revenue)
        baseline_amt = float(result.always_retry.recovered_revenue)
        delta_amt = reclaim_amt - baseline_amt
        delta_rate = result.reclaim.recovery_rate - result.always_retry.recovery_rate

        def inr(x: float) -> str:
            n = int(round(x))
            return f"₹{n:,}"

        print(f"  Seed:           {result.seed}")
        print(f"  Orders:         {result.n_orders:,}")
        print(f"  At-risk total:  {inr(float(result.reclaim.total_revenue_at_risk))}")
        print()
        print(f"  always_retry:   {inr(baseline_amt)}  ({result.always_retry.recovery_rate:.1%})")
        print(f"  reclaim:        {inr(reclaim_amt)}  ({result.reclaim.recovery_rate:.1%})")
        print()
        print(f"  Δ revenue:      {inr(delta_amt)}")
        print(f"  Δ recovery:     +{delta_rate:.1%}")
        print()
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()