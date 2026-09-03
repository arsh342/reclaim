# Reclaim

AI revenue-recovery agent with Gemini, deterministic safety controls, live agent visualization, and MCP interoperability.

## Interfaces

- `/` — Overview dashboard
- `/agent` — Agent Control Center (live pipeline + event timeline)
- `/mcp` — MCP Control Center (live activity + tool catalog)
- `/docs` — Documentation portal
- `/orders` — Order management
- `/simulate` — Webhook simulator
- `/api/health` — Health check
- `/mcp` — MCP Streamable HTTP endpoint

## Core Architecture

```text
Payment Event (Razorpay)
        ↓
Webhook Ingestion (idempotent)
        ↓
SQLite / PostgreSQL State
        ↓
Reclaim Agent Runtime (10 stages)
        ↓
Gemini LLM (or mock provider)
        ↓
Structured Recovery Plan
        ↓
Policy Gate (hard constraints + ERV)
        ↓
Safe Executor (idempotent, re-validates)
        ↓
Payment Action
        ↓
Outcome / Replan
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or SQLite for demo)

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit DATABASE_URL, GEMINI_API_KEY
uvicorn backend.api.main:app --reload --port 8000
```

### Frontend
```bash
cd dashboard
npm install
npm run dev
```

### With Docker
```bash
docker-compose up -d
# Includes PostgreSQL + Redis + API
```

## Features

### Agent Pipeline (10 Stages)
| Stage | Description |
|-------|-------------|
| RECEIVED | Webhook event validated |
| CONTEXT_LOADING | Order, customer, merchant, payment history |
| DIAGNOSING | Failure classification + severity |
| GENERATING_CANDIDATES | Relevant interventions from allowed actions |
| EVALUATING_COUNTERFACTUALS | ERV per candidate via simulator |
| PLANNING | Bounded recovery plan with stop conditions |
| SAFETY_CHECK | Policy gate: hard constraints + ERV ranking |
| EXECUTING | Idempotent action execution |
| WAITING_FOR_OUTCOME | Monitors for payment outcome |
| COMPLETED | Run complete / replan if needed |

### Recovery Actions
- `RETRY_NOW` — Immediate retry
- `RETRY_DELAYED` — Scheduled retry (default 4hr)
- `PAYMENT_LINK` — Send payment link to customer
- `WHATSAPP_NUDGE` — WhatsApp reminder
- `ALTERNATE_METHOD` — Switch payment method
- `NO_ACTION` — Safe no-op (terminal orders)
- `HUMAN_REVIEW` — Escalate to operator

### Safety First
- **Hard constraints**: max retries, hard declines, contact budget, terminal states
- **ERV scoring**: P(recovery)×amount − costs − friction − risk
- **Executor re-check**: Policy re-validated at execution time
- **Idempotency**: Every action recorded, duplicates rejected
- **Audit trail**: Every stage, tool call, decision persisted

### MCP Server
Exposes 9 tools over Streamable HTTP at `/mcp`:
- 6 read-only (context, allowed actions, estimates, runs, events, eval)
- 3 guarded write (start run, execute action, cancel action)
All side-effects go through the same policy gate + executor.

### Evaluation
Compare `reclaim` vs `always_retry` baseline:
- Incremental recovered revenue
- Recovery rate
- Unnecessary interventions
- Customer contact count
- Time to resolution

## Documentation
- `/docs` — Interactive documentation portal
- `docs/DOCUMENTATION.md` — Full system documentation
- `docs/MCP.md` — MCP integration guide
- `docs/API.md` — API reference
- `docs/reclaim-system-design.md` — System design
- `docs/reclaim-implementation-plan.md` — Day-by-day build plan

## Demo Data
```bash
# Seed demo orders (idempotent)
curl -X POST http://localhost:8000/api/seed

# Or from Python
python scripts/seed_demo.py
```

## Testing
```bash
# Backend tests
make test

# E2E test (requires PostgreSQL)
make test-e2e

# Frontend lint
cd dashboard && npm run lint
```

## Project Structure
```
reclaim/
├── backend/
│   ├── agent_runtime/    # Orchestrator, state, events, LLM provider
│   ├── agents/           # Diagnosis, candidates, planner, replanner
│   ├── api/              # FastAPI routes, webhooks, SSE
│   ├── db/               # SQLAlchemy models, session, schema
│   ├── evaluator/        # Baseline comparison
│   ├── executor/         # Safe execution, idempotency
│   ├── gemini/           # Google GenAI provider
│   ├── mcp_server/       # MCP v2 server, tools, activity
│   ├── policy/           # Constraints, ERV scoring, validator
│   ├── simulator/        # Seeded outcome simulator
│   ├── tools/            # Internal tool registry
│   └── tests/            # Pytest suite
├── dashboard/
│   ├── app/              # Next.js 16 App Router pages
│   ├── components/       # React components (shadcn-style)
│   └── lib/              # API client, SSE, types
├── docs/                 # Markdown documentation
└── scripts/              # Seeding, E2E test
```

## License
MIT