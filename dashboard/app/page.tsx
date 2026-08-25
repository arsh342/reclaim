"use client";

import { useEffect, useState } from "react";
import { TrendingUp, DollarSign, RefreshCw, Activity, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, EvalSummary, OrderSummary } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface KPICardProps {
  title: string;
  value: string;
  change?: string;
  icon: React.ReactNode;
  variant?: "default" | "success" | "warning";
}

function KPICard({ title, value, change, icon, variant = "default" }: KPICardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {change && (
          <p className={`text-xs mt-1 ${variant === "success" ? "text-green-600" : variant === "warning" ? "text-yellow-600" : "text-muted-foreground"}`}>
            {change}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  const [evalData, setEvalData] = useState<EvalSummary | null>(null);
  const [recentOrders, setRecentOrders] = useState<OrderSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [evalResult, ordersResult] = await Promise.all([
          api.evalSummary(2000, 42),
          api.orders(),
        ]);
        setEvalData(evalResult);
        setRecentOrders(ordersResult.slice(0, 5));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center text-destructive">
        Error: {error}
      </div>
    );
  }

  const incrementalRevenue = evalData?.incremental_revenue ?? 0;
  const incrementalRate = evalData?.incremental_recovery_rate ?? 0;

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Overview</h1>
        <p className="text-muted-foreground mt-1">Revenue recovery agent control center</p>
      </div>

      {/* KPI Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <KPICard
          title="Revenue at Risk"
          value={`₹${(evalData?.always_retry.total_revenue_at_risk ?? 0 / 100000).toFixed(1)}L`}
          icon={<DollarSign className="h-4 w-4 text-muted-foreground" />}
        />
        <KPICard
          title="Recovered (Reclaim)"
          value={`₹${(evalData?.reclaim.recovered_revenue ?? 0 / 100000).toFixed(1)}L`}
          change={`+₹${(incrementalRevenue / 100000).toFixed(1)}L vs baseline`}
          variant="success"
          icon={<TrendingUp className="h-4 w-4 text-green-600" />}
        />
        <KPICard
          title="Recovery Rate"
          value={`${(evalData?.reclaim.recovery_rate ?? 0 * 100).toFixed(1)}%`}
          change={`+${(incrementalRate * 100).toFixed(1)}pp vs baseline`}
          variant="success"
          icon={<Activity className="h-4 w-4 text-green-600" />}
        />
        <KPICard
          title="Active Agent Runs"
          value={`${recentOrders.filter(o => o.status === 'pending').length}`}
          icon={<RefreshCw className="h-4 w-4 text-muted-foreground" />}
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 md:grid-cols-2 mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Recovery Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              {evalData && (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[
                    { policy: "Always Retry", revenue: evalData.always_retry.recovered_revenue / 100000 },
                    { policy: "Reclaim", revenue: evalData.reclaim.recovered_revenue / 100000 },
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="policy" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Key Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Unnecessary Interventions</span>
                  <span className="font-medium">{evalData?.reclaim.unnecessary_interventions ?? 0}</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div className="h-full bg-green-500" style={{ width: `${Math.max(0, 100 - (evalData?.reclaim.unnecessary_interventions ?? 0) / 10)}%` }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Customer Contacts</span>
                  <span className="font-medium">{evalData?.reclaim.contact_count ?? 0}</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500" style={{ width: `${Math.max(0, 100 - (evalData?.reclaim.contact_count ?? 0) / 5)}%` }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Policy Rejections</span>
                  <span className="font-medium">{evalData?.reclaim.policy_rejections ?? 0}</span>
                </div>
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div className="h-full bg-orange-500" style={{ width: `${Math.max(0, 100 - (evalData?.reclaim.policy_rejections ?? 0) / 10)}%` }}></div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Orders */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Orders</CardTitle>
          <Button variant="ghost" size="sm" onClick={() => window.location.href = "/orders"}>
            View All
          </Button>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="pb-3 pr-4">Order ID</th>
                  <th className="pb-3 pr-4">Amount</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Latest Attempt</th>
                  <th className="pb-3 pr-4">Reason</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.map((order) => (
                  <tr key={order.order_id} className="border-b last:border-0">
                    <td className="py-3 pr-4 font-mono text-sm">{order.order_id}</td>
                    <td className="py-3 pr-4">₹{order.amount.toLocaleString()}</td>
                    <td className="py-3 pr-4">
                      <Badge variant={order.status === "recovered" ? "success" : order.status === "lost" ? "destructive" : "default"}>
                        {order.status}
                      </Badge>
                    </td>
                    <td className="py-3 pr-4 text-sm text-muted-foreground">{order.latest_attempt_status ?? "-"}</td>
                    <td className="py-3 pr-4 text-sm text-muted-foreground">{order.latest_attempt_reason ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}