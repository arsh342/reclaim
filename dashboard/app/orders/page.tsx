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
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}