type MoneyProps = {
  value: number;
  signed?: boolean;
  emphasize?: boolean;
};

const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function Money({ value, signed, emphasize }: MoneyProps) {
  const sign = signed && value > 0 ? "+" : "";
  const cls = emphasize ? "text-2xl text-ink" : "text-ink";
  return <span className={`num ${cls}`}>{sign}{inr.format(value)}</span>;
}

const pct = new Intl.NumberFormat("en-IN", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function Percent({ value, signed, emphasize }: { value: number; signed?: boolean; emphasize?: boolean }) {
  const sign = signed && value > 0 ? "+" : "";
  const cls = emphasize ? "text-2xl text-ink" : "text-ink";
  return <span className={`num ${cls}`}>{sign}{pct.format(value)}</span>;
}
