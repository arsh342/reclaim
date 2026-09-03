"use client";

import { useState } from "react";
import { ChevronRight, FileText, BookOpen, Code, Server, Shield, Zap, Activity, Wrench, GitBranch } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface DocSection {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: string;
  badge?: string;
  badgeVariant?: "default" | "success" | "warning" | "destructive";
}

const DOCS: DocSection[] = [
  {
    id: "introduction",
    title: "Introduction",
    icon: <BookOpen className="h-4 w-4" />,
    content: `
# What is Reclaim?

Reclaim is an AI revenue-recovery platform for failed payments. It observes failed payment attempts, diagnoses the failure, determines relevant interventions, evaluates recovery alternatives, builds a bounded plan, executes permitted actions, and adapts when payment state changes.

> Reclaim is not a retry bot and not a chatbot.

## Core Principle

> **AI decides what should happen. Deterministic infrastructure guarantees what is allowed to happen.**

### AI Responsibilities
- Failure diagnosis
- Customer/payment context interpretation
- Candidate generation
- Counterfactual reasoning
- Recovery planning
- Replanning
- Natural-language explanation

### Deterministic Responsibilities
- Payment state
- Hard constraints
- Expected-value calculation
- Idempotency
- Action execution
- Stopping rules
- Audit trail
    `,
  },
  {
    id: "architecture",
    title: "Architecture",
    icon: <Server className="h-4 w-4" />,
    content: `
# System Architecture

\`\`\`text
Razorpay Event
      ↓
Webhook Ingestion (idempotent)
      ↓
SQLite/PostgreSQL State
      ↓
Reclaim Agent Runtime
      ↓
Gemini (or mock provider)
      ↓
Structured Plan
      ↓
Policy Gate (hard constraints + ERV)
      ↓
Safe Executor (idempotent, re-validates)
      ↓
Payment Action
      ↓
Outcome Event
      ↓
Replan or Complete
\`\`\`

## Components

1. **Webhook Ingestion** - Idempotent event ingestion with deduplication by \`event_id\`
2. **Agent Runtime** - 10-stage state machine orchestrating the recovery flow
3. **Gemini Provider** - LLM for diagnosis, planning, replanning (with mock fallback)
4. **Tool Registry** - Internal tools for context, policy, execution, simulation
5. **Policy Engine** - Hard constraints + ERV scoring + validation
6. **Safe Executor** - Idempotent action execution with policy re-validation
7. **Database** - Persistent state and complete audit trail
8. **MCP Server** - Interoperability layer exposing same domain services
    `,
  },
  {
    id: "agent-runtime",
    title: "Agent Runtime",
    icon: <Zap className="h-4 w-4" />,
    badge: "Updated",
    badgeVariant: "success",
    content: `
# Agent Runtime

The agent runtime is a Reclaim-owned state machine, not a vendor-specific agent wrapper. Runs execute in the background with live SSE streaming.

## Agent Stages (10)

\`\`\`text
RECEIVED
  ↓
CONTEXT_LOADING
  ↓
DIAGNOSING
  ↓
GENERATING_CANDIDATES
  ↓
EVALUATING_COUNTERFACTUALS
  ↓
PLANNING
  ↓
SAFETY_CHECK
  ├── rejected → REPLANNING (max 3×)
  └── approved → EXECUTING
                    ↓
              WAITING_FOR_OUTCOME
                    ↓
              COMPLETED
\`\`\`

These are logical stages; not necessarily separate Gemini API calls.

## Runtime Responsibilities

1. Create \`agent_run\` record with unique \`run_id\`
2. Load order, merchant, customer, and payment history via \`get_order_context\`
3. Ask LLM for structured diagnosis (failure class, severity, recoverability)
4. Ask LLM to generate relevant candidate interventions (respecting allowed actions)
5. Call deterministic tools for each candidate: \`estimate_recovery\` (ERV)
6. Give LLM the counterfactual results
7. Generate a bounded recovery plan with stop conditions
8. Validate the plan against deterministic policy (hard constraints + ERV)
9. Execute only permitted actions via safe executor
10. Stream every stage event to frontend via SSE
11. Persist complete audit trail to \`agent_events\`
12. Replan when an action is rejected or payment state changes

## Key Improvements

- **Background execution**: Runs start immediately, stream events via SSE
- **Full pipeline on all orders**: Terminal orders execute NO_ACTION through full pipeline
- **Live durations**: Stage durations computed from actual timestamps
- **Auto-refresh**: Runs list updates when SSE signals completion
    `,
  },
  {
    id: "ai-boundary",
    title: "AI / Deterministic Boundary",
    icon: <Code className="h-4 w-4" />,
    content: `
# AI / Deterministic Boundary

\`\`\`text
                    AI CONTROLLED
        +----------------------------------+
        | failure diagnosis                |
        | contextual interpretation        |
        | candidate generation             |
        | counterfactual reasoning         |
        | plan generation                  |
        | replanning                       |
        +----------------+-----------------+
                         |
                         v
                STRUCTURED PLAN
                         |
        +----------------+-----------------+
        | DETERMINISTIC CONTROL            |
        | hard constraints                 |
        | ERV calculation                  |
        | action validation                |
        | idempotency                      |
        | payment state                    |
        | execution                        |
        | audit                            |
        +----------------------------------+
\`\`\`

This prevents an LLM-generated statement such as \`retry_now\` from becoming a financial action without validation.

## How It Works

1. **LLM proposes** — Output is schema-validated (Pydantic/JSON Schema)
2. **Policy gate** — Hard constraints filter forbidden actions; ERV ranks remaining
3. **Executor re-checks** — Before execution, policy is re-evaluated against current state
4. **Idempotency** — Every action recorded with unique constraints; duplicates rejected
5. **Audit trail** — Every stage, tool call, policy decision, and outcome persisted
    `,
  },
  {
    id: "recovery-policy",
    title: "Recovery Policy",
    icon: <Shield className="h-4 w-4" />,
    content: `
# Recovery Policy

## Candidate Actions

\`\`\`text
RETRY_NOW
RETRY_DELAYED
PAYMENT_LINK
WHATSAPP_NUDGE
ALTERNATE_METHOD
NO_ACTION
HUMAN_REVIEW
\`\`\`

## Hard Constraints (Evaluated Before Scoring)

\`\`\`python
# Terminal order states
if order.status in {"recovered", "lost"}:
    allowed = []  # only NO_ACTION/HUMAN_REVIEW via validator

# Max retries exceeded
if attempt_number > merchant.max_retries:
    forbid retry actions

# Hard decline reasons
if error_reason in HARD_DECLINE_SET:  # card_blocked, invalid_card, stolen_card, expired_card
    forbid retry actions

# Daily contact budget
if daily_contact_count >= merchant.contact_budget_per_day:
    forbid contact actions (PAYMENT_LINK, WHATSAPP_NUDGE)

# Always allowed (validator contract)
NO_ACTION, HUMAN_REVIEW always permitted
\`\`\`

## Expected Recovery Value (ERV)

\`\`\`text
ERV(action) =
    P(recovery | context, action) × recoverable_amount
    − intervention_cost(action)
    − friction_cost(action, attempt_number)
    − risk_penalty(action)
\`\`\`

Costs (configurable):
- RETRY_NOW: intervention=₹0, friction=₹1
- RETRY_DELAYED: intervention=₹0, friction=₹0.5
- PAYMENT_LINK: intervention=₹5, friction=₹3
- WHATSAPP_NUDGE: intervention=₹2, friction=₹1
- ALTERNATE_METHOD: intervention=₹10, friction=₹5

The AI may request any action, but the safe executor independently re-runs the hard-constraint gate. A forbidden action cannot execute.
    `,
  },
  {
    id: "mcp",
    title: "MCP Server",
    icon: <Server className="h-4 w-4" />,
    badge: "Live",
    badgeVariant: "success",
    content: `
# MCP Server

Reclaim exposes its revenue-recovery capabilities through the Model Context Protocol (MCP). MCP is an **interoperability layer**, not a second runtime.

## Primary Endpoint

\`\`\`text
/mcp
\`\`\`

## Transport

\`\`\`text
Streamable HTTP (production)
stdio (local development)
\`\`\`

## Development

\`\`\`bash
uv run mcp dev backend/mcp_server/server.py
\`\`\`

## Tool Catalog (9 tools)

### Read-only (Safe)
| Tool | Description |
|------|-------------|
| \`reclaim_get_order_context\` | Retrieve order, customer, merchant, payment attempts |
| \`reclaim_get_allowed_actions\` | Actions allowed by deterministic policy |
| \`reclaim_estimate_recovery\` | Recovery probability & expected recovery value |
| \`reclaim_get_agent_run\` | Retrieve an agent run |
| \`reclaim_get_agent_events\` | Retrieve agent execution events |
| \`reclaim_get_evaluation_summary\` | Baseline comparison metrics |

### Guarded Side-effecting
| Tool | Description | Safety |
|------|-------------|--------|
| \`reclaim_start_recovery_run\` | Start a bounded recovery workflow | Policy gate + executor |
| \`reclaim_execute_recovery_action\` | Execute a permitted recovery action | Policy re-check + idempotency |
| \`reclaim_cancel_pending_action\` | Cancel a scheduled action | Idempotent |

Every side-effecting operation goes through the **same safety gate and executor** used by the web application. An MCP client cannot bypass policy.

## Connection

\`\`\`json
{
  "mcpServers": {
    "reclaim": {
      "url": "https://your-domain.com/mcp"
    }
  }
}
\`\`\`
    `,
  },
  {
    id: "api",
    title: "API Reference",
    icon: <Code className="h-4 w-4" />,
    content: `
# API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | \`/health\` | Health check |
| GET | \`/api/orders\` | Order list (excludes eval orders) |
| GET | \`/api/orders/{order_id}\` | Order detail with decision analysis |
| POST | \`/api/webhooks/simulate\` | Simulate Razorpay webhook |
| GET | \`/api/eval/summary\` | Evaluation summary (5-min cache) |
| GET | \`/api/agent-runs\` | Agent runs list |
| GET | \`/api/agent-runs/{run_id}\` | Run detail |
| GET | \`/api/agent-runs/{run_id}/events\` | SSE event stream |
| POST | \`/api/agent-runs/{order_id}/start\` | Start background agent run |
| POST | \`/api/agent-runs/{run_id}/replay\` | Replay run for demo |
| POST | \`/api/recovery-actions/{action_id}/complete\` | Mark action complete |
| GET | \`/api/mcp/status\` | MCP server status |
| GET | \`/api/mcp/tools\` | MCP tool catalog |
| GET | \`/api/mcp/activity\` | Recent MCP activity |
| GET | \`/api/mcp/activity/stream\` | SSE activity stream |
| POST | \`/api/seed\` | Seed demo data (idempotent) |

## Webhook Schema

\`\`\`json
{
  "entity": "event",
  "account_id": "acc_test",
  "event": "payment.failed",
  "contains": ["payment"],
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_001",
        "order_id": "order_001",
        "amount": 500000,
        "currency": "INR",
        "method": "card",
        "status": "failed",
        "attempt_number": 1,
        "error_code": "BAD_REQUEST_PAYMENT_FAILED",
        "error_description": "Payment failed",
        "error_reason": "issuer_timeout",
        "error_source": "customer",
        "error_step": "payment_authentication"
      }
    }
  }
}
\`\`\`

## Start Agent Run

\`\`\`bash
curl -X POST http://localhost:8000/api/agent-runs/order_001/start
# Returns immediately with run_id, status=running
\`\`\`

Then connect SSE: \`GET /api/agent-runs/{run_id}/events\`
    `,
  },
  {
    id: "data-model",
    title: "Data Model",
    icon: <FileText className="h-4 w-4" />,
    content: `
# Data Model

One \`order_id\` can have multiple \`payment_id\` attempts. \`event_id\` is the webhook deduplication key.

\`\`\`sql
-- Merchants & Customers
CREATE TABLE merchants (
  merchant_id TEXT PRIMARY KEY,
  max_retries INT NOT NULL DEFAULT 3,
  contact_budget_per_day INT NOT NULL DEFAULT 2
);

CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  recovery_propensity NUMERIC(3,2) NOT NULL,
  payment_method_preference TEXT,
  historical_success_rate NUMERIC(3,2),
  customer_value NUMERIC(12,2) NOT NULL
);

-- Orders & Attempts
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  merchant_id TEXT REFERENCES merchants(merchant_id),
  customer_id TEXT REFERENCES customers(customer_id),
  amount NUMERIC(12,2) NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'pending',  -- pending, recovered, lost
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (order_id, attempt_number)
);

-- Webhooks (idempotency key)
CREATE TABLE webhook_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ
);

-- Agent runs & events
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

CREATE TABLE agent_events (
  event_seq BIGSERIAL PRIMARY KEY,
  run_id TEXT REFERENCES agent_runs(run_id),
  order_id TEXT REFERENCES orders(order_id),
  agent_stage TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Recovery actions
CREATE TABLE recovery_actions (
  action_id BIGSERIAL PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  action_type TEXT NOT NULL,
  expected_value NUMERIC(12,2) NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled, executed, cancelled
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  executed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  reason TEXT
);
\`\`\`
    `,
  },
  {
    id: "evaluation",
    title: "Evaluation",
    icon: <Zap className="h-4 w-4" />,
    content: `
# Evaluation Framework

Compare exactly two policies on the same synthetic batch:

1. \`always_retry\` — baseline that retries every failed payment
2. \`reclaim\` — full AI + deterministic policy pipeline

## Metrics

- Recovered revenue
- Recovery rate
- Incremental recovered revenue (vs always_retry)
- Unnecessary interventions
- Customer contact count
- Average time to resolution

The headline pitch metric: **incremental recovered revenue versus \`always_retry\`**.

## Run Evaluation

\`\`\`bash
GET /api/eval/summary?n_orders=2000&seed=42
\`\`\`

Results cached for 5 minutes. Synthetic probabilities are seeded and disclosed — not Razorpay production statistics.
    `,
  },
  {
    id: "demo",
    title: "Demo Scenarios",
    icon: <Activity className="h-4 w-4" />,
    content: `
# Demo Scenarios

## Idempotency Demo

\`\`\`text
payment_001 fails
        ↓
agent plans delayed retry
        ↓
payment_002 captures
        ↓
order becomes recovered
        ↓
pending retry is cancelled
        ↓
payment_001 failure event is replayed
        ↓
duplicate event ignored
\`\`\`

## Replanning Demo

\`\`\`text
hard decline (card_blocked)
        ↓
agent proposes RETRY_DELAYED
        ↓
policy rejects retry (hard decline)
        ↓
agent receives rejection
        ↓
agent replans → PAYMENT_LINK
        ↓
safety gate approves
        ↓
executor executes
\`\`\`

This demonstrates the AI operating inside a real controlled agent runtime with deterministic guardrails.

## Terminal Order Demo

\`\`\`text
order already recovered
        ↓
agent loads context (status=recovered)
        ↓
full pipeline executes
        ↓
planner proposes NO_ACTION
        ↓
safety gate approves
        ↓
executor executes NO_ACTION (no-op)
        ↓
run completes cleanly
\`\`\`
    `,
  },
  {
    id: "deployment",
    title: "Deployment",
    icon: <Server className="h-4 w-4" />,
    content: `
# Deployment

\`\`\`text
Vercel (Frontend)
  ↓
FastAPI (Backend)
  ├── REST /api/*
  ├── SSE /api/agent-runs/*/events
  └── MCP /mcp
       ↓
PostgreSQL (Supabase / Render / self-hosted)
       ↓
Gemini API (Google AI Studio)
\`\`\`

## Environment Variables

### Backend
\`\`\`env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=gemini-1.5-flash
CORS_ORIGINS=https://your-frontend.vercel.app
\`\`\`

### Frontend
\`\`\`env
NEXT_PUBLIC_API_URL=https://your-backend.render.com
\`\`\`

## Backend (Render / Fly.io / Railway)
- Build: \`pip install -r requirements.txt\`
- Start: \`PYTHONPATH=. uvicorn backend.api.main:app --host 0.0.0.0 --port \$PORT\`
- Health: \`GET /health\`

## Frontend (Vercel)
- Build: \`cd dashboard && npm install && npm run build\`
- Output: \`.next\` (static export for App Router)

## Docker
\`\`\`bash
docker-compose up -d
\`\`\`
Includes PostgreSQL + Redis + API.
    `,
  },
  {
    id: "troubleshooting",
    title: "Troubleshooting",
    icon: <Wrench className="h-4 w-4" />,
    content: `
# Troubleshooting

## Common Issues

### Backend won't start
- Check \`DATABASE_URL\` is correct (async driver: \`postgresql+asyncpg://\`)
- Verify \`GEMINI_API_KEY\` is set (or mock will be used)
- Ensure database is accessible (PostgreSQL or SQLite)

### Frontend shows "Backend not responding"
- Verify \`NEXT_PUBLIC_API_URL\` matches backend URL
- Check CORS settings on backend (\`CORS_ORIGINS\`)
- Ensure backend is deployed and healthy (\`GET /health\`)

### Agent not running / stuck
- Check webhook ingestion works (\`POST /api/webhooks/simulate\`)
- Verify \`agent_runs\` table has entries
- Check SSE connection in browser dev tools (\`/api/agent-runs/{run_id}/events\`)
- Background task may have failed — check backend logs

### MCP connection fails
- Verify \`/mcp\` endpoint is accessible
- Check MCP SDK version compatibility (v2+)
- Ensure Streamable HTTP transport is configured
- For stdio: \`uv run mcp dev backend/mcp_server/server.py\`

### Order status not updating
- \`payment.failed\` → order status = \`failed\`
- \`payment.captured\` → order status = \`recovered\`, pending actions cancelled
- Executor re-checks policy before execution

## Debug Commands

\`\`\`bash
# Backend health
curl https://your-backend.com/health

# Orders
curl https://your-backend.com/api/orders

# Evaluation
curl https://your-backend.com/api/eval/summary

# Test webhook (payment.failed)
curl -X POST http://localhost:8000/api/webhooks/simulate \\
  -H "Content-Type: application/json" \\
  -d '{"entity":"event","account_id":"acc_test","event":"payment.failed","contains":["payment"],"payload":{"payment":{"entity":{"id":"pay_test","order_id":"order_test","amount":500000,"currency":"INR","method":"card","status":"failed","attempt_number":1,"error_reason":"issuer_timeout"}}}}'

# Test webhook (payment.captured)
curl -X POST http://localhost:8000/api/webhooks/simulate \\
  -H "Content-Type: application/json" \\
  -d '{"entity":"event","account_id":"acc_test","event":"payment.captured","contains":["payment"],"payload":{"payment":{"entity":{"id":"pay_test_2","order_id":"order_test","amount":500000,"currency":"INR","method":"card","status":"captured","attempt_number":2}}}}'

# Start agent run
curl -X POST http://localhost:8000/api/agent-runs/order_test/start

# Stream events
curl http://localhost:8000/api/agent-runs/{run_id}/events
\`\`\`
    `,
  },
  {
    id: "contributing",
    title: "Contributing",
    icon: <GitBranch className="h-4 w-4" />,
    badge: "New",
    badgeVariant: "default",
    content: `
# Contributing

## Development Setup

\`\`\`bash
# Clone
git clone https://github.com/your-org/reclaim
cd reclaim

# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit DATABASE_URL, GEMINI_API_KEY
uvicorn backend.api.main:app --reload --port 8000

# Frontend (separate terminal)
cd dashboard
npm install
npm run dev
\`\`\`

## Running Tests

\`\`\`bash
# Backend tests (requires database)
make test
# or
cd backend && DATABASE_URL=sqlite+aiosqlite:///./test.db ./venv/bin/pytest

# E2E test (requires PostgreSQL)
make test-e2e

# Frontend lint
cd dashboard && npm run lint
\`\`\`

## Code Style

- Backend: Ruff (line-length 100, single quotes) + MyPy (strict-ish)
- Frontend: ESLint + TypeScript strict
- Commit messages: Conventional Commits

## Project Structure

\`\`\`text
reclaim/
├── backend/
│   ├── agent_runtime/    # Orchestrator, state, events, provider
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
\`\`\`
    `,
  },
];

