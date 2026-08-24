from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from backend.api.fixtures import WebhookPayload
from backend.api.webhooks import IngestResult, ingest_webhook
from backend.api.schemas import (
    OrderDetail,
    OrderSummary,
    EvalSummary,
    IngestResult,
    PolicyMetrics,
    PaymentAttemptSchema,
    RecoveryActionSchema,
    CandidateAction,
    DecisionAnalysis,
)
from backend.agent.query_repo import QueryRepository
from backend.db.models import Order, PaymentAttempt, RecoveryAction, Merchant as MerchantModel, Customer
from backend.policy.select import select_action
from backend.policy.types import PolicyContext, OrderView, AttemptView, Merchant as MerchantView, CustomerView
from backend.db.session import get_db
from backend.eval.runner import run_evaluation
from backend.agent.tools import get_order_context, get_allowed_actions, estimate_recovery
from backend.config import get_settings
from backend.db.session import SessionLocal

router = APIRouter()


@router.post("/webhooks/simulate", response_model=IngestResult)
def simulate_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db),
) -> IngestResult:
    return ingest_webhook(db, payload)


@router.get("/orders", response_model=list[OrderSummary])
def list_orders(db: Session = Depends(get_db)) -> list[OrderSummary]:
    rows = db.execute(select(Order).order_by(Order.created_at.desc()).limit(100)).scalars().all()
    return [
        OrderSummary(
            order_id=o.order_id,
            amount=float(o.amount),
            currency=o.currency,
            status=o.status,
            created_at=o.created_at,
        )
        for o in rows
    ]


@router.get("/orders/{order_id}", response_model=OrderDetail)
def get_order(order_id: str, db: Session = Depends(get_db)) -> OrderDetail:
    order = db.execute(
        select(Order)
        .where(Order.order_id == order_id)
        .options(
            selectinload(Order.payment_attempts),
            selectinload(Order.recovery_actions),
        )
    ).scalar_one_or_none()

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")

    # Build candidate-action ERV breakdown by re-running the policy decision
    # to get the full ranked alternatives (stored on the latest recovery action
    # or recomputed for display)
    erv_breakdown = []
    selected_action = None
    try:
        repo = QueryRepository(db)
        policy_ctx = repo.build_estimate_recovery_policy_ctx(order_id)
        decision = select_action(policy_ctx)
        selected_action = decision.selected_action
        erv_breakdown = [
            {"action": action, "erv": round(erv, 2)}
            for action, erv in decision.ranked
        ]
    except Exception:
        # If recomputation fails, fall back to stored recovery actions
        erv_breakdown = [
            {"action": r.action_type, "erv": float(r.expected_value)}
            for r in order.recovery_actions
        ]

    recovery_actions = sorted(
        order.recovery_actions,
        key=lambda action: action.action_id,
        reverse=True,
    )
    latest_action = recovery_actions[0] if recovery_actions else None
    if selected_action is None and latest_action:
        selected_action = latest_action.action_type

    return OrderDetail(
        order_id=order.order_id,
        merchant_id=order.merchant_id,
        customer_id=order.customer_id,
        amount=float(order.amount),
        currency=order.currency,
        status=order.status,
        created_at=order.created_at,
        payment_attempts=[
            PaymentAttemptSchema(
                payment_id=a.payment_id,
                attempt_number=a.attempt_number,
                method=a.method,
                status=a.status,
                error_code=a.error_code,
                error_reason=a.error_reason,
                created_at=a.created_at,
            )
            for a in order.payment_attempts
        ],
        recovery_actions=[
            RecoveryActionSchema(
                action_id=r.action_id,
                action_type=r.action_type,
                expected_value=float(r.expected_value),
                status=r.status,
                scheduled_at=r.scheduled_at,
                executed_at=r.executed_at,
                cancelled_at=r.cancelled_at,
                reason=r.reason,
                explanation=r.explanation,
                explanation_model=r.explanation_model,
            )
            for r in recovery_actions
        ],
        decision_analysis=DecisionAnalysis(
            candidate_actions=[
                CandidateAction(action=a["action"], erv=a["erv"])
                for a in erv_breakdown
            ],
            selected_action=selected_action,
        ),
    )


