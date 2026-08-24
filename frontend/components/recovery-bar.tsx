"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import BentoCard from "@/components/ui/bento-card";

interface Datum {
  name: string;
  recovered: number;
  fill: string;
}

export function RecoveryBar({ data }: { data: Datum[] }) {
  return (
    <BentoCard className="p-4 sm:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-rule pb-4">
        <p className="eyebrow">recovered revenue comparison</p>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          {data.map((item) => (
            <span key={item.name} className="flex items-center gap-2 text-xs text-ink-muted">
              <span className="size-2 rounded-full" style={{ backgroundColor: item.fill }} aria-hidden="true" />
              <span>{item.name}</span>
            </span>
          ))}
        </div>
      </div>
      <div
        className="h-64 w-full"
        role="img"
        aria-label={`Recovered revenue comparison: ${data.map((item) => `${item.name} ${item.recovered.toLocaleString("en-IN")} INR`).join(", ")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
            <CartesianGrid stroke="var(--rule)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="name"
              stroke="var(--ink-muted)"
              tick={{ fill: "var(--ink-muted)", fontFamily: "var(--font-geist-mono)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--rule)" }}
            />
            <YAxis
              stroke="var(--ink-muted)"
              tick={{ fill: "var(--ink-muted)", fontFamily: "var(--font-geist-mono)", fontSize: 11 }}
              tickFormatter={(v) => `₹${(v / 100000).toFixed(1)}L`}
              tickLine={false}
              axisLine={false}
              width={52}
            />
            <Tooltip
              cursor={{ fill: "var(--accent-soft)" }}
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--rule-strong)",
                borderRadius: 16,
                boxShadow: "0 12px 28px rgba(26, 26, 26, 0.08)",
                color: "var(--ink)",
                fontFamily: "var(--font-geist-mono)",
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--ink)", marginBottom: 6 }}
              itemStyle={{ color: "var(--ink)" }}
              formatter={(v) =>
                new Intl.NumberFormat("en-IN", {
                  style: "currency",
                  currency: "INR",
                  maximumFractionDigits: 0,
                }).format(Number(v))
              }
            />
            <Bar dataKey="recovered" barSize={54} radius={[12, 12, 4, 4]}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </BentoCard>
  );
}
