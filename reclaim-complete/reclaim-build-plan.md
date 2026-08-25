# Reclaim — Complete Build Plan

Razorpay AI Builder Internship 2026 · Track 3: AI Revenue Recovery · Solo · 14 days · Gemini-powered standalone agent runtime

## 1. Project Definition

**One-liner:** Given a failed payment attempt, Reclaim diagnoses the failure, builds a bounded recovery plan, evaluates counterfactual actions, executes the best permitted intervention, and adapts when new payment events change the situation.

**Problem:** Failed payments lose revenue twice — when the payment fails and when the merchant responds with the wrong intervention. A good recovery system must decide when to retry, when to change payment method, when to contact the customer, and when to stop.

**Solution:** Reclaim is a complete agentic revenue-recovery system. It owns the agent runtime, state machine, planning loop, tool registry, policy engine, execution layer, event stream, audit trail, simulator, evaluation harness, and frontend. Gemini is the LLM provider used for diagnosis, candidate generation, counterfactual reasoning, planning, and replanning. Gemini is not the product architecture.

**Core principle:** AI decides what should happen; deterministic infrastructure guarantees what is allowed to happen.

**AI is used for actual work, not only explanation:**
- Failure diagnosis from structured payment context.
- Customer/payment-context interpretation.
- Dynamic recovery-candidate generation.
- Counterfactual comparison of candidate recovery paths.
- Multi-step recovery planning.
- Replanning after tool rejection or new payment events.
- Natural-language explanation of the resulting plan.

**Deterministic systems remain authoritative:** payment state, hard constraints, expected-value calculation, idempotency, action execution, stopping rules, and audit records.

### Non-goals
- No dispute/chargeback agent.
- No online learning/contextual bandit in the 14-day build.
- No train/validation/stress split for the hand-authored simulator.
- No unnecessary multi-agent LLM calls merely to make the UI look complex.
- No separate evaluation dashboard.
- No production payment movement with real customer money.

## 2. Product Architecture

```text
Razorpay Sandbox / Simulated Events
              |
              v
       Webhook Ingestion
              |
              v
      Event + State Store
              |
              v
       Reclaim Agent Runtime
       +--------------------+
       | Context Analyzer   |
       | Diagnosis           |
       | Candidate Generator|
       | Counterfactual Eval |
       | Recovery Planner    |
       | Replanner           |
       +----------+---------+
                  |
          Gemini LLM Provider
                  |
                  v
        Internal Tool Registry
        +----------------------+
        | context tools        |
        | policy tools         |
        | simulator tools      |
        | recovery tools       |
        | customer tools       |
        +----------+-----------+
                   |
          Deterministic Gate
                   |
             Safe Executor
                   |
          Razorpay Sandbox
                   |
             PostgreSQL
                   |
             Event Stream
                   |
             Next.js UI
```

The system does **not** depend on Claude, Claude Agent SDK, or MCP for its core operation. MCP may be added later as an interoperability adapter, but it is not part of the core architecture.

## 3. Payment Data Model

One `order_id` can have multiple `payment_id` attempts. `event_id` is the webhook deduplication key.

```sql
CREATE TABLE merchants (
  merchant_id TEXT PRIMARY KEY,
  max_retries INT NOT NULL DEFAULT 3,
  contact_budget_per_day INT NOT NULL DEFAULT 2
);

CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  recovery_propensity NUMERIC NOT NULL,
  payment_method_preference TEXT,
  historical_success_rate NUMERIC,
  customer_value NUMERIC NOT NULL
);

CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  merchant_id TEXT REFERENCES merchants(merchant_id),
  customer_id TEXT REFERENCES customers(customer_id),
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payment_attempts (
  payment_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  attempt_number INT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,
  error_code TEXT,
  error_description TEXT,
  error_reason TEXT,
  error_source TEXT,
  error_step TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE webhook_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ
);

CREATE TABLE agent_runs (
  run_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  status TEXT NOT NULL,
  current_stage TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  final_action TEXT,
  final_reason TEXT
);

CREATE TABLE agent_events (
  event_seq BIGSERIAL PRIMARY KEY,
  run_id TEXT REFERENCES agent_runs(run_id),
  order_id TEXT REFERENCES orders(order_id),
  agent_stage TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE recovery_actions (
  action_id BIGSERIAL PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  action_type TEXT NOT NULL,
  expected_value NUMERIC NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled',
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  executed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  reason TEXT
);
```

