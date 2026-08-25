/** SSE client for real-time agent events */

export interface AgentEvent {
  event_seq: number;
  run_id: string;
  order_id: string;
  agent_stage: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export type EventHandler = (event: AgentEvent) => void;

export class AgentEventStream {
  private eventSource: EventSource | null = null;
  private handlers: Set<EventHandler> = new Set();
  private runId: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  constructor(runId: string) {
    this.runId = runId;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      this.eventSource = new EventSource(`${apiUrl}/api/agent-runs/${this.runId}/events`);

      this.eventSource.onopen = () => {
        this.reconnectAttempts = 0;
        resolve();
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handlers.forEach((handler) => handler(data));
        } catch (e) {
          console.error('Failed to parse SSE event:', e);
        }
      };

      this.eventSource.onerror = () => {
        this.eventSource?.close();
        this.attemptReconnect();
      };
    });
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    setTimeout(() => {
      this.connect().catch(console.error);
    }, delay);
  }

  onEvent(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  disconnect() {
    this.eventSource?.close();
    this.eventSource = null;
    this.handlers.clear();
  }
}

export function createEventStream(runId: string): AgentEventStream {
  return new AgentEventStream(runId);
}