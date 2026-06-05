# ADR-0001: Two-layer config — Phoenix Base + Agent Custom

## Status

Accepted

## Context

Release metrics and policies were hardcoded or tied to the stability_ops reference integration. We need a simple model for multiple agents without policy inheritance libraries.

## Decision

- **Phoenix Base** (`configs/phoenix/`): shared eval-derived metrics and default thresholds for all agents.
- **Agent Custom** (`configs/agents/<agent>/*_custom.json`): per-agent dimensions and business policy.
- Merge with a single flat merge; custom overrides base on key conflict.
- No `extends` chains, no shared company policy directory for other agents to import.

## Consequences

- New agents copy `configs/agents/_template/` and fill custom files; Phoenix base is applied automatically.
- stability_ops demo = Phoenix base + stability_ops custom (not special-cased in Python).
