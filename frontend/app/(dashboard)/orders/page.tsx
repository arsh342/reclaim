import Link from "next/link";
import { api } from "@/lib/api";
import { Money } from "@/components/format";
import { PageHeader, PageShell } from "@/components/page-shell";
import { Status } from "@/components/status";
import BentoCard from "@/components/ui/bento-card";

import type { OrderSummary } from "@/lib/api";

const STATUS_TONE: Record<OrderSummary["status"], "default" | "accent" | "danger" | "pending"> = {
  pending: "pending",
  recovered: "accent",
  lost: "danger",
} as const;

export default async function OrdersPage() {
  let orders = null;
  let error: string | null = null;

  try {
    orders = await api.orders();
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown error";
  }

  if (error || !orders) {
    return (
      <div className="p-8">
        <h1 className="text-xl font-semibold">Backend unreachable</h1>
        <p className="num mt-2 text-sm text-ink-muted">{error}</p>
      </div>
    );
  }

  const recoveredCount = orders.filter((order) => order.status === "recovered").length;
  const pendingCount = orders.filter((order) => order.status === "pending").length;
  const lostCount = orders.filter((order) => order.status === "lost").length;

  return (
    <PageShell>
      <PageHeader
        eyebrow="Orders / case queue"
        title={`${orders.length} payment cases.`}
        description="Every failed payment entering the recovery engine, ordered from newest to oldest."
        meta={<span className="num text-xs uppercase tracking-widest text-ink-faint">newest first</span>}
      />

      <section className="mb-10 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <BentoCard className="border-rule bg-surface-raised">
          <p className="eyebrow">pending</p>
          <p className="num mt-3 text-3xl tracking-[-0.05em] text-ink">{pendingCount}</p>
          <p className="mt-2 text-xs text-ink-muted">awaiting outcome</p>
        </BentoCard>
        <BentoCard className="border-accent bg-accent-soft/35">
          <p className="eyebrow text-accent-strong">recovered</p>
          <p className="num mt-3 text-3xl tracking-[-0.05em] text-ink">{recoveredCount}</p>
          <p className="mt-2 text-xs text-ink-muted">payment captured</p>
        </BentoCard>
        <BentoCard className="border-danger bg-danger-soft/35">
          <p className="eyebrow text-danger">lost</p>
          <p className="num mt-3 text-3xl tracking-[-0.05em] text-ink">{lostCount}</p>
          <p className="mt-2 text-xs text-ink-muted">no recovery</p>
        </BentoCard>
      </section>

      <div className="panel hidden overflow-hidden md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-rule-strong bg-surface-raised">
              <th className="num px-5 py-3 text-left text-xs uppercase tracking-widest text-ink-faint">
                Order
              </th>
              <th className="num px-5 py-3 text-right text-xs uppercase tracking-widest text-ink-faint">
                Amount
              </th>
              <th className="num px-5 py-3 text-left text-xs uppercase tracking-widest text-ink-faint">
                Status
              </th>
              <th className="num px-5 py-3 text-right text-xs uppercase tracking-widest text-ink-faint">
                Created
              </th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr
                key={order.order_id}
                className="border-b border-rule transition-colors last:border-0 hover:bg-accent-soft/25"
              >
                <td className="px-5 py-4">
                  <Link
                    href={`/orders/${order.order_id}`}
                    className="num text-ink underline decoration-rule underline-offset-4 hover:decoration-ink"
                  >
                    {order.order_id}
                  </Link>
                </td>
                <td className="px-5 py-4 text-right">
                  <Money value={order.amount} />
                </td>
                <td className="px-5 py-4">
                  <Status value={order.status} tone={STATUS_TONE[order.status]} />
                </td>
                <td className="num px-5 py-4 text-right text-xs text-ink-muted">
                  {order.created_at ? formatDate(order.created_at) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="space-y-2 md:hidden">
        {orders.map((order) => (
          <Link
            key={order.order_id}
            href={`/orders/${order.order_id}`}
            className="panel block p-4 transition-colors hover:border-accent hover:bg-accent-soft/20"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="num text-sm text-ink">{order.order_id}</p>
                <p className="num mt-2 text-[10px] uppercase tracking-widest text-ink-faint">
                  {order.created_at ? formatDate(order.created_at) : "time unavailable"}
                </p>
              </div>
              <Status value={order.status} tone={STATUS_TONE[order.status]} />
            </div>
            <div className="mt-5 flex items-baseline justify-between border-t border-rule pt-3">
              <span className="eyebrow">amount</span>
              <Money value={order.amount} />
            </div>
          </Link>
        ))}
      </div>
    </PageShell>
  );
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")} ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}
