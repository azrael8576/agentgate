from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
REFERENCE_WORKFLOW_PATH = DOCS_DIR / "REFERENCE_WORKFLOW.md"
PRODUCT_PRD_PATH = DOCS_DIR / "PRD_PRODUCT.md"

REFERENCE_WORKFLOW_JOURNEY_PHRASES = (
    "Five-Step Judge Demo Journey",
    "Featured release intervention",
    "Generate future release controls",
    "Generated release controls",
    "regression_gates.json is the technical artifact backing generated release controls.",
    "Approved, not perfect",
    "APPROVED with warnings",
)

REFERENCE_WORKFLOW_BRIDGE_PHRASES = (
    "future release controls",
    "regression_gates.json",
    "Public product language is **release controls**",
    "technical artifact contract remains **`regression_gates.json`**",
)

DEMO_STEP_HEADINGS = (
    "Step 1: Homepage proves release intervention",
    "Step 3: v2 BLOCKED report is the proof moment",
    "Step 4: Generated release controls are backed by regression gates",
    "Step 5: v2.1 closes the loop",
)

PRODUCT_PRD_INTERVENTION_PHRASES = (
    "Converted into future release controls",
    "Featured release intervention",
    "Generated release controls",
    "APPROVED with warnings",
    "generated release controls on blocked candidates",
    "regression_gates.json` as the technical artifact",
    "Approved, not perfect.",
)


def _read_doc(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_all_present(text: str, required: tuple[str, ...], *, doc_name: str) -> None:
    missing = [phrase for phrase in required if phrase not in text]
    assert not missing, f"{doc_name} missing phrases: {', '.join(missing)}"


def test_reference_workflow_describes_implemented_demo_journey() -> None:
    _assert_all_present(
        _read_doc(REFERENCE_WORKFLOW_PATH),
        REFERENCE_WORKFLOW_JOURNEY_PHRASES,
        doc_name="REFERENCE_WORKFLOW.md",
    )


def test_reference_workflow_bridges_release_controls_and_regression_gates() -> None:
    _assert_all_present(
        _read_doc(REFERENCE_WORKFLOW_PATH),
        REFERENCE_WORKFLOW_BRIDGE_PHRASES,
        doc_name="REFERENCE_WORKFLOW.md",
    )


def test_reference_workflow_steps_follow_demo_journey_order() -> None:
    text = _read_doc(REFERENCE_WORKFLOW_PATH)
    positions = [text.index(heading) for heading in DEMO_STEP_HEADINGS]
    assert positions == sorted(positions)


def test_product_prd_matches_release_intervention_public_story() -> None:
    _assert_all_present(
        _read_doc(PRODUCT_PRD_PATH),
        PRODUCT_PRD_INTERVENTION_PHRASES,
        doc_name="PRD_PRODUCT.md",
    )
