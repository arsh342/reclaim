"use client";

import { useEffect, useState } from "react";
import { Search, Filter, ChevronDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, OrderSummary, OrderDetail } from "@/lib/api";
import { ORDER_STATUS_LABELS } from "@/lib/types";

export default function OrdersPage() {
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    api.orders().then(setOrders).catch(console.error).finally(() => setLoading(false));
  }, []);

  const handleViewOrder = async (orderId: string) => {
    const detail = await api.order(orderId);
    setSelectedOrder(detail);
  };

  const filteredOrders = orders.filter((order) => {
    const matchesSearch = order.order_id.toLowerCase().includes(search.toLowerCase()) ||
      order.customer_id.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || order.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Orders</h1>
        <p className="text-muted-foreground mt-1">Payment orders and recovery status</p>
      </div>

      {/* Search and Filter */}
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search orders..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="pl-10 pr-8 appearance-none border border-input bg-background rounded-md py-2 px-3 text-sm"
              >
                <option value="all">All Status</option>
                <option value="pending">Pending</option>
                <option value="recovered">Recovered</option>
                <option value="lost">Lost</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Orders Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Orders ({filteredOrders.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : filteredOrders.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">No orders found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-muted-foreground">
                    <th className="pb-3 pr-4">Order ID</th>
                    <th className="pb-3 pr-4">Customer</th>
                    <th className="pb-3 pr-4">Amount</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 pr-4">Latest Attempt</th>
                    <th className="pb-3 pr-4">Reason</th>
                    <th className="pb-3 pr-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((order) => (
                    <tr key={order.order_id} className="border-b last:border-0 hover:bg-accent/50 cursor-pointer" onClick={() => handleViewOrder(order.order_id)}>
                      <td className="py-3 pr-4 font-mono text-sm">{order.order_id}</td>
                      <td className="py-3 pr-4 text-sm">{order.customer_id}</td>
                      <td className="py-3 pr-4">₹{order.amount.toLocaleString()}</td>
                      <td className="py-3 pr-4">
                        <Badge variant={order.status === "recovered" ? "success" : order.status === "lost" ? "destructive" : "default"}>
                          {ORDER_STATUS_LABELS[order.status as keyof typeof ORDER_STATUS_LABELS] || order.status}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 text-sm text-muted-foreground">{order.latest_attempt_status ?? "-"}</td>
                      <td className="py-3 pr-4 text-sm text-muted-foreground">{order.latest_attempt_reason ?? "-"}</td>
                      <td className="py-3 pr-4">
                        <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); handleViewOrder(order.order_id); }}>
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Order Detail Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setSelectedOrder(null)}>
          <div className="bg-background rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <Card className="m-4">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Order Detail: {selectedOrder.order.order_id}</CardTitle>
                <Button variant="ghost" size="icon" onClick={() => setSelectedOrder(null)}>✕</Button>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2 mb-6">
                  <div>
                    <h4 className="font-medium text-sm text-muted-foreground">Order Info</h4>
                    <div className="space-y-1 text-sm mt-1">
                      <div><strong>Amount:</strong> ₹{selectedOrder.order.amount.toLocaleString()} {selectedOrder.order.currency}</div>
                      <div><strong>Status:</strong> <Badge variant={selectedOrder.order.status === "recovered" ? "success" : "default"}>{selectedOrder.order.status}</Badge></div>
                      <div><strong>Created:</strong> {new Date(selectedOrder.order.created_at).toLocaleString()}</div>
                    </div>
                  </div>
                  <div>
                    <h4 className="font-medium text-sm text-muted-foreground">Payment Attempts</h4>
                    <div className="space-y-1 text-sm mt-1">
                      {selectedOrder.attempts.map((a) => (
                        <div key={a.payment_id} className="flex items-center gap-2 text-xs">
                          <Badge variant={a.status === "captured" ? "success" : "default"}>{a.status}</Badge>
                          <span>{a.method}</span>
                          <span className="text-muted-foreground">{a.error_reason ?? "-"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Recovery Actions */}
                {selectedOrder.recovery_actions.length > 0 && (
                  <div className="mb-6">
                    <h4 className="font-medium text-sm text-muted-foreground mb-2">Recovery Actions</h4>
                    <div className="space-y-2">
                      {selectedOrder.recovery_actions.map((action) => (
                        <div key={action.action_id} className="p-3 border rounded-lg text-sm">
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{action.action_type}</span>
                            <Badge variant={action.status === "executed" ? "success" : action.status === "cancelled" ? "destructive" : "default"}>
                              {action.status}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Expected: ₹{action.expected_value.toLocaleString()} | {action.reason ?? "No reason"}
                          </div>
                          {action.status === "scheduled" && (
                            <div className="mt-2 flex gap-2">
                              <button
                                onClick={async () => {
                                  const result = await api.completeRecoveryAction(action.action_id, true, "Marked as recovered manually");
                                  if (result.success) {
                                    const updated = await api.order(selectedOrder.order.order_id);
                                    setSelectedOrder(updated);
                                  }
                                }}
                                className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 transition-colors"
                              >
                                Mark Recovered
                              </button>
                              <button
                                onClick={async () => {
                                  const result = await api.completeRecoveryAction(action.action_id, false, "Marked as failed manually");
                                  if (result.success) {
                                    const updated = await api.order(selectedOrder.order.order_id);
                                    setSelectedOrder(updated);
                                  }
                                }}
                                className="px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors"
                              >
                                Mark Failed
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Agent Runs */}
                {selectedOrder.agent_runs.length > 0 && (
                  <div>
                    <h4 className="font-medium text-sm text-muted-foreground mb-2">Agent Runs</h4>
                    <div className="space-y-2">
                      {selectedOrder.agent_runs.map((run) => (
                        <div key={run.run_id} className="p-3 border rounded-lg text-sm">
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-medium">{run.run_id}</span>
                            <Badge variant={run.status === "completed" ? "success" : run.status === "failed" ? "destructive" : "default"}>
                              {run.status}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground mt-1">
                            Stage: {run.current_stage ?? "-"} | Action: {run.final_action ?? "-"}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Decision Inspector */}
                {selectedOrder.decision_analysis && (() => {
                  const da = selectedOrder.decision_analysis!;
                  return (
                    <div className="mt-6 p-4 border rounded-lg bg-muted/50">
                      <h4 className="font-medium text-sm text-muted-foreground mb-3 flex items-center gap-2">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        Decision Inspector
                      </h4>
                      <div className="space-y-4 text-sm">
                      {da.diagnosis && Object.keys(da.diagnosis).length > 0 && (
                        <div>
                          <div className="font-medium mb-1">Diagnosis</div>
                          <pre className="text-xs text-muted-foreground bg-background p-2 rounded overflow-auto max-h-32">{JSON.stringify(da.diagnosis, null, 2)}</pre>
                        </div>
                      )}
                      {da.candidates && da.candidates.length > 0 && (
                        <div>
                          <div className="font-medium mb-1">Candidates Evaluated</div>
                          <div className="space-y-2">
                            {da.candidates.map((c: any, idx: number) => {
                              const isChosen = da.chosen_action === c.action;
                              return (
                                <div key={idx} className={`p-2 border rounded ${isChosen ? 'bg-primary/10 border-primary' : ''}`}>
                                  <div className="flex items-center justify-between">
                                    <span className="font-medium">{c.action}</span>
                                    {isChosen && (
                                      <Badge variant="success" className="text-xs">CHOSEN</Badge>
                                    )}
                                  </div>
                                  <div className="text-xs text-muted-foreground flex gap-4 mt-1">
                                    <span>P(recovery): {(c.probability * 100).toFixed(1)}%</span>
                                    <span>EV: ₹{c.expected_value.toLocaleString()}</span>
                                    <span>Cost: ₹{c.intervention_cost.toLocaleString()}</span>
                                    <span>Friction: {c.friction_cost.toFixed(1)}</span>
                                    <span>Risk: {c.risk_penalty.toFixed(1)}</span>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      {da.stop_conditions && da.stop_conditions.length > 0 && (
                        <div>
                          <div className="font-medium mb-1">Stop Conditions</div>
                          <ul className="list-disc list-inside text-xs text-muted-foreground space-y-1">
                            {da.stop_conditions.map((reason: string, idx: number) => (
                              <li key={idx}>{reason}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                  );
                })()}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}