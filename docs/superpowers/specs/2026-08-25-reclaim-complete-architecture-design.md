# Reclaim — Complete Architecture Design

**Date:** 2026-08-25  
**Scope:** Full rebuild following 14-day plan from `reclaim-complete/reclaim-implementation-plan.md`  
**Classification:** Architectural (new project structure, new agent runtime, MCP server, new frontend pages)

---

## 1. Problem Statement

Build Reclaim: an AI revenue-recovery agent for failed payments (Razorpay-style) that:
- Diagnoses failure from structured payment context
- Generates relevant recovery candidates
- Evaluates counterfactual outcomes using deterministic simulator
- Plans bounded recovery interventions
- Executes only policy-approved actions via safe executor
- Replans when actions are rejected or payment state changes
- Exposes everything via live Agent Control Center, MCP server, and documentation portal

**Core Principle:** AI decides what should happen; deterministic infrastructure guarantees what is allowed to happen.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        RECLAIM CORE                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Web UI    │  │ Agent       │  │   MCP       │              │
│  │  (Next.js)  │  │  Runtime    │  │  Server     │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          ▼                                       │
│                 ┌─────────────────┐                              │
│                 │ Domain Services │                              │
│                 │  (Single Source │                              │
│                 │   of Truth)     │                              │
│                 └────────┬────────┘                              │
│                          │                                       │
│        ┌─────────────────┼─────────────────┐                    │
│        ▼                 ▼                 ▼                    │
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│ │   Policy    │  │  Executor   │  │  PostgreSQL │              │
│ │   Engine    │  │  (Idempotent)│  │  (State)    │              │
│ └─────────────┘  └─────────────┘  └─────────────┘              │
│                          │                                       │
│                          ▼                                       │
│                 ┌─────────────┐                                  │
│                 │   Gemini    │                                  │
│                 │  (Provider) │                                  │
│                 └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Interfaces
| Interface | Path | Purpose |
|-----------|------|---------|
| REST API | `/health`, `/orders`, `/webhooks/simulate`, `/eval/summary`, `/agent-runs` | Web app + external integrations |
| SSE | `/agent-runs/{run_id}/events` | Live agent event stream |
| MCP | `/mcp` (Streamable HTTP) | Interoperability for MCP hosts |
| Frontend | `/`, `/agent`, `/mcp`, `/docs` | Human control surfaces |

---

## 3. Repository Structure

