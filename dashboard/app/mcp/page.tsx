"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Server, Database, Shield, Terminal, Link2, Copy, CheckCircle, XCircle, AlertTriangle, RefreshCw, Wifi, WifiOff, Activity } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, MCPStatus, MCPTool, MCPActivity } from "@/lib/api";

export default function MCPPage() {
  const [status, setStatus] = useState<MCPStatus | null>(null);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [activity, setActivity] = useState<MCPActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const activityQueueRef = useRef<MCPActivity[]>([]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const connectActivityStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/mcp/activity/stream`);
    eventSourceRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    es.onmessage = (event) => {
      try {
        const activity = JSON.parse(event.data) as MCPActivity;
        activityQueueRef.current = [activity, ...activityQueueRef.current].slice(0, 100);
        setActivity([...activityQueueRef.current]);
      } catch {
        // ignore parse errors
      }
    };
  }, []);

  useEffect(() => {
    api.mcpStatus().then(setStatus).catch(console.error);
    api.mcpTools().then(setTools).catch(console.error);
    api.mcpActivity(50).then(setActivity).catch(console.error).finally(() => setLoading(false));
    activityQueueRef.current = activity;
    connectActivityStream();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [connectActivityStream]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <Server className="h-8 w-8 text-primary" />
          Reclaim MCP Control Center
        </h1>
        <p className="text-muted-foreground mt-1">Model Context Protocol server for Reclaim revenue recovery platform</p>
      </div>

      {/* Server Status */}
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Server Status</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant={status?.status === "online" ? "success" : "destructive"}>
                {status?.status?.toUpperCase() ?? "UNKNOWN"}
              </Badge>
              <span className={`flex h-2 w-2 rounded-full ${status?.status === "online" ? "bg-green-500" : "bg-red-500"}`} />
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Endpoint</span>
              <div className="flex items-center gap-2">
                <code className="bg-muted px-2 py-1 rounded text-xs">{status?.endpoint}</code>
                <Button variant="ghost" size="icon" onClick={() => copyToClipboard(status?.endpoint ?? "")}>
                  <Copy className="h-3 w-3" />
                </Button>
              </div>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Transport</span>
              <span>{status?.transport}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Protocol</span>
              <span>{status?.protocol}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Tools Available</span>
              <span className="font-medium">{status?.tools_count}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Connection</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-muted-foreground mb-2">Production (Streamable HTTP)</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-muted px-2 py-1 rounded text-xs">https://your-domain.com/mcp</code>
                <Button variant="ghost" size="icon" onClick={() => copyToClipboard("https://your-domain.com/mcp")}>
                  <Copy className="h-3 w-3" />
                </Button>
              </div>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-2">Local Development (stdio)</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-muted px-2 py-1 rounded text-xs">uv run mcp dev backend/mcp_server/server.py</code>
                <Button variant="ghost" size="icon" onClick={() => copyToClipboard("uv run mcp dev backend/mcp_server/server.py")}>
                  <Copy className="h-3 w-3" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Safety Architecture</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-600" />
              <span className="text-sm">Policy gate enforces hard constraints</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-600" />
              <span className="text-sm">Executor re-validates before every execution</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-600" />
              <span className="text-sm">All side-effects audited in agent_events</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              <span className="text-sm text-orange-600">Hard declines block retry actions</span>
            </div>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-600" />
              <span className="text-sm text-blue-600">NO_ACTION executes as safe no-op</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tools Catalog */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Tool Catalog ({tools.length} tools)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="pb-3 pr-4">Tool</th>
                  <th className="pb-3 pr-4">Description</th>
                  <th className="pb-3 pr-4">Type</th>
                  <th className="pb-3 pr-4">Financial Side Effect</th>
                  <th className="pb-3 pr-4">Safety</th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool) => (
                  <tr key={tool.name} className="border-b last:border-0">
                    <td className="py-3 pr-4 font-mono text-sm">{tool.name}</td>
                    <td className="py-3 pr-4 text-sm text-muted-foreground max-w-md truncate">{tool.description}</td>
                    <td className="py-3 pr-4">
                      <Badge variant={tool.read_only ? "default" : "warning"}>
                        {tool.read_only ? "READ" : "WRITE"}
                      </Badge>
                    </td>
                    <td className="py-3 pr-4">
                      <Badge variant={tool.financial_side_effect ? "destructive" : "success"}>
                        {tool.financial_side_effect ? "YES" : "NO"}
                      </Badge>
                    </td>
                    <td className="py-3 pr-4">
                      <Badge variant={tool.financial_side_effect ? "warning" : "success"}>
                        {tool.financial_side_effect ? "GUARDED" : "SAFE"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Live Activity */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle>Live MCP Activity</CardTitle>
            <span className={`flex h-2 w-2 rounded-full ${connected ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={() => api.mcpActivity(50).then(setActivity).catch(console.error)}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="max-h-64 overflow-y-auto space-y-2">
            {activity.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">No activity yet — connect an MCP client to see live tool calls</p>
            ) : (
              activity.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground font-mono">{new Date(item.timestamp).toLocaleTimeString()}</span>
                    <code className="text-sm font-mono">{item.tool}</code>
                    <span className="text-xs text-muted-foreground">{item.duration_ms}ms</span>
                    <Badge variant={
                      item.status === "OK" ? "success" :
                      item.status === "APPROVED" ? "success" :
                      item.status === "REJECTED" ? "destructive" : "destructive"
                    }>
                      {item.status}
                    </Badge>
                    {item.order_id && (
                      <span className="text-xs text-muted-foreground font-mono">{item.order_id}</span>
                    )}
                  </div>
                  {item.error && (
                    <span className="text-xs text-red-600 dark:text-red-400">{item.error}</span>
                  )}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}