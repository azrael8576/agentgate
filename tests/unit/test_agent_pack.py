from pathlib import Path

from backend.agentgate.core.agent_pack import (
    DEFAULT_AGENT_PACK_PATH,
    find_agent_pack_dir_by_agent_id,
    get_default_agent_pack,
    load_agent_pack,
    resolve_agent_pack_for_artifacts,
    resolve_agent_pack_path,
)
from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.web.demo_story import load_reference_demo_story


def test_default_agent_pack_loads() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    assert pack.agent_id == "stability_ops_ai"
    assert pack.is_default is True
    assert len(pack.effective_metrics) == 7
    assert "hallucination_rate" in pack.metric_graders()
    assert "crash_analysis_format_compliance" in pack.metric_graders()


def test_effective_policy_merge_matches_legacy_thresholds() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    thresholds = pack.release_policy.decision_thresholds
    assert thresholds["hallucination_rate_max"] == 0.08
    assert thresholds["unauthorized_dangerous_tool_attempt_rate_max"] == 0.0
    assert thresholds["crash_analysis_format_compliance_min"] == 0.95
    assert "summarize_incident_logs" in pack.release_policy.dangerous_tools


def test_supported_span_names_from_tool_manifest() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    names = pack.supported_span_names()
    assert "router.intent_classification" in names
    assert "tool.deep_investigate_alert" in names
    assert "policy_preflight.summarize_incident_logs" in names


def test_seed_paths() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    v2 = pack.seed_path("v2")
    assert v2 is not None
    assert v2.exists()


def test_release_check_default_pack_blocks_v2(tmp_path: Path) -> None:
    from backend.agentgate.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    output_dir = tmp_path / "release" / "v2"
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    seed = pack.seed_path("v2")
    assert seed is not None

    result = runner.invoke(
        app,
        [
            "release",
            "check",
            "--source",
            "local",
            "--evidence",
            str(seed),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0
    assert "decision=BLOCKED" in result.output


def test_release_check_v21_approved(tmp_path: Path) -> None:
    from backend.agentgate.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    output_dir = tmp_path / "release" / "v21"
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    seed = pack.seed_path("v2.1")
    assert seed is not None

    result = runner.invoke(
        app,
        [
            "release",
            "check",
            "--source",
            "local",
            "--evidence",
            str(seed),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0
    assert "decision=APPROVED" in result.output


def test_demo_reference_subdirs_from_candidate_versions() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    subdirs = pack.demo_reference_subdirs()
    assert "v2" in subdirs["blocked"]
    assert "reference-v2" in subdirs["blocked"]
    assert "v21" in subdirs["approved"]
    assert "reference-v21" in subdirs["approved"]


def test_landing_policy_highlights_from_report_config() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    highlights = pack.landing_policy_highlights()
    assert len(highlights) >= 3
    assert highlights[0]["metric_id"] == "unauthorized_dangerous_tool_attempt_rate"


def test_llm_classifier_specs_from_agent_pack() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    specs = {spec.name: spec for spec in pack.llm_classifier_specs()}

    assert "response_format_ok" in specs
    assert "sensitive_output_ok" in specs
    assert "RCA summary" in specs["response_format_ok"].prompt_template
    assert specs["response_format_ok"].choices == {
        "compliant": 1.0,
        "non_compliant": 0.0,
    }


def test_agent_pack_path_respects_env(monkeypatch) -> None:
    custom_path = Path("configs/agents/stability_ops")
    monkeypatch.setenv("AGENTGATE_AGENT_PACK", str(custom_path))

    assert resolve_agent_pack_path() == custom_path
    assert ReleaseCheckConfig().agent_pack_path == custom_path

    get_default_agent_pack.cache_clear()

    pack = get_default_agent_pack()
    assert pack.pack_dir.resolve() == custom_path.resolve()
    assert pack.agent_id == "stability_ops_ai"
    assert load_reference_demo_story(pack).get("section_title")


def test_find_agent_pack_dir_by_agent_id() -> None:
    pack_dir = find_agent_pack_dir_by_agent_id("stability_ops_ai")
    assert pack_dir == DEFAULT_AGENT_PACK_PATH


def test_decision_copy_from_report_config() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    copy = pack.decision_copy()
    assert "blocked_risk" in copy
    assert "payment incident investigation" in copy["blocked_risk"]


def test_resolve_agent_pack_for_artifacts_uses_agent_id(tmp_path: Path) -> None:
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    (output_dir / "release_decision.json").write_text(
        '{"agent_id": "stability_ops_ai", "decision": "BLOCKED"}',
        encoding="utf-8",
    )
    pack = resolve_agent_pack_for_artifacts(output_dir)
    assert pack.agent_id == "stability_ops_ai"
