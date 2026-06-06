import json
from pathlib import Path

from backend.agentgate.adk.dataset_planner_agent import build_dataset_planner_agent
from backend.agentgate.adk.pattern_finder_agent import build_pattern_finder_agent
from backend.agentgate.adk.release_evidence_agent import (
    build_release_evidence_agent,
    run_local_release_evidence_check,
)
from backend.agentgate.demo.trace_seed_generator import write_seed_evidence


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_adk_wrapper_runs_existing_release_pipeline(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "adk"

    payload = run_local_release_evidence_check(
        evidence,
        output_dir,
        diagnosis_mode="deterministic",
    )

    assert payload["decision"] == "BLOCKED"
    assert (output_dir / "release_decision.json").exists()
    decision = _read_json(output_dir / "release_decision.json")
    assert decision["decision"] == "BLOCKED"
    assert "comparison_version" not in decision


def test_adk_render_release_report_includes_html(tmp_path: Path) -> None:
    from backend.agentgate.adk.tools import render_release_report

    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "adk"
    run_local_release_evidence_check(
        evidence,
        output_dir,
        diagnosis_mode="deterministic",
    )

    paths = render_release_report(output_dir)

    assert "release_report" in paths
    assert paths["release_report"].endswith("release_report.html")


def test_build_release_evidence_agent_returns_agent_or_none() -> None:
    agent = build_release_evidence_agent()
    if agent is not None:
        assert agent.name == "agentgate_release_evidence_agent"
        assert agent.tools


def test_build_pattern_finder_agent_returns_agent_or_none() -> None:
    agent = build_pattern_finder_agent()
    if agent is not None:
        assert agent.name == "agentgate_pattern_finder_agent"
        assert agent.tools == []


def test_build_dataset_planner_agent_returns_agent_or_none() -> None:
    agent = build_dataset_planner_agent()
    if agent is not None:
        assert agent.name == "agentgate_dataset_planner_agent"
        assert agent.tools == []


def test_dataset_planner_prompt_preserves_human_review_boundary() -> None:
    from backend.agentgate.adk.dataset_planner_agent import DATASET_PLANNER_AGENT_INSTRUCTION

    assert "dataset, annotation, or future-control planning candidates" in (
        DATASET_PLANNER_AGENT_INSTRUCTION
    )
    assert "do not approve or block releases" in DATASET_PLANNER_AGENT_INSTRUCTION.lower()
    assert "do not directly add golden dataset items" in DATASET_PLANNER_AGENT_INSTRUCTION.lower()
