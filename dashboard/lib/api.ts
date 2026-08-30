/** API client and types for Reclaim frontend */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === 'string' ? body.detail : response.statusText;
    throw new ApiError(response.status, `${response.status} ${detail}`);
  }

  return (await response.json()) as T;
}

// Types
export interface OrderSummary {
  order_id: string;
  merchant_id: string;
  customer_id: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
  latest_attempt_status?: string;
  latest_attempt_reason?: string;
}

export interface PaymentAttempt {
  payment_id: string;
  order_id: string;
  attempt_number: number;
  method: string;
  status: string;
  error_code?: string;
  error_reason?: string;
  error_source?: string;
  error_step?: string;
  created_at: string;
}

export interface RecoveryAction {
  action_id: number;
  order_id: string;
  action_type: string;
  expected_value: number;
  status: string;
  scheduled_at: string;
  executed_at?: string;
  cancelled_at?: string;
  reason?: string;
}

export interface AgentEvent {
  event_seq: number;
  run_id: string;
  order_id: string;
  agent_stage: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AgentRun {
  run_id: string;
  order_id: string;
  status: string;
  current_stage?: string;
  started_at: string;
  completed_at?: string;
  final_action?: string;
  final_reason?: string;
}

export interface CandidateAction {
  action: string;
  probability: number;
  expected_value: number;
  intervention_cost: number;
  friction_cost: number;
  risk_penalty: number;
}

export interface DecisionAnalysis {
  diagnosis: Record<string, unknown>;
  candidates: CandidateAction[];
  chosen_action?: string;
  stop_conditions: string[];
}

export interface MCPStatus {
  status: string;
  endpoint: string;
  transport: string;
  protocol: string;
  tools_count: number;
}

export interface MCPTool {
  name: string;
  description: string;
  read_only: boolean;
  financial_side_effect: boolean;
}

export interface MCPActivity {
  timestamp: string;
  tool: string;
  duration_ms: number;
  status: string;
  order_id?: string;
  error?: string;
}

export interface PolicyMetrics {
  policy_name: string;
  recovered_revenue: number;
  recovery_rate: number;
  total_revenue_at_risk: number;
  unnecessary_interventions: number;
  contact_count: number;
  avg_time_to_resolution_hours: number;
  policy_rejections: number;
}

export interface EvalSummary {
  always_retry: PolicyMetrics;
  reclaim: PolicyMetrics;
  incremental_revenue: number;
  incremental_recovery_rate: number;
  total_orders: number;
  seed: number;
}

export interface OrderDetail {
  order: OrderSummary;
  attempts: PaymentAttempt[];
  recovery_actions: RecoveryAction[];
  agent_runs: AgentRun[];
  decision_analysis?: DecisionAnalysis;
}

export interface IngestResult {
  status: string;
  event_id: string;
  order_id?: string;
  message: string;
}

export interface SimulateWebhookRequest {
  entity: 'event';
  account_id: string;
  event: 'payment.failed' | 'payment.captured';
  contains: string[];
  payload: {
    payment: {
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
}

// API
export const api = {
  health: () => request<{ status: string }>('/api/health'),
  orders: () => request<OrderSummary[]>('/api/orders'),
  order: (orderId: string) => request<OrderDetail>(`/api/orders/${orderId}`),
  evalSummary: (nOrders = 2000, seed = 42) =>
    request<EvalSummary>(`/api/eval/summary?n_orders=${nOrders}&seed=${seed}`),
  agentRuns: () => request<AgentRun[]>('/api/agent-runs'),
  agentRun: (runId: string) => request<AgentRun>(`/api/agent-runs/${runId}`),
  agentEvents: (runId: string) => request<AgentEvent[]>(`/api/agent-runs/${runId}/events`),
  startAgentRun: (orderId: string) =>
    request<AgentRun>(`/api/agent-runs/${orderId}/start`, { method: 'POST' }),
  replayAgentRun: (runId: string) =>
    request<AgentRun>(`/api/agent-runs/${runId}/replay`, { method: 'POST' }),
  simulateWebhook: (body: SimulateWebhookRequest) =>
    request<IngestResult>('/api/webhooks/simulate', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  mcpStatus: () => request<MCPStatus>('/api/mcp/status'),
  mcpTools: () => request<MCPTool[]>('/api/mcp/tools'),
  mcpActivity: (limit = 50) => request<MCPActivity[]>(`/api/mcp/activity?limit=${limit}`),
  completeRecoveryAction: (actionId: number, success = true, reason?: string) =>
    request<{ success: boolean; action_id: number | null; reason?: string }>(
      `/api/recovery-actions/${actionId}/complete`,
      {
        method: 'POST',
        body: JSON.stringify({ action_id: actionId, success, reason }),
      },
    ),
};

// Helpers
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
}): SimulateWebhookRequest {
  const amountPaise = Math.round(params.amount * 100);
  return {
    entity: 'event',
    account_id: 'acc_test',
    event: 'payment.failed',
    contains: ['payment'],
    payload: {
      payment: {
        id: params.payment_id,
        order_id: params.order_id,
        amount: amountPaise,
        currency: 'INR',
        method: params.method ?? 'card',
        status: 'failed',
        attempt_number: params.attempt_number ?? 1,
        error_code: params.error_code ?? 'BAD_REQUEST_PAYMENT_FAILED',
        error_description: 'Payment failed',
        error_reason: params.error_reason ?? 'issuer_timeout',
        error_source: params.error_source ?? 'customer',
        error_step: params.error_step ?? 'payment_authentication',
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
}): SimulateWebhookRequest {
  const amountPaise = Math.round(params.amount * 100);
  return {
    entity: 'event',
    account_id: 'acc_test',
    event: 'payment.captured',
    contains: ['payment'],
    payload: {
      payment: {
        id: params.payment_id,
        order_id: params.order_id,
        amount: amountPaise,
        currency: 'INR',
        method: params.method ?? 'card',
        status: 'captured',
        attempt_number: params.attempt_number ?? 1,
      },
    },
  };
}