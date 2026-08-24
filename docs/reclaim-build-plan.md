# Reclaim — Complete Build Plan
Razorpay AI Builder Internship 2026 · Track 3: AI Revenue Recovery · Solo · 14 days

> This is the original build and pitch plan. The current implementation has
> shipped the core demo path, including the Decision Inspector, Gemini
> explanation fallback, and method-aware `alternate_method` recommendations.
> Recovery actions are still recorded intent; real provider execution,
> delayed jobs, and refunds remain production follow-ups.

---

## 1. Project Definition

**One-liner:** Given a failed payment attempt, Reclaim decides which recovery action maximizes expected recovered revenue, subject to hard payment-state and merchant-policy constraints — then records the recovery intent idempotently.

**Problem:** Failed payments lose revenue twice — once when they fail, and again when the response (usually "retry immediately") is wrong for that failure type, wastes contact budget, or fires after the customer already recovered on their own.

**Solution:** A layered decision system — deterministic state machine, statistical expected-value scoring, LLM explanation on top — that treats retry as one of several possible actions, not the default.

**AI's role:** Orchestration and explanation only. Financial state transitions and hard constraints are deterministic code. The LLM never decides whether to move money; it explains why the deterministic/statistical layers made the choice they did.

**Non-goals (do not build, do not let scope creep back in):**
- No dispute/chargeback agent. Mention as a future extension in the pitch, nothing more.
- No train/validation/stress split. One simulator environment. There's nothing to overfit — the policy is hand-authored, not fit to data.
- No 3rd or 4th baseline unless Days 1–12 finish early and you have spare time on Day 13.
- No online learning / contextual bandit. Static policy. One sentence in the pitch as future work.
- No separate "evaluation" dashboard view. Fold the baseline-delta number into the overview.

---

## 2. Data Model

Three-level identity, matching Razorpay's actual model (verified against `razorpay.com/docs/webhooks`): one `order_id` can have several `payment_id` attempts; the order flips to `paid`/recovered when any one attempt is captured.

```sql
CREATE TABLE merchants (
  merchant_id TEXT PRIMARY KEY,
  max_retries INT NOT NULL DEFAULT 3,
  contact_budget_per_day INT NOT NULL DEFAULT 2
);

CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  recovery_propensity NUMERIC NOT NULL,     -- latent, simulator-only
  payment_method_preference TEXT,
  historical_success_rate NUMERIC,
  customer_value NUMERIC NOT NULL
);

CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  merchant_id TEXT REFERENCES merchants(merchant_id),
  customer_id TEXT REFERENCES customers(customer_id),
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | recovered | lost
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payment_attempts (
  payment_id TEXT PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  attempt_number INT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,                     -- failed | captured
  error_code TEXT,
  error_description TEXT,
  error_reason TEXT,
  error_source TEXT,
  error_step TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE webhook_events (
  event_id TEXT PRIMARY KEY,                -- dedup key, insert-or-ignore
  event_type TEXT NOT NULL,                 -- payment.failed | payment.captured | order.paid
  payload JSONB NOT NULL,
  processed_at TIMESTAMPTZ
);

CREATE TABLE recovery_actions (
  action_id SERIAL PRIMARY KEY,
  order_id TEXT REFERENCES orders(order_id),
  action_type TEXT NOT NULL,                -- see §4
  expected_value NUMERIC NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled', -- scheduled | executed | cancelled
  scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  executed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  reason TEXT,
  recommended_method TEXT,
  explanation TEXT,
  explanation_model TEXT
);
```

Idempotency = `event_id` primary key (duplicate webhook, insert fails silently) + `orders.status` as the single source of truth for "is this order still open." Any `payment_attempts` insert with `status='captured'` flips the parent order to `recovered` and cancels all `scheduled` rows in `recovery_actions` for that `order_id` in the same transaction.

---

## 3. Recovery Outcome Simulator

Purpose: generate synthetic failed-payment histories with a documented, disclosed probability model — not claimed as a forecast of real data.

**README disclosure sentence (use this verbatim):**
> Because no proprietary merchant-level outcome dataset is available, Reclaim uses a synthetic simulator with transparent, hand-set assumptions to evaluate policy behavior. It is not presented as a forecast of Razorpay's production recovery rates.

**Config-driven, not code-driven** — put every constant in one `simulator_config.yaml` so it's auditable in one place:

```
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

action_fit:              # action effectiveness multiplier per failure_reason
  insufficient_funds: {retry_now: 0.3, retry_delayed: 1.4, payment_link: 1.1, whatsapp_nudge: 1.0, alternate_method: 0.8}
  issuer_timeout:     {retry_now: 1.6, retry_delayed: 1.0, payment_link: 0.7, whatsapp_nudge: 0.6, alternate_method: 0.7}
card_blocked:       {retry_now: 0.0, retry_delayed: 0.0, payment_link: 1.2, whatsapp_nudge: 0.8, alternate_method: 1.4}
```

