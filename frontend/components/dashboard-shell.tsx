"use client";

import type { ReactNode } from "react";

import { Sidebar } from "@/components/sidebar";

export function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <main className="min-w-0 md:ml-56">
        {children}
      </main>
    </div>
  );
}
