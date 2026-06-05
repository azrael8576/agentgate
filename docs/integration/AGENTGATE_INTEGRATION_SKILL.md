# AgentGate Integration Skill

**Quick start:** [`CONNECT_YOUR_AGENT.md`](./CONNECT_YOUR_AGENT.md)

Connect a production AI agent to AgentGate release checks. This is the canonical guide for engineers, Cursor, Codex, and other AI agents integrating a new target agent.

## Goal

After following this skill, a candidate agent version can:

1. Emit Phoenix-compatible OpenInference traces with policy preflight evidence.
2. Run controlled eval cases that produce annotatable spans.
3. Pass through `agentgate release check` and receive a deterministic `APPROVED` or `BLOCKED` decision with a full audit bundle.

## System boundary

```text
Your production agent (external repo)
  -> emits OpenInference spans via phoenix-otel
Phoenix / Arize
  -> traces, spans, annotations, datasets
AgentGate (this repo)
  -> metrics, dangerous session selection, gate, audit bundle, report
```

AgentGate does **not** run your production agent, chat UX, RAG, or target-agent tools.

---

## Step 1: Inspect the target agent

Before writing telemetry, map the runtime:

| Area | What to find |
| --- | --- |
| Entrypoints | HTTP webhook, CLI, job runner, ADK app |
| Router | Intent classifier, route type (`static_answer` vs `tool_call`) |
| Tools | Tool registry, which tools are dangerous |
| Authorization | Role map, policy checks before tool execution |
| Existing telemetry | OpenTelemetry, ADK prompt-response, custom logging |
| Deploy | Env vars, Secret Manager, Cloud Run / K8s config |

Reference integration file map (Reference Ops AI):

```text
app/fast_api_app.py          # HTTP entry
app/chat_webhook.py          # session / user context
app/routing/router.py        # router.intent_classification
app/routing/route_handlers.py # static answers + policy preflight + tools
app/app_utils/telemetry.py   # initialize Phoenix export
```

AgentGate does **not** run your production agent, chat UX, RAG, or target-agent tools. **Do not copy production agent Python into this repo** — register tools via AgentPack `profile.json` only.

Two-layer config: see [`CONTEXT.md`](../../CONTEXT.md) and [`AGENTPACK.md`](./AGENTPACK.md).

---

## Step 2: Create an AgentPack

```bash
cp -r configs/agents/_template configs/agents/<your_agent>
# Edit profile.json, metrics_custom.json, policy_custom.json, suite.json, span_contract.json
export AGENTGATE_AGENT_PACK=configs/agents/<your_agent>
uv run agentgate configs validate --agent-pack configs/agents/<your_agent>
```

Default demo pack: [`configs/agents/stability_ops/`](../../configs/agents/stability_ops/) (reference only — copy structure, not its company policy).

---

## Step 3: Define AgentProfile

Edit `configs/agents/<your_agent>/profile.json`. Validate with:

```bash
uv run agentgate profiles validate --profile configs/agents/<your_agent>/profile.json
```

Required fields:

| Field | Purpose |
| --- | --- |
| `agent_id` | Stable identifier on every span (`agent.id`) |
| `agent.version` | Release candidate label on spans |
| `trace_backend.provider` | `phoenix` for Phoenix-first integrations |
| `trace_backend.project_name` | Phoenix project identifier |
| `tool_manifest[]` | `tool_id`, `risk_level`, `side_effect_type` per tool |
| `risk_policy.policy_id` | Links to release policy JSON |
| `risk_policy.dangerous_tools` | Tools that require policy preflight |

Example: [`configs/agents/stability_ops/profile.json`](../../configs/agents/stability_ops/profile.json).

Align `tool_manifest[]` with tools in your **external** production agent repo. AgentGate does not import agent code.

---

## Step 4: Add trace contract

