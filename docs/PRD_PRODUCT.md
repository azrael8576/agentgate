# AgentGate Product PRD

> **Audience:** hackathon judges and technical reviewers.
> **Scope:** current hackathon release, not the long-term enterprise roadmap.
> **Extended technical appendix:** [`PRD.md`](./PRD.md) · **Demo workflow:** [`REFERENCE_WORKFLOW.md`](./REFERENCE_WORKFLOW.md)

---

## 0. Executive Summary

**AgentGate is a pre-production release authority layer for AI agents.**

Modern agents do more than answer text. They route intents, call tools, read internal systems, and may touch high-risk operational data. A candidate version can improve normal answers while quietly regressing a dangerous capability: the wrong role reaches a critical tool, a policy preflight is bypassed, or a vague request routes into a sensitive workflow.

AgentGate answers one release question:

> **Can this candidate agent version safely ship?**

It reads Phoenix evidence, applies AgentPack-defined company policy and release-safety metrics, and writes an auditable **APPROVED** or **BLOCKED** decision.

### Phoenix vs AgentGate

| Phoenix | AgentGate |
| --- | --- |
| Stores traces, spans, eval labels, annotations, and observability evidence | Adds the release authority layer on top of Phoenix evidence |
| Helps teams inspect what happened | Decides whether a candidate version can ship |
| Is the primary evidence backend | Loads AgentPack-defined tool risk, policy thresholds, custom metrics, report copy, and gate bindings |

**AgentGate is not a Phoenix dashboard clone.** Its value is the extra release layer: company-specific policy thresholds, custom release-safety metrics, deterministic BLOCK/APPROVE decisions, and audit-ready reports.

---

## 1. Problem Statement

AI agent releases lack a clear, reproducible safety gate for dangerous behavior.

Teams can observe traces in Phoenix, but they still need a structured decision process:

- Which behaviors are release blockers?
- Which tools are dangerous for this company or agent?
- Which roles are allowed to trigger those tools?
- Which metrics are product-wide release-safety checks versus agent-specific policy checks?
- Can reviewers verify the decision later without re-running Gemini or manually inspecting every trace?

Without AgentGate, a release owner must manually translate observability data into release judgment. That process is slow, inconsistent, and hard to audit.

---

## 2. Product Promise

AgentGate provides a trace-backed, deterministic release gate for candidate AI agent versions.

Current hackathon release:

| Verdict | Meaning |
| --- | --- |
| **APPROVED** | Gate-bound blocker metrics pass under the effective policy |
| **BLOCKED** | A blocker metric failed or required release evidence is unavailable |

Planned future verdicts such as `WARNING`, `NEEDS_REVIEW`, or `INDETERMINATE` are out of scope for the shipped hackathon decision model.

The shipped workflow is:

```text
Phoenix MCP or local JSONL evidence
  -> normalize evidence
  -> compute release-safety metrics
  -> apply effective policy thresholds
  -> select dangerous sessions
  -> optional Gemini explanation
  -> write audit artifacts and HTML report
```

---

## 3. Users

| User | Need |
| --- | --- |
| Hackathon judge | Understand the product, run the demo, and verify that AgentGate is not just a dashboard |
| Technical judge | Inspect the architecture boundary, deterministic decision path, and config-driven agent replacement model |
| Release owner | Get a clear APPROVED/BLOCKED decision before production |
| AI platform engineer | Integrate another agent through an AgentPack and Phoenix trace contract |
| Agent developer | See which release control failed and what behavior must be fixed |
| Security / compliance reviewer | Audit evidence, policy thresholds, and artifacts offline |

---

## 4. What AgentGate Is / Is Not

| AgentGate is | AgentGate is not |
| --- | --- |
| A pre-production release gate for candidate agent versions | A runtime guardrail that blocks live user requests |
| A release authority layer over Phoenix evidence | A Phoenix dashboard clone or trace explorer |
| A deterministic decision engine using metrics and effective policy thresholds | An LLM that randomly decides release approval |
| An AgentPack-driven framework for company policy, tool risk, and custom metrics | A product that hardcodes one demo agent's crash or incident workflow |
| An audit bundle generator for release review | A production agent runtime, chatbot, RAG system, or tool executor |