## 4. Recovery Outcome Simulator

The simulator is explicitly synthetic. It supplies probabilities to the decision layer; it is not presented as Razorpay production data.

README disclosure:

> Because no proprietary merchant-level outcome dataset is available, Reclaim uses a synthetic simulator with transparent, hand-set assumptions to evaluate policy behavior. It is not presented as a forecast of Razorpay's production recovery rates.

Keep all assumptions in `simulator/simulator_config.yaml`.

```yaml
base_rate:
  insufficient_funds: 0.35
  issuer_timeout: 0.55
  card_blocked: 0.02
  invalid_card: 0.01
  network_error: 0.60

method_factor:
  card: 1.0
  upi: 1.15
  netbanking: 0.9

action_fit:
  insufficient_funds: {retry_now: 0.3, retry_delayed: 1.4, payment_link: 1.1, whatsapp_nudge: 1.0, alternate_method: 0.8}
  issuer_timeout: {retry_now: 1.6, retry_delayed: 1.0, payment_link: 0.7, whatsapp_nudge: 0.6, alternate_method: 0.7}
  card_blocked: {retry_now: 0.0, retry_delayed: 0.0, payment_link: 1.2, whatsapp_nudge: 0.8, alternate_method: 1.4}
```

`P(recovery | context, action)` is generated from documented simulator assumptions and clipped to `[0, 0.95]`.

## 5. Policy and Safety

Candidate actions:

`RETRY_NOW`, `RETRY_DELAYED`, `PAYMENT_LINK`, `WHATSAPP_NUDGE`, `ALTERNATE_METHOD`, `NO_ACTION`, `HUMAN_REVIEW`.

Hard constraints are evaluated before economic scoring:

```text
if order.status in {recovered, lost}:
    no actions allowed

if attempt_number > merchant.max_retries:
    forbid retry actions

if error_reason in HARD_DECLINE_SET:
    forbid retry actions

if daily_contact_count >= contact_budget:
    forbid contact actions
```

Expected value:

```text
ERV(action) =
    P(recovery | context, action) * recoverable_amount
    - intervention_cost(action)
    - friction_cost(action, attempt_number)
    - risk_penalty(action)
```

The AI may request any action, but the safe executor independently re-runs the hard-constraint gate. A forbidden action cannot execute.

## 6. Reclaim Agent Runtime

The runtime is a Reclaim-owned state machine, not a vendor-specific agent wrapper.

### Agent stages

```text
RECEIVED
  -> CONTEXT_LOADING
  -> DIAGNOSING
  -> GENERATING_CANDIDATES
  -> EVALUATING_COUNTERFACTUALS
  -> PLANNING
  -> SAFETY_CHECK
  -> EXECUTING
  -> WAITING_FOR_OUTCOME
  -> COMPLETED
```

On rejection or new payment information:

```text
SAFETY_REJECTED -> REPLANNING -> SAFETY_CHECK
NEW_PAYMENT_EVENT -> CONTEXT_REFRESH -> REPLANNING
```

### Runtime responsibilities

1. Create `agent_run`.
2. Load order, merchant, customer, and payment history.
3. Ask Gemini for structured diagnosis.
4. Ask Gemini to generate relevant candidate interventions.
5. Call deterministic tools for allowed actions and recovery estimates.
6. Give Gemini the counterfactual results.
7. Generate a bounded recovery plan.
8. Validate the plan against deterministic policy.
9. Execute only permitted actions.
10. Stream every stage to the frontend.
11. Persist the complete audit trail.
12. Replan when an action is rejected or the payment state changes.

### Tool registry

Internal tools are ordinary Reclaim functions. They are not tied to MCP.

