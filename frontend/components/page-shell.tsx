import type { ReactNode } from "react";

export function PageShell({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`page-enter mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-10 lg:py-12 ${className}`}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  meta,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  meta?: ReactNode;
}) {
  return (
    <header className="mb-10 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-xl text-sm leading-6 text-ink-muted">
            {description}
          </p>
        )}
      </div>
      {meta && <div className="shrink-0">{meta}</div>}
    </header>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h2 className="text-lg font-medium tracking-[-0.02em] text-ink">
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  detail?: string;
  tone?: "default" | "accent" | "danger";
}) {
  const toneClass = {
    default: "border-rule",
    accent: "border-accent bg-accent-soft/30",
    danger: "border-danger bg-danger-soft/20",
  }[tone];

  return (
    <div className={`panel border-l-2 p-4 sm:p-5 ${toneClass}`}>
      <p className="eyebrow">{label}</p>
      <div className="mt-2 text-xl font-medium tracking-tight text-ink sm:text-2xl">
        {value}
      </div>
      {detail && <p className="mt-2 text-xs leading-5 text-ink-muted">{detail}</p>}
    </div>
  );
}
