from pathlib import Path

import pytest


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
DOC_EXPECTATIONS = (
    (
        "RELEASE_PIPELINE.md",
        DOCS_DIR / "getting-started" / "RELEASE_PIPELINE.md",
        (
            "--agentic-review/--no-agentic-review",
            "Phoenix runs default to agentic review enabled.",
            "Local/offline runs default to agentic review disabled.",
            "APPROVED runs can still finish with no agent-review action or warning-only findings.",
        ),
    ),
    (
        "PHOENIX_INTEGRATION.md",
        DOCS_DIR / "integration" / "PHOENIX_INTEGRATION.md",
        (
            "full trace logs",
            "Pattern Finder and Dataset Planner",
            "trace_pull",
            "Failures are recorded in `agent_review_input.json`",
            "agentic review artifacts remain informational only",
        ),
    ),
    (
        "RELEASE_OUTPUT.md",
        DOCS_DIR / "integration" / "RELEASE_OUTPUT.md",
        (
            "`agent_review_input.json`",
            "`pattern_finder_plan.json`",
            "`pattern_finder_results.json`",
            "`dataset_planner_results.json`",
            "Agent review artifacts",
            "separate from decision inputs",
            "do not approve or block releases",
            "do not write back to Phoenix datasets or annotation queues in P0",
        ),
    ),
    (
        "REFERENCE_WORKFLOW.md",
        DOCS_DIR / "REFERENCE_WORKFLOW.md",
        (
            "Pattern Finder",
            "Dataset Planner",
            "Agents investigate and plan. The gate decides.",
            "Human review still decides whether dataset candidates",
            "annotation recommendations",
            "future control candidates",
            "Approved, no extra action needed",
            "Warning-only follow-up",
        ),
    ),
)


def _read_doc(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_all_present(text: str, required: tuple[str, ...], *, doc_name: str) -> None:
    missing = [phrase for phrase in required if phrase not in text]
    assert not missing, f"{doc_name} missing phrases: {', '.join(missing)}"


@pytest.mark.parametrize(("doc_name", "path", "required_phrases"), DOC_EXPECTATIONS)
def test_agentic_review_docs_cover_expected_phrases(
    doc_name: str, path: Path, required_phrases: tuple[str, ...]
) -> None:
    _assert_all_present(_read_doc(path), required_phrases, doc_name=doc_name)
