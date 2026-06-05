# Connect your agent to AgentGate

AgentGate is **agent-agnostic**. Your production agent stays in its own repository; AgentGate reads Phoenix evidence and applies your **AgentPack** policy.

## Three steps

```bash
cp -r configs/agents/_template configs/agents/my_agent
# Edit profile.json, policy_custom.json, metrics_custom.json, suite.json, report_config.json
export AGENTGATE_AGENT_PACK=configs/agents/my_agent
uv run agentgate configs validate --agent-pack configs/agents/my_agent
```

Then emit spans per [`INTEGRATION_CONTRACT.md#trace-contract`](./INTEGRATION_CONTRACT.md#trace-contract) and run:

```bash
uv run agentgate release check --source phoenix --agent-version <candidate> --output-dir artifacts/release/<candidate>
```

## What belongs where

| Layer | Path | You configure |
| --- | --- | --- |
| **Shared base** | `configs/phoenix/` | Hallucination and intent-routing metrics (auto-merged) |
| **Your agent** | `configs/agents/my_agent/` | Tools, roles, dangerous-tool policy, custom metrics, demo seed, report copy |
| **Product UI** | `backend/agentgate/web/templates/` | **Do not edit for your agent** — dashboard text comes from your `report_config.json` |

**Rule:** Company names, stock tickers, release-channel queries, and tool-specific demo stories must live only in **your AgentPack** (and optional `docs/integrations/<your-agent>/`). Do not add them to product HTML or core Python.

## Reference demo (optional)

The default open-box pack is [`configs/agents/stability_ops/`](../integrations/stability_ops/README.md) (v2 BLOCKED → v2.1 APPROVED). It validates the product; replace it with your pack for production use:

```bash
export AGENTGATE_AGENT_PACK=configs/agents/my_agent
```

## Full integration path

- Hub: [`integration/README.md`](./README.md)
- Skill: [`AGENTGATE_INTEGRATION_SKILL.md`](./AGENTGATE_INTEGRATION_SKILL.md)
- Contract: [`INTEGRATION_CONTRACT.md`](./INTEGRATION_CONTRACT.md)
- Pipeline: [`../getting-started/RELEASE_PIPELINE.md`](../getting-started/RELEASE_PIPELINE.md)
