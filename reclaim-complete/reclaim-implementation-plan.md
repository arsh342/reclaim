# Reclaim — Implementation Plan

Razorpay AI Builder Internship 2026 · Track 3 · Solo · Gemini-powered standalone agent runtime

This document is the implementation checklist. Module names and interfaces are intentionally aligned with `reclaim-system-design-gemini.md`.

## 1. Day 0 — Environment

### Repository

```text
reclaim/
  backend/
    api/
    agent_runtime/
    agents/
    tools/
    policy/
    simulator/
    executor/
    db/
    tests/
  dashboard/
  docs/
  .env.example
  docker-compose.yml
  requirements.txt
  README.md
```

### Python dependencies

```text
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
pydantic
pyyaml
python-dotenv
google-genai
mcp[cli]
pytest
httpx
```

Google's current Python SDK is `google-genai`; the SDK reads `GEMINI_API_KEY` from the environment. citeturn0search1turn0search2

### Environment

```env
DATABASE_URL=postgresql://reclaim:reclaim@localhost:5432/reclaim
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-3.7-flash
CORS_ORIGINS=http://localhost:3000
```

Never commit `.env`.

### Postgres

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: reclaim
      POSTGRES_PASSWORD: reclaim
      POSTGRES_DB: reclaim
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

### Dashboard

```bash
npx create-next-app@latest dashboard --typescript --tailwind --app
cd dashboard
npm install recharts
```

## 2. Days 1–2 — State Machine

- [ ] Create all PostgreSQL tables.
- [ ] Create SQLAlchemy models.
- [ ] Implement `POST /webhooks/simulate`.
- [ ] Insert `event_id` before processing any event.
- [ ] Duplicate event returns `duplicate, ignored`.
- [ ] `payment.failed` creates a payment attempt.
- [ ] `payment.captured` updates the attempt and parent order transactionally.
- [ ] Captured payment cancels all scheduled recovery actions.
- [ ] Add row locking around order state transitions.
- [ ] Tests for duplicate events and captured-payment/action cancellation race.

**Definition of done:** a clean DB can process the complete payment lifecycle deterministically.

## 3. Days 3–4 — Simulator

- [ ] Implement `simulator/simulator_config.yaml`.
- [ ] Implement `generate_orders(n, seed)`.
- [ ] Implement `simulate_outcome(order, action)`.
- [ ] Generate 2,000–3,000 orders.
- [ ] Verify reproducibility from a fixed seed.
- [ ] Print recovery-rate distributions by failure reason.
- [ ] Keep the simulator disclosure in README.

**Definition of done:** simulator output is deterministic for a fixed seed and does not produce degenerate probabilities.

## 4. Days 5–6 — Policy and Executor

### Constraint gate

Implement:

```python
get_allowed_actions(order, attempt, merchant) -> list[str]
```

Rules:

- recovered/lost order → no action
- max retries exceeded → no retry
- hard decline → no retry
- contact budget exhausted → no contact action

### Scoring

Implement:

```python
expected_value(order, attempt, action) -> float
```

### Executor

Implement:

```python
execute(order_id, action) -> ActionResult
```

The executor must re-check the constraint gate immediately before execution.

**Definition of done:** no LLM output can bypass a deterministic safety rule.

## 5. Day 7 — Evaluation

- [ ] Implement `always_retry`.
- [ ] Implement `reclaim` deterministic policy baseline.
- [ ] Run both against the same synthetic batch.
- [ ] Store evaluation summary.
- [ ] Expose `GET /eval/summary`.

Metrics:

```text
recovered_revenue
recovery_rate
incremental_revenue
unnecessary_interventions
contact_count
average_time_to_resolution
```

## 6. Day 8 — Agent Runtime + Gemini Provider

Create:

```text
backend/agent_runtime/
  orchestrator.py
  state.py
  events.py
  provider.py

backend/agents/
  diagnosis.py
  candidate_generator.py
  planner.py
  replanner.py
```

### Gemini provider

Use the official Google GenAI SDK:

```python
from google import genai

client = genai.Client()
```

The model name comes from `GEMINI_MODEL`; do not hard-code it in business logic. citeturn0search2

Create a provider interface:

```python
class LLMProvider:
    async def structured_generate(self, *, system, input, schema):
        raise NotImplementedError
```