function DocSidebar({ activeId, onSelect }: { activeId: string; onSelect: (id: string) => void }) {
  return (
    <aside className="w-64 border-r bg-muted/30 p-4 overflow-y-auto h-[calc(100vh-4rem)] sticky top-4">
      <nav className="space-y-1">
        {DOCS.map((section) => (
          <button
            key={section.id}
            onClick={() => onSelect(section.id)}
            className={`w-full text-left p-2 rounded transition-colors flex items-center justify-between ${
              activeId === section.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent"
            }`}
          >
            <div className="flex items-center gap-2">
              {section.icon}
              <span className="text-sm font-medium">{section.title}</span>
            </div>
            {section.badge && (
              <Badge variant={section.badgeVariant} className="text-xs">
                {section.badge}
              </Badge>
            )}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  
  let inCodeBlock = false;
  let codeContent = "";
  
  lines.forEach((line, idx) => {
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <pre key={idx} className="bg-muted p-4 rounded-lg overflow-auto">
            <code className="text-sm">{codeContent}</code>
          </pre>
        );
        codeContent = "";
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
    } else if (inCodeBlock) {
      codeContent += line + "\n";
    } else if (line.startsWith("# ")) {
      elements.push(<h1 key={idx} className="text-3xl font-bold mt-6 mb-4">{line.slice(2)}</h1>);
    } else if (line.startsWith("## ")) {
      elements.push(<h2 key={idx} className="text-2xl font-bold mt-6 mb-3">{line.slice(3)}</h2>);
    } else if (line.startsWith("### ")) {
      elements.push(<h3 key={idx} className="text-xl font-bold mt-4 mb-2">{line.slice(4)}</h3>);
    } else if (line.startsWith("> ")) {
      elements.push(<blockquote key={idx} className="border-l-4 border-primary pl-4 italic text-muted-foreground my-4">{line.slice(2)}</blockquote>);
    } else if (line.startsWith("- ")) {
      elements.push(<li key={idx} className="ml-4 mb-1">{line.slice(2)}</li>);
    } else if (line.startsWith("`") && line.endsWith("`") && line.length > 2) {
      elements.push(<code key={idx} className="bg-muted px-1.5 py-0.5 rounded text-sm">{line.slice(1, -1)}</code>);
    } else if (line.trim() === "") {
      elements.push(<div key={idx} className="my-2" />);
    } else {
      elements.push(<p key={idx} className="my-2 leading-relaxed">{line}</p>);
    }
  });
  
  return <div className="prose max-w-none">{elements}</div>;
}

export default function DocsPage() {
  const [activeId, setActiveId] = useState("introduction");

  const activeSection = DOCS.find(s => s.id === activeId) || DOCS[0];

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Documentation</h1>
        <p className="text-muted-foreground mt-1">Complete guide to Reclaim revenue recovery platform</p>
      </div>

      <div className="flex gap-8">
        <DocSidebar activeId={activeId} onSelect={setActiveId} />
        <main className="flex-1 min-w-0">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{activeSection.title}</CardTitle>
                {activeSection.badge && (
                  <Badge variant={activeSection.badgeVariant}>{activeSection.badge}</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <MarkdownRenderer content={activeSection.content} />
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  );
}