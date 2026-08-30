# Reclaim Documentation Index

- `DOCUMENTATION.md` — product, architecture, agent runtime, Gemini, policy, frontend, deployment.
- `MCP.md` — MCP server, tools, transports, safety, testing, deployment, and `/mcp` console.
- `API.md` — REST and MCP interface reference.
- `../reclaim-build-plan.md` — 14-day product/build/pitch plan.
- `../reclaim-implementation-plan.md` — engineering checklist.
- `../reclaim-system-design.md` — HLD/LLD, diagrams, state machines, APIs, and MCP architecture.

## Product interfaces

```text
/          Overview
/agent     Agent Control Center
/mcp       MCP Control Center
/docs      Documentation Portal
/mcp       MCP Streamable HTTP endpoint (backend)
```

## Architectural rule

Reclaim owns the agent runtime. Gemini supplies model inference. MCP provides interoperability. The dashboard provides the human control surface. All three interfaces use the same domain services, database state, policy gate, and safe executor.
