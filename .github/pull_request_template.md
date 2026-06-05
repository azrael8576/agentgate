---
name: Pull request
about: Create a pull request
label: 'triage'
---
Thank you for opening a Pull Request!

Before submitting your PR, please make sure you:

- [ ] Include a PR description which states **what you've done and why**
- [ ] Open a GitHub issue as a bug/feature request before writing your code — that way we can discuss the change, evaluate designs, and agree on the general idea
- [ ] Ensure tests and lint pass:
  - `uv run pytest`
  - `uv run ruff check backend tests`
  - `uv run ruff format backend tests` (auto-apply formatting)
- [ ] Run config validation when AgentPack or configs change:
  - `uv run agentgate configs validate`
  - `uv run agentgate profiles validate --profile configs/agents/stability_ops/profile.json`
  - `uv run agentgate suites validate --suite configs/agents/stability_ops/suite.json`
- [ ] Respect the AgentGate boundary — no production agent runtime, chat bot, RAG, or target-agent tool execution in core
- [ ] Keep `BLOCKED` / `APPROVED` deterministic (Gemini explains dangerous sessions only)
- [ ] Update any relevant documentation

Are you a first-time contributor?

- [ ] Read [`AGENTS.md`](../../AGENTS.md) and [`CONTEXT.md`](../../CONTEXT.md)
- [ ] Familiarize yourself with the release evidence pipeline and AgentPack layout

Fixes #<issue_number_goes_here>
