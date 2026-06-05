# AgentGate Reference Workflow

> **Demo script** — judge-facing walkthrough for the Reference Ops AI demo integration.
> Product story: [`PRD_PRODUCT.md`](./PRD_PRODUCT.md) §0–§4 · Config paths: [`integrations/stability_ops/README.md`](./integrations/stability_ops/README.md)
> Run commands: [`getting-started/RELEASE_PIPELINE.md`](./getting-started/RELEASE_PIPELINE.md)

## One-liner

AgentGate blocks unsafe AI agent versions before production, then turns blocked failures into **future release controls** backed by **`regression_gates.json`**.

## Reference Workflow Scope

This reference workflow validates one production-style integration: **Reference Ops AI**. AgentGate as a product supports any agent that meets the integration contract; this walkthrough covers one validated example.

AgentGate does not run the production agent. The target agent emits OpenInference/Phoenix traces. Phoenix stores the evidence. AgentGate validates suite and profile **contracts**, computes deterministic release guardrails over that evidence, writes an audit bundle, and issues the release decision.

## What AgentGate Is

```text
Phoenix / Arize
  -> evidence backend: traces, spans, annotations, datasets

AgentGate
  -> release authority: suite, grader, metric provenance, decision, audit bundle
```

AgentGate is not a Phoenix dashboard clone. The dashboard answers "what happened?" AgentGate answers "can this candidate version ship?"

## Demo curve

Use this spoken arc when presenting the bundled reference intervention:

```text
Danger
  -> Caught in controlled release evidence
  -> Blocked before production
  -> Converted into future release controls
  -> Verified on the follow-up candidate
  -> Approved, not perfect
```

**Unsafe ≠ imperfect.** Blocker controls must pass before ship. Non-blocking warning variance can remain visible on an approved candidate.

## Controlled vs Observed

| Mode | Source | Release impact |
| --- | --- | --- |
| `controlled` | Known eval suite intentionally run against a candidate version | Can APPROVE or BLOCK in the current release |
| `observed` | Production, shadow, or ad hoc traces | WARNING, triage, or recommended regression task only |

Only controlled evidence can block a release in the current release.

## Five-Step Judge Demo Journey

Start the local dashboard:

```bash
uv run uvicorn backend.agentgate.main:app --reload
```

Open http://127.0.0.1:8000/ and follow the implemented product path below. Fixed offline bundles live in `examples/artifacts/reference-v2/` (BLOCKED) and `examples/artifacts/reference-v21/` (APPROVED with warnings).

### Step 1: Homepage proves release intervention

**Say:** "AgentGate stopped a dangerous AI agent release before production. The homepage proof is fixed to the bundled reference intervention, not whichever latest run happened most recently."

**Show on `/`:**
- **Featured release intervention** card for Reference Ops AI **v2** → `BLOCKED`
- Dangerous trace count and **Generated release controls** count
- **Loop-closing follow-up** card for **v2.1** → `APPROVED` with non-blocking variance still under review

The first viewport still separates Phoenix (evidence backend) from AgentGate (release authority).

### Step 2: Run Check shows the release-control journey

**Say:** "Release check is deterministic. The Run Check page walks the same authority path the CLI uses."

**Show on `/run`:**
- Step list ending with **Generate future release controls** and **Write ship / no-ship decision**
- Version selector for bundled reference candidates when present
- Saved-run summary that names BLOCKED + generated controls, or APPROVED with warning variance

### Step 3: v2 BLOCKED report is the proof moment

**Say:** "Reference Ops AI v2 improves coverage, but a low-privilege role can still trigger engineering-only VIP payment incident investigation. AgentGate reads controlled evidence, not the live agent, and issues BLOCKED."

**Show on the v2 report (`/reports/latest` after selecting v2, or open `examples/artifacts/reference-v2/release_report.html`):**
- Final verdict: `BLOCKED`
- Blocker metrics: `unauthorized_dangerous_tool_attempt_rate`, `dangerous_tool_policy_violation_rate`
- `dangerous_sessions.json` findings with trace IDs
- **Future release controls** section with generated controls from blocker evidence

Release decisions come from gate-bound metrics and saved artifacts, not from Gemini alone.

### Step 4: Generated release controls are backed by regression gates

**Say:** "Blocked failures do not disappear after the decision. AgentGate converts them into future release controls backed by regression gates."

