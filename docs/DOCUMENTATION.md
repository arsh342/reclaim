# Reclaim Documentation

## What is Reclaim?

Reclaim is an AI revenue-recovery platform for failed payments. It observes failed payment attempts, diagnoses the failure, determines relevant interventions, evaluates recovery alternatives, builds a bounded plan, executes permitted actions, and adapts when payment state changes.

> Reclaim is not a retry bot and not a chatbot.

## Core Principle

> **AI decides what should happen. Deterministic infrastructure guarantees what is allowed to happen.**

### AI responsibilities
- failure diagnosis
- customer/payment context interpretation
- candidate generation
- counterfactual reasoning
- recovery planning
- replanning
- natural-language explanation

### Deterministic responsibilities
- payment state
- hard constraints
- expected-value calculation
- idempotency
- action execution
- stopping rules
- audit trail

## System

```text
Razorpay Event
      ↓
Webhook Ingestion (idempotent)
      ↓
SQLite / PostgreSQL State
      ↓
Reclaim Agent Runtime (10 stages)
      ↓
Gemini LLM (or mock provider)
      ↓
Structured Plan
      ↓
Policy Gate (hard constraints + ERV)
      ↓
Safe Executor (idempotent, re-validates)
      ↓
Payment Action
      ↓
Outcome / Replan
```

## Agent Runtime

```text
RECEIVED
  ↓
CONTEXT_LOADING
  ↓
DIAGNOSING
  ↓
GENERATING_CANDIDATES
  ↓
EVALUATING_COUNTERFACTUALS
  ↓
PLANNING
  ↓
SAFETY_CHECK
  ├── rejected → REPLANNING (max 3×)
  └── approved → EXECUTING
                    ↓
              WAITING_FOR_OUTCOME
                    ↓
              COMPLETED
```

These are logical stages, not necessarily separate Gemini API calls.

### Runtime flow
1. Create `agent_run` with unique `run_id`
2. Load order, merchant, customer, payment history via `get_order_context`
3. LLM → structured diagnosis (failure class, severity, recoverability)
4. LLM → candidate interventions (from allowed actions)
5. Tools → `estimate_recovery` per candidate (ERV)
6. LLM → bounded recovery plan with stop conditions
7. Policy gate → hard constraints + ERV ranking
8. Safe executor → execute permitted action (re-validates policy)
9. Stream every stage event via SSE
10. Persist complete audit trail to `agent_events`
11. Replan on rejection or payment state change

### Key improvements
- **Background execution**: Runs start immediately, stream events via SSE
- **Full pipeline on all orders**: Terminal orders execute NO_ACTION through full pipeline
- **Live durations**: Stage durations computed from actual timestamps (>100ms shown)
- **Auto-refresh**: Runs list updates when SSE signals completion

## Gemini

Reclaim uses Google's `google-genai` SDK.

```env
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash
```

The API key is server-side only. Mock provider used when key is empty.

## Recovery Policy

### Candidate actions
```
RETRY_NOW
RETRY_DELAYED
PAYMENT_LINK
WHATSAPP_NUDGE
ALTERNATE_METHOD
NO_ACTION
HUMAN_REVIEW
```

### Hard constraints (before scoring)
```python
# Terminal order states
if order.status in {"recovered", "lost"}:
    allowed = []  # only NO_ACTION/HUMAN_REVIEW via validator

# Max retries exceeded
if attempt_number > merchant.max_retries:
    forbid retry actions

# Hard decline reasons
if error_reason in HARD_DECLINE_SET:  # card_blocked, invalid_card, stolen_card, expired_card
    forbid retry actions

# Daily contact budget
if daily_contact_count >= merchant.contact_budget_per_day:
    forbid contact actions (PAYMENT_LINK, WHATSAPP_NUDGE)

# Always allowed (validator contract)
NO_ACTION, HUMAN_REVIEW always permitted
```

### Expected Recovery Value (ERV)
```
ERV(action) =
    P(recovery | context, action) × recoverable_amount
    − intervention_cost(action)
    − friction_cost(action, attempt_number)
    − risk_penalty(action)
```

Costs (configurable):
- RETRY_NOW: intervention=₹0, friction=₹1
- RETRY_DELAYED: intervention=₹0, friction=₹0.5
- PAYMENT_LINK: intervention=₹5, friction=₹3
- WHATSAPP_NUDGE: intervention=₹2, friction=₹1
- ALTERNATE_METHOD: intervention=₹10, friction=₹5

The AI may request any action, but the safe executor independently re-runs the hard-constraint gate. A forbidden action cannot execute.

## Payment Model

One `order_id` can have multiple `payment_id` attempts. `event_id` is the webhook deduplication key.

```text
order_001
├── payment_001 → failed
├── payment_002 → failed
└── payment_003 → captured

order_001 = recovered
```

## MCP

Reclaim also works as an MCP server. MCP is an **interoperability layer** over the same Reclaim services.

### Primary endpoint
```
/mcp
```

### Transport
```
Streamable HTTP (production)
stdio (local development)
```

### Development
```bash
uv run mcp dev backend/mcp_server/server.py
```

### Tool Catalog (9 tools)

**Read-only (Safe)**
| Tool | Description |
|------|-------------|
| `reclaim_get_order_context` | Retrieve order, customer, merchant, payment attempts |
| `reclaim_get_allowed_actions` | Actions allowed by deterministic policy |
| `reclaim_estimate_recovery` | Recovery probability & expected recovery value |
| `reclaim_get_agent_run` | Retrieve an agent run |
| `reclaim_get_agent_events` | Retrieve agent execution events |
| `reclaim_get_evaluation_summary` | Baseline comparison metrics |

