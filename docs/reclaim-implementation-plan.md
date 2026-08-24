# Reclaim — Implementation Plan

> Status: this is the original delivery checklist. The implementation now
> includes webhook ingestion, idempotency, simulator/evaluation, deterministic
> policy selection, Gemini explanations, the dashboard views, and method-aware
> alternate recovery recommendations. Remaining production work includes real
> provider execution, delayed jobs, refund/reversal handling, authentication,
> webhook signature verification, and production-calibrated probabilities.

Fills in the day-by-day schedule from `reclaim-build-plan.md` with actual tasks. Module names, table names, action types, and endpoints below match `reclaim-system-design.md` exactly — don't rename anything as you go, or the three documents drift out of sync with the repo.

---

## 1. Environment Setup (Day 0 — before Day 1 starts)

**Folder scaffold:**
```
reclaim/
  simulator/          __init__.py  generate.py  config_loader.py  simulator_config.yaml
  policy/             __init__.py  constraints.py  scoring.py
  agent/              __init__.py  tools.py  router.py  explain.py
  policy/             alternate.py
  api/                __init__.py  routes.py  main.py
  db/                 __init__.py  models.py  schema.sql
  dashboard/          (Next.js app, scaffolded separately)
  tests/              test_constraints.py  test_scoring.py  test_dedup.py  test_executor.py
  requirements.txt
  .env.example
  README.md
```

```bash
mkdir -p reclaim/{simulator,policy,agent,executor,api,db,tests}
cd reclaim && python -m venv venv && source venv/bin/activate
```

**`requirements.txt`:**
```
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
pydantic
pyyaml
python-dotenv
google-genai
mcp
pytest
httpx
```

**Postgres:** any Postgres 14+ database. The repo uses Supabase (free tier, project ref in `backend/.env`); a local `docker-compose.yml` with `postgres:16` works identically if you'd rather not depend on a hosted free tier.
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

**`.env.example`:**
```
DATABASE_URL=postgresql://user:pass@host:5432/reclaim
GEMINI_API_KEY=AIza...
```

**Dashboard scaffold:**
```bash
npx create-next-app@latest dashboard --typescript --tailwind --app
cd dashboard && npm install recharts
```

**One-time run:**
```bash
pip install -r requirements.txt
# schema already applied to Supabase via MCP; re-apply only if migrating:
psql $DATABASE_URL -f db/schema.sql
```

---

## 2. Day-by-Day Task Checklist

### Days 1–2 — State machine
- [ ] Write `db/schema.sql` (tables from system-design §4.1), apply it
- [ ] `db/models.py` — SQLAlchemy models mirroring the schema
- [ ] Webhook fixtures for `payment.failed` / `payment.captured` using real Razorpay field names (`error_code`, `error_reason`, `error_source`, `error_step`, `order_id`, `payment_id`)
- [ ] `POST /webhooks/simulate` — insert into `webhook_events` first (PK on `event_id` is the dedup mechanism); if insert fails on conflict, return `duplicate, ignored` and stop
- [ ] On `payment.captured`: single transaction that updates `orders.status = 'recovered'` **and** cancels every `scheduled` row in `recovery_actions` for that `order_id`
- [ ] Tests: same `event_id` fired twice → one row; `payment.captured` → order flips **and** pending action cancels in the same test
- **Definition of done:** firing fixtures via `curl` produces correct DB state; all three tests green.

### Days 3–4 — Simulator
- [ ] `simulator/simulator_config.yaml` — `base_rate`, `method_factor`, `action_fit` tables (system-design §2 values as a starting point)
- [ ] `generate_orders(n, seed)` — seeded, reproducible synthetic merchants/customers/orders/attempts
- [ ] `simulate_outcome(order, action)` — applies the probability formula, returns a boolean outcome
- [ ] A throwaway script that generates 2,000 orders and prints recovery-rate-by-failure-reason, so you can eyeball that the numbers roughly match the config before trusting anything built on top
- **Definition of done:** same seed → same dataset, every run; sanity numbers look plausible, not degenerate (not 0% or 100% everywhere).

### Days 5–6 — Policy engine
- [ ] `policy/constraints.py::get_allowed_actions(order, attempt, merchant)` — the hard-constraint gate, exactly as specified, never touching a score
- [ ] `policy/scoring.py::expected_value(order, attempt, action)` — the ERV formula
- [ ] Ranking + selection: max ERV among allowed actions; `NO_ACTION` if all negative; `HUMAN_REVIEW` if order value is high and top two actions are close
- [ ] Tests: hard decline forbids retry; `attempt_number > max_retries` forbids retry; contact budget exhausted forbids nudge; already-`recovered`/`lost` order returns an empty allowed set
- **Definition of done:** given any `(order, attempt)` pair, the function is deterministic and every constraint test passes.

