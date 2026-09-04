"use client";

import { useState, useEffect } from "react";
import { Send, Loader2, CheckCircle, AlertCircle, Zap, Brain, ChevronRight, Target } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api, buildPaymentFailedWebhook, buildPaymentCapturedWebhook, IngestResult, AgentRun, AgentEvent, createEventStream } from "@/lib/api";
import { TaskSteps, TaskStep } from "@/components/ui/task-steps";
import { STAGE_LABELS, STAGE_DESCRIPTIONS, AgentStage, AgentStageStatus, AGENT_STAGES } from "@/lib/types";

const ERROR_REASONS = [
  "issuer_timeout",
  "insufficient_funds",
  "card_blocked",
  "invalid_card",
  "network_error",
];

const METHODS = ["card", "upi", "netbanking"];

const STAGE_STATUS_CONFIG: Record<AgentStageStatus, { bg: string; border: string; text: string; label: string; icon: React.ReactNode }> = {
  idle: { bg: "bg-gray-50", border: "border-gray-200", text: "text-gray-500", label: "Pending", icon: <div className="h-3 w-3 rounded-full bg-gray-300" /> },
  running: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-600", label: "Running", icon: <div className="h-3 w-3 rounded-full bg-blue-500 animate-pulse" /> },
  completed: { bg: "bg-green-50", border: "border-green-200", text: "text-green-600", label: "Completed", icon: <CheckCircle className="h-3 w-3" /> },
  rejected: { bg: "bg-red-50", border: "border-red-200", text: "text-red-600", label: "Rejected", icon: <AlertCircle className="h-3 w-3" /> },
  failed: { bg: "bg-red-50", border: "border-red-200", text: "text-red-600", label: "Failed", icon: <AlertCircle className="h-3 w-3" /> },
  waiting: { bg: "bg-yellow-50", border: "border-yellow-200", text: "text-yellow-600", label: "Waiting", icon: <Zap className="h-3 w-3 animate-pulse" /> },
};

function getStageStatus(stage: AgentStage, run: AgentRun, events: AgentEvent[]): AgentStageStatus {
  const stageEvents = events.filter((e) => e.agent_stage === stage);
  const hasCompleted = stageEvents.some((e) => e.event_type === "agent.stage.completed");
  const hasRejected = stageEvents.some((e) => e.event_type === "agent.policy.rejected");
  const hasFailed = stageEvents.some((e) => e.event_type === "agent.tool.completed" && (e.payload as any).error);
  const isCurrent = run.current_stage === stage;
  const runCompleted = run.status === "completed";

  if (hasRejected) return "rejected";
  if (hasFailed) return "failed";
  if (hasCompleted) return "completed";
  
  // For completed runs: all stages up to and including COMPLETED are completed
  if (runCompleted) {
    const completedIdx = AGENT_STAGES.indexOf("COMPLETED");
    const stageIdx = AGENT_STAGES.indexOf(stage);
    if (stageIdx <= completedIdx) return "completed";
    return "idle";
  }
  
  if (isCurrent) return "running";
  return "idle";
}

