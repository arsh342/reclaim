# Reclaim — System Design Document

Companion to `reclaim-build-plan.md`. That file has the schedule, pitch script, and panel prep. This file has the architecture: HLD, LLD, diagrams, tech stack, module design, API contract.

---

## 1. Overview

Reclaim ingests Razorpay-style `payment.failed` / `payment.captured` events, runs each failed attempt through a deterministic constraint gate and a statistical expected-value scorer, records the highest-value permitted recovery intent idempotently, and explains the decision via an LLM layer that never touches financial state itself.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend / API | FastAPI (Python) | Simulator and policy-scoring logic is numeric; Python's ecosystem fits better than Node here, and keeping one language backend-to-agent reduces solo-build overhead. |
| Database | PostgreSQL | Row-level locking (`SELECT ... FOR UPDATE`) for order-level idempotency — same pattern as dispatchCore. |
| Agent / MCP | MCP Python SDK | Single-language backend; tools defined as plain FastAPI-adjacent functions, exposed via MCP. |
| LLM | Gemini API (Google) | Explanation layer only — receives a decision JSON, returns prose. Automatic function calling is disabled; never called to decide an action. |
| Frontend | Next.js + React + Tailwind | Matches CareerCompass / dispatchCore stack — no new framework to learn under deadline. |
| Charts | Recharts | Two charts total (Overview bar chart, Decision Inspector ERV comparison) — no need for a heavier library. |
| Testing | pytest | Idempotency and constraint-gate logic are exactly what a panel will probe — cover them with real tests, not manual clicking. |
| Deployment | Vercel (frontend) + Render or Railway (API + Postgres) | Free-tier, zero-ops, fast to stand up — this is a demo artifact, not production infra. |

---

## 3. High-Level Design

### 3.1 System Context

```mermaid
flowchart TB
    RZP[Razorpay-style Webhook Source<br/>simulated]
    MERCHANT[Merchant / Demo Operator]
    PANEL[Panel Interviewer]
    SYS[Reclaim]

    RZP -->|payment.failed / payment.captured| SYS
    SYS -->|recovery actions: retry, payment link, nudge| MERCHANT
    SYS -->|Overview + Decision Inspector| MERCHANT
    SYS -->|live demo| PANEL
```

### 3.2 Container / Component Diagram

```mermaid
flowchart TB
    subgraph Ingestion
        WH[Webhook Receiver]
        DEDUP[Event Dedup]
    end

    subgraph Core
        SIM[Recovery Outcome Simulator]
        POL[Policy Engine<br/>constraints + ERV scoring + method choice]
        EXE[Action Recorder<br/>idempotent scheduled intent]
    end

    subgraph AgentLayer[Agent / MCP]
        MCP[MCP Tool Server]
        ROUTER[Router Agent]
        LLM[Gemini — explanation only]
    end

    subgraph Presentation
        API[Dashboard API]
        UI[Dashboard UI]
    end

    DB[(PostgreSQL)]

    WH --> DEDUP --> DB
    DB --> ROUTER
    ROUTER --> MCP
    MCP --> POL
    MCP --> SIM
    POL --> EXE
    EXE --> DB
    ROUTER --> LLM
    LLM --> API
    API --> UI
    DB --> API
```

---

## 4. Low-Level Design

### 4.1 Data Model

Schema is identical to `reclaim-build-plan.md` §2. ER form:

```mermaid
erDiagram
    MERCHANTS ||--o{ ORDERS : has
    CUSTOMERS ||--o{ ORDERS : places
    ORDERS ||--o{ PAYMENT_ATTEMPTS : has
    ORDERS ||--o{ RECOVERY_ACTIONS : triggers

    MERCHANTS {
        string merchant_id PK
        int max_retries
        int contact_budget_per_day
    }
    CUSTOMERS {
        string customer_id PK
        numeric recovery_propensity
        string payment_method_preference
        numeric historical_success_rate
        numeric customer_value
    }
    ORDERS {
        string order_id PK
        string merchant_id FK
        string customer_id FK
        numeric amount
        string currency
        string status
        timestamp created_at
    }
    PAYMENT_ATTEMPTS {
        string payment_id PK
        string order_id FK
        int attempt_number
        string method
        string status
        string error_code
        string error_reason
        timestamp created_at
    }
    RECOVERY_ACTIONS {
        int action_id PK
        string order_id FK
        string action_type
        numeric expected_value
        string status
        timestamp scheduled_at
        timestamp executed_at
        timestamp cancelled_at
        string recommended_method
        string explanation
        string explanation_model
    }
```

`webhook_events(event_id PK, event_type, payload, processed_at)` is intentionally not linked with a foreign key — it's a pure dedup log, checked by primary-key insert before anything else runs.

### 4.2 State Machines

**Order:**
```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> recovered: any payment_attempt captured
    pending --> lost: max_retries exceeded, no action succeeds
    recovered --> [*]
    lost --> [*]
```

**Recovery action:**
```mermaid
stateDiagram-v2
    [*] --> scheduled
    scheduled --> executed: provider adapter fires action
    scheduled --> cancelled: order recovered or action abandoned
    executed --> [*]
    cancelled --> [*]
```

### 4.3 Sequence Diagrams

**Core idempotency scenario** (the live-demo script from the build plan, §7):

