# Reclaim: AI Revenue Recovery Platform
## Razorpay AI Builder Internship 2026 — Track 3 Submission

---

## Problem Statement

**Failed payments = lost revenue.**  
Every failed payment is a customer who wanted to pay but couldn't. Current recovery is:
- **Manual** — ops teams chase failures via spreadsheets
- **Blind retries** — same action, same failure, wasted cost
- **No intelligence** — no learning from what worked

**Result:** 20-30% recovery rate on ₹100M+ at-risk revenue.

---

## Solution: Reclaim

**Autonomous AI agent that diagnoses, plans, and executes recovery — learning from every outcome.**

```
Failed Payment → Webhook → AI Agent (11 stages) → Smart Action → Outcome → Learn
                     ↓
            Policy Engine + Counterfactual Evaluation
```

**Key Differentiator:** Not just "retry" — **selects the right action** (retry, payment link, WhatsApp nudge, alternate method, human review) based on expected revenue recovery (ERV).

---

## Architecture

### Backend (Python/FastAPI)
| Layer | Components |
|-------|------------|
| **Ingestion** | Razorpay webhook handler, idempotency, merchant/customer auto-create |
| **Policy** | `RecoveryPolicy` with retry caps, contact budgets, terminal states |
| **Scoring** | `calculate_expected_value()` — probabilistic ERV per action |
| **Executor** | Immediate/scheduled actions, idempotency keys, completion API |
| **Simulator** | Deterministic outcome simulation, 1000+ order generation |
| **Agent Runtime** | 11-stage orchestrator, LLM-driven, safety checks, replanning |
| **LLM Provider** | Google Gemini (real) + Mock fallback |
| **MCP Server** | 9 tools, JSON-RPC, SSE activity stream |
| **Evaluator** | Counterfactual "always retry" baseline, revenue metrics |

### Frontend (Next.js 16 + Tailwind v4)
- **7 pages** — Overview, Orders, Agent Control Center, Simulator, MCP Inspector, Docs
- **Real-time SSE** — Live agent pipeline, event timeline
- **Decision Inspector** — Diagnosis, candidate ERV breakdown, chosen action rationale

---

## Results (Evaluation on 1000 synthetic orders)

| Metric | Always Retry (Baseline) | Reclaim (AI Agent) | Improvement |
|--------|------------------------|-------------------|-------------|
| **Recovery Rate** | 29% | **88%** | **+59 pp** |
| **Recovered Revenue** | ₹423K | **₹1.16M** | **+₹737K** |
| **Cost per Recovery** | High (blind retries) | Optimized (ERV-driven) | **~40% lower** |

---

## Demo Flow (2 minutes)

1. **Start backend** → `PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000`
2. **Start frontend** → `cd dashboard && npm run dev`
3. **Open** `http://localhost:3000/agent`
4. **Click "Start New Agent Run (Demo)"** on `order_demo_insufficient_funds`
5. **Watch 11-stage pipeline** execute live:
   - RECEIVED → CONTEXT_LOADING → DIAGNOSING → GENERATING_CANDIDATES
   - EVALUATING_COUNTERFACTUALS → PLANNING → SAFETY_CHECK → EXECUTING
   - WAITING_FOR_OUTCOME → COMPLETED
6. **Open Order Detail** → See Decision Inspector with ERV breakdown
7. **Click "Mark Recovered"** on scheduled action → Order status updates instantly

---

## Technical Highlights

- **Type-safe** — Python 3.12 + Pydantic v2, TypeScript strict mode
- **Tested** — 24 unit/integration tests, deterministic seeds
- **Observable** — Structured logs, MCP activity SSE, agent event stream
- **Deployable** — Dockerfile, docker-compose, health checks
- **Extensible** — Tool registry, pluggable policies, MCP for external agents

---

## Next Steps (Post-Internship)

| Priority | Initiative |
|----------|------------|
| **P0** | Production hardening — auth, rate limits, structured logging |
| **P1** | Real merchant onboarding — sandbox webhook registration |
| **P1** | A/B testing framework — policy variants per merchant |
| **P2** | Multi-channel actions — email, IVR, push notifications |
| **P2** | Dashboard analytics — cohort retention, LTV impact |
| **P3** | Fine-tuned LLM — domain-specific recovery planner |

---

## Appendix: Code Structure

```
Reclaim/
├── backend/
│   ├── api/           # FastAPI routes, SSE, schemas
│   ├── db/            # SQLAlchemy models, session, migrations
│   ├── policy/        # Constraints, scoring, actions
│   ├── executor/      # Action execution, completion
│   ├── simulator/     # Outcome simulation, order gen
│   ├── agent_runtime/ # 11-stage orchestrator, state
│   ├── gemini/        # LLM provider (real + mock)
│   ├── mcp_server/    # 9 tools, JSON-RPC, SSE
│   ├── evaluator/     # Counterfactual baseline, metrics
│   └── tests/         # 24 passing tests
├── dashboard/         # Next.js 16 frontend
│   ├── app/           # 7 pages (App Router)
│   ├── components/    # UI (shadcn-style), agent pipeline
│   └── lib/           # API client, SSE, types
├── scripts/           # seed_demo.py
├── docs/              # Architecture, API, MCP guides
├── Dockerfile
├── docker-compose.yml
└── .env               # SQLite + GEMINI_API_KEY
```

---

## Contact

**Built for Razorpay AI Builder Internship 2026 — Track 3**  
*14-day solo build • Python/FastAPI + Next.js • 24 tests passing • Live demo ready*