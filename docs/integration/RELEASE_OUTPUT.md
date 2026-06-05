# Release Output

Every `agentgate release check` run writes a reproducible audit bundle under `--output-dir`, optionally with Gemini explanation on dangerous sessions.

Gemini does **not** decide release; BLOCK/APPROVE remains deterministic from `metrics_summary.json` and effective policy thresholds.

## Audit artifacts

| File | Role |
| --- | --- |
| `release_decision.json` | Deterministic `APPROVED` / `BLOCKED`, diagnosis metadata, evidence source |
| `metrics_summary.json` | Metrics with provenance (numerator, denominator, grader_ids, sample_tier) |
| `dangerous_sessions.json` | Selected high-risk sessions + critical findings |
| `regression_gates.json` | Suggested regression tasks from dangerous findings |
| `agent_profile.json` | Snapshot of agent contract config |
| `eval_suite.json` | Snapshot of suite contract config |
| `audit_manifest.json` | SHA-256 hashes + reproducibility recipe |
| `release_report.html` | Offline Certificate + Evidence Dossier |

The dashboard report and standalone `release_report.html` share the same audit structure. The HTML artifact is not a Phoenix export; it is AgentGate's offline release review package.

## Evidence source metadata

`release_decision.json` records:

```text
evidence_source.type = local_jsonl | phoenix_mcp | phoenix_mcp_spans_json
evidence_source.query
evidence_source.dangerous_trace_ids
phoenix_dangerous_traces   # full traces for audit only
```

## Reproducibility

Reviewers should be able to reproduce BLOCK/APPROVE from saved `metrics_summary.json` and policy thresholds without re-running Gemini or LLM judges.

`audit_manifest.json` hashes each artifact for integrity verification.

## Dashboard access

When `AGENTGATE_LATEST_ARTIFACT_DIR` points to a run directory:

- `/reports/latest` — server-rendered report
- `/artifacts/*` — allowlisted JSON + `release_report.html`

## Writer implementation

- `backend/agentgate/release/artifact_writer.py`
- Report templates: `backend/agentgate/web/templates/`

---

## Gemini diagnosis (optional)

### Role in the pipeline

```text
Phoenix spans -> metrics + DangerousEvidenceClassifier
              -> dangerous_session_summaries (structured)
              -> GeminiDangerousSessionDiagnoser (optional)
              -> release_decision.json diagnosis_metadata
              -> deterministic decide_release() unchanged
```

### What Gemini receives

- Structured `dangerous_session_summaries` built from `critical_findings` and selected evidence spans.
- Not full trace dumps from `phoenix_dangerous_traces` (those stay in artifacts for human audit only).

### What Gemini does not do

- Compute release metrics
- Override `APPROVED` / `BLOCKED`
- Decide permissions or policy
- Replace deterministic graders for gate metrics

### CLI usage

```bash
uv run agentgate release check --source phoenix \
  --agent-version v2 \
  --diagnosis-mode gemini \
  --output-dir artifacts/release/v2-gemini
```

Without Vertex credentials, AgentGate falls back to `DeterministicDiagnoserAdapter`.

### Configuration

```bash
export GOOGLE_CLOUD_PROJECT="<dedicated-gcp-project>"
export GOOGLE_CLOUD_LOCATION="global"
export GOOGLE_GENAI_USE_VERTEXAI="True"
export AGENTGATE_GEMINI_MODEL="gemini-flash-latest"
```

Use a dedicated GCP project for AgentGate Vertex calls, separate from the target agent's production runtime project.

If Vertex credentials are unavailable or quota-limited, release checks should still complete through the deterministic fallback diagnoser. Diagnosis quality may degrade, but release authority does not move from deterministic metrics to Gemini.

### ADK wrapper

`backend/agentgate/release/adk_release_evidence_agent.py` exposes the same release pipeline through a thin Google ADK agent wrapper. ADK is optional; CLI release checks do not require launching the ADK runtime.

### Implementation

| Module | Role |
| --- | --- |
| `release/gemini_diagnoser.py` | Vertex Gemini structured diagnosis |
| `release/diagnosis.py` | Deterministic fallback diagnoser |
| `release/release_check.py` | Wires diagnosis before artifact write |

Evidence suitable for Gemini: high-risk session summaries with finding types, policy context, and redacted tool outcomes. Do not send raw secrets, full SQL, or entire chat logs.
