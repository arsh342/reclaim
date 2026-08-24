import type { ReactNode } from "react";

export function BentoCard({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <article className={`rounded-xl border border-rule bg-surface p-5 shadow-[0_1px_2px_rgba(26,26,26,0.04)] ${className}`}>
      {children}
    </article>
  );
}

export default BentoCard;
