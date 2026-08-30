# Reclaim API Reference

## REST

### GET /health
Returns service status.

### GET /orders
Returns orders for the dashboard.

### GET /orders/{order_id}
Returns order, customer, merchant, payment attempts, recovery actions, and the latest agent run.

### POST /webhooks/simulate
Accepts Razorpay-style test events such as `payment.failed`, `payment.captured`, and `order.paid`.

### GET /eval/summary
Returns baseline and Reclaim evaluation metrics.

### GET /agent-runs
Returns recent agent runs.

### GET /agent-runs/{run_id}
Returns the complete agent run.

### GET /agent-runs/{run_id}/events
Server-Sent Events stream for live agent execution.

## MCP

The MCP server is available at `/mcp` using Streamable HTTP.

See `MCP.md` for the complete tool catalog and connection guide.
