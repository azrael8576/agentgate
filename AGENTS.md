# AgentGate Agent Guide

Rules for AI coding agents working in this repository.

**Domain vocabulary:** [`CONTEXT.md`](CONTEXT.md)  
**Product docs:** [`docs/README.md`](docs/README.md) · [`docs/PRD_PRODUCT.md`](docs/PRD_PRODUCT.md)  
**Connect your agent:** [`docs/integration/CONNECT_YOUR_AGENT.md`](docs/integration/CONNECT_YOUR_AGENT.md) · [`docs/integration/AGENTGATE_INTEGRATION_SKILL.md`](docs/integration/AGENTGATE_INTEGRATION_SKILL.md)  
**Pipeline commands:** [`docs/getting-started/RELEASE_PIPELINE.md`](docs/getting-started/RELEASE_PIPELINE.md)

## What this repo is

AgentGate is the **release authority** layer for AI agents. It blocks unsafe candidate versions before production, especially dangerous capability regressions where the wrong role triggers high-risk tools.

The default reference demo pack is `configs/agents/stability_ops/`; that is not the product boundary. Integrators use `AGENTGATE_AGENT_PACK` with their own pack.

## System boundary (non-negotiable)

Do **not** implement inside AgentGate:

- Google Chat bot behavior
- RAG retrieval or answer generation
- Target-agent tool execution (BigQuery, Crashlytics, etc.)
- A fake production agent runtime or intent router serving users

AgentGate may contain: AgentPacks (`configs/agents/`), Phoenix base (`configs/phoenix/`), seed JSONL, Phoenix query logic, metrics, diagnosis, reports.

**Do not copy production agent code** from external agent repos. Register tools via AgentPack `profile.json` `tool_manifest` only. Do not embed agent-specific queries (stock, release channels, company names) in product HTML or core Python.

Config model and AgentPack layout: [`CONTEXT.md`](CONTEXT.md).

## Release authority rules

- Phoenix MCP is the default evidence source; local JSONL is fallback only.
- BLOCK/APPROVE is **deterministic** from `metrics_summary.json` and effective policy thresholds (Phoenix base + agent custom).
- Gemini explains dangerous sessions only; it does not decide release.
- Runtime metrics come from AgentPack effective config + `metrics_aggregator.py` (fixed aggregators).
- Suite contract names and runtime metric names may differ; runtime BLOCK/APPROVE follows policy thresholds and effective metrics.

## Evidence pipeline (code path)

```text
Phoenix MCP get-spans -> phoenix_normalizer
  -> metrics_aggregator + audit_session_report
  -> DangerousEvidenceClassifier -> capped get-trace
  -> optional GeminiDangerousSessionDiagnoser
  -> decision_engine -> artifact_writer (7 JSON + release_report.html)
```

Key modules:

- `backend/agentgate/release/phoenix_mcp_client.py`
- `backend/agentgate/release/phoenix_evidence_source.py`
- `backend/agentgate/release/dangerous_evidence_classifier.py`
- `backend/agentgate/release/decision_engine.py`
- `backend/agentgate/web/routes_dashboard.py`

## Span contract (do not break)

Production agents must emit spans per [`docs/integration/INTEGRATION_CONTRACT.md#trace-contract`](docs/integration/INTEGRATION_CONTRACT.md#trace-contract):

- `router.intent_classification`
- `answer.static`
- `policy_preflight.<tool>`
- `tool.<tool>`

## Environment

Phoenix (space-scoped collector URL required):

```bash
export PHOENIX_COLLECTOR_ENDPOINT="https://app.phoenix.arize.com/s/<your-space>/v1/traces"
export PHOENIX_API_KEY="..."
export PHOENIX_PROJECT_NAME="agentgate-reference-ops-demo"
```

Optional release-check tuning:

```bash
export AGENTGATE_MAX_DANGEROUS_TRACES="25"
export AGENTGATE_PULL_REVIEWED_SAFE_TRACES="false"
export AGENTGATE_CANDIDATE_VERSIONS="v2,v2.1"
```

Vertex (Gemini diagnosis — use a dedicated GCP project, not the target agent's prod project):

```bash
export GOOGLE_CLOUD_PROJECT="<agentgate-gcp-project>"
export GOOGLE_CLOUD_LOCATION="global"
export GOOGLE_GENAI_USE_VERTEXAI="True"
```

## Development commands

```bash
uv run pytest
uv run agentgate configs validate
uv run agentgate profiles validate --profile configs/agents/stability_ops/profile.json
uv run agentgate suites validate --suite configs/agents/stability_ops/suite.json
uv run agentgate eval sync-dataset
uv run agentgate eval run --agent-version v2.1 --output-dir artifacts/eval/v2.1
uv run agentgate release check --source phoenix --agent-version v2.1 --output-dir artifacts/release/v2.1
uv run uvicorn backend.agentgate.main:app --reload
```

## Sandcastle (autonomous issue loop)

Label GitHub issues with `Sandcastle` (or set `SANDCASTLE_ISSUE_LABEL` in `.sandcastle/.env`).

```bash
cp .sandcastle/.env.example .sandcastle/.env   # GH_TOKEN (gh auth token), optional CODEX_MODEL
npm install
npm run sandcastle:build-image                 # Docker image with Codex CLI
npm run sandcastle                             # Docker + Codex CLI (default)
# npm run sandcastle:host                      # host mode (no Docker)
```

Runs implement → review on the **current branch** unless `SANDCASTLE_BRANCH` is set. Commits use the `RALPH:` prefix.

## Design rule

```text
Production agent code answers operational questions.
Phoenix stores what happened.
AgentGate turns that evidence into an auditable release gate.
```

If a change makes AgentGate answer user questions or run production tools, redesign it as telemetry, evidence fixtures, Phoenix queries, metrics, or reporting instead.
