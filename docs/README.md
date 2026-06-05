# Documentation index

Documents are organized by **reading path**. Start with the path that matches your goal.

## A. Judge path (hackathon default)

For hackathon judges and technical reviewers — understand the product boundary, then inspect the Reference Ops AI demo.

| Step | Document | Purpose |
| --- | --- | --- |
| 1 | [`../README.md`](../README.md) | Repo overview, quickstart, AgentGate vs Phoenix |
| 2 | [`PRD_PRODUCT.md`](./PRD_PRODUCT.md) | Hackathon-scope product PRD and release checklist |
| 3 | [`REFERENCE_WORKFLOW.md`](./REFERENCE_WORKFLOW.md) | Five-step Reference Ops AI demo walkthrough: homepage proof, blocked report, generated release controls, approved-with-warnings follow-up |

```text
README → PRD_PRODUCT → REFERENCE_WORKFLOW
```

Optional supporting material: [`DEMO_CICD.md`](./DEMO_CICD.md), [`getting-started/RELEASE_PIPELINE.md`](./getting-started/RELEASE_PIPELINE.md), [`../examples/artifacts/README.md`](../examples/artifacts/README.md), [`getting-started/DEPLOYMENT.md`](./getting-started/DEPLOYMENT.md).

## B. Connect your own agent

For integrators attaching a production agent via AgentPack.

| Document | Purpose |
| --- | --- |
| [`integration/README.md`](./integration/README.md) | Integration hub and reading order |
| [`integration/CONNECT_YOUR_AGENT.md`](./integration/CONNECT_YOUR_AGENT.md) | Three-step entry |
| [`integration/AGENTGATE_INTEGRATION_SKILL.md`](./integration/AGENTGATE_INTEGRATION_SKILL.md) | End-to-end integration guide |
| [`integration/INTEGRATION_CONTRACT.md`](./integration/INTEGRATION_CONTRACT.md) | Certification tiers and span contract |
| [`integration/AGENTPACK.md`](./integration/AGENTPACK.md) | Suite and policy JSON |
| [`integration/PHOENIX_INTEGRATION.md`](./integration/PHOENIX_INTEGRATION.md) | MCP, normalizer, eval labels |
| [`integration/RELEASE_OUTPUT.md`](./integration/RELEASE_OUTPUT.md) | Audit bundle and Gemini boundaries |

Extended schema and gate rules: [`PRD.md`](./PRD.md) (integrators and auditors).

## C. Reference integration (Reference Ops AI demo pack)

| Document | Purpose |
| --- | --- |
| [`REFERENCE_WORKFLOW.md`](./REFERENCE_WORKFLOW.md) | Demo narrative and CLI |
| [`integrations/stability_ops/README.md`](./integrations/stability_ops/README.md) | Canonical config paths and PII checklist |

Canonical configs: `configs/agents/stability_ops/`.

## D. Maintainers

For contributors and AI coding agents — not required for hackathon demo.

| Document | Purpose |
| --- | --- |
| [`../AGENTS.md`](../AGENTS.md) | Rules for AI agents in this repo |
| [`../CONTEXT.md`](../CONTEXT.md) | Domain vocabulary (AgentPack, EffectiveConfig, …) |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | System shape and modules |
| [`adr/README.md`](./adr/README.md) | Architecture decision records |
| [`PRD.md`](./PRD.md) | Extended technical specification |
