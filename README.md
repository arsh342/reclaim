# Reclaim

> **Decides the highest-value action for every failed payment.**

---

## The Problem

Failed payments lose revenue twice:

1. **When they fail** — the customer didn't pay, the merchant didn't get paid.
2. **When the response is wrong** — the default response in most systems is "retry immediately." But that's often the wrong response:
   - **Hard declines** (`card_blocked`, `invalid_card`, `stolen_card`) — retrying wastes money and contact budget, and will never succeed.
   - **Soft declines** (`issuer_timeout`, `network_error`) — a delayed retry often succeeds, but an immediate one may hit the same transient issue.
   - **Insufficient funds** — the customer needs time or a different method (UPI, payment link).
   - **Customer already recovered** — the order is already `recovered`; retrying wastes money and annoys the customer.

Most payment systems treat "retry" as the default. Reclaim treats **retry as one of several ranked actions**, not the default.

---

## The Solution

**Reclaim is a decision engine for payment recovery.** Given a `payment.failed` webhook, it:

1. **Ingests** the webhook idempotently (PK on `event_id`).
2. **Constrains** — applies hard rules: no retry on hard declines, no retry past `max_retries`, no nudge past contact budget.
3. **Scores** — computes Expected Recovery Value (ERV) for each allowed action:
   ```
   ERV = P(recovery | context, action) × recoverable_amount
       − intervention_cost(action)
       − friction_cost(action, attempt_number)
       − risk_penalty(action)
   ```
4. **Chooses** the highest-ERV action (or `NO_ACTION`/`HUMAN_REVIEW` if appropriate).
5. **Records** the recovery intent idempotently via row-locked insert; auto-cancels on `payment.captured`.
6. **Explains** the decision via Google Gemini — the LLM narrates, never decides.

---

## The Headline Number

Run on the same simulated order set (`seed=42, n=2000`):

| Policy | Recovered Revenue | Recovery Rate |
|--------|-------------------|---------------|
| `always_retry` (naive baseline) | **₹4.37 Cr** | 41.5% |
| `reclaim` (full policy) | **₹9.12 Cr** | 86.6% |
| **Δ (incremental)** | **+₹4.75 Cr** | **+45.2 pp** |

Reproduce:
```bash
cd backend && PYTHONPATH=.. ./venv/bin/python -m backend.demo.run_demo --eval
```

---

## What It Does

| Capability | Description |
|------------|-------------|
| **Idempotent ingestion** | Razorpay-shaped webhooks (`payment.failed`, `payment.captured`) deduplicated on `event_id` primary key. |
| **Hard constraint gate** | Bans retry on `card_blocked`/`invalid_card`/`stolen_card`; enforces `max_retries`; caps daily nudges. |
| **Statistical ERV scoring** | Computes Expected Recovery Value for each allowed action using a disclosed simulator (`simulator_config.yaml`). |
| **Method-aware alternate routing** | When `alternate_method` wins, recommends concrete method: UPI for hard card failures/insufficient funds, another card otherwise. |
| **Idempotent action recording** | Row-locked inserts with `SELECT ... FOR UPDATE`; auto-cancels scheduled actions the moment `payment.captured` arrives. |
| **LLM explanation layer** | Google Gemini (`google-genai` SDK) narrates the deterministic decision; deterministic template fallback when no API key. **LLM never decides actions.** |

---

## Architecture

```
payment.failed webhook
        │
        ▼
┌────────────────────────────────────────────────┐
│  api/webhooks.py — idempotent ingest (PK dedup) │
└────────────────────────┬───────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│  agent/router.py — orchestrator                 │
│  ├── tools: context / constraints / estimates  │
│  │   / execute_recovery                         │
│  ├── policy — constraints + ERV ranking +      │
│  │   alternate-method recommendation            │
│  └── agent/explain.py — Gemini narrative        │
└────────────────────────┬───────────────────────┘
                         │
                         ▼
            recovery_actions table (idempotent)
```

### Data Flow

1. **Webhook received** → `POST /webhooks/simulate`
2. **Deduplication** → insert into `webhook_events` on `event_id` PK; duplicate returns `409`
3. **Record attempt** → insert `payment_attempts` (idempotent on `payment_id`)
4. **Run agent** → `router.run_agent(order_id)`:
   - `get_order_context` → full order/customer/merchant/attempts
   - `get_allowed_actions` → hard constraint gate
   - `estimate_recovery` for each allowed → ERV
   - `select_action` → highest ERV (or `NO_ACTION`/`HUMAN_REVIEW`)
   - `execute_recovery_action` → idempotent insert into `recovery_actions`