Then implement:

```text
GeminiProvider
```

This preserves the option to add another model provider later without changing Reclaim's agent runtime.

## 7. Day 9 — AI Capabilities

### Diagnosis

Input:

```text
order context
customer history
payment attempts
failure metadata
```

Output:

```json
{
  "failure_class": "temporary_financial",
  "severity": "medium",
  "recoverability": "high",
  "key_factors": [],
  "candidate_strategy": "delayed_retry"
}
```

### Candidate generation

Gemini proposes relevant interventions. The system then intersects them with the deterministic allowed-action set.

```text
AI candidates ∩ policy allowed actions = executable candidates
```

### Counterfactual evaluation

For each relevant candidate, deterministic tools return probability, recoverable amount, costs, and ERV.

Gemini receives those values and compares the futures.

### Planning

Gemini generates a bounded plan with:

- actions
- order
- conditions
- delays
- stop conditions

The deterministic validator must approve every step.

### Replanning

When:

- a tool rejects an action,
- payment state changes,
- an attempt fails,
- contact budget changes,

the runtime creates a new planning cycle.

## 8. Day 10 — Tool Registry + Safe Execution

Create:

```text
tools/context_tools.py
tools/customer_tools.py
tools/policy_tools.py
tools/recovery_tools.py
tools/simulation_tools.py
tools/registry.py
```

Tools are internal Python functions exposed to the agent runtime. No MCP dependency is required.

Core tools:

```text
get_order_context
get_customer_history
get_allowed_actions
estimate_recovery
get_action_cost
create_recovery_action
execute_recovery_action
cancel_pending_action
```

Tool calls must be logged as `agent_events`.

## 9. Day 11 — Event Streaming

Implement:

```text
GET /agent-runs/{run_id}/events
GET /agent-runs/{run_id}
```

Use Server-Sent Events for live updates.

Example event:

```json
{
  "run_id": "run_123",
  "agent_stage": "EVALUATING_COUNTERFACTUALS",
  "event_type": "candidate.evaluated",
  "payload": {
    "action": "RETRY_DELAYED",
    "expected_value": 1436
  }
}
```

The browser must receive the actual events generated by the backend. Do not fake agent animations in React.

## 10. Day 12 — Agent Control Center

### Overview

- KPI row.
- Baseline comparison.
- Active agent runs.
- Revenue at risk.
- Recovered revenue.

### Live agent view

Visualize:

```text
Event
 ↓
Context
 ↓
Diagnosis
 ↓
Candidates
 ↓
Counterfactuals
 ↓
Plan
 ↓
Safety
 ↓
Execution
 ↓
Outcome / Replan
```

Each node receives status from the SSE event stream.

### Decision Inspector

Show:

- order timeline
- customer history
- diagnosis
- candidate actions
- ERVs
- plan
- safety constraints
- rejected actions
- executed action
- event timeline

## 11. Day 13 — Buffer

Only:

- [ ] Fix demo failures.
- [ ] Fix race/idempotency issues.
- [ ] Improve agent visualization if necessary.
- [ ] Test clean clone.
- [ ] Record demo.
- [ ] Finalize README.
- [ ] Clean commit history.

Do not add new capabilities.

## 12. Day 14 — Pitch

5-minute structure:

```text
0:00–0:30  Revenue recovery problem
0:30–1:15  Reclaim architecture
1:15–3:30  Live agent execution + replanning demo
3:30–4:20  Measured revenue impact
4:20–5:00  Safety, scale, and future work
```

## 13. Testing

### Unit

- constraint gate
- ERV calculation
- simulator
- structured AI-output validation
- plan validator

### Integration

- duplicate event
- payment capture cancellation
- executor rejection
- agent replanning
- DB transaction behavior

### End-to-end

```text
webhook
 -> database
 -> agent runtime
 -> Gemini
 -> tools
 -> policy
 -> executor
 -> event stream
 -> dashboard
```

## 14. Failure Priorities

If behind schedule:

1. Keep payment state/idempotency.
2. Keep deterministic safety gate.
3. Keep Gemini diagnosis + planning.
4. Keep agent event stream.
5. Keep live agent visualization.
6. Remove secondary dashboard metrics.
7. Remove human-review confidence logic if necessary.
8. Never remove the idempotency demo.

