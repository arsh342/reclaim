const DEFAULT_API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${DEFAULT_API_URL}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, `${response.status} ${detail}`);
  }

  return (await response.json()) as T;
}

// ---- Import generated types from OpenAPI spec ----------------------
// Run `npm run gen:types` to regenerate from backend
import type {
  components,
  operations,
} from "@/lib/api.generated";

// ---- Type aliases for generated response types ---------------------

export type OrderSummary = components["schemas"]["OrderSummary"];
export type OrderDetail = components["schemas"]["OrderDetail"];
export type PaymentAttempt = components["schemas"]["PaymentAttemptSchema"];
export type RecoveryAction = components["schemas"]["RecoveryActionSchema"];
export type CandidateAction = components["schemas"]["CandidateAction"];
export type DecisionAnalysis = components["schemas"]["DecisionAnalysis"];
export type PolicyMetrics = components["schemas"]["PolicyMetrics"];
export type EvaluationSummary = components["schemas"]["EvalSummary"];
export type IngestResult = components["schemas"]["IngestResult"];

// ---- Frontend-specific types (request payloads, UI-specific) ---------

export interface WebhookSimulateRequest {
  entity: "event";
  account_id: string;
  event: "payment.failed" | "payment.captured";
  contains: string[];
  payload: {
    payment: {
      entity: {
        id: string;
        order_id: string;
        /** Razorpay webhook amount in paise. */
        amount: number;
        currency: string;
        method: string;
        status: string;
        attempt_number: number;
        error_code?: string;
        error_description?: string;
        error_reason?: string;
        error_source?: string;
        error_step?: string;
      };
    };
  };
}

export type WebhookResult = IngestResult;

// ---- API surface ------------------------------------------------------

export const api = {
  health: () => request<{ status: string }>("/health"),
  orders: () => request<components["schemas"]["OrderSummary"][]>("/orders"),
  order: (orderId: string) => request<components["schemas"]["OrderDetail"]>(`/orders/${orderId}`),
  evalSummary: (nOrders = 2000, seed = 42) =>
    request<components["schemas"]["EvalSummary"]>(
      `/eval/summary?n_orders=${nOrders}&seed=${seed}`,
    ),
  simulateWebhook: (body: {
    entity: "event";
    account_id: string;
    event: "payment.failed" | "payment.captured";
    contains: string[];
    payload: {
      payment: {
        entity: {
          id: string;
          order_id: string;
          amount: number;
          currency: string;
          method: string;
          status: string;
          attempt_number: number;
          error_code?: string;
          error_description?: string;
          error_reason?: string;
          error_source?: string;
          error_step?: string;
        };
      };
    };
  }) => request<components["schemas"]["IngestResult"]>("/webhooks/simulate", {
    method: "POST",
    body: JSON.stringify(body),
  }),
};

// Helper to build webhook payload with rupee amount (converted to paise)
export function buildPaymentFailedWebhook(params: {
  event_id: string;
  payment_id: string;
  order_id: string;
  amount: number; // rupees
  method?: string;
  attempt_number?: number;
  error_code?: string;
  error_reason?: string;
  error_source?: string;
  error_step?: string;
}) {
  const amountPaise = Math.round(params.amount * 100);
  return {
    entity: "event" as const,
    account_id: "acc_test",
    event: "payment.failed" as const,
    contains: ["payment"],
    payload: {
      payment: {
        entity: {
          id: params.payment_id,
          order_id: params.order_id,
          amount: amountPaise,
          currency: "INR",
          method: params.method ?? "card",
          status: "failed",
          attempt_number: params.attempt_number ?? 1,
          error_code: params.error_code ?? "BAD_REQUEST_PAYMENT_FAILED",
          error_description: "Payment failed",
          error_reason: params.error_reason ?? "issuer_timeout",
          error_source: params.error_source ?? "customer",
          error_step: params.error_step ?? "payment_authentication",
        },
      },
    },
  };
}

export function buildPaymentCapturedWebhook(params: {
  event_id: string;
  payment_id: string;
  order_id: string;
  amount: number; // rupees
  method?: string;
  attempt_number?: number;
}) {
  const amountPaise = Math.round(params.amount * 100);
  return {
    entity: "event" as const,
    account_id: "acc_test",
    event: "payment.captured" as const,
    contains: ["payment"],
    payload: {
      payment: {
        entity: {
          id: params.payment_id,
          order_id: params.order_id,
          amount: amountPaise,
          currency: "INR",
          method: params.method ?? "card",
          status: "captured",
          attempt_number: params.attempt_number ?? 1,
        },
      },
    },
  };
}