```text
get_order_context(order_id)
get_customer_history(customer_id)
get_allowed_actions(order_id)
estimate_recovery(order_id, action)
get_action_cost(action)
create_recovery_action(order_id, action, schedule)
execute_recovery_action(order_id, action)
cancel_pending_action(order_id)
get_recent_agent_events(run_id)
```

## 7. Gemini Integration

Use Google's current Python GenAI SDK: `google-genai`. Gemini API credentials are loaded from `GEMINI_API_KEY`; do not expose the key to Next.js or the browser. Google's current documentation recommends environment-variable authentication and the `google-genai` SDK. urlGemini API authentication documentationturn0search0 urlGemini API getting started documentationturn0search1

Configuration:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.7-flash
```

Keep `GEMINI_MODEL` configurable so the project does not hard-code a model dependency.

The backend owns the Gemini client. The frontend talks only to Reclaim's API/WebSocket layer.

```text
Browser
  -> Reclaim API
  -> Agent Runtime
  -> Gemini Provider
```

## 8. Agent Prompt Contract

Gemini must return structured data for decision stages. Do not let free-form text directly execute a payment action.

Example diagnosis schema:

```json
{
  "failure_class": "temporary_financial",
  "severity": "medium",
  "recoverability": "high",
  "key_factors": ["issuer_timeout", "customer_previous_recovery"],
  "candidate_strategy": "delayed_retry"
}
```

Example plan schema:

```json
{
  "objective": "maximize_expected_recovered_revenue",
  "steps": [
    {"action": "RETRY_DELAYED", "delay_minutes": 240},
    {"condition": "retry_failed", "action": "PAYMENT_LINK"},
    {"condition": "customer_unresponsive", "action": "WHATSAPP_NUDGE"}
  ],
  "stop_conditions": [
    "order_recovered",
    "hard_decline",
    "contact_budget_exhausted",
    "max_retries_exceeded"
  ]
}
```

The deterministic validator converts this proposed plan into an executable plan or rejects it.

## 9. Frontend: Agent Control Center

The frontend is part of the product, not a dashboard pasted onto an API.

### Overview

- Revenue at risk.
- Recovered revenue.
- Incremental recovered revenue vs. `always_retry`.
- Recovery rate.
- Active agent runs.
- Recent recoveries.

### Live Agent Console

Show the actual backend agent state:

```text
Webhook Received
      |
      v
Context Analysis
      |
      v
Failure Diagnosis
      |
      v
Candidate Generation
      |
      v
Counterfactual Evaluation
      |
      v
Recovery Planning
      |
      v
Safety Gate
      |
      v
Execution
      |
      v
Outcome / Replan
```

Each node shows status, latency, input summary, output summary, tool calls, and errors/rejections.

### Decision Inspector

For an `order_id`, show:

- Payment-attempt timeline.
- Customer history.
- Failure diagnosis.
- Candidate actions.
- ERV for each evaluated candidate.
- Agent-generated plan.
- Hard constraints that fired.
- Rejected actions.
- Executed action.
- Agent event timeline.
- Final outcome.

## 10. Real-Time Event Streaming

Use Server-Sent Events for the first implementation because the UI mainly needs server-to-browser updates. WebSockets can be introduced only if bidirectional interaction becomes necessary.

Events include:

```text
agent.run.started
agent.stage.started
agent.stage.completed
agent.tool.called
agent.tool.completed
agent.policy.rejected
agent.plan.created
agent.action.executed
agent.replan.started
order.recovered
agent.run.completed
```

## 11. Evaluation

Compare exactly two policies on the same synthetic batch:

1. `always_retry`.
2. `reclaim`.

Metrics:

- recovered revenue
- recovery rate
- incremental recovered revenue
- unnecessary interventions
- customer contact count
- average time to resolution
- number of policy rejections
- agent execution failures

The headline pitch metric is incremental recovered revenue versus `always_retry`.

## 12. Live Demo

1. Create a ₹25,000 order.
2. Fire `payment.failed` for `payment_001` with `issuer_timeout`.
3. Show Reclaim's agent runtime loading context and diagnosing the failure.
4. Show candidate generation and counterfactual evaluation.
5. Show the agent planning `RETRY_DELAYED`.
6. Show deterministic safety approval.
7. Fire `payment.captured` for `payment_002` on the same `order_id`.
8. Show the order moving to `recovered`.
9. Show the pending action being cancelled.
10. Replay the original `event_id`.
11. Show `duplicate event_id ignored`.
12. Show the complete event trace in the frontend.

### Second demo: AI replanning

Create a high-value hard-decline order.

```text
Agent proposes RETRY_NOW
        |
        v
