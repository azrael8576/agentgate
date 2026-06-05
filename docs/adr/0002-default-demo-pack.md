# ADR-0002: Default demo pack is config, not core hardcode

## Status

Accepted

## Context

The reference demo (v2 BLOCKED → v2.1 APPROVED) must work out of the box, but the core must stay agent-agnostic.

## Decision

- Default agent pack: `configs/agents/stability_ops/`
- Core exposes one constant: `DEFAULT_AGENT_PACK_PATH`
- Demo seed JSONL lives under the pack (`seed/`), not in Python
- Production agent code stays in `stability-ops-automation/`; AgentGate only registers tools via `profile.json` `tool_manifest`

## Consequences

- CLI/Dashboard default to the reference demo pack without hardcoding demo-agent logic in release pipeline code.
- Tool manifest must be updated manually when the external agent adds tools.
