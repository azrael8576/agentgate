# Changelog

## 0.1.0 - 2026-06-15

### Breaking Changes

- **Initial Release:** `0.1.0` is the first public release of AgentGate. There is no upgrade path from an earlier stable version yet; this version defines the initial CLI, dashboard, AgentPack, and artifact contract.

### Major Features and Improvements

- **What AgentGate Is:**

  - **Release Authority for AI Agents:** AgentGate is a pre-production release gate for AI agents. It reads Phoenix trace evidence, applies policy and release metrics, and answers one question: can this candidate version safely ship?
  - **Deterministic Decision Path:** The first version establishes a reproducible `APPROVED` / `BLOCKED` decision flow driven by evidence and policy thresholds rather than human intuition alone.
  - **Auditable Output:** Every release check produces an audit bundle so teams can inspect why a candidate passed or failed.

- **Core Product Capabilities:**

  - **Phoenix Evidence Source:** AgentGate can run release checks against Phoenix-backed traces, spans, eval labels, policy preflights, and tool activity.
  - **Local JSONL Fallback:** The first version also supports offline evidence replay for demos, testing, and reproducible review.
  - **Release Reports:** Added HTML and JSON release artifacts including release decision, metrics summary, dangerous sessions, regression gates, and verification results.

- **AgentPack Model:**

  - **Two-Layer EffectiveConfig:** The product ships with a PhoenixBase plus AgentCustom configuration model for policies and metrics.
  - **DefaultDemoPack:** `configs/agents/stability_ops/` serves as the bundled reference AgentPack for the first public version.
  - **Agent-Agnostic Boundary:** Production agent behavior stays outside AgentGate. AgentGate integrates through AgentPack config, trace evidence, and tool registration.

- **Operator Experience:**

  - **Web Dashboard:** Added landing, run, latest report, artifact download, and health routes for reviewing release status.
  - **Future Controls:** Blocked candidates can emit release controls that later candidates must verify.
  - **Optional AI Assistance:** Advisory review and dangerous-session diagnosis are available without taking release authority away from deterministic policy evaluation.

- **Foundation for Future Versions:**

  - **Testing Coverage:** The first release includes unit coverage for release checks, dashboard rendering, AgentPack loading, Phoenix normalization, telemetry replay, and demo seed generation.
  - **Maintainable Architecture:** The codebase establishes the initial AgentPack, release, reporting, and dashboard seams for future product work.

### Bug Fixes and Other Changes

- **Version Metadata Alignment:** Standardized project metadata on version `0.1.0` across Python and Node package manifests.
- **Validation Workflow:** Verified the release with unit tests, Ruff checks, AgentPack config validation, profile validation, and suite validation.
