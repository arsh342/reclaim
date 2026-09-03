# Reclaim API Reference

Base URL: `http://localhost:8000` (dev) or `https://your-backend.com`

All endpoints under `/api` unless noted.

## Health

### `GET /health`
Health check with database connectivity.

**Response**
```json
{
  "status": "healthy",
  "checks": {
    "database": "healthy",
    "api": "healthy"
  },
  "version": "1.0.0"
}
```

## Orders

### `GET /api/orders`
List orders (excludes evaluation orders).

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 50 | Max results (max 200) |
| offset | int | 0 | Pagination offset |

**Response**
```json
[
  {
    "order_id": "order_001",
    "merchant_id": "merch_001",
    "customer_id": "cust_001",
    "amount": 5000,
    "currency": "INR",
    "status": "failed",
    "created_at": "2024-01-15T10:30:00Z",
    "latest_attempt_status": "failed",
    "latest_attempt_reason": "insufficient_funds"
  }
]
```

### `GET /api/orders/{order_id}`
Order detail with decision analysis.

**Response**
```json
{
  "order": { ... },
  "attempts": [...],
  "recovery_actions": [...],
  "agent_runs": [...],
  "decision_analysis": {
    "diagnosis": { ... },
    "candidates": [...],
    "chosen_action": "RETRY_DELAYED",
    "stop_conditions": [...]
  }
}
```

## Webhooks

### `POST /api/webhooks/simulate`
Simulate a Razorpay webhook (idempotent by `event_id`).

**Request**
```json
{
  "entity": "event",
  "account_id": "acc_test",
  "event": "payment.failed",
  "contains": ["payment"],
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_001",
        "order_id": "order_001",
        "amount": 500000,
        "currency": "INR",
        "method": "card",
        "status": "failed",
        "attempt_number": 1,
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_description": "Payment failed",
        "error_reason": "insufficient_funds",
        "error_source": "customer",
        "error_step": "payment_authentication"
      }
    }
  }
}
```

**Response**
```json
{
  "status": "processed",
  "event_id": "pay_001",
  "order_id": "order_001",
  "message": "Event processed successfully"
}
```

On duplicate `event_id`: `status: "duplicate"`

### `POST /api/seed`
Seed demo data (idempotent).

## Evaluation

### `GET /api/eval/summary`
Compare `reclaim` vs `always_retry` baseline.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| n_orders | int | 200 | Number of synthetic orders (50-500) |
| seed | int | 42 | Random seed |

**Response** (cached 5 min)
```json
{
  "always_retry": {
    "policy_name": "always_retry",
    "recovered_revenue": 1250000,
    "recovery_rate": 0.42,
    "total_revenue_at_risk": 3000000,
    "unnecessary_interventions": 150,
    "contact_count": 80,
    "avg_time_to_resolution_hours": 4.5
  },
  "reclaim": {
    "policy_name": "reclaim",
    "recovered_revenue": 1800000,
    "recovery_rate": 0.60,
    "total_revenue_at_risk": 3000000,
    "unnecessary_interventions": 20,
    "contact_count": 35,
    "avg_time_to_resolution_hours": 2.1
  },
  "incremental_revenue": 550000,
  "incremental_recovery_rate": 0.18,
  "total_orders": 200,
  "seed": 42
}
```

## Agent Runs

### `GET /api/agent-runs`
List recent agent runs.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 20 | Max results (max 100) |

### `GET /api/agent-runs/{run_id}`
Run detail.

### `GET /api/agent-runs/{run_id}/events`
Server-Sent Events stream for live updates.

**Events**
```json
{
  "event_seq": 1,
  "run_id": "run_abc123",
  "order_id": "order_001",
  "agent_stage": "DIAGNOSING",
  "event_type": "agent.stage.started",
  "payload": {},
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Event Types**
- `agent.run.started`
- `agent.stage.started` / `agent.stage.completed`
- `agent.tool.called` / `agent.tool.completed`
- `agent.policy.rejected`
- `agent.plan.created`
- `agent.replan.started`
- `agent.action.executed`
- `agent.run.completed`

### `POST /api/agent-runs/{order_id}/start`
Start a background agent run for an order.

**Response** (immediate)
```json
{
  "run_id": "run_abc123",
  "order_id": "order_001",
  "status": "running",
  "current_stage": "RECEIVED",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": null,
  "final_action": null,
  "final_reason": null
}
```

Connect to SSE: `GET /api/agent-runs/{run_id}/events`

### `POST /api/agent-runs/{run_id}/replay`
Replay an agent run for demo purposes.

## Recovery Actions

### `POST /api/recovery-actions/{action_id}/complete`
Mark a recovery action as completed.

**Request**
```json
{
  "action_id": 1,
  "success": true,
  "reason": "Payment captured via retry"
}
```

**Response**
```json
{
  "success": true,
  "action_id": 1,
  "reason": "Recovery completed successfully"
}
```

## MCP

### `GET /api/mcp/status`
MCP server status.

### `GET /api/mcp/tools`
MCP tool catalog.

### `GET /api/mcp/activity`
Recent MCP activity.

**Query Parameters**
| Param | Type | Default |
|-------|------|---------|
| limit | int | 50 |

### `GET /api/mcp/activity/stream`
SSE stream for live MCP activity.

## Webhook Schema

### Payment Failed
```json
{
  "entity": "event",
  "account_id": "acc_test",
  "event": "payment.failed",
  "contains": ["payment"],
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_001",
        "order_id": "order_001",
        "amount": 500000,
        "currency": "INR",
        "method": "card",
        "status": "failed",
        "attempt_number": 1,
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_description": "Payment failed",
        "error_reason": "insufficient_funds",
        "error_source": "customer",
        "error_step": "payment_authentication"
      }
    }
  }
}
```

### Payment Captured
```json
{
  "entity": "event",
  "account_id": "acc_test",
  "event": "payment.captured",
  "contains": ["payment"],
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_002",
        "order_id": "order_001",
        "amount": 500000,
        "currency": "INR",
        "method": "card",
        "status": "captured",
        "attempt_number": 2
      }
    }
  }
}
```

## Error Responses

All errors follow RFC 7807:
```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP codes:
- 400 — Invalid request
- 404 — Not found
- 409 — Duplicate event_id
- 500 — Internal error