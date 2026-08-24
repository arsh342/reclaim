import { api } from "@/lib/api";
import { Money } from "@/components/format";
import { RecoveryBar } from "@/components/recovery-bar";
import { PageHeader, PageShell, SectionHeading } from "@/components/page-shell";
import { Status } from "@/components/status";
import StatsBento from "@/components/ui/stats-bento";
import Link from "next/link";
import type { OrderSummary } from "@/lib/api";

const STATUS_TONE: Record<OrderSummary["status"], "default" | "accent" | "danger" | "pending"> = {
  pending: "pending",
  recovered: "accent",
  lost: "danger",
} as const;

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: Promise<{ n?: string; seed?: string }>;
}) {
  const params = await searchParams;
  const nOrders = Number(params.n ?? 2000);
  const seed = Number(params.seed ?? 42);

  let summary = null;
  let orders = null;
  let error: string | null = null;

  try {
    // Parallel fetch — these are independent reads on the same backend
    [summary, orders] = await Promise.all([
      api.evalSummary(nOrders, seed),
      api.orders(),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown error";
  }

  if (error || !summary || !orders) {
    return (
      <div className="p-8">
        <h1 className="text-xl font-semibold">Backend unreachable</h1>
        <p className="num mt-2 text-sm text-ink-muted">{error ?? "no data"}</p>
      </div>
    );
  }

  const chartData = [
    { name: "Always retry", recovered: summary.always_retry.recovered_revenue, fill: "var(--ink-faint)" },
    { name: "Reclaim", recovered: summary.reclaim.recovered_revenue, fill: "var(--accent)" },
  ];

  const recoveredCount = orders.filter((o) => o.status === "recovered").length;
  const lostCount = orders.filter((o) => o.status === "lost").length;
  const pendingCount = orders.filter((o) => o.status === "pending").length;

  return (
    <PageShell>
      <PageHeader
        eyebrow="Overview / recovery operations"
        title="The money that came back."
        description="A live read on how the deterministic recovery policy performs against a naive retry strategy."
        meta={
          <div className="text-left sm:text-right">
            <p className="eyebrow">simulation window</p>
            <p className="num mt-2 text-xs text-ink-muted">
              {summary.n_orders.toLocaleString("en-IN")} orders · seed {summary.seed}
            </p>
          </div>
        }
      />

      <StatsBento
        incrementalRecoveredRevenue={summary.delta.recovered_revenue}
        reclaimRate={summary.reclaim.recovery_rate}
        baselineRate={summary.always_retry.recovery_rate}
        recoveredOrders={recoveredCount}
        lostOrders={lostCount}
        pendingOrders={pendingCount}
        totalOrders={summary.n_orders}
      />

      <section className="mb-12">
        <SectionHeading
          eyebrow="policy comparison"
          title="Recovered revenue by policy"
          action={<p className="num text-xs text-ink-faint">INR</p>}
        />
        <RecoveryBar data={chartData} />
      </section>

      <section className="border-t border-rule pt-8">
        <SectionHeading
          eyebrow="latest cases"
          title="Recent orders"
          action={
            <Link href="/orders" className="text-sm text-ink underline decoration-rule underline-offset-4 hover:decoration-ink">
              View all
            </Link>
          }
        />
        <div className="panel overflow-hidden">
          {orders.slice(0, 5).map((order) => (
            <Link
              key={order.order_id}
              href={`/orders/${order.order_id}`}
              className="flex items-center justify-between gap-4 border-b border-rule px-4 py-4 transition-colors last:border-0 hover:bg-accent-soft/25 sm:px-5"
            >
              <div className="min-w-0">
                <p className="num truncate text-sm text-ink">{order.order_id}</p>
                <p className="num mt-1 text-[10px] uppercase tracking-widest text-ink-faint">
                  {order.created_at ? formatDate(order.created_at) : "time unavailable"}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                <Money value={order.amount} />
                <Status value={order.status} tone={STATUS_TONE[order.status]} />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </PageShell>
  );
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}
