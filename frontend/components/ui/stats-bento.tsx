import { CheckCircle2, Clock3, XCircle } from "lucide-react";

import BentoCard from "@/components/ui/bento-card";

type StatsBentoProps = {
  incrementalRecoveredRevenue: number;
  reclaimRate: number;
  baselineRate: number;
  recoveredOrders: number;
  lostOrders: number;
  pendingOrders: number;
  totalOrders: number;
};

const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const percent = new Intl.NumberFormat("en-IN", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const decorativeBars = [28, 42, 36, 58, 48, 72, 62, 82, 70, 94, 78];

export function StatsBento({
  incrementalRecoveredRevenue,
  reclaimRate,
  baselineRate,
  recoveredOrders,
  lostOrders,
  pendingOrders,
  totalOrders,
}: StatsBentoProps) {
  const recoveryLift = reclaimRate - baselineRate;

  return (
    <section className="mb-12" aria-label="Recovery performance summary">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-6 md:grid-rows-2">
        <BentoCard className="relative flex min-h-[280px] flex-col justify-between overflow-hidden border-ink bg-ink p-6 text-background md:col-span-3 md:row-span-2 md:p-8">
          <div>
            <span className="inline-block rounded-md border border-background/20 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-ink/60">
              incremental recovery
            </span>
            <p className="num mt-6 text-4xl tracking-[-0.06em] sm:text-5xl text-ink">
              {inr.format(incrementalRecoveredRevenue)}
            </p>
          </div>
          <div>
            <p className="max-w-xs text-sm leading-6 text-ink/60">
              Additional value recovered by Reclaim compared with always-retry across {totalOrders.toLocaleString("en-IN")} simulated orders.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-background/15 pt-4">
              <span className="num text-xs uppercase tracking-widest text-accent">
                policy lift
              </span>
              <span className="num text-xs text-background/50">
                {formatSignedPercent(recoveryLift)} recovery rate
              </span>
            </div>
          </div>
        </BentoCard>

        <BentoCard className="flex min-h-[132px] items-center justify-between gap-6 border-accent bg-accent-soft/55 p-6 md:col-span-3">
          <div>
            <p className="eyebrow text-accent-strong">recovery rate</p>
            <p className="num mt-2 text-3xl tracking-[-0.05em] text-ink">
              {formatSignedPercent(recoveryLift)}
            </p>
            <p className="mt-1 text-xs text-ink-muted">
              {percent.format(reclaimRate)} reclaim vs {percent.format(baselineRate)} baseline
            </p>
          </div>
          <div
            className="flex h-10 items-end gap-1"
            aria-hidden="true"
          >
            {decorativeBars.map((height, index) => (
              <span
                key={index}
                className="w-1.5 rounded-full bg-ink/70"
                style={{ height: `${height}%` }}
              />
            ))}
          </div>
        </BentoCard>

        <StatCountCard
          className="border-accent bg-accent-soft/35"
          icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
          iconClassName="text-accent-strong"
          label="Recovered"
          value={recoveredOrders}
          detail="orders returned to paid"
        />
        <StatCountCard
          className="border-danger bg-danger-soft/35"
          icon={<XCircle className="h-4 w-4" aria-hidden="true" />}
          iconClassName="text-danger"
          label="Lost"
          value={lostOrders}
          detail="orders beyond recovery"
        />
        <StatCountCard
          className="border-rule bg-surface"
          icon={<Clock3 className="h-4 w-4" aria-hidden="true" />}
          iconClassName="text-ink-muted"
          label="Pending"
          value={pendingOrders}
          detail="orders still in queue"
        />
      </div>
    </section>
  );
}

function StatCountCard({
  className,
  icon,
  iconClassName,
  label,
  value,
  detail,
}: {
  className: string;
  icon: React.ReactNode;
  iconClassName: string;
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <BentoCard className={`p-5 md:col-span-1 ${className}`}>
      <div className={`mb-5 ${iconClassName}`}>{icon}</div>
      <p className="num text-3xl tracking-[-0.05em] text-ink">{value}</p>
      <p className="mt-1 text-xs font-semibold uppercase tracking-widest text-ink-muted">
        {label}
      </p>
      <p className="mt-3 text-xs leading-5 text-ink-faint">{detail}</p>
    </BentoCard>
  );
}

function formatSignedPercent(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)} pp`;
}

export default StatsBento;
