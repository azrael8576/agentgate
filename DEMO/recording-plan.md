# Demo Recording Plan

**Three acts:** slides 1–7 → **5 fixed report shots** → slides 16–17.

Slides 8–15 are deck reference only. Do not record them between act 1 and act 3.

**Style:** Keynote pacing (short lines, pauses). Act 2 = **evidence cards**, not report tour — one proof per shot, overlay required. Cut to browser: first frame = report hero, no mouse wandering.

## Screen flow

| Act | Screen | Duration guide | Purpose |
| --- | --- | --- | --- |
| 1 | Slide deck 1–7 | ~90 s | Hook, gap, product boundary, evidence stack, advisory agents |
| 2 | v2 report shots 1–4 | ~45 s | BLOCKED proof: metrics, DENY → EXECUTED, controls |
| 2 | v2.1 report shot 5 | ~8–10 s | Loop proof: inherited controls passed, warnings remain |
| 3 | Slide deck 16–17 | ~20 s | System loop + dual tagline close |

## Act 1 — Slides 1–7

| Slide | On-screen headline | Narration focus |
| --- | --- | --- |
| 1 | A wrong AI answer can become a real business consequence. | Air Canada = **chatbot** wrong answer, not agent action — no logo |
| 2 | Agents are moving from answers to actions. | Bridge: chatbot answer → agent action → release risk |
| 3 | Agent releases need gates too. | CI/CD gap; prompts / models / tools / permissions → release authority |
| 4 | AgentGate + Can this version ship? | Product reveal — logo + release authority tagline |
| 5 | Ship or no-ship, from evidence. | Pipeline + audit report + regression candidates |
| 6 | Trace. Decide. Improve. | Phoenix / AgentGate / Gemini — split lines; end with **Advisory only**; do not repeat footer line aloud |
| 7 | Agents investigate. Humans approve. Gates decide. | Advisory agents → **Humans approve** → gate decides → **「Let's look at a real release report for v2.」** → pause 0.5–1 s → cut away |

## Act 2 — Fixed proof shots (not free scroll)

**Not a report walkthrough — evidence cards.** One proof per shot. Overlay required.

**v2:** `AGENTGATE_LATEST_ARTIFACT_DIR=artifacts/release/reference-v2`  
**v2.1:** `AGENTGATE_LATEST_ARTIFACT_DIR=artifacts/release/reference-v21`  
**URL:** `http://127.0.0.1:8000/reports/latest`

| # | Scroll target | Narration (product voice) | Hold / overlay |
| --- | --- | --- | --- |
| 1 | Report hero | Real release check for candidate v2 → v2 BLOCKED → release decision | Overlay: **Release decision** |
| 2 | Blocker metrics | Deterministic: policy + blocker metrics, not LLM opinion | Overlay: **Deterministic, not LLM** — do not add words |
| 3 | Dangerous session | Key trace: policy denied — tool still ran | Overlay: **DENY → EXECUTED** — **hold ≥1s** |
| 4 | Generated release controls | Failure → future requirements, not debug notes | Overlay: **Failure → future requirements** |
| 5 | v2.1 inherited controls | 4 loaded / 4 passed / 0 blocking / warnings remain → **pause 0.5s** → Approved, not perfect | Overlay: **Verified against v2 controls** — **show yellow warnings** |

Use overlay cards if the report UI does not make each beat obvious at a glance.

**Recommended overlay labels (one per shot):**

| Shot | Overlay text |
| --- | --- |
| 1 | Release decision |
| 2 | Deterministic, not LLM |
| 3 | DENY → EXECUTED |
| 4 | Failure → future requirements |
| 5 | Verified against v2 controls |

Report must visibly show (or overlay):

```text
v2 BLOCKED
DENY → EXECUTED
failed blocker metrics
release controls generated
v2.1 inherited controls passed
warnings remain
```

## Act 3 — Slides 16–17

| Slide | On-screen | Close |
| --- | --- | --- |
| 16 | Phoenix provides evidence. / AgentGate enforces release policy. / Gemini → regression coverage | Regression coverage loop |
| 17 | AgentGate + two taglines | Ship with evidence, not vibes + blocked failures → requirements |

## Local setup

```bash
uv run uvicorn backend.agentgate.main:app --reload
```

v2 report:

```bash
AGENTGATE_LATEST_ARTIFACT_DIR=artifacts/release/reference-v2 uv run uvicorn backend.agentgate.main:app --reload
```

v2.1 report (Shot 5):

```bash
AGENTGATE_LATEST_ARTIFACT_DIR=artifacts/release/reference-v21 uv run uvicorn backend.agentgate.main:app --reload
```
