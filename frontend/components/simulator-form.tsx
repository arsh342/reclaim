"use client";

import { useState } from "react";
import { api, type WebhookSimulateRequest, type WebhookResult } from "@/lib/api";
import Link from "next/link";

const REASONS = [
  "issuer_timeout",
  "insufficient_funds",
  "card_blocked",
  "invalid_card",
  "network_error",
];

export function SimulatorForm() {
  const [event, setEvent] = useState<"payment.failed" | "payment.captured">(
    "payment.failed",
  );
  const [orderId, setOrderId] = useState("order_demo");
  const [paymentId, setPaymentId] = useState("pay_001");
  const [amount, setAmount] = useState("1200");
  const [errorReason, setErrorReason] = useState("issuer_timeout");
  const [attempt, setAttempt] = useState("1");
  const [result, setResult] = useState<WebhookResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const amountRupees = Number(amount);
    if (!Number.isFinite(amountRupees) || amountRupees <= 0) {
      setError("Enter an amount greater than zero.");
      setLoading(false);
      return;
    }

    const body: WebhookSimulateRequest = {
      entity: "event",
      account_id: "acc_test",
      event,
      contains: ["payment"],
      payload: {
        payment: {
          entity: {
            id: paymentId,
            order_id: orderId,
            // Razorpay's webhook wire format is paise; the UI accepts rupees.
            amount: Math.round(amountRupees * 100),
            currency: "INR",
            method: "card",
            status: event === "payment.failed" ? "failed" : "captured",
            attempt_number: Number(attempt),
            ...(event === "payment.failed"
              ? {
                  error_code: "BAD_REQUEST_PAYMENT_FAILED",
                  error_description: "Payment failed",
                  error_reason: errorReason,
                  error_source: "customer",
                  error_step: "payment_authentication",
                }
              : {}),
          },
        },
      },
    };

    try {
      const r = await api.simulateWebhook(body);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="panel p-5 sm:p-7">
        <div className="mb-6 flex items-start justify-between gap-4 border-b border-rule pb-5">
          <div>
            <p className="eyebrow">event payload</p>
            <h2 className="mt-2 text-lg font-medium tracking-tight">Create a payment event</h2>
          </div>
          <span className="num text-[10px] uppercase tracking-widest text-ink-faint">synthetic</span>
        </div>
        <div className="grid grid-cols-1 gap-x-6 gap-y-5 md:grid-cols-2">
        <Field label="Event type" hint="Choose the event to ingest.">
          <select
            value={event}
            onChange={(e) =>
              setEvent(e.target.value as "payment.failed" | "payment.captured")
            }
            className={INPUT_CLASS}
          >
            <option value="payment.failed">payment.failed</option>
            <option value="payment.captured">payment.captured</option>
          </select>
        </Field>

        <Field label="Order ID" hint="Use the same ID to replay a case.">
          <input
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>

        <Field label="Payment ID">
          <input
            value={paymentId}
            onChange={(e) => setPaymentId(e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>

        <Field label="Amount (INR)" hint="Enter rupees; 1200 = INR 1,200.">
          <input
            type="number"
            value={amount}
            min="0.01"
            step="0.01"
            required
            onChange={(e) => setAmount(e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>

        <Field label="Attempt number">
          <input
            type="number"
            value={attempt}
            min={1}
            onChange={(e) => setAttempt(e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>

        {event === "payment.failed" && (
          <Field label="Failure reason" hint="This drives the policy constraints.">
            <select
              value={errorReason}
              onChange={(e) => setErrorReason(e.target.value)}
              className={INPUT_CLASS}
            >
              {REASONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </Field>
        )}
        </div>
      </div>

      <div className="flex flex-col gap-4 border-t border-rule pt-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-ink-muted">
          The event is persisted and processed by the live backend.
        </p>
        <button
          type="submit"
          disabled={loading}
          className="num inline-flex min-h-11 items-center justify-center rounded-xl border border-ink bg-ink px-5 py-2 text-sm uppercase tracking-wider text-background transition-colors hover:bg-ink-muted disabled:cursor-wait disabled:opacity-50"
        >
          {loading ? "Sending…" : "Fire webhook"}
        </button>
      </div>

      {result && (
        <div className="rounded-xl border border-accent border-l-2 bg-accent-soft/65 p-5" aria-live="polite">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow text-accent">event accepted</p>
              <p className="mt-2 text-lg font-medium">{result.status}</p>
            </div>
            {result.action_id && (
              <span className="num text-xs uppercase tracking-widest text-accent">action #{result.action_id}</span>
            )}
          </div>
          <div className="mt-5 grid gap-3 border-t border-accent/25 pt-4 text-sm sm:grid-cols-2">
            <div><p className="eyebrow text-accent">order</p><p className="num mt-1">{result.order_id}</p></div>
            <div><p className="eyebrow text-accent">event</p><p className="num mt-1">{result.event_id}</p></div>
          </div>
          <Link
            href={`/orders/${result.order_id}`}
            className="mt-5 inline-flex text-sm text-ink underline decoration-accent underline-offset-4 hover:decoration-ink"
          >
            Open decision inspector →
          </Link>
          <details className="mt-5 border-t border-accent/25 pt-4">
            <summary className="num cursor-pointer text-[10px] uppercase tracking-widest text-accent">raw response</summary>
            <pre className="num mt-3 overflow-x-auto whitespace-pre-wrap text-xs text-ink-muted">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-danger border-l-2 bg-danger-soft/70 p-5" role="alert">
          <p className="eyebrow text-danger">event rejected</p>
          <p className="num mt-2 text-sm">{error}</p>
          <p className="mt-3 text-xs leading-5 text-danger/80">Check the backend status and payload values, then try again.</p>
        </div>
      )}
    </form>
  );
}

const INPUT_CLASS = "num min-h-11 w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm text-ink transition-colors hover:border-ink-muted focus:border-accent focus:outline-none";

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="num block text-xs uppercase tracking-widest text-ink-faint">
        {label}
      </span>
      {hint && <span className="mt-1 block text-xs leading-5 text-ink-muted">{hint}</span>}
      <span className="mt-2 block">
      {children}
      </span>
    </label>
  );
}
