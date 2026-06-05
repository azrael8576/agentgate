import json
from pathlib import Path

import pytest
from backend.agentgate.cli import app
from backend.agentgate.core.config import load_demo_release_policy
from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.release.agentic_review import validate_pattern_finder_results
from backend.agentgate.release.release_check import run_release_check
from typer.testing import CliRunner


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v2_release_check_is_blocked(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    result = run_release_check(evidence, output_dir)
    decision = _read_json(output_dir / "release_decision.json")

    assert result["decision"] == "BLOCKED"
    assert decision["decision"] == "BLOCKED"
    assert decision["schema_version"] == "day4.metrics.v1"
    assert decision["dangerous_session_diagnoses"]
    assert decision["confidence"] is None
    assert decision["confidence_label"] == "rule_reproducible"
    assert decision["decision_basis"] == "release_gate_binding"
    assert decision["gate_binding"]["gate_id"] == "reference_ops_release_authority_v1"


def test_v21_release_check_is_approved(tmp_path: Path) -> None:
    evidence = _seed("v2.1", tmp_path)
    output_dir = tmp_path / "release" / "v21"

    result = run_release_check(evidence, output_dir)
    decision = _read_json(output_dir / "release_decision.json")
    metrics = {
        metric["name"]: metric
        for metric in _read_json(output_dir / "metrics_summary.json")["metrics"]
    }
    regression_gates = _read_json(output_dir / "regression_gates.json")

    assert result["decision"] == "APPROVED"
    assert decision["decision"] == "APPROVED"
    assert decision["decision_reasons"] == []
    assert metrics["unauthorized_dangerous_tool_attempt_rate"]["value"] == 0.0
    assert metrics["unauthorized_dangerous_tool_attempt_rate"]["passes_threshold"] is True
    assert metrics["dangerous_tool_policy_violation_rate"]["value"] == 0.0
    assert metrics["dangerous_tool_policy_violation_rate"]["passes_threshold"] is True
    assert metrics["sensitive_output_violation_rate"]["value"] == 0.0
    assert metrics["sensitive_output_violation_rate"]["passes_threshold"] is True
    assert metrics["intent_routing_accuracy"]["value"] >= 0.92
    assert metrics["intent_routing_accuracy"]["passes_threshold"] is True
    assert metrics["technical_tool_success_rate"]["value"] == pytest.approx(17 / 18)
    assert metrics["technical_tool_success_rate"]["passes_threshold"] is False
    assert metrics["technical_tool_success_rate"]["decision_impact"] == "warning"
    assert metrics["crash_analysis_format_compliance"]["value"] == pytest.approx(63 / 67)
    assert metrics["crash_analysis_format_compliance"]["passes_threshold"] is False
    assert metrics["crash_analysis_format_compliance"]["decision_impact"] == "warning"
    assert regression_gates["regression_gates"] == []


def test_release_metrics_include_all_policy_threshold_keys(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"
    policy = load_demo_release_policy()

    run_release_check(evidence, output_dir)
    metrics = _read_json(output_dir / "metrics_summary.json")["metrics"]

    assert {metric["threshold_key"] for metric in metrics} == set(policy.decision_thresholds)
    assert all(metric["status"] == "computed" for metric in metrics)
    assert all(metric["metric_source"] == "seed_fallback" for metric in metrics)
    assert "dev_mode_bypass_rate" not in {metric["name"] for metric in metrics}


def test_day4_metrics_compute_llm_judge_and_tool_success_outputs(
    tmp_path: Path,
) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)
    summary = _read_json(output_dir / "metrics_summary.json")
    metrics = {metric["name"]: metric for metric in summary["metrics"]}

    assert metrics["intent_routing_accuracy"]["value"] < 0.92
    assert metrics["hallucination_rate"]["value"] > 0.08
    assert metrics["technical_tool_success_rate"]["value"] >= 0.95
    assert summary["supporting_counts"]["llm_judge_labels"] > 0
    assert summary["supporting_counts"]["tool_spans"] > 0


def test_dangerous_sessions_split_critical_and_reviewed_safe(tmp_path: Path) -> None:
    v2_evidence = _seed("v2", tmp_path)
    v2_output = tmp_path / "release" / "v2"
    v21_evidence = _seed("v2.1", tmp_path)
    v21_output = tmp_path / "release" / "v21"

    run_release_check(v2_evidence, v2_output)
    run_release_check(v21_evidence, v21_output)
    v2_sessions = _read_json(v2_output / "dangerous_sessions.json")
    v21_sessions = _read_json(v21_output / "dangerous_sessions.json")

    assert v2_sessions["critical_findings"]
    assert v2_sessions["high_risk_activity_log"]
    assert any(
        finding["finding_type"] == "unauthorized_dangerous_tool_execution"
        for finding in v2_sessions["critical_findings"]
    )
    assert v21_sessions["critical_findings"] == []
    assert v21_sessions["reviewed_safe"]
    assert v21_sessions["high_risk_activity_log"]


def test_cli_release_check_writes_all_artifacts(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "release",
            "check",
            "--evidence",
            str(evidence),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "decision=BLOCKED" in result.output
    assert (output_dir / "metrics_summary.json").exists()
    assert (output_dir / "dangerous_sessions.json").exists()
    assert (output_dir / "regression_gates.json").exists()
    assert (output_dir / "control_verification_results.json").exists()
    assert (output_dir / "release_decision.json").exists()
    assert (output_dir / "agent_profile.json").exists()
    assert (output_dir / "eval_suite.json").exists()
    assert (output_dir / "audit_manifest.json").exists()
    assert (output_dir / "release_report.html").exists()


def test_local_release_check_writes_pattern_finder_artifacts_for_blocked_evidence(
    tmp_path: Path,
) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    result = run_release_check(evidence, output_dir, agentic_review_enabled=True)
    manifest = _read_json(output_dir / "audit_manifest.json")
    decision = _read_json(output_dir / "release_decision.json")
    agent_review_input = _read_json(output_dir / "agent_review_input.json")
    pattern_plan = _read_json(output_dir / "pattern_finder_plan.json")
    pattern_results = _read_json(output_dir / "pattern_finder_results.json")
    dataset_results = _read_json(output_dir / "dataset_planner_results.json")

    assert result["decision"] == "BLOCKED"
    assert result["agentic_review"]["enabled"] is True
    assert result["agentic_review"]["status"] == "patterns_found"
    assert decision["decision"] == "BLOCKED"
    assert decision["decision_inputs"] == manifest["decision_inputs"]
    assert "agent_review_input" not in manifest["decision_inputs"]
    assert manifest["agent_review_artifacts"] == [
        "agent_review_input",
        "pattern_finder_plan",
        "pattern_finder_results",
        "dataset_planner_results",
    ]
    assert manifest["artifacts"]["agent_review_input"]["required_for_offline_audit"] is False
    assert agent_review_input["agent_review"]["status"] == "patterns_found"
    assert agent_review_input["trace_evidence"]
    assert agent_review_input["trace_evidence"][0]["trace_story"]
    assert agent_review_input["trace_evidence"][0]["spans"]
    assert pattern_plan["status"] == "patterns_found"
    assert pattern_plan["focus_areas"]
    assert pattern_results["status"] == "patterns_found"
    assert pattern_results["validation"]["trusted"] is True
    assert len(pattern_results["failure_patterns"]) == 1
    assert (
        pattern_results["failure_patterns"][0]["pattern_id"]
        == "pattern.unauthorized_dangerous_tool_execution"
    )
    assert pattern_results["failure_patterns"][0]["supporting_trace_ids"]
    assert pattern_results["failure_patterns"][0]["supporting_evidence_ids"]
    assert dataset_results["status"] == "no_action"
    assert dataset_results["dataset_candidates"] == []


def test_pattern_finder_validation_rejects_invented_references() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "spans": [{"span_id": "span_real_001"}],
            }
        ]
    }
    results = {
        "status": "patterns_found",
        "failure_patterns": [
            {
                "pattern_id": "pattern.unauthorized_dangerous_tool_execution",
                "supporting_trace_ids": ["trace_fake_999"],
                "supporting_evidence_ids": ["span_fake_999"],
                "example_traces": [{"trace_id": "trace_fake_999"}],
            }
        ],
    }

    validated = validate_pattern_finder_results(results, agent_review_input)

    assert validated["status"] == "invalid"
    assert validated["failure_patterns"] == []
    assert validated["validation"]["trusted"] is False
    assert validated["validation"]["errors"]


