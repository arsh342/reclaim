"use client";

import { useEffect, useState, useMemo } from "react";
import {
  Play,
  RotateCcw,
  Search,
  Clock,
  Zap as ZapIcon,
  CheckCircle2,
  CircleX,
  AlertTriangle as AlertTriangleIcon,
  Loader2 as Loader2Icon,
  Circle as CircleIcon,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  TaskSteps,
  TaskStep,
} from "@/components/ui/task-steps";

import { api, AgentRun, AgentEvent } from "@/lib/api";
import {
  STAGE_LABELS,
  STAGE_DESCRIPTIONS,
  AgentStage,
  AgentStageStatus,
} from "@/lib/types";

import { createEventStream } from "@/lib/sse";

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

interface StageStatusConfig {
  bg: string;
  border: string;
  text: string;
  icon: React.ReactNode;
  label: string;
}

const STAGE_STATUS_CONFIG: Record<
  AgentStageStatus,
  StageStatusConfig
> = {
  idle: {
    bg: "bg-gray-50",
    border: "border-gray-200",
    text: "text-gray-500",
    icon: <CircleIcon className="h-3 w-3" />,
    label: "Pending",
  },

  running: {
    bg: "bg-blue-50",
    border: "border-blue-200",
    text: "text-blue-600",
    icon: <Loader2Icon className="h-3 w-3 animate-spin" />,
    label: "Running",
  },

  completed: {
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-600",
    icon: <CheckCircle2 className="h-3 w-3" />,
    label: "Completed",
  },

  rejected: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-600",
    icon: <CircleX className="h-3 w-3" />,
    label: "Rejected",
  },

  failed: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-600",
    icon: <AlertTriangleIcon className="h-3 w-3" />,
    label: "Failed",
  },

  waiting: {
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-600",
    icon: <ZapIcon className="h-3 w-3 animate-pulse" />,
    label: "Waiting",
  },
};

function stageDurationMeta(
  events: AgentEvent[],
  stage: AgentStage
): string | undefined {
  const started = events.find(
    (e) =>
      e.agent_stage === stage &&
      e.event_type === "agent.stage.started"
  );
  const completed = [...events]
    .reverse()
    .find(
      (e) =>
        e.agent_stage === stage &&
        e.event_type === "agent.stage.completed"
    );

  if (!started || !completed) return undefined;

  const ms =
    new Date(completed.created_at).getTime() -
    new Date(started.created_at).getTime();

  if (ms < 100) return undefined; // Only show durations > 100ms

  return `${(ms / 1000).toFixed(1)}s`;
}

