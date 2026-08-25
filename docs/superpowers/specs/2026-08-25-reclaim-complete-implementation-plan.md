# Reclaim — Implementation Plan

**Date:** 2026-08-25  
**Based on:** `docs/superpowers/specs/2026-08-25-reclaim-complete-architecture-design.md`  
**Approach:** Option A - Sequential 14-day build with MCP scaffolded early

---

## Phase 0: Repository Setup (Day 1 Morning)

### Tasks

- [ ] Initialize git repository at `/Users/arsh/Developer/Projects/Reclaim`
- [ ] Create directory structure per spec
- [ ] Create `.env.example` with all required variables
- [ ] Create `docker-compose.yml` for local development (optional, Supabase for prod)
- [ ] Create `requirements.txt` with all Python dependencies
- [ ] Create `README.md` with project overview
- [ ] Initialize Next.js dashboard with TypeScript + Tailwind

### Commands

```bash
# Backend structure
mkdir -p backend/{api,agent_runtime,agents,tools,policy,simulator,executor,db,mcp_server,gemini,tests}

# Dashboard structure
npx create-next-app@latest dashboard --typescript --tailwind --app --no-git
cd dashboard && npm install recharts date-fns lucide-react

# Root files
touch .env.example docker-compose.yml requirements.txt README.md ARCHITECTURE.md
```

### Files to Create

| File | Purpose |
|------|---------|
| `.env.example` | Template for all env vars |
| `docker-compose.yml` | Local Postgres (optional) |
| `requirements.txt` | Python deps |
| `backend/.env.example` | Backend-specific env template |
| `dashboard/.env.example` | Frontend env template |

### Environment Variables

```env
# Backend (.env)
DATABASE_URL=postgresql://postgres:password@localhost:5432/reclaim
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-3.7-flash
CORS_ORIGINS=http://localhost:3000

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Dependencies

```txt
# requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
pydantic==2.9.2
pydantic-settings==2.6.1
pyyaml==6.0.2
python-dotenv==1.0.1
google-genai==1.0.0
mcp[cli]==1.6.0
pytest==8.3.4
httpx==0.28.1
pytest-asyncio==0.24.0
```

---

## Phase 1: Database & Webhook Ingestion (Day 1-2)

### Day 1: Database Schema & Models

#### Tasks

- [ ] Create SQLAlchemy models for all tables
- [ ] Create database session management
- [ ] Create `init_db.py` for schema creation
- [ ] Apply schema to Supabase (or local Postgres)
- [ ] Write tests for model creation

#### Files

| File | Description |
|------|-------------|
| `backend/db/models.py` | All SQLAlchemy models |
| `backend/db/session.py` | Async session factory |
| `backend/db/init_db.py` | Create tables |
| `backend/tests/conftest.py` | Test fixtures with per-test schemas |

#### Key Models

```python
# Merchants, Customers, Orders, PaymentAttempts, WebhookEvents
# AgentRun, AgentEvent, RecoveryAction
```

### Day 2: Webhook Ingestion & State Machine

#### Tasks

- [ ] Implement `POST /webhooks/simulate` endpoint
- [ ] Idempotent ingestion via `event_id` primary key
- [ ] `payment.failed` → create payment attempt
- [ ] `payment.captured` → update attempt + order transactionally
- [ ] Captured payment cancels scheduled recovery actions
- [ ] Row locking (`SELECT ... FOR UPDATE`) for order state transitions
- [ ] Tests: duplicate events, capture cancels actions, race conditions

#### Files

| File | Description |
|------|-------------|
| `backend/api/schemas.py` | Pydantic webhook schemas |
| `backend/api/routes.py` | Webhook endpoint |
| `backend/api/main.py` | FastAPI app with CORS, lifespan |
| `backend/tests/test_webhooks.py` | Webhook tests |

#### Webhook Schema

```python
class WebhookEvent(BaseModel):
    entity: Literal["event"]
    account_id: str
    event: Literal["payment.failed", "payment.captured"]
    contains: list[str]
    payload: PaymentPayload

class PaymentPayload(BaseModel):
    payment: PaymentEntity

class PaymentEntity(BaseModel):
    id: str
    order_id: str
    amount: int  # paise
    currency: str
    method: str
    status: str
    attempt_number: int
    error_code: str | None = None
    error_description: str | None = None
    error_reason: str | None = None
    error_source: str | None = None
    error_step: str | None = None