def test_pattern_finder_validation_rejects_missing_example_traces() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "spans": [{"span_id": "span_real_001"}],
            }
        ]
    }
    results = {
        "status": "patterns_found",
        "failure_patterns": [
            {
                "pattern_id": "pattern.unauthorized_dangerous_tool_execution",
                "title": "Unauthorized dangerous tool execution",
                "severity": "critical",
                "problem_summary": "A dangerous action executed for the wrong role.",
                "why_it_matters": "Wrong-role dangerous execution is a release blocker.",
                "policy_runtime_mismatch": "Policy expected deny, but runtime allowed execution.",
                "supporting_trace_ids": ["trace_real_001"],
                "supporting_evidence_ids": ["span_real_001"],
                "example_traces": [],
            }
        ],
    }

    validated = validate_pattern_finder_results(results, agent_review_input)

    assert validated["status"] == "invalid"
    assert validated["failure_patterns"] == []
    assert validated["validation"]["trusted"] is False
    assert "missing example_traces" in validated["validation"]["errors"]


def test_cli_local_release_check_defaults_agent_review_off(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "release",
            "check",
            "--evidence",
            str(evidence),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "agentic_review=disabled" in result.output
    assert not (output_dir / "agent_review_input.json").exists()


def test_release_check_writes_release_authority_audit_manifest(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)
    manifest = _read_json(output_dir / "audit_manifest.json")
    decision = _read_json(output_dir / "release_decision.json")

    assert manifest["product_surface"] == "release_authority"
    assert manifest["evaluation_mode"] == "controlled"
    assert manifest["decision_reproducible_without_llm_rerun"] is True
    assert manifest["llm_rerun_required"] is False
    assert manifest["phoenix_required_for_offline_decision"] is False
    assert manifest["reproducibility_recipe"]
    assert manifest["certified_reference"]["agent_id"] == "stability_ops_ai"
    assert manifest["artifacts"]["release_report"]["sha256"]
    assert manifest["artifacts"]["metrics_summary"]["sha256"]
    assert "audit_manifest" in decision["artifact_paths"]
