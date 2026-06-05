# Sample release artifacts

Curated **reference integration** bundles only — not required to connect your own agent.

| Directory | Decision | Notes |
| --- | --- | --- |
| `reference-v2/` | BLOCKED | Sample JSON subset + generated release controls in `regression_gates.json` |
| `reference-v21/` | APPROVED | Sample JSON + `release_report.html` with warning-only variance (`Approved, not perfect.`) |

Full offline bundles for the dashboard: `artifacts/release/reference-v2/` and `artifacts/release/reference-v21/`.

Regenerate after updating `configs/agents/stability_ops/demo_cases.json` or seed:

```bash
uv run agentgate demo seed-v2 --output configs/agents/stability_ops/seed/v2_evidence.jsonl
uv run agentgate demo seed-v21 --output configs/agents/stability_ops/seed/v21_evidence.jsonl
uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v2_evidence.jsonl \
  --output-dir artifacts/release/reference-v2
uv run agentgate release check --source local \
  --evidence configs/agents/stability_ops/seed/v21_evidence.jsonl \
  --output-dir artifacts/release/reference-v21
```

Older HTML under `reference-v21/release_report.html` may lag until you re-run release check.