The repository also contains an explicit `alternate_method_fit` table for
`upi` and `another_card`. For that action,
`P(recovery | context, action, method)` multiplies the selected method factor
on top of the base action fit. All probabilities are clipped to [0, 0.95].
Generate however many synthetic orders the eval table needs (2,000–3,000 is
plenty) — no formal train/val/stress split.

---

## 4. Policy Engine

**Candidate actions:** `RETRY_NOW, RETRY_DELAYED, PAYMENT_LINK, WHATSAPP_NUDGE, ALTERNATE_METHOD, NO_ACTION, HUMAN_REVIEW`

**Hard constraints — evaluated first, as a boolean gate, never folded into the score:**
```
if order.status in ('recovered', 'lost'):
    allowed_actions = {}                       # nothing to do

if attempt_number > merchant.max_retries:
    forbid RETRY_NOW, RETRY_DELAYED

if error_reason in HARD_DECLINE_SET:            # card_blocked, invalid_card, stolen_card
    forbid RETRY_NOW, RETRY_DELAYED

if daily_contact_count(customer) >= merchant.contact_budget_per_day:
    forbid WHATSAPP_NUDGE
```

**Expected value — computed only on what survives the gate:**
```
ERV(action) = P(recovery | context, action) × recoverable_amount
              − intervention_cost(action)
              − friction_cost(action, attempt_number)
              − risk_penalty(action)
```
`intervention_cost` and `friction_cost` are small hand-set constants (e.g. WhatsApp nudge costs more friction per repeat contact). Rank surviving actions by ERV, pick the max. If max ERV < 0, action = `NO_ACTION`. If confidence is low (order value above a threshold and top-two actions are close), route to `HUMAN_REVIEW` instead of auto-executing.

When `ALTERNATE_METHOD` wins, the policy also selects a concrete method. The
current implementation recommends `upi` for insufficient funds and hard card
failures, otherwise `another_card`. The recommendation is persisted on the
recovery action and returned by the order inspector.

---

## 5. Evaluation

**Two baselines only:**
1. `always_retry` — every `payment.failed` → `RETRY_NOW`, no other logic.
2. `reclaim` — the full policy engine above.

**Metrics:** recovered revenue, recovery rate, unnecessary interventions (action taken on an order that would have recovered anyway, or was already lost), average time-to-resolution, customer contact count. Report as one table, `always_retry` vs `reclaim`, on the same simulated order set. The single number for the pitch: **incremental recovered revenue vs. the naive baseline.**

---

## 6. Agent / MCP Layer

```
get_order_context(order_id) -> { order, customer, merchant, attempts[], status }
get_allowed_actions(order_id) -> [ActionType]          # applies §4 hard constraints
estimate_recovery(order_id, action) -> { probability, recoverable_amount, cost, expected_value }
execute_recovery_action(order_id, action) -> { result, recommended_method, scheduled_at }   # idempotent intent record
cancel_pending_action(order_id) -> null                # called automatically on order recovery
```

Router agent calls `get_order_context` → `get_allowed_actions` → `estimate_recovery` for each allowed action → picks the max → `execute_recovery_action`. The LLM sits *after* this, receiving the decision as JSON and producing only the explanation:

```json
{
  "selected_action": "payment_link",
  "expected_value": 1842,
  "alternatives": {"retry_now": 0, "alternate_method": 1690},
  "constraints_applied": ["retry forbidden: hard decline"],
  "reasons": ["second failed card attempt", "alternate route has higher simulated recovery probability"]
}
```
→ *"Retry was not attempted — this is the second failed card attempt on a hard decline. A payment-link recovery was chosen instead, with the highest expected recovery value under current policy."*

---

## 7. Recovery Intent and Demo Script

Rehearse this until it's reliable live. It is the strongest three minutes of the whole pitch.

1. Order `₹25,000` created. Fire `payment.failed` for `payment_001` (reason: `issuer_timeout`).
2. System records a `RETRY_DELAYED` action, shown in the Decision Inspector.
3. Fire `payment.captured` for `payment_002` on the same `order_id`.
4. Order flips to `recovered`. The scheduled action for `payment_001` auto-cancels — show this happening in the UI.
5. Replay the *original* `payment.failed` event (same `event_id`).
6. System logs: `duplicate event_id ignored, no action taken.` Nothing re-fires.

That one sequence demonstrates: payment-domain understanding, correct state management, idempotency, agentic decisioning, and event-driven design — without a slide.

