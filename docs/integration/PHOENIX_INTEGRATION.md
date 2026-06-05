# Phoenix Integration

How AgentGate reads Phoenix evidence, runs eval automation, and normalizes spans for release checks.

## Architecture

```text
Target agent -> phoenix-otel -> Phoenix (traces + annotations)
AgentGate:
  eval run     -> writes annotations via Phoenix evaluators
  release check -> Phoenix MCP get-spans / get-trace -> normalize -> metrics -> gate
```

AgentGate does not call Phoenix REST directly for release checks; it uses the official `@arizeai/phoenix-mcp` server (`npx -y @arizeai/phoenix-mcp@latest`).

## Environment

```bash
export PHOENIX_COLLECTOR_ENDPOINT="https://app.phoenix.arize.com/s/<your-space>/v1/traces"
export PHOENIX_BASE_URL="https://app.phoenix.arize.com/s/<your-space>"
export PHOENIX_API_KEY="..."
export PHOENIX_PROJECT_NAME="<your-project>"
```

MCP base URL resolution:

```text
PHOENIX_HOST or PHOENIX_BASE_URL
  else derived from PHOENIX_COLLECTOR_ENDPOINT (strip /v1/traces, keep /s/<space>)
```

Wrong collector URL (missing `/s/<space>`) typically causes `401 Unauthorized` from MCP.

## MCP tools

### `get-spans`

- Used for all release metric computation.
- Filters by supported span names (see [`INTEGRATION_CONTRACT.md#trace-contract`](./INTEGRATION_CONTRACT.md#trace-contract)).
- Post-filters by `agent.version` when `--agent-version` is set.
- Paginates with MCP cursor.

### `get-trace`

- Called only after dangerous session selection.
- Capped by `AGENTGATE_MAX_DANGEROUS_TRACES` (default 25).
- `AGENTGATE_PULL_REVIEWED_SAFE_TRACES=false` by default (critical findings only).

Full traces are stored in `release_decision.json` for audit. Gemini receives `dangerous_session_summaries` only, not full trace dumps.

## Normalization

`backend/agentgate/release/phoenix_normalizer.py` maps Phoenix span attributes (flat dict or OTEL `{key,value}` lists) into AgentGate evidence records.

Supported span names are allowlisted in `phoenix_evidence_source.py` — extend the list when adding new tools to your agent contract.

Missing subjective eval labels become `not_available` metrics, not synthetic failures.

## Eval automation

```bash
uv run agentgate eval sync-dataset
uv run agentgate eval run --agent-version v2.1 --output-dir artifacts/eval/v2.1
```

| `metric_source` | Meaning |
| --- | --- |
| `phoenix_eval_automation` | Phoenix eval job wrote annotations |
| `span_aggregate` | Computed from production spans |
| `seed_fallback` | Local JSONL replay |
| `not_available` | Required eval inputs missing |

For first-time integrations, verify one trace per required span type in Phoenix before relying on eval automation. Missing router or policy preflight spans usually indicate target-agent instrumentation gaps, not AgentGate grading failures.

### Span ID alignment

Phoenix MCP `id` is base64 internal; REST annotations require OTEL hex `context.span_id`. See `backend/agentgate/release/phoenix_span_identity.py`.

### REST annotation parser

Annotation REST dataframe uses flat columns (`annotation_name`, `result.label`). See `backend/agentgate/evals/annotation_parser.py`.

### Eval tuning

```bash
export AGENTGATE_EVAL_LOCAL_SUMMARY_FALLBACK=false   # do not mask REST failures
export GOOGLE_CLOUD_PROJECT=<project>              # Vertex for eval LLM judges
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_GENAI_USE_VERTEXAI=True
```

## Release check commands

```bash
# Primary
uv run agentgate release check --source phoenix \
  --project-identifier <phoenix-project> \
  --agent-version v2.1 \
  --last-n-minutes 1440 \
  --output-dir artifacts/release/phoenix-v21

# Offline spans JSON (CI / debugging)
uv run agentgate release check-phoenix \
  --spans-json artifacts/phoenix/spans.json \
  --output-dir artifacts/release/phoenix
```

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `401` from MCP | Space-scoped `PHOENIX_COLLECTOR_ENDPOINT`, valid `PHOENIX_API_KEY` |
| Zero matched spans | Replay seed, run target agent, widen lookback, omit `--agent-version` to debug |
| `hallucination_rate not_available` | Run `agentgate eval run`; confirm annotations in Phoenix |
| `eval_label_count=0` | Span ID fix deployed; `AGENTGATE_EVAL_LOCAL_SUMMARY_FALLBACK=false` |
| Eval LLM 429 | Vertex quota; eval retry/cooldown in eval runner |

## Key modules

| Module | Role |
| --- | --- |
| `release/phoenix_mcp_client.py` | MCP stdio client |
| `release/phoenix_evidence_source.py` | get-spans query |
| `release/phoenix_normalizer.py` | Span → evidence records |
| `release/dangerous_evidence_classifier.py` | Critical findings + trace priority |
| `release/phoenix_span_identity.py` | MCP id ↔ OTEL span id |
| `evals/annotation_parser.py` | REST annotation parsing |
