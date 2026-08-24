# Reclaim — Backend

FastAPI service. Owns webhook ingestion, deterministic policy scoring,
idempotent recovery-action recording, simulator evaluation, and the Gemini
explanation layer.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL (Supabase) + GEMINI_API_KEY
```

## Apply schema to Supabase

```bash
psql "$DATABASE_URL" -f db/schema.sql
```

Or paste `db/schema.sql` into the Supabase SQL Editor.

## Run

```bash
cd ..
uvicorn backend.api.main:app --reload --port 8000
```

Open http://localhost:8000/health — should return `{"status": "ok"}`.

The API uses the Supabase session pooler connection string. A direct Supabase
database hostname may be IPv6-only and fail on IPv4-only networks.

## Test

```bash
pytest
```

The integration fixtures need a reachable `DATABASE_URL`. Pure policy and
simulator checks can run without a live database.

## Module map

- `db/` — SQLAlchemy models + schema.sql + session/engine
- `api/` — `/webhooks/simulate`, `/orders`, `/orders/{order_id}`, `/eval/summary`, and `/health`
- `policy/` — hard-constraint gate, ERV scoring, action selection, and concrete alternate-method recommendation
- `agent/` — context/estimate/execute tools, router, and Gemini explanation
- `simulator/` — seeded outcomes with disclosed, config-driven probabilities
- `eval/` — Reclaim versus always-retry comparison
- `tests/` — policy, simulator, webhook, router, and API tests

`alternate_method` currently recommends either `upi` or `another_card` and
persists that recommendation as `recovery_actions.recommended_method`.
`retry_delayed` currently records scheduled intent; a production worker still
needs to trigger the later payment attempt.

See `../docs/reclaim-implementation-plan.md` for the day-by-day task list.
