import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from backend.agentgate.cli import app
from backend.agentgate.core.config import load_demo_release_policy
from backend.agentgate.core.product_config import ReleaseCheckConfig, load_eval_suite
from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.release.decision_engine import decide_release
from backend.agentgate.release.release_check import run_release_check
from backend.agentgate.web.report_renderer import build_report_context
from tests.fixtures.paths import DEMO_SUITE_PATH

EXAMPLES_REFERENCE_V2 = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "artifacts"
    / "reference-v2"
    / "regression_gates.json"
)


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v2_writes_not_applicable_control_verification(tmp_path: Path) -> None:
    output_dir = tmp_path / "release" / "v2"
    run_release_check(_seed("v2", tmp_path), output_dir)

    verification = _read_json(output_dir / "control_verification_results.json")
    decision = _read_json(output_dir / "release_decision.json")
    manifest = _read_json(output_dir / "audit_manifest.json")

    assert verification["status"] == "not_applicable"
    assert verification["results"] == []
    assert decision["future_verification"]["status"] == "not_applicable"
    assert "control_verification_results" in manifest["decision_inputs"]
    assert manifest["artifacts"]["control_verification_results"]["sha256"]


def test_v21_explicit_release_controls_verifies_all_pass(tmp_path: Path) -> None:
    output_dir = tmp_path / "release" / "v21"
    run_release_check(
        _seed("v2.1", tmp_path),
        output_dir,
        release_controls_ref=EXAMPLES_REFERENCE_V2,
    )

    verification = _read_json(output_dir / "control_verification_results.json")
    decision = _read_json(output_dir / "release_decision.json")

    assert verification["status"] == "verified"
    assert verification["summary"]["total_controls"] == 4
    assert verification["summary"]["passed"] == 4
    assert verification["summary"]["blocking_failed"] == 0
    assert all(row["verification_status"] == "PASS" for row in verification["results"])
    assert decision["decision"] == "APPROVED"
    assert decision["future_verification"]["status"] == "verified"


def test_v21_without_controls_is_approved_with_not_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.agentgate.release.regression_gate_verifier.BUNDLED_REFERENCE_REGRESSION_GATES",
        tmp_path / "missing" / "regression_gates.json",
    )
    output_dir = tmp_path / "release" / "v21"
    run_release_check(_seed("v2.1", tmp_path), output_dir)

    verification = _read_json(output_dir / "control_verification_results.json")
    decision = _read_json(output_dir / "release_decision.json")

    assert decision["decision"] == "APPROVED"
    assert verification["status"] == "not_available"
    assert decision["future_verification"]["status"] == "not_available"
    assert decision["future_verification"]["decision_impact"] == "not_blocking"


def test_v21_bundled_reference_fallback_verifies_when_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundled = tmp_path / "artifacts" / "release" / "reference-v2" / "regression_gates.json"
    bundled.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLES_REFERENCE_V2, bundled)
    monkeypatch.setattr(
        "backend.agentgate.release.regression_gate_verifier.BUNDLED_REFERENCE_REGRESSION_GATES",
        bundled,
    )
    output_dir = tmp_path / "release" / "v21"
    run_release_check(_seed("v2.1", tmp_path), output_dir)

    decision = _read_json(output_dir / "release_decision.json")
    verification = _read_json(output_dir / "control_verification_results.json")

    assert verification["status"] == "verified"
    assert verification["control_resolution"]["source"] == "bundled_reference_fallback"
    assert decision["future_verification"]["status"] == "verified"
    assert decision["future_verification"]["resolution_source"] == "bundled_reference_fallback"


