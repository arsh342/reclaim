"use client";

import { useState } from "react";
import { ChevronRight, FileText, BookOpen, Code, Server, Shield, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface DocSection {
  id: string;
  title: string;
  icon: React.ReactNode;
  content: string;
  children?: DocSection[];
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
Webhook Ingestion
      ↓
PostgreSQL State
      ↓
Reclaim Agent Runtime
      ↓
Gemini
      ↓
Structured Plan
      ↓
Policy Gate
      ↓
Safe Executor
      ↓
Payment Action
      ↓
Outcome Event
      ↓
Replan or Complete
\`\`\`

## Components

1. **Webhook Ingestion** - Idempotent event ingestion with deduplication
2. **Agent Runtime** - State machine orchestrating the recovery flow
3. **Gemini Provider** - LLM for diagnosis, planning, replanning
4. **Tool Registry** - Internal tools for context, policy, execution
5. **Policy Engine** - Hard constraints + ERV scoring
5. **Safe Executor** - Idempotent action execution with re-validation
6. **PostgreSQL** - Persistent state and audit trail
7. **MCP Server** - Interoperability layer
    `,
  },
  {
    id: "agent-runtime",
    title: "Agent Runtime",
    icon: <Zap className="h-4 w-4" />,
    content: `
# Agent Runtime

The agent runtime is a Reclaim-owned state machine, not a vendor-specific agent wrapper.

## Agent Stages

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
  ├── rejected → REPLANNING
  └── approved → EXECUTING
                    ↓
              WAITING_FOR_OUTCOME
                    ↓
              COMPLETED / REPLANNING
\`\`\`

These are logical stages, not necessarily separate Gemini API calls.

## Runtime Responsibilities

1. Create \`agent_run\`
2. Load order, merchant, customer, and payment history
3. Ask Gemini for structured diagnosis
4. Ask Gemini to generate relevant candidate interventions
5. Call deterministic tools for allowed actions and recovery estimates
6. Give Gemini the counterfactual results
7. Generate a bounded recovery plan
8. Validate the plan against deterministic policy
9. Execute only permitted actions
10. Stream every stage to the frontend
11. Persist the complete audit trail
12. Replan when an action is rejected or the payment state changes
    `,
  },
  {
    id: "ai-boundary",
    title: "AI Boundary",
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
if order.status in {recovered, lost}:
    no actions allowed

if attempt_number > merchant.max_retries:
    forbid retry actions

if error_reason in HARD_DECLINE_SET:
    forbid retry actions

if daily_contact_count >= contact_budget:
    forbid contact actions
\`\`\`

## Expected Value (ERV)

\`\`\`text
ERV(action) =
    P(recovery | context, action) * recoverable_amount
    - intervention_cost(action)
    - friction_cost(action, attempt_number)
    - risk_penalty(action)
\`\`\`

The AI may request any action, but the safe executor independently re-runs the hard-constraint gate. A forbidden action cannot execute.
    `,
  },
  {
    id: "mcp",
    title: "MCP Server",
    icon: <Server className="h-4 w-4" />,
    content: `
# MCP Server

Reclaim also works as an MCP server. MCP is an interoperability layer over the same Reclaim services.

## Primary Endpoint

\`\`\`text
/mcp
\`\`\`

## Primary Transport

\`\`\`text
Streamable HTTP
\`\`\`

## Development

\`\`\`bash
uv run mcp dev backend/mcp_server/server.py
\`\`\`

## Tool Catalog

### Read-only
- \`reclaim_get_order_context\`
- \`reclaim_get_allowed_actions\`
- \`reclaim_estimate_recovery\`
- \`reclaim_get_agent_run\`
- \`reclaim_get_agent_events\`
- \`reclaim_get_evaluation_summary\`

### Guarded Side-effecting
- \`reclaim_start_recovery_run\`
- \`reclaim_execute_recovery_action\`
- \`reclaim_cancel_pending_action\`

Every side-effecting operation goes through the same safety gate and executor used by the web application.
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
| GET | \`/orders\` | Order list |
| GET | \`/orders/{order_id}\` | Order detail |
| POST | \`/webhooks/simulate\` | Simulated webhook |
| GET | \`/eval/summary\` | Evaluation summary |
| GET | \`/agent-runs\` | Agent runs |
| GET | \`/agent-runs/{run_id}\` | Run detail |
| GET | \`/agent-runs/{run_id}/events\` | SSE event stream |
| POST | \`/agent-runs/{run_id}/replay\` | Replay run for demo |

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
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  merchant_id TEXT REFERENCES merchants(merchant_id),
  customer_id TEXT REFERENCES customers(customer_id),
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payment_attempts (
  payment_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  attempt_number INT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,
  error_code TEXT,
  error_reason TEXT,
  error_source TEXT,
  error_step TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_runs (
  run_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  status TEXT NOT NULL,
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

CREATE TABLE recovery_actions (
  action_id BIGSERIAL PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  action_type TEXT NOT NULL,
  expected_value NUMERIC NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled',
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
# Evaluation

Compare exactly two policies on the same synthetic batch:

1. \`always_retry\`
2. \`reclaim\`

## Metrics

- Recovered revenue
- Recovery rate
- Incremental recovered revenue
- Unnecessary interventions
- Customer contact count
- Average time to resolution

The headline pitch metric is **incremental recovered revenue versus \`always_retry\`**.

Run evaluation:
\`\`\`bash
GET /eval/summary?n_orders=2000&seed=42
\`\`\`
    `,
  },
  {
    id: "demo",
    title: "Demo",
    icon: <Zap className="h-4 w-4" />,
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
hard decline
        ↓
agent proposes retry
        ↓
policy rejects retry
        ↓
agent receives rejection
        ↓
agent replans
        ↓
payment link
        ↓
safe executor accepts
\`\`\`

This is the strongest demonstration that the AI is operating inside a real controlled agent runtime.
    `,
  },
  {
    id: "deployment",
    title: "Deployment",
    icon: <Server className="h-4 w-4" />,
    content: `
# Deployment

\`\`\`text
Vercel
  ↓
FastAPI
  ├── REST
  ├── SSE
  └── MCP /mcp
       ↓
PostgreSQL
       ↓
Gemini API
\`\`\`

## Environment Variables

### Backend
\`\`\`env
DATABASE_URL=postgresql://...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.7-flash
CORS_ORIGINS=https://your-frontend.vercel.app
\`\`\`

### Frontend
\`\`\`env
NEXT_PUBLIC_API_URL=https://your-backend.render.com
\`\`\`

## Backend (Render)
- Build: \`pip install -r requirements.txt\`
- Start: \`PYTHONPATH=. uvicorn backend.api.main:app --host 0.0.0.0 --port \$PORT\`

## Frontend (Vercel)
- Build: \`cd dashboard && npm install && npm run build\`
- Output: \`.next\` (static export)
    `,
  },
  {
    id: "troubleshooting",
    title: "Troubleshooting",
    icon: <Shield className="h-4 w-4" />,
    content: `
# Troubleshooting

## Common Issues

### Backend won't start
- Check \`DATABASE_URL\` is correct
- Verify \`GEMINI_API_KEY\` is set
- Ensure PostgreSQL is accessible

### Frontend shows "Backend not responding"
- Verify \`NEXT_PUBLIC_API_URL\` matches backend URL
- Check CORS settings on backend
- Ensure backend is deployed and healthy

### Agent not running
- Check webhook ingestion works
- Verify \`agent_runs\` table has entries
- Check SSE connection in browser dev tools

### MCP connection fails
- Verify \`/mcp\` endpoint is accessible
- Check MCP SDK version compatibility
- Ensure Streamable HTTP transport is configured

## Debug Commands

\`\`\`bash
# Check backend health
curl https://your-backend.com/health

# Check orders
curl https://your-backend.com/api/orders

# Check eval
curl https://your-backend.com/api/eval/summary

# Test webhook
curl -X POST https://your-backend.com/api/webhooks/simulate \
  -H "Content-Type: application/json" \
  -d '{"entity":"event","account_id":"acc_test","event":"payment.failed","contains":["payment"],"payload":{"payment":{"entity":{"id":"pay_test","order_id":"order_test","amount":500000,"currency":"INR","method":"card","status":"failed","attempt_number":1,"error_reason":"issuer_timeout"}}}}'
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
            className={`w-full text-left p-2 rounded transition-colors ${
              activeId === section.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent"
            }`}
          >
            <div className="flex items-center gap-2">
              {section.icon}
              <span className="text-sm font-medium">{section.title}</span>
            </div>
          </button>
        ))}
      </nav>
    </aside>
  );
}

function MarkdownRenderer({ content }: { content: string }) {
  // Simple markdown renderer for our docs
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
              <CardTitle>{activeSection.title}</CardTitle>
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