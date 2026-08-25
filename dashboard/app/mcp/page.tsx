"use client";

import { useEffect, useState } from "react";
import { Server, Database, Shield, Terminal, Link2, Copy, CheckCircle, XCircle, AlertTriangle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface MCPTool {
  name: string;
  description: string;
  read_only: boolean;
  financial_side_effect: boolean;
}

interface MCPStatus {
  status: string;
  endpoint: string;
  transport: string;
  protocol: string;
  tools_count: number;
}

interface MCPActivity {
  timestamp: string;
  tool: string;
  duration_ms: number;
  status: "OK" | "APPROVED" | "REJECTED" | "ERROR";
}

export default function MCPPage() {
  const [status, setStatus] = useState<MCPStatus | null>(null);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [activity, setActivity] = useState<MCPActivity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In real implementation, these would be API calls
    // For now, use mock data
    setStatus({
      status: "online",
      endpoint: "/mcp",
      transport: "Streamable HTTP",
      protocol: "MCP v2",
      tools_count: 9,
    });
    setTools([
      { name: "reclaim_get_order_context", description: "Retrieve order, customer, merchant, and payment attempts", read_only: true, financial_side_effect: false },
      { name: "reclaim_get_allowed_actions", description: "Retrieve actions allowed by policy", read_only: true, financial_side_effect: false },
      { name: "reclaim_estimate_recovery", description: "Calculate recovery probability and expected recovery value", read_only: true, financial_side_effect: false },
      { name: "reclaim_get_agent_run", description: "Retrieve an agent run", read_only: true, financial_side_effect: false },
      { name: "reclaim_get_agent_events", description: "Retrieve agent execution events", read_only: true, financial_side_effect: false },
      { name: "reclaim_get_evaluation_summary", description: "Retrieve baseline comparison metrics", read_only: true, financial_side_effect: false },
      { name: "reclaim_start_recovery_run", description: "Start a bounded recovery workflow", read_only: false, financial_side_effect: true },
      { name: "reclaim_execute_recovery_action", description: "Execute a permitted recovery action", read_only: false, financial_side_effect: true },
      { name: "reclaim_cancel_pending_action", description: "Cancel a scheduled action", read_only: false, financial_side_effect: true },
    ]);
    setActivity([
      { timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), tool: "reclaim_get_order_context", duration_ms: 84, status: "OK" },
      { timestamp: new Date(Date.now() - 1000 * 60 * 4).toISOString(), tool: "reclaim_estimate_recovery", duration_ms: 91, status: "OK" },
      { timestamp: new Date(Date.now() - 1000 * 60 * 2).toISOString(), tool: "reclaim_execute_recovery_action", duration_ms: 112, status: "APPROVED" },
      { timestamp: new Date(Date.now() - 1000 * 30).toISOString(), tool: "reclaim_get_allowed_actions", duration_ms: 45, status: "OK" },
      { timestamp: new Date(Date.now() - 1000 * 10).toISOString(), tool: "reclaim_execute_recovery_action", duration_ms: 67, status: "REJECTED" },
    ]);
    setLoading(false);
  }, []);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-[60vh]"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>;
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
            <Badge variant={status?.status === "online" ? "success" : "destructive"}>
              {status?.status?.toUpperCase() ?? "UNKNOWN"}
            </Badge>
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
              <p className="text-sm text-muted-foreground mb-2">Streamable HTTP</p>
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
            <CardTitle>Safety Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-600" />
              <span className="text-sm">Policy gate active</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-600" />
              <span className="text-sm">Executor validates before execution</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-600" />
              <span className="text-sm">All side-effects audited</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              <span className="text-sm text-orange-600">Hard declines block retry actions</span>
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
                  <th className="pb-3 pr-4">Side Effect</th>
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
          <CardTitle>Live MCP Activity</CardTitle>
          <Button variant="ghost" size="icon" onClick={() => setActivity((prev) => [...prev])}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <div className="max-h-64 overflow-y-auto space-y-2">
            {activity.length === 0 ? (
              <p className="text-muted-foreground text-center py-4">No activity yet</p>
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
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}