5. **Explain** → `explain_decision(decision)` → Gemini narrative (or template fallback)
6. **Persist explanation** → update `recovery_actions.explanation` + `explanation_model`
7. **On `payment.captured`** → flip order to `recovered` + cancel scheduled actions in same transaction

---

## The Dashboard

| Route | Purpose |
|-------|---------|
| `/` | **Overview** — headline delta (incremental revenue), KPI grid, bar chart (always_retry vs reclaim), recent orders |
| `/orders` | **Order list** — all failed payments, status, amount, link to inspector |
| `/orders/{id}` | **Decision Inspector** — attempt timeline, candidate actions with ERVs, selected action + method, recovery actions with explanations |
| `/simulate` | **Webhook simulator** — fire `payment.failed` / `payment.captured` from UI |

---

## Demo — Build-Plan §7 Scenarios

`backend/demo/run_demo.py` runs three end-to-end scenarios:

```bash
# Zero-setup (SQLite in-memory)
PYTHONPATH=. ./backend/venv/bin/python -m backend.demo.run_demo --scenario all --eval --db-url sqlite:///:memory:

# Or against PostgreSQL
PYTHONPATH=. ./backend/venv/bin/python -m backend.demo.run_demo --scenario all --eval --db-url postgresql://postgres:postgres@localhost:5432/reclaim_test
```

| Scenario | Description |
|----------|-------------|
| **1. Idempotency** | `payment.failed` for `pay_001` → schedule `retry_now`; `payment.captured` for `pay_002` → order flips to `recovered`, action auto-cancels; replay original `event_id` → `duplicate` ignored. |
| **2. Soft decline** | ₹1,200 `issuer_timeout` → immediate retry (`retry_now`) → succeeds. |
| **3. Hard decline, high value** | ₹78,000 `card_blocked` × 2 → retry forbidden by constraint gate; `alternate_method` (UPI) chosen on ERV; explanation shows why retry was never on the table. |

---

## The Simulator — Disclosed Assumptions

> **Because no proprietary merchant-level outcome dataset is available, Reclaim uses a synthetic simulator with transparent, hand-set assumptions to evaluate policy behavior. It is not presented as a forecast of Razorpay's production recovery rates.**

The simulator (`backend/simulator/simulator_config.yaml`) is fully disclosed:

- **5 failure reasons** with base recovery rates
- **3 payment methods** with effectiveness multipliers
- **5 recovery actions** × 5 reasons = 25 explicit `action_fit` cells
- **Alternate method** factors for UPI vs another card
- **Customer propensity** factor: `clip(0.5 + propensity, 0.5, 1.5)`
- **Probability clipping** to `[0, 0.95]`

All 25 `action_fit` cells are explicit — missing cells raise at load time, never silently default.

---

## Project Layout

```
.
├── backend/                    FastAPI + SQLAlchemy + Gemini
│   ├── api/                    routes, webhooks, fixtures, schemas
│   ├── agent/                  MCP tool set + orchestrator + LLM explain
│   ├── policy/                 constraints + ERV scoring + method selection
│   ├── simulator/              seeded world + outcome simulator
│   ├── eval/                   runner + baselines + metrics
│   ├── demo/run_demo.py        §7 scenario walk-through
│   ├── db/                     models + schema.sql + session
│   └── tests/                  46 tests (policy, simulator, webhook, router, API)
├── frontend/                   Next.js 16 + React 19 + Tailwind v4 + Recharts
│   ├── app/(dashboard)/        route group: /, /orders, /orders/[id], /simulate
│   └── components/             shared UI primitives (inline SVG icons)
├── docs/
│   ├── reclaim-build-plan.md        the design ask + pitch script + panel prep
│   ├── reclaim-system-design.md     architecture (HLD/LLD/sequences/ER)
│   └── reclaim-implementation-plan.md   day-by-day task list
├── scripts/test-e2e.sh             full end-to-end test script
├── pyproject.toml                  packaging + pytest + ruff + mypy config
├── Makefile                        common dev commands
├── README.md                       this file
└── .gitignore
```

---

## How to Run

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (or use SQLite in-memory for zero-setup)

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in DATABASE_URL and GEMINI_API_KEY

# Apply schema (or use Supabase MCP — schema already applied to project ref tzutffjemyydnimzesgj)
psql $DATABASE_URL -f db/schema.sql

# Run the API from the repository root
cd ..
uvicorn backend.api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env  # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

**Dashboard:** <http://localhost:3000>  
**Decision Inspector:** <http://localhost:3000/orders/order_demo_001> (after running demo)

### Tests