```
reclaim/
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, lifespan, middleware
│   │   ├── routes.py            # REST endpoints
│   │   ├── sse.py               # SSE event streaming
│   │   └── schemas.py           # Pydantic request/response models
│   ├── agent_runtime/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # Main agent loop
│   │   ├── state.py             # AgentStage enum, RunState dataclass
│   │   ├── events.py            # Event types, emission, persistence
│   │   └── provider.py          # LLMProvider interface
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── diagnosis.py         # Failure diagnosis via Gemini
│   │   ├── candidate_generator.py  # Candidate generation via Gemini
│   │   ├── planner.py           # Recovery planning via Gemini
│   │   └── replanner.py         # Replanning after rejection/new event
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py          # Tool registry with metadata
│   │   ├── context_tools.py     # get_order_context, get_customer_history
│   │   ├── policy_tools.py      # get_allowed_actions, estimate_recovery
│   │   ├── recovery_tools.py    # create_recovery_action, execute_recovery_action, cancel_pending_action
│   │   ├── simulation_tools.py  # simulate_outcome
│   │   └── customer_tools.py    # get_customer_history
│   ├── policy/
│   │   ├── __init__.py
│   │   ├── constraints.py       # Hard constraint gate
│   │   ├── scoring.py           # ERV calculation
│   │   └── validator.py         # Plan validation
│   ├── simulator/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic config model
│   │   ├── config_loader.py     # YAML loading with validation
│   │   ├── generator.py         # generate_orders(n, seed)
│   │   └── outcome.py           # simulate_outcome(order, action)
│   ├── executor/
│   │   ├── __init__.py
│   │   └── executor.py          # Safe executor with row locking
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── session.py           # Session management
│   │   └── init_db.py           # Schema creation
│   ├── mcp_server/
│   │   ├── __init__.py
│   │   ├── server.py            # MCP server with tool registration
│   │   └── adapters.py          # Adapters to domain services
│   ├── gemini/
│   │   ├── __init__.py
│   │   └── provider.py          # GeminiProvider implementation
│   └── tests/
│       ├── conftest.py
│       ├── test_simulator.py
│       ├── test_policy.py
│       ├── test_executor.py
│       ├── test_agent_runtime.py
│       └── test_mcp.py
├── dashboard/
│   ├── app/
│   │   ├── page.tsx             # Overview
│   │   ├── layout.tsx           # Root layout with providers
│   │   ├── globals.css          # Design tokens
│   │   ├── agent/
│   │   │   ├── page.tsx         # Agent Control Center
│   │   │   └── components/
│   │   ├── mcp/
│   │   │   ├── page.tsx         # MCP Control Center
│   │   │   └── components/
│   │   └── docs/
│   │       ├── page.tsx         # Documentation Portal
│   │       └── components/
│   ├── components/
│   │   ├── ui/                  # Base UI components
│   │   ├── agent-graph/         # Agent stage visualization
│   │   ├── agent-timeline/      # Event timeline
│   │   ├── mcp-tools/           # MCP tool catalog
│   │   └── markdown/            # MDX rendering
│   ├── lib/
│   │   ├── api.ts               # Typed API client
│   │   ├── sse.ts               # SSE connection manager
│   │   └── types.ts             # Shared TypeScript types
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   └── tailwind.config.ts
├── docs/
│   ├── README.md                # Documentation index
│   ├── DOCUMENTATION.md         # Main documentation
│   ├── MCP.md                   # MCP integration guide
│   └── API.md                   # API reference
├── .env.example
├── docker-compose.yml
├── requirements.txt
├── README.md
└── ARCHITECTURE.md
```

---

## 4. Data Model

### Core Tables (Extended from Current)

```sql
-- Merchants
CREATE TABLE merchants (
  merchant_id TEXT PRIMARY KEY,
  max_retries INT NOT NULL DEFAULT 3,
  contact_budget_per_day INT NOT NULL DEFAULT 2
);

-- Customers
CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  recovery_propensity NUMERIC NOT NULL,
  payment_method_preference TEXT,
  historical_success_rate NUMERIC,
  customer_value NUMERIC NOT NULL
);

-- Orders
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  merchant_id TEXT REFERENCES merchants(merchant_id),
  customer_id TEXT REFERENCES customers(customer_id),
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'pending',  -- pending, recovered, lost
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Payment Attempts
CREATE TABLE payment_attempts (
  payment_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  attempt_number INT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,  -- failed, captured, pending
  error_code TEXT,
  error_description TEXT,
  error_reason TEXT,
  error_source TEXT,
  error_step TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Webhook Events (Idempotency)
CREATE TABLE webhook_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ
);

-- Agent Runs
CREATE TABLE agent_runs (
  run_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  status TEXT NOT NULL,  -- running, completed, failed
  current_stage TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  final_action TEXT,
  final_reason TEXT
);

-- Agent Events (Audit Trail + SSE Source)
CREATE TABLE agent_events (
  event_seq BIGSERIAL PRIMARY KEY,
  run_id TEXT REFERENCES agent_runs(run_id),
  order_id TEXT REFERENCES orders(order_id),
  agent_stage TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Recovery Actions
CREATE TABLE recovery_actions (
  action_id BIGSERIAL PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  action_type TEXT NOT NULL,
  expected_value NUMERIC NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled, executed, cancelled
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  executed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  reason TEXT
);
```

---

## 5. Agent Runtime

### Stages (State Machine)

