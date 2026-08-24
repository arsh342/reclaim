"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/orders", label: "Orders" },
  { href: "/simulate", label: "Simulate" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden h-screen w-56 shrink-0 flex-col overflow-y-auto border-r border-rule bg-surface md:flex">
        <div className="border-b border-rule px-4 py-5">
          <Link href="/" className="flex items-center gap-3 text-sm font-semibold tracking-tight">
            <span>Reclaim</span>
          </Link>
          <p className="num mt-3 text-[10px] uppercase tracking-widest text-ink-faint">
            revenue recovery desk
          </p>
        </div>
        <nav aria-label="Primary navigation" className="flex flex-col gap-2 p-4">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center justify-between rounded-lg border px-3 py-3 text-sm transition-colors ${
                  active
                    ? "border-accent bg-accent-soft/55 font-medium text-ink"
                    : "border-transparent text-ink-muted hover:border-rule hover:bg-surface-raised hover:text-ink"
                }`}
              >
                <span>{item.label}</span>
                <span className="num text-[10px] text-ink-faint">{item.href === "/" ? "01" : item.href === "/orders" ? "02" : "03"}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mx-3 mb-3 mt-auto rounded-lg border border-rule bg-surface-raised p-4">
          <p className="text-[10px] uppercase tracking-widest text-ink-faint">
            revenue recovery desk
          </p>
        </div>
      </aside>

      <div className="sticky top-0 z-30 border-b border-rule bg-surface md:hidden">
        <div className="flex items-center justify-between px-4 py-4">
          <Link href="/" className="flex items-center gap-2 text-sm font-semibold tracking-tight">
            <span className="flex size-8 items-center justify-center rounded-md bg-sidebar-primary text-xs text-sidebar-primary-foreground">R</span>
            Reclaim
          </Link>
        </div>
        <nav aria-label="Primary navigation" className="flex gap-2 overflow-x-auto border-t border-rule px-3 py-2">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded-xl border px-3 py-2 text-xs ${
                  active ? "border-accent bg-accent-soft/55 font-medium text-ink" : "border-transparent text-ink-muted"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );
}