export default function SimulatePage() {
  const [orderId, setOrderId] = useState("order_demo_001");
  const [paymentId, setPaymentId] = useState("pay_demo_001");
  const [amount, setAmount] = useState(5000);
  const [method, setMethod] = useState("card");
  const [attemptNumber, setAttemptNumber] = useState(1);
  const [errorReason, setErrorReason] = useState("insufficient_funds");
  const [eventType, setEventType] = useState<"payment.failed" | "payment.captured">("payment.failed");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [history, setHistory] = useState<Array<{ request: any; result: IngestResult; timestamp: Date }>>([]);
  
  const [autoCapture, setAutoCapture] = useState(true);
  const [captureDelay, setCaptureDelay] = useState(3);
  const [autoCapturePending, setAutoCapturePending] = useState(false);
  const [autoCaptureCountdown, setAutoCaptureCountdown] = useState(0);

  // Agent workflow state
  const [currentRun, setCurrentRun] = useState<AgentRun | null>(null);
  const [currentEvents, setCurrentEvents] = useState<AgentEvent[]>([]);
  const [eventStream, setEventStream] = useState<any>(null);
  const [workflowLoading, setWorkflowLoading] = useState(false);

  const sendWebhook = async (webhook: any) => {
    const res = await api.simulateWebhook(webhook);
    return res;
  };

  const fetchAgentRun = async (runId: string) => {
    setWorkflowLoading(true);
    try {
      const [run, events] = await Promise.all([
        api.agentRun(runId),
        api.agentEvents(runId),
      ]);
      setCurrentRun(run);
      setCurrentEvents(events);
      
      // Connect SSE for live updates
      const stream = createEventStream(runId);
      stream.connect();
      setEventStream(stream);
      
      stream.onEvent((event: any) => {
        setCurrentEvents((prev) => [...prev, event]);
        setCurrentRun((prev) => prev ? {
          ...prev,
          current_stage: event.event_type === "agent.stage.started" ? event.agent_stage : prev.current_stage,
          status: event.payload?.status === "completed" ? "completed" : event.payload?.status === "failed" ? "failed" : prev.status,
        } : null);
        
        if (event.payload?.status === "completed" || event.payload?.status === "failed") {
          stream.disconnect();
        }
      });
    } catch (e) {
      console.error("Failed to fetch agent run:", e);
    } finally {
      setWorkflowLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setCurrentRun(null);
    setCurrentEvents([]);

    let webhook;
    
    if (eventType === "payment.failed") {
      webhook = buildPaymentFailedWebhook({
        event_id: `evt_${Date.now()}`,
        payment_id: paymentId,
        order_id: orderId,
        amount,
        method,
        attempt_number: attemptNumber,
        error_reason: errorReason,
      });
    } else {
      const capturedPaymentId = paymentId.endsWith("_captured") 
        ? paymentId 
        : `${paymentId}_captured`;
      webhook = buildPaymentCapturedWebhook({
        event_id: `evt_${Date.now()}`,
        payment_id: capturedPaymentId,
        order_id: orderId,
        amount,
        method,
        attempt_number: attemptNumber + 1,
      });
    }

    try {
      const res = await sendWebhook(webhook);
      setResult(res);
      setHistory((prev) => [{ request: webhook, result: res, timestamp: new Date() }, ...prev]);
      
      // Start agent run automatically for failed payments
      if (res.order_id && eventType === "payment.failed") {
        try {
          const runResult = await api.startAgentRun(res.order_id);
          await fetchAgentRun(runResult.run_id);
        } catch (e) {
          console.error("Failed to start agent run:", e);
        }
      }
      
      if (eventType === "payment.failed" && autoCapture) {
        setAutoCapturePending(true);
        setAutoCaptureCountdown(captureDelay);
        
        const countdownInterval = setInterval(() => {
          setAutoCaptureCountdown((prev) => {
            if (prev <= 1) {
              clearInterval(countdownInterval);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
        
        setTimeout(async () => {
          const capturedPaymentId = `${paymentId}_captured`;
          const captureWebhook = buildPaymentCapturedWebhook({
            event_id: `evt_${Date.now()}`,
            payment_id: capturedPaymentId,
            order_id: orderId,
            amount,
            method,
            attempt_number: attemptNumber + 1,
          });
          await sendWebhook(captureWebhook);
          setAutoCapturePending(false);
        }, captureDelay * 1000);
      }
    } catch (e) {
      setResult({ status: "error", event_id: "", message: e instanceof Error ? e.message : "Unknown error" });
    } finally {
      setLoading(false);
    }
  };

  // Pipeline steps for TaskSteps
  const pipelineSteps: TaskStep[] = AGENT_STAGES.map((stage) => ({
    id: stage,
    label: STAGE_LABELS[stage],
  }));

  const currentStageIndex = currentRun ? AGENT_STAGES.indexOf(currentRun.current_stage as AgentStage) : -1;
  const pipelineCurrent = currentRun && currentRun.status === "completed" ? AGENT_STAGES.length : Math.max(currentStageIndex, 0);
  const pipelineFailed = currentRun?.status === "failed";

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Webhook Simulator</h1>
        <p className="text-muted-foreground mt-1">Test the recovery agent with simulated payment events</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        {/* Left: Webhook Form + Agent Pipeline */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Send Webhook</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4" id="simulate-form">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium mb-1">Event Type</label>
                    <select
                      value={eventType}
                      onChange={(e) => setEventType(e.target.value as "payment.failed" | "payment.captured")}
                      className="w-full border border-input bg-background rounded-md py-2 px-3 text-sm"
                    >
                      <option value="payment.failed">payment.failed</option>
                      <option value="payment.captured">payment.captured</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Order ID</label>
                    <Input value={orderId} onChange={(e) => setOrderId(e.target.value)} placeholder="order_001" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Payment ID</label>
                    <Input value={paymentId} onChange={(e) => setPaymentId(e.target.value)} placeholder="pay_001" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Amount (₹)</label>
                    <Input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value))} min="1" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Method</label>
                    <select value={method} onChange={(e) => setMethod(e.target.value)} className="w-full border border-input bg-background rounded-md py-2 px-3 text-sm">
                      {METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Attempt Number</label>
                    <Input type="number" value={attemptNumber} onChange={(e) => setAttemptNumber(Number(e.target.value))} min="1" />
                  </div>
                  {eventType === "payment.failed" && (
                    <div>
                      <label className="block text-sm font-medium mb-1">Error Reason</label>
                      <select value={errorReason} onChange={(e) => setErrorReason(e.target.value)} className="w-full border border-input bg-background rounded-md py-2 px-3 text-sm">
                        {ERROR_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </div>
                  )}
                </div>

                {eventType === "payment.failed" && (
                  <div className="md:col-span-2 p-4 bg-muted/50 rounded-lg space-y-3 border">
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        id="autoCapture"
                        checked={autoCapture}
                        onChange={(e) => setAutoCapture(e.target.checked)}
                        className="w-4 h-4 rounded border-input"
                      />
                      <label htmlFor="autoCapture" className="font-medium text-sm">
                        Auto-capture after failed payment
                      </label>
                      <span className="text-xs text-muted-foreground ml-auto">
                        Simulates successful retry after delay
                      </span>
                    </div>
                    {autoCapture && (
                      <div className="flex items-center gap-3">
                        <label className="text-sm text-muted-foreground">Delay:</label>
                        <Input
                          type="number"
                          value={captureDelay}
                          onChange={(e) => setCaptureDelay(Math.max(1, Math.min(30, Number(e.target.value))))}
                          min="1"
                          max="30"
                          className="w-20"
                        />
                        <span className="text-sm text-muted-foreground">seconds</span>
                      </div>
                    )}
                    {autoCapturePending && (
                      <div className="flex items-center gap-3 text-sm">
                        <span className="text-orange-600 animate-pulse">⏳ Auto-capturing in {autoCaptureCountdown}s...</span>
                      </div>
                    )}
                  </div>
                )}

                <Button disabled={loading} className="w-full md:col-span-2">
                  {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Send Webhook
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Agent Pipeline - Live */}
          {currentRun && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5 text-primary" />
                  Agent Pipeline — Live
                </CardTitle>
                <Badge variant={currentRun.status === "completed" ? "success" : currentRun.status === "failed" ? "destructive" : "default"}>
                  {currentRun.status.toUpperCase()}
                </Badge>
              </CardHeader>
              <CardContent>
                <TaskSteps
                  steps={pipelineSteps}
                  current={pipelineCurrent}
                  failed={pipelineFailed}
                  label="Recovery agent progress"
                  className="mb-4"
                />
                
                {/* Stage Details */}
                <ScrollArea className="h-64">
                  <div className="space-y-2">
                    {AGENT_STAGES.map((stage) => {
                      const status = getStageStatus(stage, currentRun, currentEvents);
                      const stageEvents = currentEvents.filter((e) => e.agent_stage === stage);
                      const config = STAGE_STATUS_CONFIG[status];
                      const isCurrent = currentRun.current_stage === stage;

                      return (
                        <div
                          key={stage}
                          className={`flex items-start gap-3 p-3 rounded-lg transition-colors ${
                            isCurrent ? "bg-primary/5 border border-primary/20" : "bg-gray-50/50"
                          }`}
                        >
                          <div className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full border-2 ${config.bg} ${config.border} ${config.text}`}>
                            {config.icon}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-sm truncate">{STAGE_LABELS[stage]}</span>
                              <Badge variant={
                                status === "completed" ? "success" :
                                status === "running" ? "default" :
                                status === "rejected" || status === "failed" ? "destructive" : "secondary"
                              } className="text-[10px]">
                                {config.label}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5">{STAGE_DESCRIPTIONS[stage]}</p>
                            {stageEvents.length > 0 && (
                              <div className="mt-1 pt-1 border-t border-gray-100">
                                <div className="space-y-1 max-h-20 overflow-y-auto">
                                  {stageEvents.slice(-3).map((e) => (
                                    <div key={e.event_seq} className="text-[10px] text-muted-foreground font-mono flex items-center gap-1">
                                      <span>{new Date(e.created_at).toLocaleTimeString()}</span>
                                      <ChevronRight className="h-2.5 w-2.5" />
                                      <span>{e.event_type}</span>
                                    </div>
                                  ))}
                                  {stageEvents.length > 3 && (
                                    <div className="text-[10px] text-muted-foreground">+{stageEvents.length - 3} more...</div>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          )}

          {/* Decision Inspector */}
          {currentRun && currentEvents.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-primary" />
                  Decision Inspector
                </CardTitle>
              </CardHeader>
              <CardContent>
                {(() => {
                  // Build decision analysis from events
                  let diagnosis: any = {};
                  let candidates: any[] = [];
                  let counterfactuals: any[] = [];
                  let chosenAction: string | null = null;
                  let stopConditions: string[] = [];

                  for (const event of currentEvents) {
                    const output = (event.payload?.output || {}) as Record<string, any>;
                    if (event.event_type === "agent.stage.completed" && event.agent_stage === "DIAGNOSING") {
                      diagnosis = output;
                    } else if (event.event_type === "agent.stage.completed" && event.agent_stage === "GENERATING_CANDIDATES") {
                      candidates = output.candidates || [];
                    } else if (event.event_type === "agent.stage.completed" && event.agent_stage === "EVALUATING_COUNTERFACTUALS") {
                      counterfactuals = output.counterfactuals || [];
                    } else if (event.event_type === "agent.stage.completed" && event.agent_stage === "PLANNING") {
                      if (output.steps?.[0]?.action) {
                        chosenAction = output.steps[0].action;
                      }
                    } else if (event.event_type === "agent.policy.rejected") {
                      stopConditions.push((event.payload?.reason as string) || "Policy rejection");
                    }
                  }

                  // Enrich candidates with ERV scores
                  const enrichedCandidates = candidates.map((candidate: any) => {
                    const action = candidate.action;
                    const cf = counterfactuals.find((c: any) => c.action === action) || {};
                    return {
                      ...candidate,
                      probability: cf.probability || 0,
                      expected_value: cf.expected_value || 0,
                      intervention_cost: cf.intervention_cost || 0,
                      friction_cost: cf.friction_cost || 0,
                      risk_penalty: cf.risk_penalty || 0,
                      recoverable_amount: cf.recoverable_amount || 0,
                    };
                  });

                  if (Object.keys(diagnosis).length === 0 && enrichedCandidates.length === 0) {
                    return null;
                  }

                  return (
                    <div className="space-y-6">
                      {/* Diagnosis */}
                      {Object.keys(diagnosis).length > 0 && (
                        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <Brain className="h-4 w-4 text-blue-600" />
                            <span className="font-medium text-blue-800">AI Diagnosis</span>
                          </div>
                          <div className="grid gap-2 text-sm">
                            <div><span className="font-medium">Failure Class:</span> <span className="text-muted-foreground">{diagnosis.failure_class || "unknown"}</span></div>
                            <div><span className="font-medium">Severity:</span> <span className="text-muted-foreground">{diagnosis.severity || "medium"}</span></div>
                            <div><span className="font-medium">Recoverability:</span> <span className="text-muted-foreground">{diagnosis.recoverability || "unknown"}</span></div>
                            <div><span className="font-medium">Strategy:</span> <span className="text-muted-foreground">{diagnosis.candidate_strategy || "N/A"}</span></div>
                            {diagnosis.key_factors?.length && (
                              <div><span className="font-medium">Key Factors:</span> <span className="text-muted-foreground">{diagnosis.key_factors.join(", ")}</span></div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Candidates Evaluated */}
                      {enrichedCandidates.length > 0 && (
                        <div>
                          <div className="flex items-center gap-2 mb-3">
                            <Target className="h-4 w-4 text-primary" />
                            <span className="font-medium">Candidates Evaluated</span>
                          </div>
                          <div className="space-y-3">
                            {enrichedCandidates.map((c: any, idx: number) => {
                              const isChosen = c.action === chosenAction;
                              const ev = c.expected_value || 0;
                              const prob = (c.probability * 100).toFixed(1);
                              return (
                                <div key={idx} className={`p-4 border rounded-lg ${isChosen ? "bg-primary/5 border-primary" : "bg-gray-50"}`}>
                                  <div className="flex items-center justify-between mb-2">
                                    <span className={`font-medium ${isChosen ? "text-primary" : ""}`}>{c.action}</span>
                                    {isChosen && (
                                      <Badge variant="success" className="text-xs flex items-center gap-1">
                                        <CheckCircle className="h-2.5 w-2.5" /> CHOSEN
                                      </Badge>
                                    )}
                                  </div>
                                  <div className="text-xs text-muted-foreground mb-2">{c.rationale || "No rationale provided"}</div>
                                  <div className="grid grid-cols-2 gap-2 text-xs">
                                    <div className="bg-white/50 p-2 rounded">
                                      <div className="text-muted-foreground">P(recovery)</div>
                                      <div className="font-medium">{c.probability ? `${(c.probability * 100).toFixed(1)}%` : "N/A"}</div>
                                    </div>
                                    <div className="bg-white/50 p-2 rounded">
                                      <div className="text-muted-foreground">Expected Value</div>
                                      <div className="font-medium text-green-600">₹{c.expected_value ? c.expected_value.toLocaleString() : "0"}</div>
                                    </div>
                                    <div className="bg-white/50 p-2 rounded">
                                      <div className="text-muted-foreground">Intervention Cost</div>
                                      <div className="font-medium">₹{c.intervention_cost?.toLocaleString() || "0"}</div>
                                    </div>
                                    <div className="bg-white/50 p-2 rounded">
                                      <div className="text-muted-foreground">Friction Cost</div>
                                      <div className="font-medium">₹{c.friction_cost?.toFixed(1) || "0"}</div>
                                    </div>
                                    <div className="bg-white/50 p-2 rounded">
                                      <div className="text-muted-foreground">Risk Penalty</div>
                                      <div className="font-medium">₹{c.risk_penalty?.toFixed(1) || "0"}</div>
                                    </div>
                                    <div className="bg-white/50 p-2 rounded">
                                      <div className="text-muted-foreground">Recoverable Amt</div>
                                      <div className="font-medium">₹{c.recoverable_amount?.toLocaleString() || "0"}</div>
                                    </div>
                                  </div>
                                  {isChosen && (
                                    <div className="mt-3 p-3 bg-primary/5 border border-primary/20 rounded text-sm">
                                      <span className="font-medium text-primary">Why this won:</span> Highest Expected Recovery Value (ERV) after subtracting intervention, friction, and risk costs. Policy gate approved.
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Chosen Action */}
                      {chosenAction && (
                        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle className="h-4 w-4 text-green-600" />
                            <span className="font-medium text-green-800">Chosen Action: {chosenAction}</span>
                          </div>
                          <p className="text-sm text-green-700">
                            This action maximizes Expected Recovery Value while respecting all policy constraints. 
                            The safety gate validated it against hard limits (max retries, hard declines, contact budget).
                          </p>
                        </div>
                      )}

                      {/* Stop Conditions */}
                      {stopConditions.length > 0 && (
                        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <AlertCircle className="h-4 w-4 text-amber-600" />
                            <span className="font-medium text-amber-800">Policy Rejections / Stop Conditions</span>
                          </div>
                          <ul className="list-disc list-inside text-sm text-amber-700 space-y-1">
                            {stopConditions.map((reason, idx) => (
                              <li key={idx}>{reason}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Results + History */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Result</CardTitle>
            </CardHeader>
            <CardContent>
              {result ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Badge variant={result.status === "processed" ? "success" : result.status === "duplicate" ? "warning" : "destructive"}>
                      {result.status}
                    </Badge>
                    <span className="text-sm text-muted-foreground">{result.message}</span>
                  </div>
                  <div className="text-sm">
                    <p><strong>Event ID:</strong> {result.event_id}</p>
                    {result.order_id && <p><strong>Order ID:</strong> {result.order_id}</p>}
                  </div>
                  <pre className="text-xs text-muted-foreground bg-muted p-3 rounded overflow-auto">{JSON.stringify(result, null, 2)}</pre>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-8">Submit a webhook to see results</p>
              )}
            </CardContent>
          </Card>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Webhook History</CardTitle>
            </CardHeader>
            <CardContent>
              {history.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No webhooks sent yet</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b text-left text-sm text-muted-foreground">
                        <th className="pb-3 pr-4">Time</th>
                        <th className="pb-3 pr-4">Event</th>
                        <th className="pb-3 pr-4">Order</th>
                        <th className="pb-3 pr-4">Amount</th>
                        <th className="pb-3 pr-4">Status</th>
                        <th className="pb-3 pr-4">Message</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((item, idx) => (
                        <tr key={idx} className="border-b last:border-0">
                          <td className="py-3 pr-4 text-sm font-mono">{item.timestamp.toLocaleTimeString()}</td>
                          <td className="py-3 pr-4">
                            <Badge variant={item.request.payload.payment.status === "captured" ? "success" : "default"}>
                              {item.request.event}
                            </Badge>
                          </td>
                          <td className="py-3 pr-4 text-sm font-mono">{item.request.payload.payment.order_id}</td>
                          <td className="py-3 pr-4">₹{item.request.payload.payment.amount / 100}</td>
                          <td className="py-3 pr-4">
                            <Badge variant={item.result.status === "processed" ? "success" : item.result.status === "duplicate" ? "warning" : "destructive"}>
                              {item.result.status}
                            </Badge>
                          </td>
                          <td className="py-3 pr-4 text-sm text-muted-foreground">{item.result.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}