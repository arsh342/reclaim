/** Shared TypeScript types */

export type AgentStage =
  | 'RECEIVED'
  | 'CONTEXT_LOADING'
  | 'DIAGNOSING'
  | 'GENERATING_CANDIDATES'
  | 'EVALUATING_COUNTERFACTUALS'
  | 'PLANNING'
  | 'SAFETY_CHECK'
  | 'EXECUTING'
  | 'WAITING_FOR_OUTCOME'
  | 'COMPLETED'
  | 'REPLANNING';

export type AgentStageStatus = 'idle' | 'running' | 'completed' | 'rejected' | 'failed' | 'waiting';

export const AGENT_STAGES: AgentStage[] = [
  'RECEIVED',
  'CONTEXT_LOADING',
  'DIAGNOSING',
  'GENERATING_CANDIDATES',
  'EVALUATING_COUNTERFACTUALS',
  'PLANNING',
  'SAFETY_CHECK',
  'EXECUTING',
  'WAITING_FOR_OUTCOME',
  'COMPLETED',
  'REPLANNING',
];

export const STAGE_LABELS: Record<AgentStage, string> = {
  RECEIVED: 'Event Received',
  CONTEXT_LOADING: 'Context Loading',
  DIAGNOSING: 'Failure Diagnosis',
  GENERATING_CANDIDATES: 'Candidate Generation',
  EVALUATING_COUNTERFACTUALS: 'Counterfactual Evaluation',
  PLANNING: 'Recovery Planning',
  SAFETY_CHECK: 'Safety Gate',
  EXECUTING: 'Execution',
  WAITING_FOR_OUTCOME: 'Waiting for Outcome',
  COMPLETED: 'Completed',
  REPLANNING: 'Replanning',
};

export const STAGE_DESCRIPTIONS: Record<AgentStage, string> = {
  RECEIVED: 'Webhook event received and validated',
  CONTEXT_LOADING: 'Loading order, customer, and payment history',
  DIAGNOSING: 'Classifying failure type and severity',
  GENERATING_CANDIDATES: 'Proposing relevant recovery interventions',
  EVALUATING_COUNTERFACTUALS: 'Computing expected recovery value for each candidate',
  PLANNING: 'Creating bounded recovery plan with conditions',
  SAFETY_CHECK: 'Validating plan against deterministic policy',
  EXECUTING: 'Executing approved recovery action',
  WAITING_FOR_OUTCOME: 'Monitoring for payment outcome',
  COMPLETED: 'Agent run completed',
  REPLANNING: 'Adapting plan after rejection or new event',
};

export type RecoveryActionType =
  | 'RETRY_NOW'
  | 'RETRY_DELAYED'
  | 'PAYMENT_LINK'
  | 'WHATSAPP_NUDGE'
  | 'ALTERNATE_METHOD'
  | 'NO_ACTION'
  | 'HUMAN_REVIEW';

export const RECOVERY_ACTIONS: RecoveryActionType[] = [
  'RETRY_NOW',
  'RETRY_DELAYED',
  'PAYMENT_LINK',
  'WHATSAPP_NUDGE',
  'ALTERNATE_METHOD',
  'NO_ACTION',
  'HUMAN_REVIEW',
];

export const ACTION_LABELS: Record<RecoveryActionType, string> = {
  RETRY_NOW: 'Retry Now',
  RETRY_DELAYED: 'Delayed Retry',
  PAYMENT_LINK: 'Payment Link',
  WHATSAPP_NUDGE: 'WhatsApp Nudge',
  ALTERNATE_METHOD: 'Alternate Method',
  NO_ACTION: 'No Action',
  HUMAN_REVIEW: 'Human Review',
};

export const ACTION_DESCRIPTIONS: Record<RecoveryActionType, string> = {
  RETRY_NOW: 'Immediately retry the payment',
  RETRY_DELAYED: 'Retry after a delay (e.g., 4 hours)',
  PAYMENT_LINK: 'Send payment link to customer',
  WHATSAPP_NUDGE: 'Send WhatsApp reminder to customer',
  ALTERNATE_METHOD: 'Switch to alternative payment method',
  NO_ACTION: 'Take no action (hard decline)',
  HUMAN_REVIEW: 'Escalate to human operator',
};

export type OrderStatus = 'pending' | 'recovered' | 'lost';

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending: 'Pending',
  recovered: 'Recovered',
  lost: 'Lost',
};