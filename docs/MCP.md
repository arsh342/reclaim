# Reclaim MCP Server

## Overview

Reclaim exposes its revenue-recovery capabilities through the Model Context Protocol (MCP).

MCP is an **interoperability layer**, not the Reclaim agent runtime. The Reclaim runtime owns orchestration, state, policy, execution, observability, and Gemini integration. The MCP server exposes selected capabilities to compatible MCP clients.

The current official MCP Python SDK is v2. It supports tools, resources, prompts, stdio, Streamable HTTP, and ASGI integration.

## Architecture

```text
MCP Client
    |
    | MCP
    v
Reclaim MCP Server
    |
    v
Reclaim Application Services
    |
    +--> Policy Engine
    +--> Recovery Simulator
    +--> Agent Runtime
    +--> Safe Executor
    |
    v
PostgreSQL / Razorpay Sandbox
```

The MCP layer does not implement a second version of any business rule.

## Tool Catalog

### Read-only

| Tool | Purpose |
|---|---|
| `reclaim_get_order_context` | Retrieve order, customer, merchant, and payment attempts |
| `reclaim_get_allowed_actions` | Retrieve actions allowed by policy |
| `reclaim_estimate_recovery` | Calculate recovery probability and expected recovery value |
| `reclaim_get_agent_run` | Retrieve an agent run |
| `reclaim_get_agent_events` | Retrieve agent execution events |
| `reclaim_get_evaluation_summary` | Retrieve baseline comparison metrics |

### Guarded side-effecting tools

| Tool | Purpose |
|---|---|
| `reclaim_start_recovery_run` | Start a bounded recovery workflow |
| `reclaim_execute_recovery_action` | Execute a permitted recovery action |
| `reclaim_cancel_pending_action` | Cancel a scheduled action |

Every side-effecting operation goes through the same safety gate and executor used by the web application.

## Safety

An MCP client cannot directly mutate payment state.

```text
client
  ↓
MCP tool
  ↓
domain service
  ↓
hard constraint gate
  ↓
idempotent executor
  ↓
database
```

If the client requests `RETRY_NOW` for a hard decline, the policy gate rejects it before any side effect occurs.

## MCP and Gemini

MCP does not replace Gemini.

```text
Gemini
  ↓
Reclaim Agent Runtime
  ↓
Reclaim domain tools

External MCP Client
  ↓
Reclaim MCP Server
  ↓
Reclaim domain tools
```

Both paths share the same domain services.

## Run Locally

### Install
```bash
pip install -r requirements.txt
```

### Development (stdio + MCP Inspector)
```bash
uv run mcp dev backend/mcp_server/server.py
```

### Start Streamable HTTP
```bash
python -m backend.mcp_server.server
```

Default endpoint:
```
http://127.0.0.1:8000/mcp
```

## Deployment

Production endpoint:
```
https://<reclaim-host>/mcp
```

Configure the MCP SDK host/origin allowlist for the real deployment hostname.

## Testing

Use the MCP SDK's in-memory client for unit-level MCP tests where possible, and MCP Inspector for interactive development.

```bash
uv run mcp dev backend/mcp_server/server.py
```

## MCP Product Page

The Reclaim dashboard includes `/mcp`.

It displays:
- server status
- MCP endpoint
- transport
- protocol version
- tool catalog
- read/write classification
- live MCP activity (SSE)
- latency
- policy rejections
- safety status
- connection instructions

The page is an operational console, not a static marketing page.

## Connection Example

```json
{
  "mcpServers": {
    "reclaim": {
      "url": "https://your-reclaim-domain.com/mcp"
    }
  }
}
```