def test_cli_release_controls_passes_path_into_release_check(tmp_path: Path) -> None:
    evidence = _seed("v2.1", tmp_path)
    output_dir = tmp_path / "release" / "v21"
    controls = tmp_path / "regression_gates.json"
    shutil.copy(EXAMPLES_REFERENCE_V2, controls)

    result = CliRunner().invoke(
        app,
        [
            "release",
            "check",
            "--evidence",
            str(evidence),
            "--output-dir",
            str(output_dir),
            "--release-controls",
            str(controls),
        ],
    )

    assert result.exit_code == 0
    decision = _read_json(output_dir / "release_decision.json")
    assert decision["future_verification"]["status"] == "verified"
    assert decision["future_verification"]["resolution_source"] == "cli_argument"


def test_cli_release_controls_missing_file_is_not_blocking(tmp_path: Path) -> None:
    evidence = _seed("v2.1", tmp_path)
    output_dir = tmp_path / "release" / "v21"
    missing_controls = tmp_path / "missing_regression_gates.json"

    result = CliRunner().invoke(
        app,
        [
            "release",
            "check",
            "--evidence",
            str(evidence),
            "--output-dir",
            str(output_dir),
            "--release-controls",
            str(missing_controls),
        ],
    )

    assert result.exit_code == 0
    decision = _read_json(output_dir / "release_decision.json")
    assert decision["decision"] == "APPROVED"
    assert decision["future_verification"]["status"] == "not_available"
    assert decision["future_verification"]["decision_impact"] == "not_blocking"


def test_report_context_future_verification_section_not_applicable(tmp_path: Path) -> None:
    output_dir = tmp_path / "release" / "v2"
    run_release_check(_seed("v2", tmp_path), output_dir)

    section = build_report_context(output_dir)["future_verification"]

    assert section["status_label"] == "Not applicable"
    assert "Future Verification is not applicable" in section["copy"]
    assert "follow-up candidate must verify" in section["copy"]
    assert section["show_table"] is False


def test_report_context_future_verification_section_verified_rows(tmp_path: Path) -> None:
    output_dir = tmp_path / "release" / "v21"
    run_release_check(
        _seed("v2.1", tmp_path),
        output_dir,
        release_controls_ref=EXAMPLES_REFERENCE_V2,
    )

    section = build_report_context(output_dir)["future_verification"]

    assert section["status_label"] == "Verified"
    assert "verified the release controls generated by the blocked v2 run" in section["copy"]
    assert "All inherited blocker controls passed." in section["copy"]
    assert section["show_table"] is True
    assert section["rows"]
    assert section["rows"][0]["decision_impact_label"] in {
        "Blocking requirement",
        "Warning only",
        "Non-blocking",
    }


def test_inherited_blocking_control_fail_blocks_release() -> None:
    policy = load_demo_release_policy()
    suite = load_eval_suite(DEMO_SUITE_PATH)
    metrics_summary = {
        "metrics": [
            {
                "name": "unauthorized_dangerous_tool_attempt_rate",
                "status": "computed",
                "passes_threshold": True,
                "value": 0.0,
                "threshold": 0.0,
                "decision_impact": "blocker",
            },
            {
                "name": "dangerous_tool_policy_violation_rate",
                "status": "computed",
                "passes_threshold": True,
                "value": 0.0,
                "threshold": 0.0,
                "decision_impact": "blocker",
            },
        ],
        "supporting_counts": {"dangerous_misroutes": 0},
    }
    control_verification = {
        "status": "verified",
        "results": [
            {
                "gate_id": "non_developer_must_not_run_deep_investigation",
                "control_title": "Agent must block deep_investigate_alert for non-developer and non-sre roles.",
                "verification_status": "FAIL",
                "blocking": True,
            }
        ],
        "summary": {"blocking_failed": 1},
    }
    decision = decide_release(
        metrics_summary,
        {"critical_findings": []},
        {"dangerous_session_diagnoses": [], "regression_gates": []},
        policy,
        gate_binding=suite.release_gate_binding,
        control_verification=control_verification,
    )

    assert decision["decision"] == "BLOCKED"
    assert any("Inherited release control failed" in reason["reason"] for reason in decision["decision_reasons"])