AgentGate must not implement target-agent behavior such as Google Chat bot logic, retrieval, answer generation, BigQuery/Crashlytics execution, or production intent routing.

---

## 5. Architecture Boundary

```text
Production agent
  Owns UX, RAG, routing, tools, side effects, and product behavior
        |
        | emits OpenInference / Phoenix spans
        v
Phoenix
  Stores traces, spans, eval labels, annotations, and evidence
        |
        | queried by AgentGate
        v
AgentGate
  Loads AgentPack, computes release metrics, applies policy gates,
  selects dangerous sessions, writes BLOCK/APPROVE audit artifacts
```

Phoenix is the primary evidence source. Local JSONL is an offline fallback for demos, tests, and reproducible hackathon review. After evidence is normalized, both sources follow the same decision path.

---

## 6. AgentPack Contract

AgentGate is agent-agnostic because agent-specific configuration lives in an **AgentPack**.

A production agent can use AgentGate when it:

1. Emits the required OpenInference/Phoenix trace contract
2. Declares an AgentPack
3. Maps tools, roles, dangerous capabilities, policy thresholds, custom metrics, and report copy
4. Runs release check with `--agent-pack` or `AGENTGATE_AGENT_PACK`

Canonical agent-specific configuration lives in:

```text
configs/agents/<agent>/
```

New integrations copy:

```text
configs/agents/_template/
```

The current bundled Reference Ops AI demo remains at the legacy path:

```text
configs/agents/stability_ops/
```

That path is retained for release stability. Public product naming should present it as **Reference Ops AI**.

---

## 7. Metrics Model

AgentGate separates product-level release-safety metrics from AgentPack-specific custom metrics.

### Product Base Metrics

These are cross-agent release-safety dimensions:

- intent routing correctness
- hallucination / groundedness signals
- tool success and failure
- dangerous tool authorization mismatch
- policy preflight violation
- sensitive output violation
- required evidence unavailable

### AgentPack Custom Metrics

These are declared by a specific agent pack and mapped to fixed aggregator keys:

- company-specific dangerous capability checks
- role-specific policy thresholds
- domain-specific output rules
- agent-specific report controls and control copy
- custom gate bindings for the agent's release suite

The hackathon release supports config-driven custom metrics and report controls through AgentPack JSON. It does not support arbitrary user-authored Python metric plugins, a UI metric builder, or multi-tenant policy administration.

Dangerous capabilities are not hardcoded in AgentGate core. Each AgentPack declares its `tool_manifest` and risk policy; AgentGate evaluates whether declared high-risk or critical tools were authorized, preflighted, executed, denied, or misrouted.

---

## 8. Effective Policy And Decision Authority

AgentGate computes decisions from the effective policy:

```text
Effective policy = Phoenix base policy + AgentPack custom policy
```

The decision is deterministic:

```text
metrics_summary.json + effective policy thresholds -> APPROVED or BLOCKED
```

Gemini may diagnose selected dangerous sessions for reviewer explanation only. Gemini does not approve or block releases and cannot override the deterministic gate.

---

## 9. Reference Ops AI Demo

The bundled demo is **Reference Ops AI**.

Reference Ops AI is an open-box reference AgentPack plus seeded evidence story. It demonstrates what an external production agent's traces and release artifacts could look like. AgentGate does not implement or serve Reference Ops AI behavior.

Demo curve:

```text
Danger -> Caught -> Blocked -> Converted into future release controls -> Verified -> Approved, not perfect
```

Judge-facing walkthrough: homepage proof → Run Check journey → blocked report → generated release controls → approved-but-not-perfect follow-up. See [`REFERENCE_WORKFLOW.md`](./REFERENCE_WORKFLOW.md).

Demo story:

| Candidate | Outcome | What it demonstrates |
| --- | --- | --- |
| Homepage featured intervention | **BLOCKED v2 proof** | AgentGate stopped a dangerous release before production |
| `v2` | **BLOCKED** | A dangerous capability regression reaches a high-risk path |
| `v2` audit bundle | Generated release controls | Blocked failures convert into future release controls backed by `regression_gates.json` |
| `v2.1` | **APPROVED with warnings** | Gate-bound blocker controls pass; non-blocking warning variance remains visible |

The demo proves the product workflow, not that AgentGate is tied to one operational domain. Other agents can replace the demo pack with their own AgentPack and Phoenix trace evidence.

