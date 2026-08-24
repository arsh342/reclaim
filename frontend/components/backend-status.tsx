"use client";

import { useEffect, useState } from "react";

import { CheckCircle, LoaderCircle, ServerCrash } from "@/components/ui/icons";

import Admonition from "@/components/ui/admonition";
import { api } from "@/lib/api";

export type BackendStatus = "checking" | "online" | "offline";

export const BACKEND_STATUS_COPY: Record<BackendStatus, string> = {
  checking: "checking connection",
  online: "online",
  offline: "offline",
};

export const BACKEND_STATUS_TONE: Record<BackendStatus, string> = {
  checking: "bg-pending",
  online: "bg-green-600",
  offline: "bg-danger",
};

export function useBackendStatus() {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    let mounted = true;

    const checkBackend = async () => {
      // Retry up to 3 times with exponential backoff for cold starts
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          await api.health();
          if (mounted) setStatus("online");
          return;
        } catch {
          if (!mounted) return;
          if (attempt < 2) {
            // Exponential backoff: 2s, 4s
            await new Promise(r => setTimeout(r, 2000 * (attempt + 1)));
          }
        }
      }
      if (mounted) setStatus("offline");
    };

    void checkBackend();
    const interval = window.setInterval(checkBackend, 15_000);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, []);

  return status;
}

export function BackendStatusToast({ status }: { status: BackendStatus }) {
  const [dismissedStatus, setDismissedStatus] = useState<BackendStatus | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(
      () => setDismissedStatus(status),
      status === "checking" ? 8_000 : 4_500,
    );

    return () => window.clearTimeout(timeout);
  }, [status]);

  if (dismissedStatus === status) return null;

  if (status === "checking") {
    return (
      <StatusBanner
        type="warning"
        icon={LoaderCircle}
        title="Backend may take a moment to come online"
      >
        Render can wake the API after inactivity. The first request may take up to a minute; this page will update automatically.
      </StatusBanner>
    );
  }

  if (status === "offline") {
    return (
      <StatusBanner
        type="danger"
        icon={ServerCrash}
        title="Backend is not responding"
      >
        The API may be waking up or unavailable. Keep this page open and try again shortly.
      </StatusBanner>
    );
  }

  return (
    <StatusBanner type="success" icon={CheckCircle} title="Backend active">
      The recovery API is responding normally.
    </StatusBanner>
  );
}

function StatusBanner({
  type,
  icon,
  title,
  children,
}: {
  type: "warning" | "danger" | "success";
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="pointer-events-none fixed inset-x-4 top-4 z-50 flex justify-center md:left-56 md:right-4 md:justify-end">
      <div className="pointer-events-auto w-full max-w-xl shadow-lg">
        <Admonition type={type} title={title} icon={icon}>
          {children}
        </Admonition>
      </div>
    </div>
  );
}