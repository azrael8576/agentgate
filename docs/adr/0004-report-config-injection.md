# ADR-0004: Single HTML template + ReportConfig injection

## Status

Accepted

## Context

Report control definitions and demo narrative were hardcoded in `report_renderer.py`.

## Decision

- One Jinja template family; no per-agent theme overrides.
- Control labels/definitions and demo story sections come from `report_config.json` in each AgentPack.
- Product landing hero remains agent-agnostic; reference workflow section only when `pack.demo.enabled`.

## Consequences

- stability_ops-specific copy moves to `configs/agents/stability_ops/report_config.json`.
- Other agents supply their own report copy for enabled metrics.