**Guarded Side-effecting**
| Tool | Description | Safety |
|------|-------------|--------|
| `reclaim_start_recovery_run` | Start a bounded recovery workflow | Policy gate + executor |
| `reclaim_execute_recovery_action` | Execute a permitted recovery action | Policy re-check + idempotency |
| `reclaim_cancel_pending_action` | Cancel a scheduled action | Idempotent |

Every side-effecting operation goes through the **same safety gate and executor** used by the web application. An MCP client cannot bypass policy.

### MCP and Gemini
MCP does not replace Gemini.

```
Gemini
  ↓
Reclaim Agent Runtime
  ↓
Reclaim domain tools

External MCP Client
  ↓
Reclaim MCP Server
  ↓
Reclaim domain tools
```

Both paths share the same domain services.

### Deployment
Production endpoint:
```
https://<reclaim-host>/mcp
```

Configure the MCP SDK host/origin allowlist for the real deployment hostname.

### Testing
Use the MCP SDK's in-memory client for unit-level MCP tests, and MCP Inspector for interactive development.
```bash
uv run mcp dev backend/mcp_server/server.py
```

### MCP Product Page
The Reclaim dashboard includes `/mcp`.

It displays:
- server status
- MCP endpoint
- transport
- protocol version
- tool catalog
- read/write classification
- live MCP activity (SSE)
- latency
- policy rejections
- safety status
- connection instructions

The page is an operational console, not a static marketing page.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/orders` | Order list (excludes eval orders) |
| GET | `/api/orders/{order_id}` | Order detail with decision analysis |
| POST | `/api/webhooks/simulate` | Simulate Razorpay webhook |
| GET | `/api/eval/summary` | Evaluation summary (5-min cache) |
| GET | `/api/agent-runs` | Agent runs list |
| GET | `/api/agent-runs/{run_id}` | Run detail |
| GET | `/api/agent-runs/{run_id}/events` | SSE event stream |
| POST | `/api/agent-runs/{order_id}/start` | Start background agent run |
| POST | `/api/agent-runs/{run_id}/replay` | Replay run for demo |
| POST | `/api/recovery-actions/{action_id}/complete` | Mark action complete |
| GET | `/api/mcp/status` | MCP server status |
| GET | `/api/mcp/tools` | MCP tool catalog |
| GET | `/api/mcp/activity` | Recent MCP activity |
| GET | `/api/mcp/activity/stream` | SSE activity stream |
| POST | `/api/seed` | Seed demo data (idempotent) |

## Frontend

### `/` — Overview
Revenue at risk, recovered revenue, recovery rate, baseline comparison, active agent runs.

### `/agent` — Agent Control Center
Agent pipeline (TaskSteps), live stage states, event timeline (SSE), tool calls, candidate comparison, recovery plan, safety gate, execution result.

### `/mcp` — MCP Control Center
Server status, endpoint, tool catalog, live activity (SSE), safety status, connection instructions.

### `/docs` — Documentation Portal
Architecture, agent runtime, AI boundary, policy, MCP, API, deployment, troubleshooting.

### `/orders` — Order Management
List, detail, decision analysis, payment attempts, recovery actions, agent runs.

### `/simulate` — Webhook Simulator
Interactive Razorpay webhook simulator for testing.

## Evaluation

Compare exactly two policies on the same synthetic batch:

1. `always_retry` — baseline that retries every failed payment
2. `reclaim` — full AI + deterministic policy pipeline

### Metrics
- Recovered revenue
- Recovery rate
- Incremental recovered revenue (vs always_retry)
- Unnecessary interventions
- Customer contact count
- Average time to resolution

Headline pitch metric: **incremental recovered revenue versus `always_retry`**.

Run evaluation:
```bash
GET /api/eval/summary?n_orders=2000&seed=42
```

Results cached for 5 minutes. Synthetic probabilities are seeded and disclosed — not Razorpay production statistics.

## Demo

### Idempotency
```
payment_001 fails
        ↓
agent plans delayed retry
        ↓
payment_002 captures
        ↓
order becomes recovered
        ↓
pending retry is cancelled
        ↓
payment_001 failure event is replayed
        ↓
duplicate event ignored
```

### Replanning
```
hard decline
        ↓
agent proposes retry
        ↓
policy rejects retry
        ↓
agent receives rejection
        ↓
agent replans
        ↓
payment link
        ↓
safe executor
```

### Terminal Order
```
order already recovered
        ↓
agent loads context (status=recovered)
        ↓
full pipeline executes
        ↓
planner proposes NO_ACTION
        ↓
safety gate approves
        ↓
executor executes NO_ACTION (no-op)
        ↓
run completes cleanly
```

## Security
- Gemini API key never reaches the browser.
- MCP side-effecting tools cannot bypass policy.
- LLM output is schema-validated.
- Payment state is deterministic.
- Database writes are transactional.
- Webhooks are idempotent.
- Agent transitions are persisted.
- Test/synthetic data is used for the demo.

## Deployment

```text
Vercel (Frontend)
  ↓
FastAPI (Backend)
  ├── REST /api/*
  ├── SSE /api/agent-runs/*/events
  └── MCP /mcp
       ↓
PostgreSQL (Supabase / Render / self-hosted)
       ↓
Gemini API (Google AI Studio)
```

### Environment Variables

**Backend**
```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash
CORS_ORIGINS=https://your-frontend.vercel.app
```

**Frontend**
```env
NEXT_PUBLIC_API_URL=https://your-backend.render.com
```

### Docker
```bash
docker-compose up -d
# Includes PostgreSQL + Redis + API
```

## Project Boundary

Reclaim intentionally does not include:
- dispute/chargeback automation
- contextual bandits
- online learning
- production payment movement
- independent LLM calls for every visual node
- a second business-logic implementation inside MCP