## 15. Final Definition of Done

The project is complete only when:

- A failed payment creates a real agent run.
- Gemini performs structured diagnosis/planning.
- Reclaim's tools provide deterministic facts and actions.
- The agent cannot execute forbidden actions.
- The agent can replan after rejection/new payment events.
- Every agent stage appears in the frontend from backend events.
- Payment capture cancels pending recovery actions.
- Duplicate webhooks are ignored.
- Baseline vs. Reclaim metrics are reproducible.
- The complete demo works from a clean database.
- No API key is exposed to the browser or repository.

## 7A. Day 8 — MCP Server Foundation

After the Reclaim Agent Runtime is working, expose it as an MCP server.

### Dependency

Add:

```text
mcp[cli]
```

The current official Python SDK is MCP v2. It uses `MCPServer` and supports stdio and Streamable HTTP.

### Files

```text
backend/mcp_server/
  __init__.py
  server.py
```

### MCP tools

Register tools that call existing Reclaim domain services:

```text
reclaim_get_order_context
reclaim_get_allowed_actions
reclaim_estimate_recovery
reclaim_execute_recovery_action
reclaim_cancel_pending_action
reclaim_start_recovery_run
reclaim_get_agent_run
reclaim_get_agent_events
reclaim_get_evaluation_summary
```

Do not duplicate business logic in the MCP layer.

### Definition of done

- MCP Inspector can connect.
- `tools/list` returns the Reclaim tool catalog.
- Read-only tools return real database-backed data.
- Side-effecting tools pass through the same policy gate and executor.
- An attempted forbidden action is rejected.
- MCP activity is persisted in the audit/event stream.

## 7B. Day 9 — MCP + Agent Integration

The internal Reclaim Agent Runtime remains the primary orchestrator. The MCP server is an external interoperability interface.

Test both paths:

```text
Dashboard
   -> Reclaim Agent Runtime
   -> Domain Services

MCP Client
   -> MCP Server
   -> Domain Services
```

Both must produce identical payment-state and safety behavior.

### MCP transports

Development:

```bash
uv run mcp dev backend/mcp_server/server.py
```

Deployment:

```text
https://<reclaim-host>/mcp
```

Use Streamable HTTP as the primary deployed transport.

## 12A. Dashboard — MCP Page

Add:

```text
dashboard/app/mcp/page.tsx
```

The page must show:

- server status
- endpoint
- protocol/transport
- tool catalog
- read-only vs side-effecting classification
- recent requests
- latency
- rejected requests
- safety status
- connection instructions

Add API endpoints:

```text
GET /mcp/status
GET /mcp/tools
GET /mcp/activity
```

The MCP page must read actual server state. Do not hard-code online status or fake tool activity.

## 12B. Dashboard — Documentation Page

Add:

```text
dashboard/app/docs/page.tsx
```

Use Markdown/MDX files under:

```text
docs/
```

Recommended sections:

```text
Introduction
Architecture
Agent Runtime
AI Boundary
Recovery Policy
MCP
API
Data Model
Evaluation
Demo
Deployment
Troubleshooting
```

## 13A. MCP Testing

Add tests for:

```text
test_mcp_tools_list
test_mcp_get_order_context
test_mcp_get_allowed_actions
test_mcp_estimate_recovery
test_mcp_execute_forbidden_action
test_mcp_execute_allowed_action
test_mcp_duplicate_event
test_mcp_agent_run
```

The highest-priority MCP test is:

```text
MCP client
 -> execute_recovery_action(RETRY_NOW)
 -> hard decline
 -> policy rejection
 -> no database side effect
```

## 15. Updated Definition of Done

The project is complete only when:

- Reclaim runs independently of any MCP host.
- Gemini powers the AI layer through `google-genai`.
- Reclaim exposes a functioning MCP server.
- MCP supports Streamable HTTP and development stdio.
- MCP tools invoke the same domain services as the dashboard.
- MCP cannot bypass safety rules.
- `/mcp` is a functional operational console.
- `/docs` is a functional documentation portal.
- Agent events shown in the UI originate from backend events.
- Dashboard, Reclaim agent, and MCP interface operate against the same database and state machine.