```mermaid
sequenceDiagram
    participant RZP as Webhook Source
    participant ING as Ingestion
    participant DB as Postgres
    participant AGENT as Router Agent
    participant POL as Policy Engine
    participant EXE as Action Recorder
    participant UI as Dashboard

    RZP->>ING: payment.failed (event_id=e1, payment_001)
    ING->>DB: insert webhook_events(e1)
    ING->>AGENT: new failed attempt
    AGENT->>POL: get_allowed_actions(order_id)
    POL-->>AGENT: [RETRY_DELAYED, PAYMENT_LINK, ...]
    AGENT->>POL: estimate_recovery(order_id, action) for each
    POL-->>AGENT: expected values
    AGENT->>EXE: execute_recovery_action(order_id, RETRY_DELAYED)
    EXE->>DB: insert recovery_actions(status=scheduled)
    EXE-->>UI: action scheduled

    RZP->>ING: payment.captured (event_id=e2, payment_002)
    ING->>DB: insert webhook_events(e2)
    ING->>DB: update orders set status=recovered
    ING->>EXE: cancel_pending_action(order_id)
    EXE->>DB: update recovery_actions set status=cancelled
    EXE-->>UI: order recovered, action cancelled

    RZP->>ING: payment.failed (event_id=e1) replay
    ING->>DB: insert webhook_events(e1)
    DB-->>ING: primary key conflict
    ING-->>UI: duplicate event_id ignored
```

**MCP tool-calling flow:**

```mermaid
sequenceDiagram
    participant Router as Router Agent
    participant MCP as MCP Tool Server
    participant LLM as Gemini — explanation only

    Router->>MCP: get_order_context(order_id)
    MCP-->>Router: order, customer, merchant, attempts
    Router->>MCP: get_allowed_actions(order_id)
    MCP-->>Router: allowed action list
    loop each allowed action
        Router->>MCP: estimate_recovery(order_id, action)
        MCP-->>Router: expected_value
    end
    Router->>MCP: execute_recovery_action(order_id, best_action)
    MCP-->>Router: result
    Router->>LLM: decision JSON
    LLM-->>Router: explanation text
```

### 4.4 Module Design

| Module | Responsibility | Key interface |
|---|---|---|
| `simulator/` | Generate synthetic orders + outcome probabilities from `simulator_config.yaml` | `generate_world(n, seed)`, `simulate_outcome(..., alternate_method)` |
| `policy/constraints.py` | Hard-constraint gate — evaluated before scoring, never mixed into it | `get_allowed_actions(order, attempt, merchant) -> list[ActionType]` |
| `policy/scoring.py` | Expected-value ranking on whatever survives the gate | `expected_value(context, action) -> float` |
| `policy/alternate.py` | Select a concrete route for `alternate_method` | `recommend_alternate_method(context) -> upi | another_card` |
| `agent/tools.py` | The five MCP tool functions (§4.3 sequence) | see build plan §6 |
| `agent/router.py` | Orchestration loop: context → allowed actions → score each → execute best | — |
| `agent/explain.py` | Gemini API call wrapper — decision JSON in, prose out, validated fallback | `explain_decision(decision) -> ExplanationResult` |
| `agent/tools.py` | Idempotent action recording, order-level row lock, auto-cancel on recovery | `execute_recovery_action(order_id, action) -> ActionResult` |
| `api/routes.py` | FastAPI routes, §4.5 | — |
| `db/models.py` | SQLAlchemy models mirroring §4.1 | — |

### 4.5 API Contract

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/orders` | List orders with status, feeds Overview + Decision Inspector search |
| `GET` | `/orders/{order_id}` | Full context: attempts, candidate actions + ERVs, selected action/method, recovery actions, explanation |
| `POST` | `/webhooks/simulate` | Fire a simulated webhook event — this is what drives the live demo |
| `GET` | `/eval/summary` | `always_retry` vs `reclaim` comparison metrics |
| `GET` | `/health` | Liveness check |

---

## 5. Non-Functional Design Notes

**Idempotency:** `event_id` primary key rejects replayed webhooks at the insert. Order-level state transitions (attempt captured → order recovered → cancel pending actions) happen inside one transaction, row-locked on `orders.order_id`, so a captured-payment webhook and an in-flight recovery-action execution can't race.

**Consistency:** Single Postgres instance, transactional writes, no distributed state. The current executor records scheduled recovery intent; real provider execution and delayed-job delivery are explicit production follow-ups.

**Access control:** All public tables have RLS enabled with deny-all policies. The FastAPI backend connects directly via `DATABASE_URL` (psycopg2, server-side) and bypasses RLS as the database owner — so the app is unaffected. This blocks anyone reaching the DB through Supabase's REST endpoint or anon key, ensuring all writes go through the backend's idempotent / audited paths.

**What changes at scale (talking points only, not build items):** a queue (SQS/Kafka-equivalent) in front of a real provider executor to decouple webhook ingestion from action execution; the MCP tool calls would move from synchronous to async; read replicas for the dashboard so analytics queries don't contend with the write path; the simulator's config-driven probabilities would be replaced by a model trained on real merchant outcome data, with the same disclosure discipline applied to whatever replaces it.

---

## 6. Deployment View

```mermaid
flowchart LR
    subgraph Vercel
        UI[Next.js Dashboard]
    end
    subgraph Render_Railway[Render / Railway]
        API[FastAPI + MCP Server]
        PG[(PostgreSQL)]
    end
    GEMINI[Gemini API]

    UI --> API
    API --> PG
    API --> GEMINI
```

Single API service hosting both the REST routes and the MCP tool server — no separate deployment needed for the agent layer at this scale.
