# Reclaim

AI revenue-recovery agent with Gemini, deterministic safety controls, live agent visualization, and MCP interoperability.

## Interfaces

- `/` — Overview
- `/agent` — Agent Control Center
- `/mcp` — MCP Control Center
- `/docs` — Documentation Portal
- `/mcp` — MCP Streamable HTTP backend endpoint

## Core architecture

```text
Payment Event
    ↓
Reclaim Agent Runtime
    ↓
Gemini
    ↓
Structured Plan
    ↓
Deterministic Policy Gate
    ↓
Safe Executor
    ↓
Payment Action
    ↓
Outcome / Replan
```

## MCP

Reclaim is also an MCP server. The MCP layer delegates to the same domain services as the web application.

```bash
uv run mcp dev backend/mcp_server/server.py
```

Production transport:

```text
https://<host>/mcp
```

See `docs/MCP.md`.
