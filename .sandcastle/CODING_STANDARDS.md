# Coding Standards (Sandcastle review)

The reviewer loads this file during review. For full project rules, read @AGENTS.md and @CONTEXT.md.

## AgentGate (non-negotiable)

- Release authority stays **deterministic** — no LLM decides `APPROVED` or `BLOCKED`.
- Do not add production agent runtime, Google Chat bot, RAG, or target-agent tool execution.
- User-facing copy: **release controls**. Technical artifact: **`regression_gates.json`**.
- Preserve product distinction: `Unsafe != Imperfect`.
- Do not embed agent-specific business queries in product HTML or core Python.

## Style

- Match surrounding code: naming, imports, types, and test patterns already in the repo.
- Prefer the smallest correct diff; avoid drive-by refactors.
- Comments only for non-obvious business logic.

## Testing

- Run `uv run pytest` before commit.
- Run `uv run agentgate configs validate` when configs change.
- New behavior should have tests at the highest practical seam (same as existing tests in the touched area).

## Architecture

- AgentGate = release gate + audit bundle from Phoenix/local evidence, not a user-facing agent.
- Integrator boundaries live in AgentPacks and docs under `docs/integration/`.