@router.get("/eval/summary", response_model=EvalSummary)
def eval_summary(
    n_orders: int = 2000,
    seed: int = 42,
) -> EvalSummary:
    result = run_evaluation(n_orders=n_orders, seed=seed)
    return EvalSummary(
        seed=result.seed,
        n_orders=result.n_orders,
        reclaim=PolicyMetrics(
            recovered_revenue=float(result.reclaim.recovered_revenue),
            total_revenue_at_risk=float(result.reclaim.total_revenue_at_risk),
            recovery_rate=result.reclaim.recovery_rate,
            unnecessary_interventions=result.reclaim.unnecessary_interventions,
            total_interventions=result.reclaim.total_interventions,
        ),
        always_retry=PolicyMetrics(
            recovered_revenue=float(result.always_retry.recovered_revenue),
            total_revenue_at_risk=float(result.always_retry.total_revenue_at_risk),
            recovery_rate=result.always_retry.recovery_rate,
            unnecessary_interventions=result.always_retry.unnecessary_interventions,
            total_interventions=result.always_retry.total_interventions,
        ),
        delta={
            "recovered_revenue": float(result.delta_recovered_revenue()),
            "recovery_rate": result.delta_recovery_rate(),
        },
    )


@router.get("/status")
def system_status() -> dict[str, Any]:
    """Comprehensive system status for status page."""
    settings = get_settings()
    timestamp = datetime.utcnow()

    # Check database
    db_status = "operational"
    db_latency = None
    db_details = {}
    try:
        db = SessionLocal()
        start = datetime.utcnow()
        db.execute(text("SELECT 1"))
        db_latency = (datetime.utcnow() - start).total_seconds() * 1000
        db_details = {"connection": "ok"}
        db.close()
    except Exception as e:
        db_status = "major_outage"
        db_details = {"error": str(e)}

    # Check configuration
    config_status = "operational"
    config_details = {}
    if not settings.gemini_api_key:
        config_status = "degraded"
        config_details["gemini_api_key"] = "not configured (using template fallback)"
    else:
        config_details["gemini_api_key"] = "configured"

    if not settings.database_url:
        config_status = "major_outage"
        config_details["database_url"] = "not configured"
    else:
        config_details["database_url"] = "configured"

    # Overall status
    overall_status = "operational"
    for svc_status in [db_status, config_status]:
        if svc_status == "major_outage":
            overall_status = "major_outage"
            break
        elif svc_status == "degraded" and overall_status == "operational":
            overall_status = "degraded"

    # Build services
    services = {
        "api": {
            "status": "operational",
            "description": "REST API and webhook ingestion",
            "latency_ms": None,
            "last_checked": datetime.utcnow().isoformat(),
        },
        "database": {
            "status": db_status,
            "description": "PostgreSQL database",
            "latency_ms": round(db_latency, 2) if db_latency else None,
            "last_checked": datetime.utcnow().isoformat(),
        },
        "configuration": {
            "status": config_status,
            "description": "Service configuration",
            "latency_ms": None,
            "last_checked": datetime.utcnow().isoformat(),
        },
    }

    # Mock incidents (in production, fetch from incident management system)
    incidents = []

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "services": services,
        "incidents": incidents,
    }


