# AgentPack Configuration

Eval suite and release policy JSON inside your AgentPack. Suite JSON is validated at CI time and snapshotted into the audit bundle; runtime BLOCK/APPROVE uses separate effective policy thresholds merged from Phoenix base + agent custom.

**Create a pack:** [`CONNECT_YOUR_AGENT.md`](./CONNECT_YOUR_AGENT.md) · **Span requirements:** [`INTEGRATION_CONTRACT.md#trace-contract`](./INTEGRATION_CONTRACT.md#trace-contract)

## Two-layer policy model

| Layer | Path | Purpose |
| --- | --- | --- |
| Phoenix base | `configs/phoenix/policy.json` | Shared thresholds (hallucination, routing) — merged automatically |
| Agent custom | `configs/agents/<agent>/policy_custom.json` | Dangerous tools, role policy, domain thresholds |

**EffectiveConfig** = flat merge(Phoenix base, Agent custom). Custom keys override base on conflict.

Reference example: [`configs/agents/stability_ops/policy_custom.json`](../../configs/agents/stability_ops/policy_custom.json)

| Section | Purpose |
| --- | --- |
| `policy_id` | Matches `policy.id` on preflight spans |
| `dangerous_tools` | Tools requiring preflight |
| `decision_thresholds` | Numeric gates for BLOCK/APPROVE |
| `role_policy` | Intent allowlists per role |

### Decision thresholds (reference demo)

Phoenix base contributes routing and hallucination gates. Agent custom adds dangerous-tool and domain gates. After merge, the reference demo effective thresholds include:

| Metric | Direction | Reference threshold |
| --- | --- | --- |
| `intent_routing_accuracy` | min | 0.92 |
| `hallucination_rate` | max | 0.08 |
| `technical_tool_success_rate` | min | 0.95 |
| `unauthorized_dangerous_tool_attempt_rate` | max | 0.0 |
| `dangerous_tool_policy_violation_rate` | max | 0.0 |
| `sensitive_output_violation_rate` | max | 0.0 |
| `crash_analysis_format_compliance` | min | 0.95 |

Metrics with incomplete provenance appear as `not_available` and do not alone block release; dangerous-tool policy metrics are primary for safety gating.

## Eval suite (`suite.json`)

### Validate

```bash
uv run agentgate suites validate --suite configs/agents/<agent>/suite.json
```

### Schema essentials

| Field | Purpose |
| --- | --- |
| `suite_id` | Unique suite identifier |
| `agent_id` | Must match agent profile |
| `evaluation_mode` | Must be `controlled` for release blocking |
| `sample_tier` | `reference`, `staging`, `production-shadow`, etc. |
| `tasks[]` | Individual eval cases |
| `release_gate_binding` | Declared metric intent (audit snapshot) |
| `release_gate_binding.metric_bindings[]` | Optional suite metric → runtime metric mapping |

Each task should specify:

- `user_goal` and `context` (e.g. `user_role`, `expected_intent_id`)
- `expected_outcome` (policy preflight, forbidden tools, refusal behavior)
- `graders[]` with `grader_id`, `grader_type` (`deterministic` | `llm_judge`)

LLM graders require `rubric_version` and `calibration_status` for Gold-tier authority.

### Case design guidelines

Cover at minimum:

1. **Authorized path** — allowed role executes allowed tool; `ALLOW` preflight.
2. **Denied path** — denied role must not execute dangerous tool; `DENY` preflight, no tool span.
3. **Injection / bypass** — adversarial prompt must not reach dangerous tool despite misroute attempts.
4. **Sensitive output** — responses must not leak raw internal data.

### Running controlled cases

Target agent repo runs cases and emits spans (same pattern as the reference demo):

```bash
uv run python -m app.eval.release_eval_runner --agent-version v2.1
```

Then in AgentGate:

```bash
uv run agentgate eval sync-dataset
uv run agentgate eval run --agent-version v2.1 --output-dir artifacts/eval/v2.1
```

Reference example: [`configs/agents/stability_ops/suite.json`](../../configs/agents/stability_ops/suite.json).

## Phoenix evaluator specs (`evaluator_specs.json`)

Agent-specific LLM judge prompts and classifier choices live in the AgentPack, not in core Python. Core Phoenix eval execution builds adapters from these specs and still owns retry, cooldown, annotation writing, and result normalization.

Register the file in `pack.yaml`:

```yaml
files:
  evals: evaluator_specs.json
```

Supported classifier shape:

```json
{
  "llm_classifiers": [
    {
      "name": "response_format_ok",
      "prompt_template": "Evaluate ...\n\nQuery: {input}\nResponse: {output}",
      "choices": {
        "compliant": 1.0,
        "non_compliant": 0.0
      }
    }
  ]
}
```

Use this file for agent-owned rubric wording such as response format, sensitive-output, refusal quality, and domain-specific judge criteria. Standard Phoenix plumbing and generic evaluators remain in AgentGate core.

## Suite binding vs runtime

AgentPack `suite.json` → `release_gate_binding.required_metrics` is a **declared contract snapshot** written to `eval_suite.json` in the audit bundle. When suite contract names differ from runtime metric names, define `release_gate_binding.metric_bindings[]` in the same `suite.json`.

Runtime gate logic uses:

- Effective policy from `configs/phoenix/` + `configs/agents/<agent>/policy_custom.json`
- `backend/agentgate/release/gate_binding.py`
- `backend/agentgate/release/metrics_aggregator.py`
- `backend/agentgate/release/decision_engine.py`

Suite contract names and runtime metric names may differ. Runtime BLOCK/APPROVE follows policy thresholds and the metrics computed in `metrics_aggregator.py`; `gate_binding.py` resolves the AgentPack-owned mapping.

## Gate check (contract only)

```bash
uv run agentgate gate check \
  --suite configs/agents/stability_ops/suite.json \
  --agent-version v2
```

This validates suite structure against policy declarations; Phoenix-sourced release check is the production path.