```python
class AgentStage(Enum):
    RECEIVED = "RECEIVED"
    CONTEXT_LOADING = "CONTEXT_LOADING"
    DIAGNOSING = "DIAGNOSING"
    GENERATING_CANDIDATES = "GENERATING_CANDIDATES"
    EVALUATING_COUNTERFACTUALS = "EVALUATING_COUNTERFACTUALS"
    PLANNING = "PLANNING"
    SAFETY_CHECK = "SAFETY_CHECK"
    EXECUTING = "EXECUTING"
    WAITING_FOR_OUTCOME = "WAITING_FOR_OUTCOME"
    COMPLETED = "COMPLETED"
    REPLANNING = "REPLANNING"
```

### Transitions

```
RECEIVED → CONTEXT_LOADING → DIAGNOSING → GENERATING_CANDIDATES
  → EVALUATING_COUNTERFACTUALS → PLANNING → SAFETY_CHECK
    ├─ approved → EXECUTING → WAITING_FOR_OUTCOME → COMPLETED
    ├─ rejected → REPLANNING → PLANNING
    └─ new_event → CONTEXT_LOADING (context refresh)
```

### Orchestrator Responsibilities

1. Create `agent_run` record
2. Load context via `context_tools.get_order_context()`
3. Call `diagnosis.analyze()` → structured diagnosis
4. Call `candidate_generator.propose()` → candidate actions
5. For each candidate: call `policy_tools.estimate_recovery()` → ERV
6. Call `planner.create_plan()` with counterfactual data → bounded plan
7. Call `validator.validate()` → approved/rejected
8. If approved: call `executor.execute()` → result
9. If rejected: call `replanner.replan()` with rejection reason
10. Stream every stage transition as `agent_event`
11. Persist complete audit trail

### Event Contract

```json
{
  "event_seq": 183,
  "run_id": "run_001",
  "order_id": "order_001",
  "agent_stage": "EVALUATING_COUNTERFACTUALS",
  "event_type": "candidate.evaluated",
  "payload": {
    "action": "RETRY_DELAYED",
    "probability": 0.61,
    "expected_value": 1436,
    "latency_ms": 842
  },
  "created_at": "2026-08-25T10:00:00Z"
}
```

Event types:
- `agent.run.started`
- `agent.stage.started`
- `agent.stage.completed`
- `agent.tool.called`
- `agent.tool.completed`
- `agent.policy.rejected`
- `agent.plan.created`
- `agent.action.executed`
- `agent.replan.started`
- `order.recovered`
- `agent.run.completed`

---

## 6. Gemini Integration

### Provider Interface

```python
class LLMProvider:
    async def structured_generate(
        self,
        *,
        system: str,
        input: dict,
        schema: dict
    ) -> dict:
        ...
```

### GeminiProvider Implementation

```python
# backend/gemini/provider.py
from google import genai

class GeminiProvider(LLMProvider):
    def __init__(self, model: str = None):
        self.client = genai.Client()
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
    
    async def structured_generate(self, *, system, input, schema):
        # Use response_schema for structured output
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[system, json.dumps(input)],
            config={"response_mime_type": "application/json", "response_schema": schema}
        )
        return json.loads(response.text)
```

### Stages Using Gemini

| Stage | Purpose | Input | Output Schema |
|-------|---------|-------|---------------|
| Diagnosis | Classify failure | Order context, attempts, customer | `failure_class`, `severity`, `recoverability`, `key_factors`, `candidate_strategy` |
| Candidate Generation | Propose interventions | Diagnosis, allowed actions | `candidates: [{action, rationale, params}]` |
| Planning | Create bounded plan | Diagnosis, candidates, ERVs | `objective`, `steps[]`, `stop_conditions[]` |
| Replanning | Adapt after rejection | Rejection reason, updated context | Updated plan |

**Configuration:**
```env
GEMINI_API_KEY=<secret>
GEMINI_MODEL=gemini-3.7-flash
```

---

## 7. Policy & Safety

### Hard Constraints (Evaluated Before Scoring)