@router.get("/", response_class=HTMLResponse)
def status_page() -> str:
    """HTML status page at root / - similar to status.claude.com"""
    settings = get_settings()
    # Get the JSON status data by calling the status endpoint logic
    # We'll reuse the logic inline for simplicity
    db_status = "operational"
    db_latency = None
    db_details = {}
    try:
        db = SessionLocal()
        start = datetime.utcnow()
        db.execute(text("SELECT 1"))
        db_latency = (datetime.utcnow() - start).total_seconds() * 1000
        db_details = {"connection": "ok"}
        db.close()
    except Exception as e:
        db_status = "major_outage"
        db_details = {"error": str(e)}

    config_status = "operational"
    config_details = {}
    if not settings.gemini_api_key:
        config_status = "degraded"
        config_details["gemini_api_key"] = "not configured (using template fallback)"
    else:
        config_details["gemini_api_key"] = "configured"

    if not settings.database_url:
        config_status = "major_outage"
        config_details["database_url"] = "not configured"
    else:
        config_details["database_url"] = "configured"

    overall_status = "operational"
    for svc_status in [db_status, config_status]:
        if svc_status == "major_outage":
            overall_status = "major_outage"
            break
        elif svc_status == "degraded" and overall_status == "operational":
            overall_status = "degraded"

    services = {
        "api": {"status": "operational", "description": "REST API and webhook ingestion", "latency_ms": None},
        "database": {"status": db_status, "description": "PostgreSQL database", "latency_ms": round(db_latency, 2) if db_latency else None},
        "configuration": {"status": config_status, "description": "Service configuration", "latency_ms": None},
    }

    # Generate services HTML
    service_status_colors = {
        "operational": "bg-green-500",
        "degraded": "bg-yellow-500",
        "partial_outage": "bg-orange-500",
        "major_outage": "bg-red-500",
        "maintenance": "bg-blue-500",
    }

    services_html = ""
    for name, svc in services.items():
        svc_status = svc["status"]
        latency_str = f'{svc["latency_ms"]:.1f}ms' if svc["latency_ms"] is not None else "\u2014"
        services_html += f'''
                <div class="panel p-5 flex items-center justify-between gap-4">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-3 h-3 rounded-full {service_status_colors[svc_status]}"></div>
                        <div class="min-w-0">
                            <h3 class="font-medium text-gray-900 truncate">{name}</h3>
                            <p class="text-sm text-gray-500 truncate">{svc["description"]}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-4 shrink-0">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {service_status_colors[svc_status]} text-white">
                            {svc_status.capitalize()}
                        </span>
                        <span class="font-mono text-sm text-gray-500">{latency_str}</span>
                        <span class="text-[10px] text-gray-400 uppercase tracking-widest">Just now</span>
                    </div>
                </div>'''

    # Embedded CSS - no external dependencies
    css = """
    <style>
        *, *::before, *::after { box-sizing: border-box; }
        * { margin: 0; padding: 0; }
        html { font-size: 16px; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #1a1a2e; background: #f8fafc; min-height: 100vh; }
        a { color: #2563eb; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; }
        .font-mono { font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace; }
        .truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .min-w-0 { min-width: 0; }
        .shrink-0 { flex-shrink: 0; }
        .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border-width: 0; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .animate-pulse { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    </style>
"""

    # Generate services HTML
    service_status_colors = {
        "operational": "bg-green-500",
        "degraded": "bg-yellow-500",
        "partial_outage": "bg-orange-500",
        "major_outage": "bg-red-500",
        "maintenance": "bg-blue-500",
    }

    services_html = ""
    for name, svc in services.items():
        svc_status = svc["status"]
        latency_str = f'{svc["latency_ms"]:.1f}ms' if svc["latency_ms"] is not None else "\u2014"
        services_html += f'''
                <div class="panel p-5 flex items-center justify-between gap-4">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-3 h-3 rounded-full {service_status_colors[svc_status]}"></div>
                        <div class="min-w-0">
                            <h3 class="font-medium text-gray-900 truncate">{name}</h3>
                            <p class="text-sm text-gray-500 truncate">{svc["description"]}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-4 shrink-0">
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {service_status_colors[svc_status]} text-white">
                            {svc_status.capitalize()}
                        </span>
                        <span class="font-mono text-sm text-gray-500">{latency_str}</span>
                        <span class="text-[10px] text-gray-400 uppercase tracking-widest">Just now</span>
                    </div>
                </div>'''

    # Status colors and labels
    status_colors = {
        "operational": "#10B981",
        "degraded": "#F59E0B",
        "partial_outage": "#F97316",
        "major_outage": "#EF4444",
        "maintenance": "#3B82F6",
    }

    status_bg_colors = {
        "operational": "#ECFDF5",
        "degraded": "#FFFBEB",
        "partial_outage": "#FFF7ED",
        "major_outage": "#FEF2F2",
        "maintenance": "#EFF6FF",
    }

    status_labels = {
        "operational": "Operational",
        "degraded": "Degraded Performance",
        "partial_outage": "Partial Outage",
        "major_outage": "Major Outage",
        "maintenance": "Under Maintenance",
    }

    service_status_colors = {
        "operational": "bg-green-500",
        "degraded": "bg-yellow-500",
        "partial_outage": "bg-orange-500",
        "major_outage": "bg-red-500",
        "maintenance": "bg-blue-500",
    }

    # Generate the complete HTML with embedded CSS
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Reclaim System Status - Real-time status of Reclaim services">
    <title>System Status | Reclaim</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    {css}