```bash
# From repo root. Integration tests need a reachable DATABASE_URL.
./backend/venv/bin/pytest backend/tests -q

# Or use Makefile
make test

# Full E2E test (starts backend, fires webhooks, verifies explanation)
./scripts/test-e2e.sh
```

### Demo

```bash
# Zero-setup (SQLite in-memory)
PYTHONPATH=. ./backend/venv/bin/python -m backend.demo.run_demo --scenario all --eval --db-url sqlite:///:memory:

# Or against PostgreSQL
PYTHONPATH=. ./backend/venv/bin/python -m backend.demo.run_demo --scenario all --eval --db-url postgresql://postgres:postgres@localhost:5432/reclaim_test
```

### Useful Makefile Commands

```bash
make test          # run all backend tests
make test-e2e      # full end-to-end test (starts backend, fires webhooks, verifies)
make frontend-build
make dev-backend   # backend with --reload
make dev-frontend  # frontend dev server
make clean         # clean build artifacts
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **LLM never decides** | Financial state transitions must be deterministic and auditable. LLM only narrates. |
| **Hard constraints as boolean gate** | Evaluated before scoring; never mixed into ERV. Ensures safety rules are absolute. |
| **ERV as ranking metric** | Risk-adjusted expected value in INR — directly comparable to revenue. |
| **Idempotency at two levels** | `event_id` PK for webhook dedup; `payment_id` check for attempt dedup; order-level row lock for state transitions. |
| **LLM explanation as separate step** | Separation of concerns: deterministic decision → explanation. Template fallback for offline/zero-key. |
| **Simulator as config, not code** | All probabilities in YAML; validated by Pydantic at load time; missing cells raise, never default. |
| **RLS enabled, no policies (yet)** | Blocks Supabase REST/anon access; backend connects as DB owner. Policies added when multi-tenant auth lands. |
| **SQLite for local dev** | Zero-setup demo: `--db-url sqlite:///:memory:` creates schema on the fly. |

---

## What I Chose Not to Build (and Why)

These are deliberate cuts under a 14-day deadline, not gaps:

| Cut | Reason |
|-----|--------|
| **Real bank-API integration** | All webhooks simulated via `/webhooks/simulate`. Production = thin Razorpay adapter in front of `ingest_webhook`. |
| **Real retry execution / delayed jobs** | Recovery actions recorded as scheduled intent; a worker + provider adapter must trigger actual payment attempt. |
| **Refund/reversal workflow** | Failed payments have no merchant settlement; provider-side reversal is a separate flow. |
| **Contact-channel adapters (SMS/email/push)** | Decision scheduled and logged; provider delivery is integration work, not design work. |
| **A/B test harness** | Deterministic simulator; statistical inference belongs in real experiment after shipping. |
| **Merchant policy editor UI** | Config loaded from YAML; UI is follow-up product surface, not load-bearing. |
| **Multi-tenant auth** | RLS enabled with deny-all; backend connects as DB owner. Per-merchant row filtering = auth-layer change. |
| **Self-hosted LLM alternatives** | Template fallback runs offline with zero API key. Production fallback (Ollama, vLLM) = config work. |
| **Dispute/chargeback agent** | Deliberate scope call under 14-day deadline. One deep pillar > two half-built. |
| **Train/val/stress split** | One simulator; policy is hand-authored, not fit to data. Nothing to overfit. |
| **Learning/bandit loop** | Static policy. One sentence in pitch as future work. |

---

## Evaluation & Disclosure

**Baselines compared:** `always_retry` (naive) vs `reclaim` (full policy) on identical simulated order set.

**Metrics reported:** recovered revenue (INR), recovery rate (%), unnecessary interventions, total interventions.

**Disclosure (verbatim from build plan):**
> *Because no proprietary merchant-level outcome dataset is available, Reclaim uses a synthetic simulator with transparent, hand-set assumptions to evaluate policy behavior. It is not presented as a forecast of Razorpay's production recovery rates.*

The absolute ₹ numbers depend on the simulator config, which is open in this repo. The **shape** of the comparison (incremental revenue vs. naive baseline) is what matters.

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [`docs/reclaim-system-design.md`](docs/reclaim-system-design.md) | Full HLD/LLD, sequence diagrams, ER diagram, API contract, deployment view |
| [`docs/reclaim-build-plan.md`](docs/reclaim-build-plan.md) | Original 14-day plan, pitch script, panel prep, cut list |
| [`docs/reclaim-implementation-plan.md`](docs/reclaim-implementation-plan.md) | Day-by-day task checklist |

---

## License

MIT — see `LICENSE` (not included in this solo build artifact).