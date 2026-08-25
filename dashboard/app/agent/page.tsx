"use client";

import { useEffect, useState } from "react";
import { ChevronRight, Circle, Loader2, CheckCircle, XCircle, AlertTriangle, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, AgentRun, AgentEvent, CandidateAction } from "@/lib/api";
import { AgentEventStream, createEventStream } from "@/lib/sse";
import { AGENT_STAGES, STAGE_LABELS, STAGE_DESCRIPTIONS, AgentStage, AgentStageStatus } from "@/lib/types";

interface AgentRunDetail {
  run: AgentRun;
  events: AgentEvent[];
}

const STAGE_ORDER: AgentStage[] = [
  "RECEIVED",
  "CONTEXT_LOADING",
  "DIAGNOSING",
  "GENERATING_CANDIDATES",
  "EVALUATING_COUNTERFACTUALS",
  "PLANNING",
  "SAFETY_CHECK",
  "EXECUTING",
  "WAITING_FOR_OUTCOME",
  "COMPLETED",
];

function StageNode({ stage, status, isCurrent }: { stage: AgentStage; status: AgentStageStatus; isCurrent: boolean }) {
  const statusConfig = {
    idle: { bg: "bg-gray-100", border: "border-gray-300", text: "text-gray-500", icon: <Circle className="h-3 w-3" /> },
    running: { bg: "bg-blue-50", border: "border-blue-300", text: "text-blue-600", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    completed: { bg: "bg-green-50", border: "border-green-300", text: "text-green-600", icon: <CheckCircle className="h-3 w-3" /> },
    rejected: { bg: "bg-red-50", border: "border-red-300", text: "text-red-600", icon: <XCircle className="h-3 w-3" /> },
    failed: { bg: "bg-red-50", border: "border-red-300", text: "text-red-600", icon: <AlertTriangle className="h-3 w-3" /> },
    waiting: { bg: "bg-yellow-50", border: "border-yellow-300", text: "text-yellow-600", icon: <Zap className="h-3 w-3 animate-pulse" /> },
  };

  const config = statusConfig[status];
  
  return (
    <div className="flex flex-col items-center space-y-2">
      <div className={`relative flex h-12 w-12 items-center justify-center rounded-full border-2 ${config.bg} ${config.border} ${config.text}`}>
        {config.icon}
      </div>
      <div className="text-center w-28">
        <p className="text-xs font-medium truncate">{STAGE_LABELS[stage]}</p>
        <p className="text-[10px] text-muted-foreground truncate">{status}</p>
      </div>
    </div>
  );
}

function StageConnector({ isLast }: { isLast: boolean }) {
  if (isLast) return null;
  return (
    <div className="flex-1 h-1 bg-gray-200 mx-2 self-center" />
  );
}

export default function AgentPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [eventStream, setEventStream] = useState<AgentEventStream | null>(null);

  useEffect(() => {
    api.agentRuns().then(setRuns).catch(console.error).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedRun) {
      const stream = createEventStream(selectedRun.run.run_id);
      stream.connect();
      const unsubscribe = stream.onEvent((event) => {
        setSelectedRun((prev) => prev ? { ...prev, events: [...prev.events, event] } : null);
      });
      setEventStream(stream);
      return () => {
        unsubscribe();
        stream.disconnect();
      };
    }
  }, [selectedRun]);

  const handleSelectRun = async (run: AgentRun) => {
    const events = await api.agentEvents(run.run_id);
    setSelectedRun({ run, events });
  };

  const getStageStatus = (stage: AgentStage): AgentStageStatus => {
    if (!selectedRun) return "idle";
    const run = selectedRun.run;
    const events = selectedRun.events;
    
    const stageEvents = events.filter(e => e.agent_stage === stage);
    const hasCompleted = stageEvents.some(e => e.event_type === "agent.stage.completed");
    const hasRejected = stageEvents.some(e => e.event_type === "agent.policy.rejected");
    const hasFailed = stageEvents.some(e => e.event_type === "agent.tool.completed" && (e.payload as any).error);
    const isCurrent = run.current_stage === stage;
    
    if (hasRejected) return "rejected";
    if (hasFailed) return "failed";
    if (hasCompleted) return "completed";
    if (isCurrent) return "running";
    if (run.status === "completed" && stage === "COMPLETED") return "completed";
    return "idle";
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>;
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Agent Control Center</h1>
        <p className="text-muted-foreground mt-1">Live view of recovery agent executions</p>
      </div>

      <div className="grid gap-8 lg:grid-cols-3">
        {/* Left: Run List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Agent Runs</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-[600px] overflow-y-auto">
              {runs.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground">No agent runs yet</div>
              ) : (
                <ul className="divide-y">
                  {runs.map((run) => (
                    <li key={run.run_id} className="p-4 hover:bg-accent cursor-pointer transition-colors" onClick={() => handleSelectRun(run)}>
                      <div className="font-mono text-sm font-medium">{run.run_id}</div>
                      <div className="text-xs text-muted-foreground">{run.order_id}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant={run.status === "completed" ? "success" : run.status === "failed" ? "destructive" : "default"}>
                          {run.status}
                        </Badge>
                        {run.current_stage && <span className="text-xs text-muted-foreground">{run.current_stage}</span>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Center: Agent Graph */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Agent Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedRun ? (
              <div className="space-y-4">
                <div className="flex flex-col items-center space-y-2">
                  {STAGE_ORDER.map((stage, idx) => (
                    <div key={stage} className="flex items-center w-full">
                      <StageNode stage={stage} status={getStageStatus(stage)} isCurrent={selectedRun.run.current_stage === stage} />
                      <StageConnector isLast={idx === STAGE_ORDER.length - 1} />
                    </div>
                  ))}
                </div>
                <div className="mt-4 p-3 bg-muted rounded-lg text-xs">
                  <strong>Current Stage:</strong> {selectedRun.run.current_stage ?? "Unknown"} | 
                  <strong>Status:</strong> {selectedRun.run.status}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center space-y-2 text-muted-foreground">
                {STAGE_ORDER.map((stage, idx) => (
                  <div key={stage} className="flex items-center w-full">
                    <StageNode stage={stage} status="idle" isCurrent={false} />
                    <StageConnector isLast={idx === STAGE_ORDER.length - 1} />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right: Event Timeline */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Event Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedRun ? (
              <div className="max-h-[500px] overflow-y-auto space-y-3">
                {selectedRun.events.length === 0 ? (
                  <p className="text-muted-foreground text-center py-4">No events yet</p>
                ) : (
                  selectedRun.events.slice().reverse().map((event) => (
                    <div key={event.event_seq} className="border-l-2 border-muted pl-3 pb-3">
                      <div className="flex items-start gap-2">
                        <span className="text-xs text-muted-foreground mt-1 min-w-[80px]">{new Date(event.created_at).toLocaleTimeString()}</span>
                        <div className="flex-1">
                          <div className="text-sm font-medium">{event.event_type}</div>
                          <div className="text-xs text-muted-foreground">{event.agent_stage}</div>
                          <pre className="text-[10px] text-muted-foreground mt-1 overflow-auto max-h-20">{JSON.stringify(event.payload, null, 2)}</pre>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-4">Select a run to view events</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}