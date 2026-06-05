# AgentGate Domain Context

## Product

AgentGate is a **release authority** for AI agents. It reads Phoenix trace evidence, applies release metrics and policy thresholds, and produces auditable APPROVED/BLOCKED decisions plus HTML/JSON artifacts.

AgentGate is **not** a production agent runtime. Production agents run in separate repositories and emit OpenInference spans to Phoenix.

## Two-layer configuration model

| Layer | Location | Purpose |
|-------|----------|---------|
| **PhoenixBase** | `configs/phoenix/` | Shared metrics and default thresholds derived from Phoenix evals (hallucination, routing, etc.). Every agent pack includes this layer automatically. |
| **AgentCustom** | `configs/agents/<agent>/metrics_custom.json`, `policy_custom.json` | Per-agent release dimensions and business policy. Each agent owns its custom files; no inheritance from other agents. |

**EffectiveConfig** = flat merge(PhoenixBase, AgentCustom). Custom keys override base keys on conflict.

## AgentPack

An **AgentPack** is one directory under `configs/agents/<agent>/` with:

- `pack.yaml` — manifest (paths, demo seed, candidate versions)
- `profile.json` — agent registration (`tool_manifest`, Phoenix project)
- `suite.json` — controlled eval suite + gate binding
- `metrics_custom.json` / `policy_custom.json` — agent-specific layer
- `span_contract.json`, `report_config.json` — span rules and report copy
- `seed/` — optional offline demo evidence (JSONL), not agent code

**DefaultDemoPack** = `configs/agents/stability_ops` (repo default, open-box demo).

## Repository boundary

| Repo / directory | Role |
|------------------|------|
| `agentgate/` | Release gate product, configs, dashboard, seed evidence |
| External agent repos | Real production agents — **not** copied into AgentGate; only tool IDs and policies are **registered** via AgentPack JSON |

## Core modules (agent-agnostic)

- `backend/agentgate/core/agent_pack.py` — load and merge PhoenixBase + AgentCustom
- `backend/agentgate/release/` — evidence pipeline, metrics, decision engine
- `backend/agentgate/web/` — dashboard and report rendering
