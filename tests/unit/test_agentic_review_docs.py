from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
RELEASE_PIPELINE_PATH = DOCS_DIR / "getting-started" / "RELEASE_PIPELINE.md"
PHOENIX_INTEGRATION_PATH = DOCS_DIR / "integration" / "PHOENIX_INTEGRATION.md"
RELEASE_OUTPUT_PATH = DOCS_DIR / "integration" / "RELEASE_OUTPUT.md"
REFERENCE_WORKFLOW_PATH = DOCS_DIR / "REFERENCE_WORKFLOW.md"

RELEASE_PIPELINE_PHRASES = (
    "--agentic-review/--no-agentic-review",
    "Phoenix runs default to agentic review enabled.",
    "Local/offline runs default to agentic review disabled.",
    "APPROVED runs can still finish with no agent-review action or warning-only findings.",
)

PHOENIX_INTEGRATION_PHRASES = (
    "full trace logs",
    "Pattern Finder and Dataset Planner",
    "trace_pull",
    "Failures are recorded in `agent_review_input.json`",
    "agentic review artifacts remain informational only",
)

RELEASE_OUTPUT_PHRASES = (
    "`agent_review_input.json`",
    "`pattern_finder_plan.json`",
    "`pattern_finder_results.json`",
    "`dataset_planner_results.json`",
    "Agent review artifacts",
    "separate from decision inputs",
    "do not approve or block releases",
    "do not write back to Phoenix datasets or annotation queues in P0",
)

REFERENCE_WORKFLOW_PHRASES = (
    "Pattern Finder",
    "Dataset Planner",
    "Agents investigate and plan. The gate decides.",
    "Human review still decides whether dataset candidates",
    "annotation recommendations",
    "future control candidates",
    "Approved, no extra action needed",
    "Warning-only follow-up",
)


def _read_doc(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_all_present(text: str, required: tuple[str, ...], *, doc_name: str) -> None:
    missing = [phrase for phrase in required if phrase not in text]
    assert not missing, f"{doc_name} missing phrases: {', '.join(missing)}"


def test_release_pipeline_documents_agentic_review_cli_behavior() -> None:
    _assert_all_present(
        _read_doc(RELEASE_PIPELINE_PATH),
        RELEASE_PIPELINE_PHRASES,
        doc_name="RELEASE_PIPELINE.md",
    )


def test_phoenix_integration_documents_full_trace_pull_and_failures() -> None:
    _assert_all_present(
        _read_doc(PHOENIX_INTEGRATION_PATH),
        PHOENIX_INTEGRATION_PHRASES,
        doc_name="PHOENIX_INTEGRATION.md",
    )


def test_release_output_documents_agent_review_artifacts_as_informational() -> None:
    _assert_all_present(
        _read_doc(RELEASE_OUTPUT_PATH),
        RELEASE_OUTPUT_PHRASES,
        doc_name="RELEASE_OUTPUT.md",
    )


def test_reference_workflow_uses_simple_agentic_review_narrative() -> None:
    _assert_all_present(
        _read_doc(REFERENCE_WORKFLOW_PATH),
        REFERENCE_WORKFLOW_PHRASES,
        doc_name="REFERENCE_WORKFLOW.md",
    )
