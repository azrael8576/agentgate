# ADR-0003: Fixed metric aggregators + JSON selection

## Status

Accepted

## Context

We need agent-specific metrics without arbitrary user Python plugins.

## Decision

- Keep a **fixed** set of Python aggregators in the core (`intent_routing`, `eval_label_rate`, `policy_preflight`, `tool_success`).
- Agent packs declare which metrics are active via `metrics_custom.json` (and inherit Phoenix base metrics from `configs/phoenix/metrics.json`).
- New metric *types* require a core code change; new metric *instances* are config-only.

## Consequences

- Predictable security and test surface for a public product.
- Domain metrics (e.g. crash analysis format) are custom JSON entries pointing at existing aggregators.