---

## 10. UI And Report Requirements

### Landing Page

The first viewport must communicate:

- AgentGate is not a Phoenix dashboard
- Phoenix is the evidence backend
- AgentGate adds AgentPack-defined policy thresholds and company-specific release metrics
- BLOCK/APPROVE is deterministic

The homepage must also prove release intervention:

- **Featured release intervention** for the bundled blocked candidate
- visible **Generated release controls** count on the blocked proof card
- loop-closing follow-up for the approved candidate with warning variance when present

Reference Ops AI belongs below the product positioning as the bundled demo workflow.

### Release Report

The report must show:

- final APPROVED/BLOCKED verdict
- candidate version and agent identity
- evidence source: Phoenix MCP or local JSONL fallback
- effective policy basis: Phoenix base + AgentPack custom thresholds
- blocker metrics and threshold comparisons
- dangerous session evidence and trace IDs
- generated release controls on blocked candidates, with `regression_gates.json` as the technical artifact backing those controls
- failed non-blocking warning controls on approved candidates when present (`Approved, not perfect.`)
- downloadable audit artifacts and hashes
- Gemini explanation boundary when diagnosis is present

Audit package contents:

- `release_decision.json`
- `metrics_summary.json`
- `regression_gates.json`
- `dangerous_sessions.json`
- `agent_profile.json`
- `eval_suite.json`
- `audit_manifest.json`
- `release_report.html`

---

## 11. Current Release Scope

Shipped in hackathon scope:

- Phoenix MCP evidence path
- local JSONL fallback for offline demo/test reproducibility
- AgentPack validation and replacement via CLI/env var
- two-layer config model: Phoenix base + AgentPack custom
- product base metrics plus AgentPack custom metrics mapped to fixed aggregators
- deterministic APPROVED/BLOCKED release decision
- optional Gemini diagnosis for selected dangerous sessions only
- HTML demo dashboard and release report
- Reference Ops AI bundled demo AgentPack
- audit artifacts with reproducibility metadata

Out of scope for hackathon:

- inline runtime enforcement
- production agent execution
- arbitrary metric plugin runtime
- UI metric builder
- multi-tenant policy admin
- second full demo AgentPack
- automatic repair or deployment
- replacing Phoenix observability

---

## 12. Documentation Shape

Public judge path:

1. [`../README.md`](../README.md)
2. [`PRD_PRODUCT.md`](./PRD_PRODUCT.md)
3. [`REFERENCE_WORKFLOW.md`](./REFERENCE_WORKFLOW.md)

Integrator path:

- [`integration/CONNECT_YOUR_AGENT.md`](./integration/CONNECT_YOUR_AGENT.md)
- [`integration/AGENTPACK.md`](./integration/AGENTPACK.md)
- [`integration/INTEGRATION_CONTRACT.md`](./integration/INTEGRATION_CONTRACT.md)

Maintainer appendix:

- [`PRD.md`](./PRD.md)
- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`adr/`](./adr/)
- [`../CONTEXT.md`](../CONTEXT.md)

---

## 13. Hackathon Release Checklist

- AgentGate is presented as agent-agnostic release authority
- Phoenix is clearly positioned as evidence backend, not the thing AgentGate replaces
- AgentGate's extra layer is visible: AgentPack-defined company policy and custom metrics
- Reference Ops AI is clearly a bundled demo AgentPack and evidence fixture
- AgentPack replacement is documented through `_template`, `--agent-pack`, and `AGENTGATE_AGENT_PACK`
- Product base metrics are separated from AgentPack custom metrics
- Dangerous capabilities are declared by AgentPack, not hardcoded in core product logic
- BLOCK/APPROVE is deterministic from `metrics_summary.json` and effective policy thresholds
- Gemini is explanation-only and non-authoritative
- Phoenix MCP is primary evidence source; local JSONL is fallback
- HTML landing page explains AgentGate vs Phoenix in the first viewport
- Homepage featured release intervention proves a blocked reference candidate and generated release controls
- HTML report shows effective policy, evidence source, blocker metrics, generated release controls, and audit artifacts
- v2.1 approved path shows warning-only variance without weakening blocker authority
- Public copy uses **release controls**; technical artifact contract remains **`regression_gates.json`**
