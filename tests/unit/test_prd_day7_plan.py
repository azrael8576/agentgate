from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
TECHNICAL_PRD_PATH = DOCS_DIR / "PRD.md"
PRODUCT_PRD_PATH = DOCS_DIR / "PRD_PRODUCT.md"


def _technical_prd_text() -> str:
    return TECHNICAL_PRD_PATH.read_text(encoding="utf-8")


def _product_prd_text() -> str:
    return PRODUCT_PRD_PATH.read_text(encoding="utf-8")


def test_technical_prd_positions_agentgate_as_release_authority_layer() -> None:
    text = _technical_prd_text()

    assert text.startswith("# AgentGate PRD v1.0")
    assert "PRD_PRODUCT.md" in text
    assert "Release Authority for AI Agents" in text
    assert "Phoenix stores evidence" in text
    assert "AgentGate adds the release authority layer" in text
    assert "AgentPack-defined company policy thresholds" in text


def test_prd_preserves_agentgate_boundary() -> None:
    text = _technical_prd_text()

    assert "Production agent" in text
    assert "owns user experience, RAG, routing, tools, side effects, and product behavior" in text
    assert "AgentGate does not implement Reference Ops AI behavior" in text
    assert "It evaluates the agent through Phoenix evidence and AgentGate eval contracts" in text


def test_product_prd_is_hackathon_judge_scope() -> None:
    text = _product_prd_text()

    assert "hackathon judges and technical reviewers" in text
    assert "current hackathon release" in text
    assert "not the long-term enterprise roadmap" in text
    assert "Can this candidate agent version safely ship?" in text


def test_product_prd_distinguishes_agentgate_from_phoenix() -> None:
    text = _product_prd_text()

    assert "Phoenix vs AgentGate" in text
    assert "Phoenix is the evidence backend" in text
    assert "AgentGate is not a Phoenix dashboard clone" in text
    assert "company-specific policy thresholds" in text
    assert "custom release-safety metrics" in text


def test_product_prd_defines_agentpack_replacement_contract() -> None:
    text = _product_prd_text()

    for required in [
        "AgentPack Contract",
        "AGENTGATE_AGENT_PACK",
        "--agent-pack",
        "configs/agents/_template/",
        "configs/agents/stability_ops/",
    ]:
        assert required in text


def test_product_prd_splits_base_and_custom_metrics() -> None:
    text = _product_prd_text()

    assert "Product Base Metrics" in text
    assert "AgentPack Custom Metrics" in text
    assert "dangerous tool authorization mismatch" in text
    assert "mapped to fixed aggregator keys" in text
    assert "Dangerous capabilities are not hardcoded in AgentGate core" in text


def test_product_prd_makes_decision_authority_deterministic() -> None:
    text = _product_prd_text()

    assert "Effective policy = Phoenix base policy + AgentPack custom policy" in text
    assert "metrics_summary.json + effective policy thresholds -> APPROVED or BLOCKED" in text
    assert "Gemini may diagnose selected dangerous sessions for reviewer explanation only" in text
    assert "Gemini does not approve or block releases" in text
