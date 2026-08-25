"use client";

import { useState } from "react";
import { Send, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, buildPaymentFailedWebhook, buildPaymentCapturedWebhook, IngestResult } from "@/lib/api";

const ERROR_REASONS = [
  "issuer_timeout",
  "insufficient_funds",
  "card_blocked",
  "invalid_card",
  "network_error",
];

const METHODS = ["card", "upi", "netbanking"];

export default function SimulatePage() {
  const [orderId, setOrderId] = useState("order_demo_001");
  const [paymentId, setPaymentId] = useState("pay_demo_001");
  const [amount, setAmount] = useState(5000);
  const [method, setMethod] = useState("card");
  const [attemptNumber, setAttemptNumber] = useState(1);
  const [errorReason, setErrorReason] = useState("issuer_timeout");
  const [eventType, setEventType] = useState<"payment.failed" | "payment.captured">("payment.failed");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [history, setHistory] = useState<Array<{ request: any; result: IngestResult; timestamp: Date }>>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);

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
      webhook = buildPaymentCapturedWebhook({
        event_id: `evt_${Date.now()}`,
        payment_id: paymentId,
        order_id: orderId,
        amount,
        method,
        attempt_number: attemptNumber,
      });
    }

    try {
      const res = await api.simulateWebhook(webhook);
      setResult(res);
      setHistory((prev) => [{ request: webhook, result: res, timestamp: new Date() }, ...prev]);
    } catch (e) {
      setResult({ status: "error", event_id: "", message: e instanceof Error ? e.message : "Unknown error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Webhook Simulator</h1>
        <p className="text-muted-foreground mt-1">Test the recovery agent with simulated payment events</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Simulator Form */}
        <Card>
          <CardHeader>
            <CardTitle>Send Webhook</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
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
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Send Webhook
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Result */}
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
      </div>

      {/* History */}
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
  );
}