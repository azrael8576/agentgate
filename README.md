# AgentGate

AgentGate blocks unsafe AI agent versions before production.

**Release Authority for AI Agents** — not a Phoenix dashboard clone.

## What it is

A telemetry-driven release gate for production AI agents with dangerous tools. AgentGate reads Phoenix evidence, applies AgentPack-defined company policy and release-safety metrics, optionally explains high-risk sessions with Gemini, and writes auditable release decision artifacts.

AgentGate is not a production agent. It does not own chat UX, RAG, or target-agent tool execution.

## AgentGate vs Phoenix

Phoenix is the evidence backend: traces, spans, eval labels, annotations, and observability data.

AgentGate adds the release authority layer on top: AgentPack-defined tool risk, company-specific policy thresholds, custom release metrics, deterministic `BLOCKED` / `APPROVED` decisions, and audit-ready reports.

## Why it exists

The core risk is **dangerous capability regression**: a prompt, routing, or policy bug lets the wrong role or route trigger high-risk tools that should stay gated. AgentGate turns trace-backed evidence into an `APPROVED` or `BLOCKED` decision with a reproducible audit package.

## How it works

```text
Production agent -> OpenInference spans -> Phoenix
Phoenix -> AgentGate (metrics, dangerous sessions, gate, audit bundle)
Optional: Gemini diagnosis on selected dangerous sessions only (non-authoritative)
```

**Connect your agent:** [`docs/integration/CONNECT_YOUR_AGENT.md`](docs/integration/CONNECT_YOUR_AGENT.md) — copy `configs/agents/_template`, set `AGENTGATE_AGENT_PACK` or pass `--agent-pack`, validate, release check.

The bundled **Reference Ops AI demo** (v2 BLOCKED with generated release controls → v2.1 APPROVED with warnings) lives in the legacy path `configs/agents/stability_ops/` — see [`docs/REFERENCE_WORKFLOW.md`](docs/REFERENCE_WORKFLOW.md). That pack is optional; production agents stay in their own repos.

## Configuration model

AgentGate uses a **two-layer config** (see [`CONTEXT.md`](CONTEXT.md)):

| Layer | Path | Purpose |
| --- | --- | --- |
| **Phoenix base** | `configs/phoenix/` | Shared metrics (hallucination, routing) — all agents get this automatically |
| **Agent custom** | `configs/agents/<agent>/` | Per-agent dimensions, policy, tools, demo seed |

Default **Reference Ops AI demo** pack: `configs/agents/stability_ops/` (legacy path, open-box story). Override with your pack:

```bash
export AGENTGATE_AGENT_PACK=configs/agents/my_agent
```

**Production agent code stays in its own repo.** AgentGate only registers tools via `profile.json` `tool_manifest` and reads Phoenix/seed evidence.

New integrations should copy `configs/agents/_template/`.

## Quickstart

**Requirements:** Python 3.11+, [uv](https://github.com/astral-sh/uv)

```bash
uv sync
uv run pytest
uv run agentgate --help
```

Phoenix-backed release check (set Phoenix env vars first — see `.env.example`):

```bash
uv run agentgate release check --source phoenix --agent-version v2.1 \
  --diagnosis-mode gemini --output-dir artifacts/release/v2.1
```

Local fixture fallback without Phoenix (uses the default Reference Ops AI demo AgentPack):

```bash
uv run agentgate configs validate
uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v2_evidence.jsonl \
  --output-dir artifacts/release/reference-v2
uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v21_evidence.jsonl \
  --output-dir artifacts/release/reference-v21
```

Legacy seed output path still works: `uv run agentgate demo seed-v21`.

Dashboard:

```bash
uv run uvicorn backend.agentgate.main:app --reload
```

Open http://127.0.0.1:8000/ — see [`docs/getting-started/DEPLOYMENT.md`](docs/getting-started/DEPLOYMENT.md).

Full pipeline: [`docs/getting-started/RELEASE_PIPELINE.md`](docs/getting-started/RELEASE_PIPELINE.md).

## Core commands

```bash
uv run agentgate configs validate
uv run agentgate release check --source phoenix --agent-version v2.1 --output-dir artifacts/release/v2.1
uv run agentgate eval run --agent-version v2.1 --output-dir artifacts/eval/v2.1
uv run uvicorn backend.agentgate.main:app --reload
```

## Documentation

### Judge path (hackathon)

[`README.md`](README.md) → [`docs/PRD_PRODUCT.md`](docs/PRD_PRODUCT.md) → [`docs/REFERENCE_WORKFLOW.md`](docs/REFERENCE_WORKFLOW.md)

### Connect your agent

[`docs/integration/CONNECT_YOUR_AGENT.md`](docs/integration/CONNECT_YOUR_AGENT.md) → [`docs/integration/README.md`](docs/integration/README.md)

### Maintainers

[`AGENTS.md`](AGENTS.md) · [`CONTEXT.md`](CONTEXT.md) · [`docs/adr/`](docs/adr/) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

Full index: [`docs/README.md`](docs/README.md)

## Current release status

- Phoenix MCP evidence path (primary) and local JSONL fallback
- Deterministic BLOCK/APPROVE with policy thresholds
- Controlled eval suite + Phoenix eval automation
- Audit bundle: 7 JSON artifacts + `release_report.html`
- Release Safety Dashboard (`/`, `/run`, `/reports/latest`)
- Reference workflow: homepage release intervention, v2 BLOCKED with generated release controls, v2.1 APPROVED with warnings

Sample artifacts: [`examples/artifacts/`](examples/artifacts/).
