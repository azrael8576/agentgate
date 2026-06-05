# ADR-0005: Production agent repos stay external

## Status

Accepted

## Context

`stability-ops-automation` is the real production agent. AgentGate is the release gate product.

## Decision

- Do not copy or vendor production agent Python into AgentGate.
- Integration is: Phoenix traces + AgentPack registration (`profile.json` tool_manifest, policy/metrics custom, span contract).
- Changes to production agent telemetry stay in the agent repo; AgentGate docs describe alignment only.

## Consequences

- AgentGate ships config + seed evidence for demo, not chat/routing/tool implementations.
- Drift between real tools and `tool_manifest` is possible; documented as manual sync.