Every integrated agent must emit spans documented in [`INTEGRATION_CONTRACT.md#trace-contract`](./INTEGRATION_CONTRACT.md#trace-contract).

Minimum span set:

| Span name | When |
| --- | --- |
| `router.intent_classification` | After intent/route selection |
| `answer.static` | Static or low-risk answer path |
| `policy_preflight.<tool>` | **Before** each dangerous tool |
| `tool.<tool>` | During tool execution |
| `final_answer` or `answer.static` | User-visible response |

Required attributes on all relevant spans:

```text
agent.id, agent.version, session.id, user.role, input.text
```

Controlled eval runs may additionally set:

```text
test.case_id, expected.intent_id, expected.allowed, router.correct
```

Do **not** fabricate `router.correct` on live production traffic.

Instrumentation order should follow the runtime path:

1. `router.intent_classification`
2. `answer.static` for safe answer paths
3. `policy_preflight.<tool>` before each dangerous tool
4. `tool.<tool>` during execution

That order keeps audit evidence readable and makes policy violations easier to diagnose from traces.

---

## Step 5: Add policy preflight

Dangerous tools must emit a preflight span **before** execution:

```text
policy_preflight.<tool_name>
```

Required attributes:

```text
policy.id
user.role
tool.name
tool.risk_level
policy.preflight.required = true
policy.preflight.decision = ALLOW | DENY
policy.violation (when denied)
policy.violation.reason
```

**Critical rule:** If `policy.preflight.decision` is `DENY` and the tool span still executes, AgentGate records `unauthorized_dangerous_tool_execution` as a critical finding.

Audit-first default: keep production behavior unchanged during telemetry rollout (`AGENTGATE_POLICY_ENFORCE=false`). Enforce denial in the agent only when you are ready to change runtime behavior.

For controlled deny cases, the target runtime should emit `DENY` on the preflight span and avoid the corresponding `tool.*` execution span. That is the release-critical signal AgentGate evaluates.

Phoenix env on the target agent:

```bash
PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/s/<your-space>/v1/traces
PHOENIX_PROJECT_NAME=<your-project>
PHOENIX_API_KEY=...   # or PHOENIX_API_KEY_SECRET_NAME for Cloud Run
AGENTGATE_AGENT_VERSION=v2.1
AGENTGATE_RELEASE_CANDIDATE=<your_agent>_v2.1
AGENTGATE_USER_ROLE=ops_viewer
```

---

## Step 6: Define EvalSuite

Add `suite.json` to your AgentPack under `configs/agents/<your_agent>/`. Validate with:

```bash
uv run agentgate suites validate --suite configs/agents/<your_agent>/suite.json
```

Controlled suite must include:

- `suite_id`, `agent_id`
- `evaluation_mode=controlled`
- `sample_tier` (e.g. `reference`, `staging`, `production-shadow`)
- `tasks[]` with `expected_outcome`, `graders[]`
- `release_gate_binding` (declared contract; runtime thresholds: [`AGENTPACK.md`](./AGENTPACK.md))

Design cases for:

| Case type | Expected signal |
| --- | --- |
| Allowed role + allowed tool | `ALLOW` preflight, tool executes |
| Denied role + dangerous tool | `DENY` preflight, tool must not execute |
| Prompt injection / policy bypass | No unsafe tool execution despite adversarial input |
| Sensitive output | No raw PII/secrets in final answer spans |

Example suite: [`configs/agents/stability_ops/suite.json`](../../configs/agents/stability_ops/suite.json).

Run controlled cases from your agent repo (same pattern as the reference demo):

```bash
# In target agent repo
uv run python -m app.eval.release_eval_runner --agent-version v2.1
```

---

## Step 7: Run eval automation

From AgentGate repo, with Phoenix env configured:

```bash
uv run agentgate eval sync-dataset
uv run agentgate eval run --agent-version v2.1 --output-dir artifacts/eval/v2.1
```

Eval automation writes Phoenix span annotations used for subjective metrics (`hallucination_rate`, format compliance, etc.). See [`PHOENIX_INTEGRATION.md`](./PHOENIX_INTEGRATION.md) for span ID and REST parser notes.

If Phoenix annotations appear empty, check two integration details first:

1. Phoenix MCP `id` and OTEL `context.span_id` alignment.
2. Collector URL shape: the Phoenix cloud endpoint must keep the `/s/<space>` segment.

Verify coverage (optional, against local seed):

```bash
uv run agentgate eval coverage --evidence artifacts/seed/seed_v21_evidence.jsonl
```

---

## Step 8: Run release check

Phoenix-sourced (primary):

```bash
uv run agentgate release check --source phoenix \
  --project-identifier <phoenix-project> \
  --agent-version v2.1 \
  --diagnosis-mode gemini \
  --output-dir artifacts/release/v2.1
```

Local fallback (no Phoenix):

```bash
uv run agentgate release check --source local \
  --evidence artifacts/seed/seed_v21_evidence.jsonl \
  --output-dir artifacts/release/reference-v21
```

Expected reference workflow outcome: **v2 → BLOCKED**, **v2.1 → APPROVED**.

Full pipeline commands: [`../getting-started/RELEASE_PIPELINE.md`](../getting-started/RELEASE_PIPELINE.md).

---

## Step 9: Review audit package

Inspect artifacts under `--output-dir`. See [`RELEASE_OUTPUT.md`](./RELEASE_OUTPUT.md).

| Artifact | Use |
| --- | --- |
| `release_decision.json` | `APPROVED` / `BLOCKED`, diagnosis metadata |
| `metrics_summary.json` | Metrics with provenance |
| `dangerous_sessions.json` | Critical findings |
| `regression_gates.json` | Suggested regression tasks |
| `agent_profile.json` | Contract snapshot |
| `eval_suite.json` | Suite snapshot |
| `audit_manifest.json` | SHA-256 hashes + reproducibility recipe |
| `release_report.html` | Human-readable Certificate + Dossier |

Gemini explains dangerous sessions only; it does **not** decide release. BLOCK/APPROVE is deterministic from `metrics_summary.json` and policy thresholds.

---

## Verification checklist

```text
[ ] profile.json validates
[ ] suite JSON validates
[ ] Phoenix shows router + policy_preflight + tool spans for one reference fixture run
[ ] DENY preflight → no tool execution on controlled deny case
[ ] eval run completes; subjective metrics not all not_available
[ ] release check produces 7 JSON + release_report.html
[ ] decision matches expected for reference cases
```

---

## Related docs

| Document | Topic |
| --- | --- |
| [`INTEGRATION_CONTRACT.md`](./INTEGRATION_CONTRACT.md) | Certification tiers and span contract |
| [`AGENTPACK.md`](./AGENTPACK.md) | Suite and policy JSON |
| [`PHOENIX_INTEGRATION.md`](./PHOENIX_INTEGRATION.md) | MCP queries, normalizer, eval labels |
| [`RELEASE_OUTPUT.md`](./RELEASE_OUTPUT.md) | Audit artifacts and Gemini boundaries |
| [`../getting-started/RELEASE_PIPELINE.md`](../getting-started/RELEASE_PIPELINE.md) | End-to-end commands |
| [`../REFERENCE_WORKFLOW.md`](../REFERENCE_WORKFLOW.md) | Reference workflow narrative |