### Day 7 — Baselines + eval
- [ ] `always_retry` policy — same call signature as the real policy engine, trivial body
- [ ] Eval runner: apply both policies to the same generated dataset, tally recovered revenue, recovery rate, unnecessary interventions, contact count
- [ ] `GET /eval/summary` returns this comparison as JSON
- **Definition of done:** one command reproduces the baseline-vs-Reclaim table from a fixed seed.

### Days 8–9 — MCP + agent + LLM
- [ ] `agent/tools.py` — the five MCP tools (`get_order_context`, `get_allowed_actions`, `estimate_recovery`, `execute_recovery_action`, `cancel_pending_action`)
- [ ] `agent/router.py` — orchestration loop: context → allowed actions → score each → execute best
- [ ] `agent/explain.py` — Gemini API call, decision JSON in, prose explanation out; the prompt must forbid the model from asserting anything not present in the input JSON
- [ ] Test: feed a hand-written decision JSON, assert the explanation text actually references the right constraint/reason, not generic filler
- [ ] Replace the Day 1–2 stub decision logic with the real router-agent flow
- **Definition of done:** firing a webhook end-to-end produces a scheduled/executed action **and** a stored explanation string, with no hard-coded shortcuts left from Day 1–2.

### Days 10–11 — Safe executor + demo scenario
- [ ] `agent/tools.py::execute_recovery_action(order_id, action)` — checks order status first, no-ops if already resolved, row-locks on `order_id`
- [ ] Wire `cancel_pending_action` to fire automatically inside the Day 1–2 recovery transaction, not as a separate manual step
- [ ] Script that fires the exact three-scenario demo sequence from build-plan §7 against a freshly seeded DB
- [ ] Rehearse it end-to-end at least three times, timed
- **Definition of done:** the idempotency scenario runs correctly from a clean DB state, repeatably, without manual intervention between steps.

### Day 12 — Dashboard
- [ ] Overview page: KPI row + Recharts bar chart, `always_retry` vs `reclaim` recovered revenue, pulled from `/eval/summary`
- [ ] Decision Inspector: order list/search, click-through to attempt timeline, candidate actions with ERVs, selected action, explanation text
- [ ] Wire to `/orders`, `/orders/{order_id}`, `/eval/summary`
- **Definition of done:** load the dashboard fresh, click through to the demo-scenario order, see the whole story without touching the API directly.

### Day 13 — Buffer + polish
- [ ] Fix whatever broke during Day 10–12 rehearsal — this day exists for exactly that, don't fill it with new features
- [ ] Write `README.md` per build-plan §10 (reframe, headline number, architecture diagram, setup steps, demo GIF, disclosure sentence, "what I chose not to build")
- [ ] Record the demo GIF/video
- [ ] Clean commit history — squash WIP commits into ones that read like real engineering
- **Definition of done:** a genuinely fresh `git clone` + the README's own setup steps works, verified by you, not assumed.

### Day 14 — Pitch + panel prep only
- [ ] Rehearse the 5-minute pitch against a timer, at least twice
- [ ] Mock panel Q&A using build-plan §12
- No new code today.

---

## 3. Testing Strategy

| Layer | Tool | Covers |
|---|---|---|
| Constraint gate, scoring | `pytest`, unit | Every hard constraint individually; ERV monotonicity on obvious cases |
| Idempotency | `pytest`, integration | Duplicate `event_id`; captured-payment race against a scheduled action |
| End-to-end webhook flow | `pytest` + `httpx` against a test DB | Full path from webhook in to action + explanation out |
| Dashboard | Manual, scripted | Walk the exact demo scenario, not free clicking |

Constraint and idempotency tests matter more than dashboard polish — that's what a panel will ask you to defend.

---

## 4. If You Fall Behind

Cut in this order, not randomly:
1. Drop `HUMAN_REVIEW` confidence logic — always auto-execute the top-ranked action.
2. Drop the Decision Inspector's per-action ERV breakdown — show only the selected action and its explanation.
3. Drop the eval runner's `unnecessary interventions` and `contact count` metrics — keep recovered revenue and recovery rate only.
4. Do not cut the idempotency demo scenario or its tests. That sequence is the entire reason this project is defensible in a panel interview — everything else is negotiable before that is.

---

The implementation is now beyond this original checklist. Use the root
`README.md` and `docs/reclaim-system-design.md` as the current operational and
architecture references; this file remains useful for historical sequencing.