Safety Gate rejects it
        |
        v
Agent receives rejection
        |
        v
Agent replans
        |
        v
PAYMENT_LINK
        |
        v
Executor accepts
```

This is the strongest demonstration that the AI is operating inside a real controlled agent runtime.

## 13. Tech Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + Python |
| Agent runtime | Custom Reclaim orchestration/state machine |
| LLM | Gemini API via `google-genai` |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Frontend | Next.js + React + TypeScript + Tailwind |
| Charts | Recharts |
| Streaming | Server-Sent Events |
| Testing | pytest + httpx |
| Deployment | Vercel + Render/Railway |
| Payments | Razorpay test/sandbox mode where available |

## 14. Day-by-Day Plan

| Day | Deliverable |
|---|---|
| 1 | Repository, Postgres, schema, environment config |
| 2 | Razorpay-style webhook ingestion, event dedup, payment/order state machine |
| 3 | Recovery simulator + configuration |
| 4 | Simulator validation + seeded dataset |
| 5 | Hard-constraint policy gate |
| 6 | ERV scoring + deterministic executor |
| 7 | Baseline evaluation |
| 8 | Reclaim agent runtime + Gemini provider |
| 9 | Diagnosis, candidate generation, planning, replanning |
| 10 | Tool registry + safe execution integration |
| 11 | Agent event persistence + SSE streaming |
| 12 | Agent Control Center + Decision Inspector |
| 13 | Buffer, testing, demo reliability, README, video |
| 14 | Pitch + panel preparation; no new features |

## 15. Repository

```text
reclaim/
├── backend/
│   ├── api/
│   ├── agent_runtime/
│   ├── agents/
│   ├── tools/
│   ├── policy/
│   ├── simulator/
│   ├── executor/
│   ├── db/
│   └── tests/
├── dashboard/
├── docs/
├── .env.example
├── docker-compose.yml
├── requirements.txt
├── README.md
└── ARCHITECTURE.md
```

## 16. What Not to Claim

- Do not claim the simulator represents Razorpay production statistics.
- Do not claim the system is production-ready payment infrastructure.
- Do not claim the LLM can override payment safety rules.
- Do not claim every visualized node is an independent LLM agent.
- Do not claim real money was recovered unless the demonstration actually uses a real test environment and clearly labels it as test-mode behavior.

## 17. Panel Thesis

> Reclaim is not a retry bot and not a chatbot. It is an AI recovery agent that diagnoses why a payment failed, explores the recovery actions that are actually relevant, compares their expected outcomes, creates a bounded recovery plan, and adapts when reality changes — while deterministic payment infrastructure guarantees that the AI can never execute a forbidden action.

## 17. MCP Interoperability Layer

MCP is a supported external interface to Reclaim, while the Reclaim Agent Runtime remains the core product. The MCP server exposes selected Reclaim capabilities to any compatible MCP host without moving orchestration into MCP.

### Supported MCP capabilities

**Read-only tools**
- `reclaim_get_order_context`
- `reclaim_get_allowed_actions`
- `reclaim_estimate_recovery`
- `reclaim_get_agent_run`
- `reclaim_get_agent_events`
- `reclaim_get_evaluation_summary`

**Controlled action tools**
- `reclaim_execute_recovery_action`
- `reclaim_cancel_pending_action`
- `reclaim_start_recovery_run`

Every side-effecting MCP tool enters the same Reclaim policy and executor path used by the web application. MCP is an adapter, not a bypass around safety.

### MCP transports

Primary transport: **Streamable HTTP** at `/mcp`.

Development transport: **stdio**, so the server can be launched by MCP hosts that use subprocess-based connections.

The official MCP Python SDK v2 supports tools, resources, prompts, stdio, Streamable HTTP, and SSE; Streamable HTTP is the primary transport for the deployed server.

### MCP architecture

```text
                   Reclaim
                      |
        +-------------+-------------+
        |                           |
 Web Application                MCP Server
        |                           |
        +-------------+-------------+
                      |
                Agent Runtime
                      |
          +-----------+-----------+
          |                       |
     Policy Engine           Safe Executor
          |                       |
          +-----------+-----------+
                      |
                 PostgreSQL