```python
HARD_DECLINE_REASONS = {"card_blocked", "invalid_card", "stolen_card"}

def get_allowed_actions(order, attempt, merchant) -> list[str]:
    actions = ALL_ACTIONS.copy()
    
    if order.status in {"recovered", "lost"}:
        return []
    
    if attempt.attempt_number > merchant.max_retries:
        actions = [a for a in actions if a not in RETRY_ACTIONS]
    
    if attempt.error_reason in HARD_DECLINE_REASONS:
        actions = [a for a in actions if a not in RETRY_ACTIONS]
    
    if daily_contact_count >= merchant.contact_budget_per_day:
        actions = [a for a in actions if a not in CONTACT_ACTIONS]
    
    return actions
```

### Expected Recovery Value (ERV)

```python
def expected_value(order, attempt, action) -> float:
    p_recovery = simulator.probability(order, attempt, action)
    recoverable = order.amount
    intervention_cost = ACTION_COSTS[action]
    friction_cost = FRICTION_COSTS[action](attempt.attempt_number)
    risk_penalty = RISK_PENALTIES.get(action, 0)
    
    return p_recovery * recoverable - intervention_cost - friction_cost - risk_penalty
```

### Validator

```python
def validate_plan(plan, order, allowed_actions) -> ValidationResult:
    for step in plan.steps:
        if step.action not in allowed_actions:
            return ValidationResult(approved=False, reason=f"Action {step.action} not allowed")
    return ValidationResult(approved=True)
```

---

## 8. Tool Registry

| Tool | Type | Side Effect | Description |
|------|------|-------------|-------------|
| `get_order_context` | Read | No | Order, customer, merchant, attempts |
| `get_customer_history` | Read | No | Customer recovery profile |
| `get_allowed_actions` | Read | No | Policy-permitted actions |
| `estimate_recovery` | Read | No | Probability, ERV for action |
| `get_action_cost` | Read | No | Intervention cost |
| `create_recovery_action` | Write | Yes | Schedule action (idempotent) |
| `execute_recovery_action` | Write | Yes | Execute via safe executor |
| `cancel_pending_action` | Write | Yes | Cancel scheduled actions |

All tools logged as `agent_events` with latency, input, output.

---

## 9. Simulator

### Configuration (`simulator/simulator_config.yaml`)

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
  insufficient_funds:
    retry_now: 0.3
    retry_delayed: 1.4
    payment_link: 1.1
    whatsapp_nudge: 1.0
    alternate_method: 0.8
  issuer_timeout:
    retry_now: 1.6
    retry_delayed: 1.0
    payment_link: 0.7
    whatsapp_nudge: 0.6
    alternate_method: 0.7
  card_blocked:
    retry_now: 0.0
    retry_delayed: 0.0
    payment_link: 1.2
    whatsapp_nudge: 0.8
    alternate_method: 1.4
```

### Functions

```python
def generate_orders(n: int, seed: int) -> list[Order]:
    """Deterministic order generation."""

def simulate_outcome(order: Order, action: str) -> SimulationResult:
    """P(recovery | context, action) clipped to [0, 0.95]"""
```

---

## 10. Executor

```python
async def execute_recovery_action(order_id: str, action: str) -> ActionResult:
    async with db.transaction():
        # Re-check policy immediately before execution
        allowed = await get_allowed_actions(order_id)
        if action not in allowed:
            return ActionResult(success=False, reason="Policy rejection at execution")
        
        # Idempotent: check for existing pending action
        existing = await get_pending_action(order_id)
        if existing:
            return ActionResult(success=False, reason="Action already pending")
        
        # Create recovery action record
        action_record = await create_recovery_action(order_id, action)
        
        # Call Razorpay sandbox (or simulate)
        result = await razorpay_client.execute(action_record)
        
        # Update status
        await update_action_status(action_record, "executed")
        
        return ActionResult(success=True, action_id=action_record.action_id)
