# Integration Contract

Formal contract for connecting a production AI agent to AgentGate release authority — certification tiers, trace requirements, and span schema.

**Step-by-step integration:** [`AGENTGATE_INTEGRATION_SKILL.md`](./AGENTGATE_INTEGRATION_SKILL.md)

## Certification tiers

| Tier | Meaning | Release authority |
| --- | --- | --- |
| Bronze | Agent emits trace-visible evidence | Observed warnings only |
| Silver | Controlled suite + deterministic graders | Can block on deterministic guardrails |
| Gold | Silver + human gold set and calibrated LLM judges | Semantic judges with stronger confidence |

Integrations must declare their target tier in the agent profile and eval suite metadata.

## Minimum trace requirements

Every integrated agent must emit:

- `agent.id`
- `agent.version`
- `trace_id` / `span_id`
- parent span or session identity
- `case_id` or `task_id` (controlled runs)
- `input.text`
- output text (final answer span)
- status
- latency when available
- cost/token metadata when available

Tool-calling agents must also emit tool name, risk level, input summary, output schema status, success/error status, tool latency, and evidence ID when available.

Dangerous tools must emit a policy preflight span **before** execution.

## Policy preflight requirements

Dangerous tool preflight spans must include:

- `policy.id`
- `user.role` or equivalent authorization context
- `tool.name`
- `tool.risk_level`
- `policy.preflight.required`
- `policy.preflight.decision` (`ALLOW` | `DENY`)
- `policy.violation`
- reason code when denied

If a denied dangerous tool later executes, AgentGate treats it as a critical finding (`unauthorized_dangerous_tool_execution`).

## Eval label / grader requirements

AgentGate consumes Phoenix annotations or local JSONL labels when they include:

- evaluator or grader ID
- label name
- label value
- score when available
- rationale
- evidence IDs
- rubric version for LLM judges
- calibration status for LLM judges

LLM judges without rubric version and calibration status are not eligible for Gold-tier release authority.

## Controlled vs observed evidence

| Mode | Source | Release impact |
| --- | --- | --- |
| `controlled` | Known eval suite run against a candidate version | Can APPROVE or BLOCK |
| `observed` | Production, shadow, or ad hoc traces | WARNING, triage, recommended regression only |

Observed findings do not directly block release until converted into controlled suite tasks.

## Controlled suite and audit requirements

Controlled suites must define `suite_id`, `agent_id`, `evaluation_mode=controlled`, `sample_tier`, tasks with expected outcomes and graders, and `release_gate_binding`. See [`AGENTPACK.md`](./AGENTPACK.md).

A release authority run must produce the artifacts in [`RELEASE_OUTPUT.md`](./RELEASE_OUTPUT.md). Reviewers must be able to reproduce BLOCKED/APPROVED without re-running LLM judges.

---

## Trace contract {#trace-contract}

Span names and attributes required for AgentGate release checks. Normalization is span-contract driven: any agent that emits these spans into Phoenix can integrate without AgentGate knowing your runtime internals.

### Layer model

```text
Production agent  -> emits spans
Phoenix           -> stores traces
AgentGate         -> reads spans, computes metrics, selects dangerous sessions
```

Authorization is deterministic in the production agent (`policy.preflight.decision`). AgentGate verifies whether runtime behavior matched those spans.

### Required spans

#### `router.intent_classification`

Emitted when the agent classifies a user request.

| Attribute | Required | Notes |
| --- | --- | --- |
| `agent.id`, `agent.version` | Yes | |
| `user.role` | Yes | |
| `input.text` | Yes | |
| `router.selected_intent_id` | Yes | |
| `router.route_type` | Yes | `static_answer`, `tool_call`, etc. |
| `router.confidence` | Recommended | |
| `expected.intent_id` | Controlled only | Do not fake on live traffic |
| `router.correct` | Controlled only | Set only when expected intent is known |
| `test.case_id` | Controlled only | |

#### `answer.static`

Emitted on static or low-risk answer paths.

| Attribute | Required |
| --- | --- |
| `intent.id` | Yes |
| `route.type` | Yes |
| `answer.source`, `answer.version` | Recommended |
| `response.policy` | Recommended |

#### `policy_preflight.<tool_name>`

Emitted **before** each dangerous tool.

| Attribute | Required |
| --- | --- |
| `policy.id` | Yes |
| `user.role` | Yes |
| `tool.name`, `tool.risk_level` | Yes |
| `policy.preflight.required` | Yes |
| `policy.preflight.decision` | Yes (`ALLOW` / `DENY`) |
| `policy.violation` | When denied |
| `policy.violation.reason` | When denied |
| `expected.allowed` | Controlled runs |

#### `tool.<tool_name>`

Emitted during tool execution.

| Attribute | Required |
| --- | --- |
| `span.kind` | Yes (`TOOL`) |
| `tool.name`, `tool.risk_level` | Yes |
| `tool.success` | Yes |
| `tool.output_schema_valid` | Recommended |

SQL-backed tools should also emit:

```text
tool.query_backend
sql.query.type = parameterized
sql.has_limit
sql.uses_select_star
tool.fixed_time_window_days
tool.limit
```

### Dangerous session finding types

AgentGate classifies critical findings including:

```text
unauthorized_dangerous_tool_execution
dangerous_tool_policy_violation
sensitive_output_violation
dangerous_intent_misroute
policy_violation_with_execution
policy_preflight_missing
```

Trace pull priority (for audit `get-trace` calls) follows severity order in `backend/agentgate/release/dangerous_evidence_classifier.py`.

### Controlled eval metadata

For release eval runs, set on the target agent:

```bash
AGENTGATE_EXPECTED_INTENT_ID=crash.issue_deep_investigation
AGENTGATE_EXPECTED_ALLOWED=false
AGENTGATE_TEST_CASE_ID=case_unauthorized_deep_investigation_001
```

Without these, live traces still provide policy/tool evidence but subjective routing metrics may be `not_available`.

### Target agent instrumentation pattern

1. Add a Phoenix telemetry wrapper (register export when env is set).
2. Call wrapper from existing `setup_telemetry()` — do not replace production behavior by default.
3. Instrument router, static answers, policy preflight, tools in that order.
4. Verify with unit tests + one Phoenix UI run per span type.

See [`AGENTGATE_INTEGRATION_SKILL.md`](./AGENTGATE_INTEGRATION_SKILL.md) Steps 3–4.
