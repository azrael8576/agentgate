# Reference Ops AI demo integration

**Config index** — canonical paths and PII checklist for the default demo pack.  
**Demo script** — spoken five-step judge workflow: [`../../REFERENCE_WORKFLOW.md`](../../REFERENCE_WORKFLOW.md)

Product integrators should start at [`../../integration/CONNECT_YOUR_AGENT.md`](../../integration/CONNECT_YOUR_AGENT.md).

## What this reference proves

1. A production-style agent emits OpenInference / Phoenix traces.
2. AgentGate validates profile and suite contracts.
3. AgentGate reads Phoenix evidence, applies runtime policy thresholds, and writes the audit bundle.
4. Reviewers inspect `APPROVED` / `BLOCKED` through JSON artifacts and `release_report.html`.

| Resource | Purpose |
| --- | --- |
| [`../../REFERENCE_WORKFLOW.md`](../../REFERENCE_WORKFLOW.md) | Five-step reference workflow (homepage proof → v2 BLOCKED → generated release controls → v2.1 APPROVED with warnings) |
| [`../../getting-started/RELEASE_PIPELINE.md`](../../getting-started/RELEASE_PIPELINE.md) | Phoenix pipeline commands |
| [`../../integration/AGENTGATE_INTEGRATION_SKILL.md`](../../integration/AGENTGATE_INTEGRATION_SKILL.md) | Integrate another production agent |

## Canonical configs

- `configs/agents/stability_ops/profile.json`
- `configs/agents/stability_ops/suite.json`
- `configs/agents/stability_ops/policy_custom.json`
- `configs/agents/stability_ops/seed/*.jsonl`

## Public-release PII checklist

Before publishing this repository, verify the reference pack contains **no real company or customer data**:

| Check | Location | Action |
| --- | --- | --- |
| Real company / product branding | `profile.json`, `intents.json`, `report_config.json`, seed JSONL | Use fictional names (e.g. Reference Ops AI, Acme App) |
| Real stock tickers or investment prompts | `intents.json`, `demo_cases.json`, seed spans | Use synthetic tickers (e.g. `DEMO`) and neutral queries |
| Real release/version answers | `demo_cases.json`, static answer spans | Use placeholder version strings only |
| Production Chat space / user IDs | seed `user.id`, `request.channel` | Use synthetic IDs (`u-demo-001`, etc.) |
| Real customer, payment, or incident IDs from production | `demo_cases.json` queries | Use synthetic IDs (`PAY-1001`, `VIP-PAY-4004`, `CHECKOUT-3003`) |
| External repo URLs with internal hostnames | docs, `.env.example` | Remove or generalize |
| Phoenix project name | `profile.json` `trace_backend.project_name` | Use a public-safe project slug |
| Curated HTML under `examples/artifacts/` | Regenerate after seed refresh | Old bundles may embed prior copy |

Regenerate seeds after edits:

```bash
uv run agentgate demo seed-v2 --output configs/agents/stability_ops/seed/v2_evidence.jsonl
uv run agentgate demo seed-v21 --output configs/agents/stability_ops/seed/v21_evidence.jsonl
```
