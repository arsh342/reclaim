"use client";

import type { ReactNode } from "react";

import {
  BackendStatusToast,
  useBackendStatus,
} from "@/components/backend-status";
import { Sidebar } from "@/components/sidebar";

export function DashboardShell({ children }: { children: ReactNode }) {
  const backendStatus = useBackendStatus();

  return (
    <div className="min-h-screen">
      <Sidebar backendStatus={backendStatus} />
      <main className="min-w-0 md:ml-56">
        <BackendStatusToast status={backendStatus} />
        {children}
      </main>
    </div>
  );
}