</head>
<body class="bg-gray-50 min-h-screen" style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <!-- Status Banner -->
    <div class="fixed top-0 left-0 right-0 z-50 px-4 py-3 border-b border-gray-200 {{
        'bg-green-50 border-green-200' if overall_status == 'operational'
        else 'bg-yellow-50 border-yellow-200' if overall_status == 'degraded'
        else 'bg-orange-50 border-orange-200' if overall_status == 'partial_outage'
        else 'bg-red-50 border-red-200'
    }}">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-3 h-3 rounded-full {{
                    'bg-green-500' if overall_status == 'operational'
                    else 'bg-yellow-500' if overall_status == 'degraded'
                    else 'bg-orange-500' if overall_status == 'partial_outage'
                    else 'bg-red-500' if overall_status == 'major_outage'
                    else 'bg-blue-500'
                }}"></div>
                <span class="text-sm font-medium text-gray-900">
                    {status_labels.get(overall_status, overall_status)}
                </span>
            </div>
            <span class="text-xs text-gray-500" id="last-updated">{datetime.utcnow().strftime('%H:%M:%S UTC')}</span>
        </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-20">
        <!-- Header -->
        <section class="mb-12">
            <h1 class="text-3xl font-semibold tracking-tight text-gray-900">System Status</h1>
            <p class="mt-2 text-sm text-gray-500">
                Real-time status of Reclaim services. Last updated:
                <time class="font-mono ml-1" id="last-updated">{datetime.utcnow().strftime('%H:%M:%S UTC')}</time>
            </p>
        </section>

        <!-- Services Grid -->
        <section class="mb-12" aria-label="Services">
            <h2 class="text-xl font-semibold tracking-tight text-gray-900 mb-6">Services</h2>
            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {services_html}
            </div>
        </section>

        <!-- Incidents -->
        <section aria-label="Incidents">
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-semibold tracking-tight text-gray-900">Recent Incidents</h2>
            </div>
            <div class="space-y-4">
                <div class="panel p-8 text-center">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 11a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p class="mt-4 text-gray-500">No incidents reported. All systems operational.</p>
                </div>
        </section>

        <!-- Footer -->
        <footer class="mt-16 pt-8 border-t border-gray-200">
            <div class="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-gray-500">
                <p>
                    <a href="/docs" class="underline hover:text-gray-900">API Documentation</a>
                    {" \u2022 "}
                    <a href="mailto:support@reclaim.example.com" class="underline hover:text-gray-900">Contact Support</a>
                    {" \u2022 "}
                    <a href="https://github.com/arsh342/reclaim" class="underline hover:text-gray-900" target="_blank" rel="noopener noreferrer">GitHub</a>
                </p>
                <p class="text-xs text-gray-400 uppercase tracking-widest">Reclaim v0.1.0</p>
            </div>
        </footer>
    </main>

    <script>
        // Update timestamp every minute
        function updateTimestamp() {{
            const now = new Date();
            const el = document.getElementById('last-updated');
            if (el) el.textContent = now.toLocaleTimeString() + ' UTC';
        }}
        setInterval(updateTimestamp, 60000);
        updateTimestamp();
    </script>
</body>
</html>
"""
    return html