```

---

## Phase 2: Simulator (Day 3-4)

### Day 3: Simulator Config & Generator

#### Tasks

- [ ] Create `simulator_config.yaml` with all rates/factors
- [ ] Create Pydantic config model with validation
- [ ] Implement `generate_orders(n, seed)` - deterministic
- [ ] Implement order/customer/merchant generation
- [ ] Persist generated orders to database

#### Files

| File | Description |
|------|-------------|
| `backend/simulator/config.py` | Pydantic config models |
| `backend/simulator/config_loader.py` | YAML loading with validation |
| `backend/simulator/generator.py` | `generate_orders(n, seed)` |
| `backend/simulator/__init__.py` | Exports |

#### Config Structure

```python
class SimulatorConfig(BaseModel):
    base_rate: dict[str, float]
    method_factor: dict[str, float]
    action_fit: dict[str, dict[str, float]]
    allowed_zero: list[str] = []
    linear_centered: bool = True
```

### Day 4: Simulator Validation & Outcome

#### Tasks

- [ ] Implement `simulate_outcome(order, action)` 
- [ ] Apply base_rate × method_factor × action_fit
- [ ] Clip probability to [0, 0.95]
- [ ] Eyeball test: print recovery rates by failure reason
- [ ] Seeded dataset generation (2000 orders, seed=42)
- [ ] Tests: reproducibility, no degenerate probabilities

#### Files

| File | Description |
|------|-------------|
| `backend/simulator/outcome.py` | `simulate_outcome()` |
| `backend/tests/test_simulator.py` | Simulator tests |

---

## Phase 3: Policy & Executor (Day 5-6)

### Day 5: Hard Constraint Gate

#### Tasks

- [ ] Define action constants: `RETRY_NOW`, `RETRY_DELAYED`, `PAYMENT_LINK`, `WHATSAPP_NUDGE`, `ALTERNATE_METHOD`, `NO_ACTION`, `HUMAN_REVIEW`
- [ ] Define `HARD_DECLINE_REASONS`, `RETRY_ACTIONS`, `CONTACT_ACTIONS`
- [ ] Implement `get_allowed_actions(order_id)` with all constraints
- [ ] Tests: each constraint individually, combinations

#### Files

| File | Description |
|------|-------------|
| `backend/policy/constraints.py` | Constraint logic |
| `backend/policy/__init__.py` | Exports |
| `backend/tests/test_policy.py` | Policy tests |

### Day 6: ERV Scoring & Executor

#### Tasks

- [ ] Implement `expected_value(order_id, action)` using simulator
- [ ] Define `ACTION_COSTS`, `FRICTION_COSTS`, `RISK_PENALTIES`
- [ ] Implement safe executor with:
  - Re-check policy before execution
  - Idempotency (check pending action)
  - Row locking for order
  - Transactional write to `recovery_actions`
- [ ] Tests: ERV calculation, executor rejects forbidden, idempotency

#### Files

| File | Description |
|------|-------------|
| `backend/policy/scoring.py` | ERV calculation |
| `backend/policy/validator.py` | Plan validation |
| `backend/executor/executor.py` | Safe executor |
| `backend/tests/test_executor.py` | Executor tests |

---

## Phase 4: Evaluation (Day 7)

### Tasks

- [ ] Implement `always_retry` baseline policy
- [ ] Implement `reclaim` deterministic policy
- [ ] Run both against same synthetic batch (2000 orders, seed=42)
- [ ] Compute metrics: recovered_revenue, recovery_rate, incremental_revenue, unnecessary_interventions, contact_count, avg_time_to_resolution
- [ ] Expose `GET /eval/summary`
- [ ] Store evaluation summary in DB

#### Files

| File | Description |
|------|-------------|
| `backend/api/routes.py` | Add `/eval/summary` endpoint |
| `backend/eval/baselines.py` | Baseline policies |
| `backend/eval/metrics.py` | Metric computation |
| `backend/eval/runner.py` | Evaluation runner |
| `backend/tests/test_eval.py` | Evaluation tests |

---

## Phase 5: Agent Runtime + Gemini (Day 8)

### Day 8: Runtime Foundation + Gemini Provider + MCP Scaffold

#### Tasks

- [ ] Create `AgentStage` enum and `RunState` dataclass
- [ ] Implement `AgentOrchestrator` with stage transitions
- [ ] Implement event emission + persistence to `agent_events`
- [ ] Create `LLMProvider` interface
- [ ] Implement `GeminiProvider` using `google-genai`
- [ ] Scaffold MCP server structure (tools delegate to domain services)
- [ ] Configure `GEMINI_MODEL` from env

#### Files

| File | Description |
|------|-------------|
| `backend/agent_runtime/state.py` | Stage enum, RunState |
| `backend/agent_runtime/orchestrator.py` | Main loop |
| `backend/agent_runtime/events.py` | Event types, emission |
| `backend/agent_runtime/provider.py` | LLMProvider interface |
| `backend/gemini/provider.py` | GeminiProvider |
| `backend/mcp_server/server.py` | MCP server scaffold |
| `backend/mcp_server/adapters.py` | Adapters to domain services |

---

## Phase 6: AI Capabilities (Day 9)

### Tasks

- [ ] **Diagnosis**: Structured failure classification via Gemini
- [ ] **Candidate Generation**: Propose relevant interventions via Gemini
- [ ] **Counterfactual Evaluation**: Call `estimate_recovery` for each candidate
- [ ] **Planning**: Generate bounded plan with steps, conditions, delays, stop conditions
- [ ] **Replanning**: Handle rejection + new payment events
- [ ] All Gemini calls use `structured_generate` with JSON schemas
- [ ] Tests: each AI stage with mocked provider

#### Files

| File | Description |
|------|-------------|
| `backend/agents/diagnosis.py` | Diagnosis agent |
| `backend/agents/candidate_generator.py` | Candidate generator |
| `backend/agents/planner.py` | Recovery planner |
| `backend/agents/replanner.py` | Replanner |
| `backend/agents/__init__.py` | Exports |
| `backend/tests/test_agents.py` | Agent tests |

#### Output Schemas

```json
// Diagnosis
{
  "failure_class": "temporary_financial",
  "severity": "medium", 
  "recoverability": "high",
  "key_factors": ["issuer_timeout"],
  "candidate_strategy": "delayed_retry"
}

