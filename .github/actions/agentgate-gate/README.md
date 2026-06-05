# agentgate-gate composite action

Run `agentgate release check` from an **external agent repository** without copying AgentGate source into the agent repo.

## Same-repo usage (this repository)

```yaml
jobs:
  release-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: ./.github/actions/agentgate-gate
        with:
          candidate-version: v2.1
          source: local
          evidence-path: configs/agents/stability_ops/seed/v21_evidence.jsonl
          agent-pack: configs/agents/stability_ops
          block-cd: "true"

  deploy:
    needs: release-gate
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploy after APPROVED"
```

## External agent repo (Phoenix evidence)

```yaml
jobs:
  release-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: your-org/agentgate/.github/actions/agentgate-gate@main
        with:
          agentgate-repository: your-org/agentgate
          candidate-version: v2.1
          source: phoenix
          agent-pack: configs/agents/stability_ops
          phoenix-project-name: ${{ secrets.PHOENIX_PROJECT_NAME }}
          phoenix-api-key: ${{ secrets.PHOENIX_API_KEY }}
          block-cd: "true"

  deploy:
    needs: release-gate
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploy candidate"
```

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `candidate-version` | (required) | Agent version label |
| `source` | `phoenix` | `local` or `phoenix` |
| `evidence-path` | — | JSONL path when `source=local` (relative to AgentGate repo root) |
| `agent-pack` | `configs/agents/stability_ops` | AgentPack directory |
| `block-cd` | `true` | Pass `--fail-on-block` |
| `diagnosis-mode` | `deterministic` | `deterministic` or `gemini` |
| `artifact-name` | `release-audit` | GitHub artifact name prefix |

## Outputs

| Output | Description |
| --- | --- |
| `decision` | `APPROVED` or `BLOCKED` |
| `output-dir` | Path to the audit bundle |

See [`docs/DEMO_CICD.md`](../../../docs/DEMO_CICD.md) for the demo recording script.