export default function AgentPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] =
    useState<AgentRunDetail | null>(null);

  const [loading, setLoading] = useState(true);
  const [eventStream, setEventStream] = useState<any>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] =
    useState<string>("all");

  useEffect(() => {
    api
      .agentRuns()
      .then(setRuns)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedRun) {
      const stream = createEventStream(
        selectedRun.run.run_id
      );

      stream.connect();

      const unsubscribe = stream.onEvent((event) => {
        setSelectedRun((prev) =>
          prev
            ? {
                ...prev,
                events: [...prev.events, event],
                run: {
                  ...prev.run,
                  // Update current_stage from stage events
                  current_stage:
                    event.event_type === "agent.stage.started"
                      ? (event.agent_stage as AgentStage)
                      : prev.run.current_stage,
                  status:
                    event.payload?.status === "completed"
                      ? "completed"
                      : event.payload?.status === "failed"
                      ? "failed"
                      : prev.run.status,
                },
              }
            : null
        );

        // Refetch runs list when run completes
        if (
          event.event_type === "agent.run.completed" ||
          (event.payload?.status === "completed" ||
            event.payload?.status === "failed")
        ) {
          api.agentRuns().then(setRuns).catch(console.error);
        }
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

    setSelectedRun({
      run,
      events,
    });
  };

  const handleStartNewRun = async () => {
    const result = await api.startAgentRun(
      "order_demo_insufficient_funds"
    );

    const events = await api.agentEvents(result.run_id);

    setSelectedRun({
      run: result,
      events,
    });
  };

  const getStageStatus = (
    stage: AgentStage
  ): AgentStageStatus => {
    if (!selectedRun) return "idle";

    const run = selectedRun.run;
    const events = selectedRun.events;

    const stageEvents = events.filter(
      (e) => e.agent_stage === stage
    );

    const hasCompleted = stageEvents.some(
      (e) => e.event_type === "agent.stage.completed"
    );

    const hasRejected = stageEvents.some(
      (e) => e.event_type === "agent.policy.rejected"
    );

    const hasFailed = stageEvents.some(
      (e) =>
        e.event_type === "agent.tool.completed" &&
        (e.payload as any).error
    );

    const isCurrent = run.current_stage === stage;

    if (hasRejected) return "rejected";
    if (hasFailed) return "failed";
    if (hasCompleted) return "completed";
    if (isCurrent) return "running";

    if (
      run.status === "completed" &&
      stage === "COMPLETED"
    ) {
      return "completed";
    }

    return "idle";
  };

  const filteredRuns = useMemo(() => {
    return runs.filter((run) => {
      const matchesSearch =
        run.run_id
          .toLowerCase()
          .includes(searchQuery.toLowerCase()) ||
        run.order_id
          .toLowerCase()
          .includes(searchQuery.toLowerCase());

      const matchesStatus =
        statusFilter === "all" ||
        run.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [runs, searchQuery, statusFilter]);

  // TaskSteps pipeline props derived from the selected run
  const runFailed = selectedRun?.run.status === "failed";
  const runCompleted =
    selectedRun?.run.status === "completed";

  const stageIndex = selectedRun
    ? STAGE_ORDER.indexOf(
        selectedRun.run.current_stage as AgentStage
      )
    : -1;

  const pipelineCurrent = !selectedRun
    ? -1
    : runCompleted
    ? STAGE_ORDER.length
    : selectedRun.run.current_stage === "REPLANNING"
    ? STAGE_ORDER.indexOf("PLANNING")
    : Math.max(stageIndex, 0);

  const pipelineSteps: TaskStep[] = STAGE_ORDER.map(
    (stage) => ({
      id: stage,
      label: STAGE_LABELS[stage],
      meta: stageDurationMeta(
        selectedRun?.events ?? [],
        stage
      ),
    })
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />

          <p className="text-muted-foreground">
            Loading agent runs...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 px-4 h-[calc(100vh-4rem)] flex flex-col gap-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Agent Control Center
          </h1>

          <p className="text-muted-foreground mt-1">
            Live view of recovery agent executions
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Refresh Runs
          </Button>

          <Button onClick={handleStartNewRun}>
            <Play className="h-4 w-4 mr-2" />
            Start New Agent Run (Demo)
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-4 min-h-0 overflow-hidden">

        {/* Top Row */}
        <div className="flex gap-4 flex-1 min-h-0 overflow-hidden">

          {/* Left: Run List */}
          <div className="w-[30%] flex-shrink-0 flex flex-col min-w-0 min-h-0 overflow-hidden">
            <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">

              <CardHeader className="pb-2 flex-shrink-0">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">
                    Agent Runs
                  </CardTitle>

                  <Badge
                    variant="outline"
                    className="text-xs"
                  >
                    {filteredRuns.length}/{runs.length}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="p-0 flex-1 flex flex-col min-h-0">

                {/* Filters */}
                <div className="p-3 border-b space-y-2 flex-shrink-0">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />

                    <Input
                      placeholder="Search runs..."
                      value={searchQuery}
                      onChange={(e) =>
                        setSearchQuery(e.target.value)
                      }
                      className="pl-8 text-sm"
                    />
                  </div>

                  <select
                    value={statusFilter}
                    onChange={(e) =>
                      setStatusFilter(e.target.value)
                    }
                    className="w-full text-sm border border-input bg-background px-2 py-1.5 rounded"
                  >
                    <option value="all">
                      All Status
                    </option>

                    <option value="completed">
                      Completed
                    </option>

                    <option value="failed">
                      Failed
                    </option>

                    <option value="running">
                      Running
                    </option>
                  </select>
                </div>

                {/* Run List Scroll */}
                <ScrollArea className="flex-1 min-h-0">
                  {filteredRuns.length === 0 ? (
                    <div className="p-6 text-center text-muted-foreground text-sm">
                      {runs.length === 0
                        ? "No agent runs yet"
                        : "No runs match filters"}
                    </div>
                  ) : (
                    <ul className="divide-y divide-gray-100">
                      {filteredRuns.map((run) => (
                        <li
                          key={run.run_id}
                          className={`p-3 hover:bg-accent/50 cursor-pointer transition-colors border-l-2 ${
                            selectedRun?.run.run_id ===
                            run.run_id
                              ? "border-primary bg-primary/5"
                              : "border-transparent"
                          }`}
                          onClick={() =>
                            handleSelectRun(run)
                          }
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">

                              <div className="font-mono text-sm font-medium truncate">
                                {run.run_id}
                              </div>

                              <div className="text-xs text-muted-foreground truncate">
                                {run.order_id}
                              </div>

                            </div>

                            <Badge
                              variant={
                                run.status ===
                                "completed"
                                  ? "success"
                                  : run.status ===
                                    "failed"
                                  ? "destructive"
                                  : run.status ===
                                    "running"
                                  ? "default"
                                  : "secondary"
                              }
                              className="text-xs shrink-0"
                            >
                              {run.status}
                            </Badge>
                          </div>

                          {run.current_stage && (
                            <div className="mt-1 text-[10px] text-muted-foreground truncate">
                              {STAGE_LABELS[
                                run.current_stage as keyof typeof STAGE_LABELS
                              ] || run.current_stage}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </ScrollArea>

              </CardContent>
            </Card>
          </div>

          {/* Right: Pipeline */}
          <div className="w-[70%] flex flex-col min-w-0 min-h-0 overflow-hidden">

            {/* Current Run Summary */}
            <Card className="mb-4 flex-shrink-0">
              <CardContent className="p-4">

                {selectedRun ? (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">

                    <div>
                      <p className="text-xs text-muted-foreground">
                        Run ID
                      </p>

                      <p className="font-mono text-sm font-medium truncate">
                        {selectedRun.run.run_id}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">
                        Order
                      </p>

                      <p className="font-mono text-sm font-medium truncate">
                        {selectedRun.run.order_id}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">
                        Status
                      </p>

                      <Badge
                        variant={
                          selectedRun.run.status ===
                          "completed"
                            ? "success"
                            : selectedRun.run.status ===
                              "failed"
                            ? "destructive"
                            : selectedRun.run.status ===
                              "running"
                            ? "default"
                            : "secondary"
                        }
                      >
                        {selectedRun.run.status}
                      </Badge>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground">
                        Current Stage
                      </p>

                      <p className="font-medium text-sm truncate">
                        {selectedRun.run.current_stage
                          ? STAGE_LABELS[
                              selectedRun.run
                                .current_stage as keyof typeof STAGE_LABELS
                            ]
                          : "Unknown"}
                      </p>
                    </div>

                  </div>
                ) : (
                  <div className="text-center text-muted-foreground py-8">
                    <Clock className="h-8 w-8 mx-auto text-muted-foreground/30" />

                    <p className="mt-2">
                      Select a run to view pipeline
                    </p>
                  </div>
                )}

              </CardContent>
            </Card>

            {/* Agent Pipeline */}
            <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">

              <CardHeader className="pb-2 flex-shrink-0">
                <CardTitle className="text-sm">
                  Agent Pipeline
                </CardTitle>
              </CardHeader>

              <CardContent className="flex-1 p-0 min-h-0 overflow-hidden">

                {/* Entire Agent Pipeline is scrollable */}
                <ScrollArea className="h-full">

                  {/* Pipeline Visualization */}
                  <div className="px-4 py-4">

                    <TaskSteps
                      steps={pipelineSteps}
                      current={pipelineCurrent}
                      failed={runFailed ?? false}
                      label="Agent pipeline progress"
                    />

                  </div>

                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Bottom: Event Timeline */}
        <div className="h-[40%] min-h-0 flex flex-col flex-shrink-0">

          <Card className="flex-1 flex flex-col min-h-0">

            <CardHeader className="pb-2 flex flex-row items-center justify-between flex-shrink-0">

              <CardTitle className="text-sm">
                Event Timeline
              </CardTitle>

            </CardHeader>

            <CardContent className="flex-1 p-0 min-h-0">

              {selectedRun ? (
                <ScrollArea className="h-full">

                  <div className="space-y-3 p-4">

                    {STAGE_ORDER.map((stage) => {
                      const status =
                        getStageStatus(stage);

                      const stageEvents =
                        selectedRun.events.filter(
                          (e) =>
                            e.agent_stage === stage
                        );

                      const hasEvents =
                        stageEvents.length > 0;

                      const config =
                        STAGE_STATUS_CONFIG[status];

                      const isCurrent =
                        selectedRun.run.current_stage ===
                        stage;

                      return (
                        <div
                          key={stage}
                          className={`flex items-start gap-3 p-3 rounded-lg transition-colors ${
                            isCurrent
                              ? "bg-primary/5 border border-primary/20"
                              : "bg-gray-50/50"
                          }`}
                        >

                          <div
                            className={`flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full border-2 ${config.bg} ${config.border} ${config.text}`}
                          >
                            {config.icon}
                          </div>

                          <div className="flex-1 min-w-0">

                            <div className="flex items-center gap-2">

                              <span className="font-medium text-sm truncate">
                                {STAGE_LABELS[stage]}
                              </span>

                              <Badge
                                variant={
                                  status === "completed"
                                    ? "success"
                                    : status === "running"
                                    ? "default"
                                    : status === "rejected" ||
                                      status === "failed"
                                    ? "destructive"
                                    : "secondary"
                                }
                                className="text-[10px]"
                              >
                                {
                                  STAGE_STATUS_CONFIG[status]
                                    .label
                                }
                              </Badge>

                            </div>

                            <p className="text-xs text-muted-foreground mt-0.5">
                              {STAGE_DESCRIPTIONS[stage]}
                            </p>

                            {hasEvents && (
                              <div className="mt-2 pt-2 border-t border-gray-100">

                                <div className="text-[10px] text-muted-foreground mb-1">
                                  {stageEvents.length} events
                                </div>

                                <div className="space-y-1 max-h-32 overflow-y-auto">

                                  {stageEvents
                                    .slice(-3)
                                    .map((e) => (
                                      <div
                                        key={e.event_seq}
                                        className="text-[10px] text-muted-foreground font-mono"
                                      >
                                        {new Date(
                                          e.created_at
                                        ).toLocaleTimeString()}{" "}
                                        - {e.event_type}
                                      </div>
                                    ))}

                                  {stageEvents.length > 3 && (
                                    <div className="text-[10px] text-muted-foreground">
                                      +
                                      {stageEvents.length - 3}{" "}
                                      more...
                                    </div>
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
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground">

                  <Clock className="h-8 w-8 text-muted-foreground/30" />

                  <p className="mt-2 text-sm">
                    Select a run to view events
                  </p>

                  <p className="text-xs">
                    Events stream live via SSE
                  </p>

                </div>
              )}

            </CardContent>
          </Card>
        </div>

      </div>
    </div>
  );
}
