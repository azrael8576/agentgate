# Release Pipeline

End-to-end commands for Phoenix-sourced release checks.

**Hackathon demo script:** [`../REFERENCE_WORKFLOW.md`](../REFERENCE_WORKFLOW.md) · **Integrate your agent:** [`../integration/README.md`](../integration/README.md)

## System boundary

```text
<your-production-agent-repo> (external) -> OpenInference spans
Phoenix / Arize                       -> traces, annotations
AgentGate (this repo)                 -> gate + audit bundle
```

## Prerequisites

```bash
export PHOENIX_COLLECTOR_ENDPOINT="https://app.phoenix.arize.com/s/<your-space>/v1/traces"
export PHOENIX_BASE_URL="https://app.phoenix.arize.com/s/<your-space>"
export PHOENIX_API_KEY="..."
export PHOENIX_PROJECT_NAME="agentgate-reference-ops-demo"
export GOOGLE_CLOUD_PROJECT="<your-gcp-project>"
export GOOGLE_CLOUD_LOCATION="global"
export GOOGLE_GENAI_USE_VERTEXAI="True"
```

Optional:

```bash
export AGENTGATE_MAX_DANGEROUS_TRACES="25"
export AGENTGATE_PULL_REVIEWED_SAFE_TRACES="false"
export AGENTGATE_CANDIDATE_VERSION="v2"
export AGENTGATE_CANDIDATE_VERSIONS="v2,v2.1"
```

## Standard pipeline (Phoenix)

Run from repository root:

```bash
# 1. Seed local replay fixtures (regression / fallback).
# Current CLI fixture command naming still uses `demo`.
uv run agentgate demo seed-v2 --output configs/agents/stability_ops/seed/v2_evidence.jsonl
uv run agentgate demo seed-v21 --output configs/agents/stability_ops/seed/v21_evidence.jsonl

# 2. Replay spans into Phoenix (if traces were cleared)
uv run agentgate telemetry replay --evidence configs/agents/stability_ops/seed/v2_evidence.jsonl
uv run agentgate telemetry replay --evidence configs/agents/stability_ops/seed/v21_evidence.jsonl

# 3. Eval automation (Phoenix annotations)
uv run agentgate eval sync-dataset
uv run agentgate eval run --agent-version v2 --output-dir artifacts/eval/v2
uv run agentgate eval run --agent-version v2.1 --output-dir artifacts/eval/v2.1

# 4. Release gate (deterministic BLOCK/APPROVE)
uv run agentgate release check --source phoenix --agent-version v2 \
  --diagnosis-mode gemini --output-dir artifacts/release/v2
uv run agentgate release check --source phoenix --agent-version v2.1 \
  --diagnosis-mode gemini --output-dir artifacts/release/v21
```

Reference workflow outcome: **v2 → BLOCKED**, **v2.1 → APPROVED**.

Controlled eval execution in the target agent repo (`release_eval_runner`) is the preferred path for a real integration. Seed replay is a local reference fixture path for regression testing, fallback execution, and offline review.

### Agentic review CLI behavior

`agentgate release check` exposes `--agentic-review/--no-agentic-review`.

- Phoenix runs default to agentic review enabled.
- Local/offline runs default to agentic review disabled.
- Use `--no-agentic-review` on Phoenix when you want the deterministic gate only.
- Use `--agentic-review` on local/offline runs when you want the informational review packet from replayed evidence.

The gate boundary does not move when agentic review is enabled. Pattern Finder and Dataset Planner investigate the release slice and write informational artifacts, but `metrics_summary.json` plus policy thresholds still decide `APPROVED` or `BLOCKED`.

APPROVED runs can still finish with no agent-review action or warning-only findings. That means the candidate cleared blocker controls, while the review artifacts either found nothing to escalate or surfaced non-blocking follow-up for humans.

## Local fixture fallback (no Phoenix)

Local fixture fallback using the current CLI fixture command:

```bash
uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v2_evidence.jsonl \
  --output-dir artifacts/release/reference-v2
uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v21_evidence.jsonl \
  --output-dir artifacts/release/reference-v21
```

## Contract validation

```bash
uv run agentgate profiles validate --profile configs/agents/stability_ops/profile.json
uv run agentgate suites validate --suite configs/agents/stability_ops/suite.json
```

## Dashboard

```bash
set -a && source .env && set +a
uv run uvicorn backend.agentgate.main:app --host 127.0.0.1 --port 8000
```

| Route | Purpose |
| --- | --- |
| `/` | Landing |
| `/run` | Release check console (candidate version selector) |
| `/reports/latest` | Certificate + Evidence Dossier |

Trigger via API:

```bash
curl -X POST http://127.0.0.1:8000/api/agentgate/release-check \
  -H 'Content-Type: application/json' \
  -d '{"agent_version":"v2.1"}'
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `hallucination_rate not_available` | Run `agentgate eval run`; confirm Phoenix annotations |
| No spans for candidate version | Replay seed or run eval runner; verify `agent.version` |
| MCP span id vs REST mismatch | `release/phoenix_span_identity.py` |
| Eval REST parser empty | `evals/annotation_parser.py` |
| MCP auth errors | Space-scoped collector URL + API key |

Details: [`../integration/PHOENIX_INTEGRATION.md`](../integration/PHOENIX_INTEGRATION.md).

## Key paths

| Area | Path |
| --- | --- |
| AgentPack | `configs/agents/stability_ops/` |
| Release policy | `configs/agents/stability_ops/policy_custom.json` |
| Agent profile | `configs/agents/stability_ops/profile.json` |
| Eval suite | `configs/agents/stability_ops/suite.json` |
| Metrics | `backend/agentgate/release/metrics_aggregator.py` |
| Gate | `backend/agentgate/release/decision_engine.py` |
| Artifacts | `backend/agentgate/release/artifact_writer.py` |
