import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { Money } from "@/components/format";
import { PageShell, SectionHeading } from "@/components/page-shell";
import { Status } from "@/components/status";
import BentoCard from "@/components/ui/bento-card";
import Link from "next/link";
import type { OrderDetail, RecoveryAction } from "@/lib/api";

const STATUS_TONE: Record<OrderDetail["status"], "default" | "accent" | "danger" | "pending"> = {
  pending: "pending",
  recovered: "accent",
  lost: "danger",
} as const;

const ACTION_TONE: Record<RecoveryAction["status"], "default" | "accent" | "danger" | "pending"> = {
  scheduled: "pending",
  executed: "accent",
  cancelled: "danger",
} as const;

export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ order_id: string }>;
}) {
  const { order_id } = await params;

  let order = null;
  let error: string | null = null;

  try {
    order = await api.order(order_id);
  } catch (e) {
    if (e instanceof Error && /404/.test(e.message)) {
      notFound();
    }
    error = e instanceof Error ? e.message : "unknown error";
  }

  if (error || !order) {
    return (
      <div className="p-8 page-enter">
        <h1 className="text-xl font-semibold">Could not load order</h1>
        <p className="num mt-2 text-sm text-ink-muted">{error}</p>
      </div>
    );
  }

  const selectedCandidate = order.decision_analysis.candidate_actions.find(
    (candidate) => candidate.action === order.decision_analysis.selected_action,
  );
  const maxErv = Math.max(
    ...order.decision_analysis.candidate_actions.map((candidate) => candidate.erv),
    1,
  );
  const latestExplanation = order.recovery_actions.find((action) => action.explanation);

  return (
    <PageShell>
      <Link
        href="/orders"
        className="num mb-8 inline-flex text-xs uppercase tracking-widest text-ink-muted underline decoration-rule underline-offset-4 hover:text-ink hover:decoration-ink"
      >
        ← all orders
      </Link>

      <header className="mb-10 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Decision inspector / case file</p>
          <h1 className="num mt-2 text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
            {order.order_id}
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="eyebrow">order value</p>
            <div className="mt-1"><Money value={order.amount} /></div>
          </div>
          <Status value={order.status} tone={STATUS_TONE[order.status]} />
        </div>
      </header>

      {/* Order summary */}
      <section className="mb-10 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <BentoCard className="p-4">
          <p className="eyebrow">currency</p>
          <p className="num mt-2 text-sm">{order.currency}</p>
        </BentoCard>
        <BentoCard className="p-4">
          <p className="eyebrow">merchant</p>
          <p className="num mt-2 truncate text-sm">{order.merchant_id ?? "—"}</p>
        </BentoCard>
        <BentoCard className="p-4">
          <p className="eyebrow">customer</p>
          <p className="num mt-2 truncate text-sm">{order.customer_id ?? "—"}</p>
        </BentoCard>
        <BentoCard className="p-4">
          <p className="eyebrow">opened</p>
          <p className="num mt-2 text-sm">{order.created_at ? formatDate(order.created_at) : "—"}</p>
        </BentoCard>
      </section>

      {/* Decision analysis */}
      <section className="mb-12 grid gap-4 lg:grid-cols-[0.88fr_1.12fr]">
        <BentoCard className="border-accent bg-accent-soft/30 p-6 sm:p-8">
          <p className="eyebrow text-accent">policy decision</p>
          <p className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-ink sm:text-3xl">
            {order.decision_analysis.selected_action
              ? formatDecisionAction(
                  order.decision_analysis.selected_action,
                )
              : "No action selected"}
          </p>
          <p className="mt-3 text-sm leading-6 text-ink-muted">
            {selectedCandidate
              ? `Highest expected recovery value among ${order.decision_analysis.candidate_actions.length} permitted actions.`
              : "The policy did not select an executable recovery action."}
          </p>
          {selectedCandidate && (
            <div className="mt-8 border-t border-accent/30 pt-5">
              <p className="eyebrow text-accent">expected recovery value</p>
              <div className="mt-2"><Money value={selectedCandidate.erv} emphasize /></div>
            </div>
          )}
        </BentoCard>

        <BentoCard className="p-6 sm:p-8">
          <SectionHeading
            eyebrow="decision tape"
            title="What the policy weighed"
            action={<span className="num text-xs text-ink-faint">ERV / INR</span>}
          />
          {order.decision_analysis.candidate_actions.length === 0 ? (
            <p className="num text-sm text-ink-muted">no candidate actions</p>
          ) : (
            <ol className="space-y-4">
              {order.decision_analysis.candidate_actions.map((candidate) => {
                const selected = candidate.action === order.decision_analysis.selected_action;
                const width = `${Math.max((candidate.erv / maxErv) * 100, 3)}%`;
                return (
                  <li key={candidate.action}>
                    <div className="mb-1.5 flex items-baseline justify-between gap-4">
                      <span className={`text-sm ${selected ? "font-medium text-accent" : "text-ink"}`}>
                        {formatAction(candidate.action)}
                        {selected && <span className="num ml-2 text-[10px] uppercase tracking-widest">selected</span>}
                      </span>
                      <span className="num text-xs text-ink-muted"><Money value={candidate.erv} /></span>
                    </div>
                    <div className="h-2 bg-rule">
                      <div
                        className={`h-full transition-all ${selected ? "bg-accent" : "bg-ink-faint"}`}
                        style={{ width }}
                      />
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </BentoCard>
      </section>

      {latestExplanation && (
        <section className="mb-12 rounded-xl border border-accent border-l-2 bg-surface-raised px-5 py-4 sm:px-6">
          <p className="eyebrow text-accent">why this happened</p>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-ink-muted">
            {latestExplanation.explanation}
          </p>
          {latestExplanation.explanation_model && (
            <p className="num mt-3 text-[10px] uppercase tracking-widest text-ink-faint">
              generated by {latestExplanation.explanation_model}
            </p>
          )}
        </section>
      )}

      {/* Attempt timeline */}
      <section className="mb-12">
        <SectionHeading eyebrow="event history" title="Payment attempts" />
        {order.payment_attempts.length === 0 ? (
          <p className="num text-sm text-ink-muted">no attempts recorded</p>
        ) : (
          <ol className="relative space-y-0 border-l border-rule pl-5 sm:pl-7">
            {order.payment_attempts.map((attempt) => (
              <li
                key={attempt.payment_id}
                className="relative border-b border-rule py-4 last:border-0"
              >
                <span className="absolute -left-[1.84rem] top-5 size-2 bg-ink sm:-left-[2.1rem]" />
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="num text-sm text-ink">Attempt #{attempt.attempt_number} · {attempt.payment_id}</p>
                    <p className="mt-1 text-xs text-ink-muted">{attempt.method} · {attempt.error_reason ?? "no failure reason"}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Status value={attempt.status} tone={attempt.status === "captured" ? "accent" : "danger"} />
                    <span className="num text-[10px] text-ink-faint">{attempt.created_at ? formatDate(attempt.created_at) : "—"}</span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Recovery actions */}
      <section className="mb-12">
        <SectionHeading eyebrow="execution log" title="Recovery actions" />
        {order.recovery_actions.length === 0 ? (
          <p className="num text-sm text-ink-muted">
            no recovery actions recorded
          </p>
        ) : (
          <ol className="space-y-3">
            {order.recovery_actions.map((action) => (
              <li key={action.action_id} className="panel p-4 sm:p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="num text-xs text-ink-faint">ACTION #{action.action_id}</p>
                    <p className="mt-1 text-sm font-medium text-ink">{formatAction(action.action_type)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Status value={action.status} tone={ACTION_TONE[action.status]} />
                    <Money value={action.expected_value} />
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t border-rule pt-3">
                  <span className="num text-[10px] uppercase tracking-widest text-ink-faint">
                    scheduled {action.scheduled_at ? formatDate(action.scheduled_at) : "—"}
                  </span>
                  {action.cancelled_at && <span className="num text-[10px] uppercase tracking-widest text-danger">cancelled {formatDate(action.cancelled_at)}</span>}
                </div>
                {action.explanation && (
                  <div className="mt-4 border-t border-rule pt-4 text-sm leading-6 text-ink-muted">
                    <p>{action.explanation}</p>
                    {action.explanation_model && (
                      <p className="num mt-1 text-xs uppercase tracking-widest text-ink-faint">
                        explanation: {action.explanation_model}
                      </p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Disclosure footer */}
      <section className="border-t border-rule pt-6 text-xs text-ink-faint">
        <p>
          Recovery probabilities from synthetic simulator with hand-set,
          disclosed assumptions — not a forecast of production rates. See
          backend/simulator/simulator_config.yaml.
        </p>
      </section>
    </PageShell>
  );
}

function formatAction(action: string) {
  const readable = action.replaceAll("_", " ");
  return readable.charAt(0).toUpperCase() + readable.slice(1);
}

function formatDecisionAction(action: string) {
  return formatAction(action);
}

function formatMethod(method: string) {
  if (method === "upi") return "UPI";
  if (method === "another_card") return "another card";
  return formatAction(method);
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")} ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}
