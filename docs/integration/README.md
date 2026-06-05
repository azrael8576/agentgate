# Integration docs

> **Hackathon / demo?** Start with [`../getting-started/RELEASE_PIPELINE.md`](../getting-started/RELEASE_PIPELINE.md) and [`../REFERENCE_WORKFLOW.md`](../REFERENCE_WORKFLOW.md) — you do not need this folder to run the reference workflow.

Connect your own production agent to AgentGate release checks.

## Reading order

```text
CONNECT_YOUR_AGENT.md
  -> AGENTGATE_INTEGRATION_SKILL.md (step-by-step)
  -> INTEGRATION_CONTRACT.md (spans + certification)
  -> AGENTPACK.md (suite.json + policy_custom.json)
  -> PHOENIX_INTEGRATION.md (evidence source)
  -> RELEASE_OUTPUT.md (audit bundle + Gemini boundaries)
  -> ../getting-started/RELEASE_PIPELINE.md (commands)
```

## Documents

| Document | Purpose |
| --- | --- |
| [`CONNECT_YOUR_AGENT.md`](./CONNECT_YOUR_AGENT.md) | Three-step entry — copy AgentPack, validate, release check |
| [`AGENTGATE_INTEGRATION_SKILL.md`](./AGENTGATE_INTEGRATION_SKILL.md) | End-to-end integration guide for engineers and AI agents |
| [`INTEGRATION_CONTRACT.md`](./INTEGRATION_CONTRACT.md) | Certification tiers, trace requirements, [span schema](./INTEGRATION_CONTRACT.md#trace-contract) |
| [`AGENTPACK.md`](./AGENTPACK.md) | Eval suite and release policy JSON in your pack |
| [`PHOENIX_INTEGRATION.md`](./PHOENIX_INTEGRATION.md) | MCP queries, normalizer, eval labels |
| [`RELEASE_OUTPUT.md`](./RELEASE_OUTPUT.md) | Audit artifacts and optional Gemini diagnosis |