// Candidate Generation
{
  "candidates": [
    {"action": "RETRY_DELAYED", "rationale": "...", "params": {"delay_minutes": 240}}
  ]
}

// Plan
{
  "objective": "maximize_expected_recovered_revenue",
  "steps": [
    {"action": "RETRY_DELAYED", "delay_minutes": 240},
    {"condition": "retry_failed", "action": "PAYMENT_LINK"}
  ],
  "stop_conditions": ["order_recovered", "hard_decline"]
}
```

---

## Phase 7: Tool Registry + Safe Execution (Day 10)

### Tasks

- [ ] Create tool registry with metadata (read_only, side_effect, description)
- [ ] Implement all 8 tools as internal Python functions
- [ ] Wire tools into agent runtime
- [ ] Ensure all tool calls logged as `agent_events`
- [ ] Connect executor to tool registry
- [ ] Tests: tool registry, tool execution, logging

#### Files

| File | Description |
|------|-------------|
| `backend/tools/registry.py` | Tool registry |
| `backend/tools/context_tools.py` | get_order_context, get_customer_history |
| `backend/tools/policy_tools.py` | get_allowed_actions, estimate_recovery, get_action_cost |
| `backend/tools/recovery_tools.py` | create_recovery_action, execute_recovery_action, cancel_pending_action |
| `backend/tools/simulation_tools.py` | simulate_outcome |
| `backend/tests/test_tools.py` | Tool tests |

---

## Phase 8: SSE Streaming (Day 11)

### Tasks

- [ ] Implement `GET /agent-runs/{run_id}/events` as SSE endpoint
- [ ] Event format matching spec
- [ ] Implement `GET /agent-runs` and `GET /agent-runs/{run_id}`
- [ ] Add `POST /agent-runs/{run_id}/replay` for demo
- [ ] Frontend: SSE connection manager (`lib/sse.ts`)
- [ ] Tests: SSE stream, event ordering

#### Files

| File | Description |
|------|-------------|
| `backend/api/sse.py` | SSE endpoint |
| `backend/api/routes.py` | Agent runs endpoints |
| `dashboard/lib/sse.ts` | SSE client |
| `dashboard/lib/api.ts` | API client updates |

---

## Phase 9: Agent Control Center (Day 10-12)

### Day 10: Skeleton + Graph

#### Tasks

- [ ] Create `/agent` page with layout
- [ ] Build `AgentGraph` component with stage nodes
- [ ] `AgentStageNode` with states: idle/running/completed/rejected/failed/waiting
- [ ] Connect SSE to update node states in real-time
- [ ] `AgentRunHeader` with run info

#### Files

| File | Description |
|------|-------------|
| `dashboard/app/agent/page.tsx` | Agent Control Center page |
| `dashboard/components/agent-graph/AgentGraph.tsx` | Stage visualization |
| `dashboard/components/agent-graph/AgentStageNode.tsx` | Individual node |
| `dashboard/components/agent-graph/StageStatus.tsx` | Status indicators |

### Day 11: Timeline + Tool Calls + Candidate Comparison

#### Tasks

- [ ] `AgentEventTimeline` - chronological event stream
- [ ] `ToolCallPanel` - input/output for selected stage
- [ ] `CandidateComparison` - ERV bar chart (Recharts)
- [ ] Connect all to SSE events

#### Files

| File | Description |
|------|-------------|
| `dashboard/components/agent-timeline/AgentEventTimeline.tsx` | Event timeline |
| `dashboard/components/agent-timeline/ToolCallPanel.tsx` | Tool panel |
| `dashboard/components/agent-timeline/CandidateComparison.tsx` | ERV chart |

### Day 12: Plan + Safety Gate + Execution + Decision Inspector + MCP Page

#### Tasks

- [ ] `RecoveryPlanPanel` - agent-generated plan steps
- [ ] `SafetyGatePanel` - constraints checked, rejections
- [ ] `ExecutionPanel` - action execution result
- [ ] Decision Inspector page at `/orders/{order_id}` (or integrate into `/agent`)
- [ ] Build `/mcp` page with:
  - Server status, endpoint, transport
  - Tool catalog with read/write classification
  - Live activity (recent requests, latency, status)
  - Safety panel (policy gate status)
  - Connection guide (stdio + HTTP)
- [ ] MCP API endpoints: `GET /mcp/status`, `GET /mcp/tools`, `GET /mcp/activity`

#### Files

| File | Description |
|------|-------------|
| `dashboard/components/agent-timeline/RecoveryPlanPanel.tsx` | Plan panel |
| `dashboard/components/agent-timeline/SafetyGatePanel.tsx` | Safety panel |
| `dashboard/components/agent-timeline/ExecutionPanel.tsx` | Execution panel |
| `dashboard/app/agent/components/DecisionInspector.tsx` | Decision inspector |
| `dashboard/app/mcp/page.tsx` | MCP Control Center |
| `dashboard/components/mcp-tools/MCPToolCatalog.tsx` | Tool table |
| `dashboard/components/mcp-tools/MCPLiveActivity.tsx` | Activity feed |
| `dashboard/components/mcp-tools/MCPSafetyPanel.tsx` | Safety panel |
| `dashboard/components/mcp-tools/MCPConnectionGuide.tsx` | Connection guide |
| `backend/api/routes.py` | MCP page API endpoints |

---

## Phase 10: Documentation Portal + Polish (Day 13)

### Tasks

- [ ] Create `/docs` page rendering Markdown from `docs/`
- [ ] Add navigation sidebar
- [ ] Syntax highlighting for code blocks
- [ ] Copy `reclaim-complete/docs/*.md` to `docs/`
- [ ] Fix any demo failures
- [ ] Test clean clone + run
- [ ] Record demo video
- [ ] Finalize README.md with headline metrics

#### Files

| File | Description |
|------|-------------|
| `dashboard/app/docs/page.tsx` | Documentation portal |
| `dashboard/components/markdown/MarkdownRenderer.tsx` | MDX rendering |
| `dashboard/components/markdown/DocSidebar.tsx` | Navigation |
| `docs/README.md` | Doc index |
| `docs/DOCUMENTATION.md` | Main docs |
| `docs/MCP.md` | MCP guide |
| `docs/API.md` | API reference |
| `README.md` | Root README |

---

## Phase 11: Pitch Prep (Day 14)

### Tasks

- [ ] Final demo run from clean database
- [ ] Verify all Definition of Done items
- [ ] Prepare 5-min pitch structure
- [ ] No new features

---

## Testing Strategy

### Unit Tests (Run on Every Commit)

```bash
pytest backend/tests/ -v --tb=short
```

| Test File | Coverage |
|-----------|----------|
| `test_simulator.py` | Config loading, generation, outcome |
| `test_policy.py` | Constraints, ERV, validator |
| `test_executor.py` | Idempotency, policy re-check, transactions |
| `test_agents.py` | Diagnosis, candidates, planning, replanning (mocked LLM) |
| `test_tools.py` | Tool registry, each tool |
| `test_webhooks.py` | Ingestion, idempotency, state machine |
| `test_eval.py` | Baseline comparison |
| `test_mcp.py` | Tool list, read tools, guarded write tools |

### Integration Tests

- [ ] Webhook → DB → Agent Runtime → Gemini → Tools → Policy → Executor → Events → Dashboard
- [ ] Duplicate event handling
- [ ] Payment capture cancels pending actions
- [ ] Replanning after rejection
- [ ] MCP tool calls through same path

### End-to-End Demo Script

```bash
# 1. Clean database
# 2. Generate 2000 orders (seed=42)
# 3. Run evaluation (capture headline metric)
# 4. Start backend + frontend
# 5. Fire payment.failed webhook
# 6. Show agent runtime in /agent
# 7. Fire payment.captured webhook
# 8. Show recovery action cancelled
# 9. Replay original event_id
# 10. Show duplicate ignored
# 11. Show complete event trace
# 12. Demo replanning: hard decline → retry rejected → payment_link
```

---

## Deployment Checklist

### Backend (Render)

- [ ] `requirements.txt` at root
- [ ] Build: `pip install -r requirements.txt`
- [ ] Start: `PYTHONPATH=. uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`
- [ ] Env vars: `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `CORS_ORIGINS`
- [ ] PostgreSQL: Supabase (existing project)

### Frontend (Vercel)

- [ ] Build: `cd dashboard && npm install && npm run build`
- [ ] Output: `.next` (static export) or web service
- [ ] Env: `NEXT_PUBLIC_API_URL=https://your-backend.render.com`
- [ ] Deploy to Vercel

### MCP Access

- [ ] Streamable HTTP at `https://backend.render.com/mcp`
- [ ] Configure MCP SDK host allowlist

---

## Definition of Done Verification

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Failed payment creates agent run | Webhook test + `/agent-runs` |
| 2 | Gemini diagnosis/planning | `/agent` shows stages |
| 3 | Tools provide deterministic facts | ERV values match simulator |
| 4 | Forbidden actions blocked | Hard decline → retry rejected |
| 5 | Replanning works | Rejection → new plan |
| 6 | Frontend shows backend events | SSE updates in real-time |
| 7 | Capture cancels pending actions | Recovery action status = cancelled |
| 8 | Duplicate webhooks ignored | Second webhook returns "duplicate" |
| 9 | Baseline vs Reclaim reproducible | `/eval/summary` stable |
| 10 | Clean DB demo works | Full demo script passes |
| 11 | MCP exposes tools | `tools/list` returns catalog |
| 12 | MCP respects safety | Forbidden action rejected |
| 13 | `/agent` live | Stage graph updates |
| 14 | `/mcp` operational | Shows live activity |
| 15 | `/docs` renders | Markdown displays |
| 16 | No key exposure | `.env` gitignored, no key in frontend |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Behind schedule | Cut: MCP page polish, docs page, secondary metrics |
| Gemini API issues | Fallback: template-based responses, keep deterministic path |
| SSE connection drops | Auto-reconnect in frontend, event replay from DB |
| Supabase connection limits | Connection pooling in SQLAlchemy |
| Simulator unrealistic | Clear disclosure, hand-tuned assumptions |

---

## Success Metrics

- **Headline:** Incremental recovered revenue vs `always_retry` (target: >25% improvement)
- **Technical:** All 46+ tests passing, clean demo from fresh DB
- **Demo:** 5-minute live agent execution + replanning
- **Code Quality:** No hardcoded secrets, type hints throughout, documented APIs