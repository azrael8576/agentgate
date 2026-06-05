# Phoenix Base (shared)

Metrics and default thresholds derived from Phoenix evals. **Every AgentPack includes this layer automatically** via flat merge in the AgentPack loader.

| File | Purpose |
|------|---------|
| `metrics.json` | Shared metrics (e.g. hallucination, intent routing) |
| `policy.json` | Default `decision_thresholds` for base metrics |

Agents do not copy these files. They add custom dimensions in `configs/agents/<agent>/metrics_custom.json` and `policy_custom.json`.
