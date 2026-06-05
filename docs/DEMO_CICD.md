# Demo CI/CD recording guide

Record the **Reference Ops AI demo** release gate in GitHub Actions: v2 BLOCKED (deploy skipped) and v2.1 APPROVED (deploy runs). No demo agent source code, Phoenix secrets, or Cloud Run required.

**Related:** five-step judge narrative [`REFERENCE_WORKFLOW.md`](./REFERENCE_WORKFLOW.md) · workflow [`.github/workflows/release-gate-demo.yml`](../.github/workflows/release-gate-demo.yml)

## What this proves

```text
Reference Ops AI (external agent repo)
  -> controlled eval emits Phoenix-compatible spans
AgentGate (this repo)
  -> release check on seed evidence -> APPROVED / BLOCKED + audit bundle
GitHub Actions
  -> gate job fails on BLOCKED -> deploy job skipped
  -> artifacts: 7 JSON + release_report.html
```

AgentGate does **not** run the production agent in CI. Seed JSONL under `configs/agents/stability_ops/seed/` stands in for Phoenix evidence after controlled eval.

## Before recording

1. Push this repo to GitHub (workflow must exist on the default branch).
2. Confirm local smoke test:

```bash
uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v2_evidence.jsonl \
  --output-dir /tmp/release-v2 \
  --agent-pack configs/agents/stability_ops \
  --fail-on-block
# expect exit 1

uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v21_evidence.jsonl \
  --output-dir /tmp/release-v21 \
  --agent-pack configs/agents/stability_ops \
  --fail-on-block
# expect exit 0
```

## Act 1 — v2 BLOCKED, CD blocked

### Narration

> Reference Ops AI v2 finished controlled eval. The release pipeline runs AgentGate on trace-backed evidence. A low-privilege role can still trigger engineering-only VIP payment incident investigation — AgentGate issues **BLOCKED**. The deploy job does not run. The audit bundle includes generated release controls backed by `regression_gates.json`.

### GitHub UI steps

1. **Actions** → **Release Gate Demo** → **Run workflow**
2. **candidate_version:** `v2`
3. **block_cd:** `true`
4. Run workflow
5. Show **`release-gate`** job **failed** (red)
6. Show **`deploy-stability-ops`** job **skipped** (grey) — `needs: release-gate`
7. Open **Artifacts** → download **`release-audit-v2`**
8. Open **`release_decision.json`** → `"decision": "BLOCKED"`
9. Open **`regression_gates.json`** → generated release controls for the next candidate
10. Optional: open **`release_report.html`** or local dashboard with `examples/artifacts/reference-v2/`

### Key artifact fields

| File | Show |
| --- | --- |
| `release_decision.json` | `decision`, `decision_reasons`, `decision_basis` |
| `metrics_summary.json` | blocker metrics over threshold |
| `dangerous_sessions.json` | critical findings + trace IDs |
| `regression_gates.json` | generated release controls from blocker evidence |
| `audit_manifest.json` | SHA-256 hashes |

## Act 3 — v2.1 APPROVED with warnings, CD continues

### Narration

> Same pipeline, v2.1 with blocker regressions fixed. Gate-bound blocker metrics pass. AgentGate issues **APPROVED** even though non-blocking warning controls still fail — approved, not perfect — and deploy proceeds.

### GitHub UI steps

1. **Run workflow** again with **candidate_version:** `v2.1`, **block_cd:** `true`
2. **`release-gate`** **succeeded** (green)
3. **`deploy-stability-ops`** **succeeded** (green)
4. Download **`release-audit-v2.1`**
5. Open **`release_decision.json`** → `"decision": "APPROVED"`, empty blocker `decision_reasons`
6. Open **`metrics_summary.json`** → warning-only failures such as `technical_tool_success_rate` and `crash_analysis_format_compliance`
7. Optional: open **`release_report.html`** → **Approved, not perfect.**

## Advisory mode (optional)

Set **block_cd:** `false` to always pass the gate job while still uploading artifacts — useful for dry runs or human review without blocking deploy.

## Artifact bundle (every run)

| File | Role |
| --- | --- |
| `release_decision.json` | Deterministic APPROVED / BLOCKED |
| `metrics_summary.json` | Metrics + thresholds + provenance |
| `dangerous_sessions.json` | High-risk sessions |
| `regression_gates.json` | Suggested regression tasks |
| `agent_profile.json` | Agent contract snapshot |
| `eval_suite.json` | Suite contract snapshot |
| `audit_manifest.json` | Integrity hashes |
| `release_report.html` | Offline Certificate + Evidence Dossier |

Reference copies: [`examples/artifacts/reference-v2/`](../examples/artifacts/reference-v2/), [`reference-v21/`](../examples/artifacts/reference-v21/).

## External agent repo integration (after demo)

When the production agent lives in another repository, use the composite action [`.github/actions/agentgate-gate/`](../.github/actions/agentgate-gate/) or checkout this repo and run the same CLI. See [`integration/CONNECT_YOUR_AGENT.md`](./integration/CONNECT_YOUR_AGENT.md).