```

Both interfaces invoke the same domain services. There is only one source of truth for payment state and safety.

### MCP server endpoints

```text
GET/POST  /mcp       MCP Streamable HTTP endpoint
GET       /health    service health
```

For local development:

```bash
uv run mcp dev backend/mcp_server/server.py
```

For Streamable HTTP:

```bash
python -m backend.mcp_server.server
```

### MCP security boundary

MCP clients can request actions, but cannot directly mutate payment state.

```text
MCP Client
    |
    v
MCP Tool
    |
    v
Reclaim Domain Service
    |
    v
Hard Constraint Gate
    |
    +---- rejected ----> MCP result
    |
    v
Idempotent Executor
    |
    v
PostgreSQL / Razorpay Sandbox
```

The same authorization, validation, idempotency, audit logging, and action limits apply regardless of whether a request originated from the dashboard, the Reclaim agent runtime, or an MCP client.

## 18. MCP Product Page

Add a first-class `/mcp` route to the Next.js dashboard. It is an operational MCP console, not a marketing-only page.

### MCP page sections

1. **Server status** — online/offline, server version, protocol, transport, endpoint.
2. **Connection** — Streamable HTTP endpoint, local stdio command, copy controls.
3. **Tools** — name, description, read-only/side-effecting classification, schema, safety class, last invocation.
4. **Resources** — available Reclaim resources and URIs.
5. **Live activity** — recent MCP requests, tool calls, duration, result status, rejections.
6. **Safety** — policy gate, side-effect restrictions, audit status, authentication status.

### MCP page visual model

```text
RECLAIM MCP
────────────────────────────────────────────
● SERVER ONLINE

Streamable HTTP
https://<host>/mcp

Protocol: MCP v2
Transport: Streamable HTTP
Tools: 9

────────────────────────────────────────────
TOOLS

reclaim_get_order_context       READ
reclaim_get_allowed_actions     READ
reclaim_estimate_recovery       READ
reclaim_execute_recovery_action WRITE / GUARDED
reclaim_start_recovery_run      WRITE / GUARDED

────────────────────────────────────────────
LIVE MCP ACTIVITY

10:42:18  get_order_context          84ms   OK
10:42:19  estimate_recovery          91ms   OK
10:42:21  execute_recovery_action   112ms   APPROVED
────────────────────────────────────────────
```

## 19. Documentation Product Page

Add a first-class `/docs` route to the Next.js dashboard. The documentation page should render version-controlled Markdown/MDX rather than duplicating architecture text inside React components.

### Documentation navigation

```text
Introduction
Architecture
Agent Runtime
Recovery Policy
Safety Model
MCP Server
API Reference
Data Model
Evaluation
Demo
Deployment
Troubleshooting
```

A new developer should be able to understand Reclaim, run it locally, configure Gemini, start the dashboard, start the MCP server, connect an MCP client, run the webhook demo, inspect an agent run, and understand the safety boundary.

## 20. Repository Update

```text
reclaim/
├── backend/
│   ├── api/
│   ├── agent_runtime/
│   ├── agents/
│   ├── tools/
│   ├── policy/
│   ├── simulator/
│   ├── executor/
│   ├── db/
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   └── server.py
│   └── tests/
├── dashboard/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── agent/
│   │   ├── mcp/
│   │   └── docs/
│   └── components/
├── docs/
│   ├── README.md
│   ├── DOCUMENTATION.md
│   ├── MCP.md
│   └── API.md
├── .env.example
├── docker-compose.yml
├── requirements.txt
├── README.md
└── ARCHITECTURE.md
```

The MCP server is an interoperability surface over the same domain services. It is not a second implementation of recovery logic.