**Show:**
- Report copy: **Generated release controls** and bridge note — `regression_gates.json is the technical artifact backing generated release controls.`
- `regression_gates.json` entries such as `non_developer_must_not_run_deep_investigation`
- Each control lists expected behavior, required fix, trigger, and source evidence IDs

Public product language is **release controls**. The technical artifact contract remains **`regression_gates.json`**.

### Step 5: v2.1 closes the loop — approved, not perfect

**Say:** "Same reference path, fixed blocker regressions. Gate-bound blocker metrics pass. AgentGate issues APPROVED even though non-blocking warning controls still fail."

**Show on the v2.1 report:**
- Final brief: **Approved, not perfect.**
- `decision: APPROVED` with empty blocker `decision_reasons`
- **Failed, non-blocking controls** — for example `technical_tool_success_rate` and `crash_analysis_format_compliance` below threshold
- Side-by-side with v2 BLOCKED on the homepage or via two artifact dirs

v2.1 proves **Unsafe ≠ Imperfect**: the candidate is safe enough to ship, not statistically perfect.

## Reproducible audit bundle

**Say:** "The audit bundle is the release authority artifact. Reviewers can verify BLOCKED/APPROVED from JSON without re-running Gemini."

Every release check writes:

- `release_decision.json`
- `metrics_summary.json`
- `dangerous_sessions.json`
- `regression_gates.json`
- `agent_profile.json`
- `eval_suite.json`
- `audit_manifest.json`
- `release_report.html`

Open `audit_manifest.json`:
- SHA-256 hashes per artifact
- `reproducibility_recipe` — recompute from gate-bound metrics, do not rerun Gemini
- `eval_suite.json` is a **declared contract snapshot**, not proof that AgentGate ran every task

**Optional deep dive:** Download `release_report.html` (Certificate + Dossier sections).

## CLI Commands

```bash
agentgate profiles validate --profile configs/agents/stability_ops/profile.json
agentgate suites validate --suite configs/agents/stability_ops/suite.json
agentgate gate check --suite configs/agents/stability_ops/suite.json --agent-version v2

# Current CLI fixture command naming still uses `demo`.
agentgate demo seed-v2 --output artifacts/seed/seed_v2_evidence.jsonl
agentgate release check --source local \
  --evidence artifacts/seed/seed_v2_evidence.jsonl \
  --output-dir artifacts/release/reference-v2 \
  --agent-pack configs/agents/stability_ops

agentgate demo seed-v21 --output artifacts/seed/seed_v21_evidence.jsonl
agentgate release check --source local \
  --evidence artifacts/seed/seed_v21_evidence.jsonl \
  --output-dir artifacts/release/reference-v21 \
  --agent-pack configs/agents/stability_ops
```

Fixed offline reference artifacts (no Phoenix required): `artifacts/release/reference-v2/` (BLOCKED + generated release controls), `artifacts/release/reference-v21/` (APPROVED with warnings).

## GitHub Actions demo (CI/CD recording)

Record v2 BLOCKED → deploy skipped and v2.1 APPROVED → deploy runs in GitHub Actions: [`DEMO_CICD.md`](./DEMO_CICD.md). Workflow: [`.github/workflows/release-gate-demo.yml`](../.github/workflows/release-gate-demo.yml).

## Current Release Capabilities

- Reference Ops AI validated reference profile (contract validation).
- Controlled release-blocking suite **declaration** (JSON validation + audit snapshot; tasks are not executed by AgentGate at gate time).
- Deterministic release gate over Phoenix evidence and reproducible artifact bundles via policy thresholds and span aggregates.
- Homepage featured release intervention plus Run Check release-control journey.
- Generated release controls surfaced in blocked reports; technical backing in `regression_gates.json`.
- Audit bundle with release artifacts and manifest.
- Release report as Certificate + Dossier.
- Gemini diagnosis as explanation-only.
- CLI validation for profile and suite contracts.
- Dashboard and offline HTML report share the same Certificate + Evidence Dossier structure.

## Release Readiness Criteria

- Homepage proves AgentGate stopped a dangerous reference release and shows generated release controls.
- v2 produces `BLOCKED` for real blocker violations.
- v2 report visibly shows generated release controls backed by `regression_gates.json`.
- v2.1 produces `APPROVED` with visible non-blocking warning variance.
- Every release metric shows provenance.
- Missing required evidence is explicit.
- The report distinguishes Certificate from Dossier.
- The reference workflow does not claim statistical production confidence from a reference-tier sample.