```

---

## 11. API Contract

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Health check |
| GET | `/orders` | Order list (summary) |
| GET | `/orders/{order_id}` | Order detail + agent context |
| POST | `/webhooks/simulate` | Simulated webhook ingestion |
| GET | `/eval/summary` | Baseline comparison |
| GET | `/agent-runs` | Recent agent runs |
| GET | `/agent-runs/{run_id}` | Run detail |
| GET | `/agent-runs/{run_id}/events` | SSE event stream |
| POST | `/agent-runs/{run_id}/replay` | Replay run for demo |

---

## 12. Frontend Architecture

### Pages

| Route | Component | Data Source |
|-------|-----------|-------------|
| `/` | Overview | `/orders`, `/eval/summary`, `/agent-runs` |
| `/agent` | Agent Control Center | SSE `/agent-runs/{run_id}/events`, `/orders/{order_id}` |
| `/mcp` | MCP Control Center | `/mcp/status`, `/mcp/tools`, `/mcp/activity` |
| `/docs` | Documentation Portal | `docs/*.md` files |

### Agent Control Center Components

```
AgentControlCenter
├── AgentRunHeader          # Run ID, order, status, timeline
├── AgentGraph              # Visual stage graph
│   └── AgentStageNode      # Individual stage (idle/running/completed/rejected)
├── AgentEventTimeline      # Chronological event stream
├── ToolCallPanel           # Tool input/output for selected stage
├── CandidateComparison     # ERV bar chart for evaluated candidates
├── RecoveryPlanPanel       # Agent-generated plan steps
├── SafetyGatePanel         # Constraints checked, rejections
└── ExecutionPanel          # Action execution result
```

### SSE Connection

```typescript
// lib/sse.ts
export function createEventStream(runId: string): EventSource {
  const es = new EventSource(`/api/agent-runs/${runId}/events`);
  return es;
}
```

### MCP Page Components

```
MCPControlCenter
├── MCPStatusCard           # Server status, endpoint, transport
├── MCPToolCatalog          # Tool table with read/write classification
├── MCPLiveActivity         # Recent requests, latency, status
├── MCPSafetyPanel          # Policy gate status, rejections
└── MCPConnectionGuide      # Stdio command, HTTP endpoint, auth
```

### Documentation Portal

- Renders Markdown/MDX from `docs/` directory
- Navigation: Introduction → Architecture → Agent Runtime → AI Boundary → Recovery Policy → MCP → API → Data Model → Evaluation → Demo → Deployment → Troubleshooting
- Client-side rendering with syntax highlighting

---

## 13. MCP Server

### Tool Catalog

**Read-Only:**
- `reclaim_get_order_context(order_id)`
- `reclaim_get_allowed_actions(order_id)`
- `reclaim_estimate_recovery(order_id, action)`
- `reclaim_get_agent_run(run_id)`
- `reclaim_get_agent_events(run_id)`
- `reclaim_get_evaluation_summary()`

**Side-Effecting (Guarded):**
- `reclaim_start_recovery_run(order_id)`
- `reclaim_execute_recovery_action(order_id, action)`
- `reclaim_cancel_pending_action(order_id)`

### Implementation

```python
# backend/mcp_server/server.py
from mcp.server import MCPServer
from reclaim.tools.registry import tool_registry
from reclaim.policy.validator import validate_plan
from reclaim.executor.executor import execute_recovery_action

mcp = MCPServer("Reclaim")

@mcp.tool()
async def reclaim_get_order_context(order_id: str) -> dict:
    return await tool_registry.call("get_order_context", order_id=order_id)

@mcp.tool()
async def reclaim_execute_recovery_action(order_id: str, action: str) -> dict:
    # Delegates to same executor used by web app
    result = await execute_recovery_action(order_id, action)
    return result.model_dump()
```

### Transports

- **Development:** `uv run mcp dev backend/mcp_server/server.py` (stdio)
- **Production:** Streamable HTTP at `/mcp` (mounted in FastAPI)

```python
# In api/main.py
from backend.mcp_server.server import mcp
app.mount("/mcp", mcp.streamable_http_app())
```

---

## 14. Security

- **Gemini API key:** Backend only (`.env`, never exposed to browser)
- **MCP side-effecting tools:** Cannot bypass policy gate (same executor path)
- **LLM output:** Schema-validated before entering runtime
- **Payment state:** Deterministic, transactional
- **Webhooks:** Idempotent via `event_id` primary key
- **Agent transitions:** Fully persisted in `agent_events`
- **Test data:** Synthetic only, clearly labeled

---

## 15. Observability

Track per agent run:
- `run_id`, `order_id`, `stage`, `model`, `model_latency_ms`
- `input_tokens`, `output_tokens` (when available)
- `tool_calls_count`, `candidate_count`, `replan_count`
- `policy_rejections`, `execution_status`, `final_action`
- `recovered_amount`

---

## 16. Deployment

```
┌─────────┐     ┌─────────────┐     ┌────────────┐
│ Browser │────▶│   Vercel    │────▶│  FastAPI   │
│         │     │  (Next.js)  │     │ (Render)   │
└─────────┘     └─────────────┘     └─────┬──────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
             ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
             │ PostgreSQL  │       │   Gemini    │       │  Razorpay   │
             │  (Supabase) │       │    API      │       │  Sandbox    │
             └─────────────┘       └─────────────┘       └─────────────┘
```

### Environment Variables

```env
# Backend
DATABASE_URL=postgresql://...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.7-flash
CORS_ORIGINS=https://your-frontend.vercel.app

# Frontend
NEXT_PUBLIC_API_URL=https://your-backend.render.com
```

---

## 17. Day-by-Day Implementation Order

| Day | Backend | Frontend |
|-----|---------|----------|
| 1 | Repo, Postgres schema, env config | Next.js + Tailwind init |
| 2 | Webhook ingestion, state machine, idempotency | API client, types |
| 3 | Simulator config, generator | — |
| 4 | Simulator validation, seeded dataset | — |
| 5 | Constraint gate, allowed actions | — |
| 6 | ERV scoring, executor | — |
| 7 | Baseline evaluation, `/eval/summary` | Overview page (KPIs, chart) |
| 8 | Agent runtime, Gemini provider, MCP scaffold | — |
| 9 | Diagnosis, candidates, planning, replanning | Agent Control Center skeleton |
| 10 | Tool registry, safe execution | Agent graph, timeline, tool panel |
| 11 | SSE streaming, agent events API | Live agent view via SSE |
| 12 | Decision Inspector, MCP server tools | Decision Inspector, MCP page |
| 13 | Buffer, demo reliability, docs | Docs page, polish |
| 14 | Pitch prep | Final demo run |

---

## 18. Definition of Done

The project is complete when:

- [ ] Failed payment creates real agent run via webhook
- [ ] Gemini performs structured diagnosis, candidate generation, planning
- [ ] Tools provide deterministic facts (probabilities, ERV, allowed actions)
- [ ] Agent cannot execute forbidden actions (policy gate at planning + execution)
- [ ] Agent replans after rejection or new payment event
- [ ] Every agent stage appears in frontend from backend SSE events
- [ ] Payment capture cancels pending recovery actions
- [ ] Duplicate webhooks ignored (idempotency)
- [ ] Baseline vs Reclaim metrics reproducible (`/eval/summary`)
- [ ] Complete demo works from clean database
- [ ] MCP server exposes tools, delegates to domain services
- [ ] MCP cannot bypass safety rules
- [ ] `/agent` shows live agent execution
- [ ] `/mcp` shows operational MCP console
- [ ] `/docs` renders documentation from `docs/`
- [ ] No API key exposed to browser or repository

---

## 19. Non-Goals (Explicit)

- Dispute/chargeback agent
- Contextual bandits / online learning
- Train/validation split for simulator
- Unnecessary multi-agent LLM calls for UI
- Separate evaluation dashboard
- Production payment movement with real money
- Second business-logic implementation inside MCP

---

## 20. Panel Thesis

> Reclaim is not a retry bot and not a chatbot. It is an AI recovery agent that diagnoses why a payment failed, explores the recovery actions that are actually relevant, compares their expected outcomes, creates a bounded recovery plan, and adapts when reality changes — while deterministic payment infrastructure guarantees that the AI can never execute a forbidden action.