Two supporting scenarios, in reserve for Q&A or if time allows:
- **Soft decline:** ₹1,200, `issuer_timeout` → immediate retry, highest ERV, succeeds.
- **Hard decline, high value:** ₹78,000, two consecutive `card_blocked` attempts → retry forbidden by the hard-constraint gate → `payment_link` chosen on ERV → explain why retrying was never on the table.

---

## 8. Dashboard — two views only

**Overview:** failed payments, at-risk revenue, recovered revenue, incremental revenue vs. baseline, recovery rate. One KPI row + one bar chart (`always_retry` vs `reclaim` recovered revenue).

**Decision Inspector:** search/click an `order_id` → attempt timeline → context (customer, merchant, failure reason) → candidate actions with their ERVs → selected action and alternate method → the LLM's explanation → which constraints fired.

---

## 9. Day-by-Day Plan

| Days | Deliverable |
|---|---|
| 1–2 | State machine: `event_id`/`payment_id`/`order_id`, webhook ingestion, dedup |
| 3–4 | Recovery Outcome Simulator, one environment, `simulator_config.yaml` |
| 5–6 | Policy engine: hard constraints → candidate actions → ERV ranking |
| 7 | Two-baseline eval, one comparison table |
| 8–9 | MCP tools + router agent + LLM explanation layer |
| 10–11 | Safe executor, idempotency, rehearse the §7 demo script until reliable |
| 12 | Dashboard: Overview + Decision Inspector |
| 13 | Buffer — fix whatever broke in rehearsal. README, architecture diagram, demo GIF |
| 14 | Pitch + panel prep only. No new code. |

---

## 10. Repo & README structure

```
/reclaim
  /simulator        (config + generation logic)
  /policy            (constraints + ERV scoring)
  /agent             (MCP tools + router + LLM explanation)
  /executor          (idempotent action execution)
  /dashboard         (Overview + Decision Inspector)
  /db                (schema.sql, migrations)
  README.md
  ARCHITECTURE.md    (this document, trimmed to what you actually built)
```

**README section order:** (1) one-line reframe — "decides the highest-value action for every failed payment," not "retries payments" — (2) the headline number: incremental recovered revenue vs. baseline (3) architecture diagram (4) setup instructions you have personally re-run from a clean clone (5) demo GIF/video link (6) the §3 disclosure sentence (7) an explicit **"What I chose not to build, and why"** section listing the non-goals from §1 — this turns the cuts into a signal of deliberate scoping under deadline, not a gap.

---

## 11. Pitch Script — 5 minutes

- **0:00–0:30** Problem, in Razorpay's own framing: revenue is lost after a payment fails not because it failed, but because nobody has time to pick the right response.
- **0:30–1:30** The reframe. Not a retry bot — a decision engine. Walk the three layers: deterministic constraints, statistical expected-value scoring, LLM explanation on top.
- **1:30–3:30** Live demo: the §7 idempotency scenario, run for real.
- **3:30–4:30** The number: incremental recovered revenue vs. the naive always-retry baseline.
- **4:30–5:00** What you'd build next at Razorpay's actual scale, and the deliberate non-goals from §1 as scope calls, not gaps.

---

## 12. Panel Interview Prep

| Likely question | Answer |
|---|---|
| "How is this different from your existing Subscription Recovery / Dispute Responder?" | Those are described publicly as retry-logic and evidence-gathering agents. This is the decision layer above that class of agent — it treats retry as one of several ranked actions, not the default, and separates hard constraints from the score. |
| "Why not let the LLM decide directly?" | Financial state transitions need to be deterministic and auditable. The LLM never touches money state — it explains a decision the constraint/scoring layers already made. |
| "Where do your probabilities come from?" | Disclosed synthetic simulator with hand-set, documented assumptions — never claimed as a forecast of real Razorpay data. State the §3 sentence plainly if asked. |
| "order_id vs payment_id?" | One order, multiple payment attempts. The order flips to paid/recovered when any one attempt is captured — matches Razorpay's own `order.paid` vs `payment.captured` webhook distinction. |
| "What breaks at 10x volume?" | Talk through the event_id/order_id indexing, where a queue would sit in front of the executor, and where the current synchronous MCP calls would need to become async. |
| "Why cut the dispute agent?" | Deliberate scope call under a 14-day deadline. A half-built second pillar increases the odds of "how is yours different from ours" without adding real differentiation — better to ship one thing deep. |

---

## Cut list — keep visible during the build

- No dispute/chargeback agent.
- No train/validation/stress split — one simulator environment.
- No 3rd/4th baseline unless days 1–12 finish early.
- No learning/bandit loop.
- No separate evaluation dashboard view.
