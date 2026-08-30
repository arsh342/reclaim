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
Webhook Ingestion
      ↓
PostgreSQL State
      ↓
Reclaim Agent Runtime
      ↓
Gemini
      ↓
Structured Plan
      ↓
Policy Gate
      ↓
Safe Executor
      ↓
Payment Action
      ↓
Outcome Event
      ↓
Replan or Complete
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
  ├── rejected → REPLANNING
  └── approved → EXECUTING
                    ↓
              WAITING_FOR_OUTCOME
                    ↓
              COMPLETED / REPLANNING
```

These are logical stages, not necessarily separate Gemini API calls.

## Gemini

Reclaim uses Google's `google-genai` SDK.

```env
GEMINI_API_KEY=...
GEMINI_MODEL=...
```

The API key is server-side only.

## Recovery Policy

Candidate actions:

```text
RETRY_NOW
RETRY_DELAYED
PAYMENT_LINK
WHATSAPP_NUDGE
ALTERNATE_METHOD
NO_ACTION
HUMAN_REVIEW
```

The policy engine first removes forbidden actions. Then it computes:

```text
ERV = P(recovery | context, action) × recoverable_amount
      − intervention_cost
      − friction_cost
      − risk_penalty
```

The simulator supplies synthetic probabilities and is not a claim about Razorpay production statistics.

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

Reclaim also works as an MCP server. MCP is an interoperability layer over the same Reclaim services.

Primary endpoint:

```text
/mcp
```

Primary transport:

```text
Streamable HTTP
```

Development:

```bash
uv run mcp dev backend/mcp_server/server.py
```

See `MCP.md` for the integration guide.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/orders` | Order list |
| GET | `/orders/{order_id}` | Order detail |
| POST | `/webhooks/simulate` | Simulated webhook |
| GET | `/eval/summary` | Evaluation summary |
| GET | `/agent-runs` | Agent runs |
| GET | `/agent-runs/{run_id}` | Run detail |
| GET | `/agent-runs/{run_id}/events` | SSE event stream |

## Frontend

### `/`
Overview: revenue at risk, recovered revenue, recovery rate, baseline comparison, active agent runs.

### `/agent`
Agent Control Center: agent graph, live stage states, event timeline, tool calls, candidate comparison, recovery plan, safety gate, execution result.

### `/mcp`
MCP Control Center: server status, endpoint, tool catalog, activity, safety status, connection instructions.

### `/docs`
Documentation portal: architecture, agent runtime, Gemini, policy, MCP, API, deployment, troubleshooting.

## Evaluation

Compare:

```text
always_retry
vs
reclaim
```

Metrics:

- recovered revenue
- recovery rate
- incremental recovered revenue
- unnecessary interventions
- customer contact count
- average time to resolution

## Demo

### Idempotency

```text
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

```text
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
Vercel
  ↓
FastAPI
  ├── REST
  ├── SSE
  └── MCP /mcp
       ↓
PostgreSQL
       ↓
Gemini API
```

## Project Boundary

Reclaim intentionally does not include:

- dispute/chargeback automation
- contextual bandits
- online learning
- production payment movement
- independent LLM calls for every visual node
- a second business-logic implementation inside MCP
