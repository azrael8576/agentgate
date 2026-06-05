# Architecture Decision Records

Maintainer reference — links domain terms in [`CONTEXT.md`](../../CONTEXT.md) to accepted design decisions.

| ADR | Status | Domain term | Decision |
| --- | --- | --- | --- |
| [0001](./0001-two-layer-config.md) | Accepted | PhoenixBase, AgentCustom, EffectiveConfig | Flat merge of shared Phoenix config + per-agent custom JSON; no inheritance chains |
| [0002](./0002-default-demo-pack.md) | Accepted | DefaultDemoPack | `configs/agents/stability_ops` is config default, not core Python hardcode |
| [0003](./0003-fixed-metric-catalog.md) | Accepted | Fixed aggregators | Runtime metrics from fixed Python aggregators + JSON selection, not user-supplied code |
| [0004](./0004-report-config-injection.md) | Accepted | ReportConfig | Single HTML template; agent copy from `report_config.json` |
| [0005](./0005-external-agent-repos.md) | Accepted | Repository boundary | Production agent code stays external; register tools via AgentPack only |
