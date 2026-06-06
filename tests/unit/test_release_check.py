import json
from pathlib import Path

import pytest
from backend.agentgate.cli import app
from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.core.config import load_demo_release_policy
from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.release.agentic_review import (
    build_agent_review_artifacts,
    validate_dataset_planner_results,
    validate_pattern_finder_results,
)
from backend.agentgate.release.release_check import run_release_check
from backend.agentgate.release.evidence_loader import load_evidence_jsonl
from backend.agentgate.web.report_renderer import (
    build_report_context,
    render_standalone_release_report_html,
)
from typer.testing import CliRunner


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rewrite_json(path: Path, update: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    update(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    assert agent_review_input["packet_audit_id"] == "agent_review_packet:stability_ops_ai:v2"
    assert agent_review_input["agent_context"]["display_name"] == "Reference Ops AI"
    assert agent_review_input["policy_context"]["policy_id"] == "reference_ops_release_policy_v1"
    assert agent_review_input["policy_context"]["tool_risk_catalog"]
    assert agent_review_input["policy_context"]["role_policy_summary"]
    assert agent_review_input["metric_context"]["metrics"]
    assert (
        agent_review_input["metric_context"]["metrics"][0]["metric_audit_id"].startswith("metric:")
    )
    assert agent_review_input["trace_evidence"]
    assert agent_review_input["trace_evidence"][0]["trace_audit_id"].startswith("trace:")
    assert agent_review_input["trace_evidence"][0]["trace_story"]
    assert (
        agent_review_input["trace_evidence"][0]["expected_intent_id"]
        == "ops.alert_deep_investigation"
    )
    assert (
        agent_review_input["trace_evidence"][0]["selected_intent_id"]
        == "ops.alert_deep_investigation"
    )
    assert "Expected intent:" in agent_review_input["trace_evidence"][0]["trace_story"]
    assert "Supporting evidence IDs:" in agent_review_input["trace_evidence"][0]["trace_story"]
    assert agent_review_input["trace_evidence"][0]["policy_expectation"]
    assert agent_review_input["trace_evidence"][0]["runtime_behavior"]
    assert agent_review_input["trace_evidence"][0]["risk_summary"]
    assert agent_review_input["trace_evidence"][0]["spans"]
    assert agent_review_input["trace_evidence"][0]["spans"][0]["span_audit_id"].startswith("span:")
    assert agent_review_input["trace_evidence"][0]["spans"][0]["plain_language_summary"]
    assert pattern_plan["status"] == "patterns_found"
    assert pattern_plan["focus_areas"]
    assert pattern_results["status"] == "patterns_found"
    assert pattern_results["validation"]["trusted"] is True
    assert len(pattern_results["failure_patterns"]) >= 2
    assert {
        pattern["pattern_id"] for pattern in pattern_results["failure_patterns"]
    } >= {
        "pattern.unauthorized_dangerous_tool_execution",
        "pattern.dangerous_tool_policy_violation",
    }
    assert all(pattern["supporting_trace_ids"] for pattern in pattern_results["failure_patterns"])
    assert all(
        pattern["supporting_evidence_ids"] for pattern in pattern_results["failure_patterns"]
    )
    assert dataset_results["status"] == "candidates_found"
    assert dataset_results["validation"]["trusted"] is True
    assert len(dataset_results["dataset_candidates"]) == 1
    candidate = dataset_results["dataset_candidates"][0]
    assert candidate["candidate_id"] == "dataset_candidate.unauthorized_dangerous_tool_execution.01"
    assert candidate["source_trace_ids"]
    assert candidate["source_evidence_ids"]
    assert candidate["source_finding_types"] == ["unauthorized_dangerous_tool_execution"]
    assert candidate["requires_human_review"] is True
    assert candidate["review_status"] == "pending_review"
    assert candidate["review_instructions"]
    assert candidate["conversion_guidance"]


def test_local_release_check_writes_warning_only_agent_review_artifacts_for_approved_evidence(
    tmp_path: Path,
) -> None:
    evidence = _seed("v2.1", tmp_path)
    output_dir = tmp_path / "release" / "v21"

    result = run_release_check(evidence, output_dir, agentic_review_enabled=True)
    decision = _read_json(output_dir / "release_decision.json")
    agent_review_input = _read_json(output_dir / "agent_review_input.json")
    pattern_results = _read_json(output_dir / "pattern_finder_results.json")
    dataset_results = _read_json(output_dir / "dataset_planner_results.json")
    html = (output_dir / "release_report.html").read_text(encoding="utf-8")

    assert result["decision"] == "APPROVED"
    assert result["agentic_review"]["enabled"] is True
    assert result["agentic_review"]["status"] == "candidates_found"
    assert decision["decision"] == "APPROVED"
    assert decision["agentic_review"]["status"] == "candidates_found"
    assert agent_review_input["agent_review"]["status"] == "candidates_found"
    assert agent_review_input["trace_evidence"]
    assert pattern_results["status"] == "no_action"
    assert pattern_results["validation"]["trusted"] is True
    assert pattern_results["failure_patterns"] == []
    assert pattern_results["warning_observations"]
    assert {
        observation["observation_id"]
        for observation in pattern_results["warning_observations"]
    } == {"warning.response_format_warning"}
    assert dataset_results["status"] == "candidates_found"
    assert dataset_results["validation"]["trusted"] is True
    assert dataset_results["dataset_candidates"]
    assert dataset_results["annotation_recommendations"]
    assert dataset_results["future_control_candidates"] == []
    assert "Review queue" in html
    assert "Review output:" in html
    assert "agent-detail-panel" in html


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
    assert validated["validation"]["reference_errors"]
    assert validated["validation"]["schema_errors"]


def test_pattern_finder_validation_supports_multiple_patterns_and_warning_observations() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "spans": [{"span_id": "span_real_001"}],
            },
            {
                "trace_id": "trace_real_002",
                "spans": [{"span_id": "span_real_002"}],
            },
        ]
    }
    results = {
        "status": "patterns_found",
        "summary": "Pattern Finder found repeated blocker patterns and one warning observation.",
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
                "example_traces": [{"trace_id": "trace_real_001"}],
            },
            {
                "pattern_id": "pattern.dangerous_tool_policy_violation",
                "title": "Dangerous tool policy violation",
                "severity": "critical",
                "problem_summary": "A dangerous tool path recorded a policy violation.",
                "why_it_matters": "Policy-preflight failures on dangerous tools are blockers.",
                "policy_runtime_mismatch": "Runtime marked policy_violation=true for the tool.",
                "supporting_trace_ids": ["trace_real_002"],
                "supporting_evidence_ids": ["span_real_002"],
                "example_traces": [{"trace_id": "trace_real_002"}],
            },
        ],
        "warning_observations": [
            {
                "observation_id": "warning.policy_preflight_missing",
                "title": "Policy preflight missing",
                "severity": "warning",
                "problem_summary": "A dangerous tool ran without a matching preflight span.",
                "why_it_matters": "Coverage gaps should stay visible for human follow-up.",
                "policy_runtime_mismatch": "Runtime showed dangerous activity, but no preflight span.",
                "supporting_trace_ids": ["trace_real_002"],
                "supporting_evidence_ids": ["span_real_002"],
                "example_traces": [{"trace_id": "trace_real_002"}],
            }
        ],
    }

    validated = validate_pattern_finder_results(results, agent_review_input)

    assert validated["status"] == "patterns_found"
    assert validated["validation"]["trusted"] is True
    assert len(validated["failure_patterns"]) == 2
    assert len(validated["warning_observations"]) == 1


def test_dataset_planner_validation_rejects_invented_references() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "finding_types": ["unauthorized_dangerous_tool_execution"],
                "spans": [{"span_id": "span_real_001"}],
            }
        ]
    }
    results = {
        "status": "candidates_found",
        "dataset_candidates": [
            {
                "candidate_id": "dataset_candidate.unauthorized_dangerous_tool_execution.01",
                "source_trace_ids": ["trace_fake_999"],
                "source_evidence_ids": ["span_fake_999"],
                "source_finding_types": ["unauthorized_dangerous_tool_execution"],
                "rationale": "Use this blocker trace as a future release-eval case.",
                "review_instructions": "Confirm the trace is representative before adding coverage.",
                "conversion_guidance": "Convert into a future release control or eval case.",
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
    }

    validated = validate_dataset_planner_results(results, agent_review_input)

    assert validated["status"] == "invalid"
    assert validated["dataset_candidates"] == []
    assert validated["validation"]["trusted"] is False
    assert validated["validation"]["errors"]
    assert validated["validation"]["reference_errors"]
    assert validated["validation"]["schema_errors"] == []


def test_dataset_planner_validation_rejects_nondeterministic_candidate_ids() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "finding_types": ["unauthorized_dangerous_tool_execution"],
                "spans": [{"span_id": "span_real_001"}],
            }
        ]
    }
    results = {
        "status": "candidates_found",
        "dataset_candidates": [
            {
                "candidate_id": "candidate made by llm",
                "source_trace_ids": ["trace_real_001"],
                "source_evidence_ids": ["span_real_001"],
                "source_finding_types": ["unauthorized_dangerous_tool_execution"],
                "rationale": "Use this blocker trace as a future release-eval case.",
                "review_instructions": "Confirm the trace is representative before adding coverage.",
                "conversion_guidance": "Convert into a future release control or eval case.",
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
    }

    validated = validate_dataset_planner_results(results, agent_review_input)

    assert validated["status"] == "invalid"
    assert validated["dataset_candidates"] == []
    assert validated["validation"]["trusted"] is False
    assert "invalid candidate_id candidate made by llm" in validated["validation"]["errors"]


def test_dataset_planner_validation_rejects_candidate_id_type_mismatch() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "finding_types": ["unauthorized_dangerous_tool_execution"],
                "spans": [{"span_id": "span_real_001"}],
            }
        ]
    }
    results = {
        "status": "candidates_found",
        "dataset_candidates": [
            {
                "candidate_id": "dataset_candidate.dangerous_intent_misroute.01",
                "source_trace_ids": ["trace_real_001"],
                "source_evidence_ids": ["span_real_001"],
                "source_finding_types": ["unauthorized_dangerous_tool_execution"],
                "rationale": "Use this blocker trace as a future release-eval case.",
                "review_instructions": "Confirm the trace is representative before adding coverage.",
                "conversion_guidance": "Convert into a future release control or eval case.",
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
    }

    validated = validate_dataset_planner_results(results, agent_review_input)

    assert validated["status"] == "invalid"
    assert validated["dataset_candidates"] == []
    assert validated["validation"]["trusted"] is False
    assert (
        "candidate_id finding type does not match source_finding_types "
        "for dataset_candidate.dangerous_intent_misroute.01"
    ) in validated["validation"]["errors"]


def test_dataset_planner_validation_accepts_all_four_planning_buckets() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "finding_types": ["unauthorized_dangerous_tool_execution"],
                "spans": [{"span_id": "span_real_001"}],
            },
            {
                "trace_id": "trace_real_002",
                "finding_types": ["policy_preflight_missing"],
                "spans": [{"span_id": "span_real_002"}],
            },
        ]
    }
    results = {
        "status": "candidates_found",
        "dataset_candidates": [
            {
                "candidate_id": "dataset_candidate.unauthorized_dangerous_tool_execution.01",
                "source_trace_ids": ["trace_real_001"],
                "source_evidence_ids": ["span_real_001"],
                "source_finding_types": ["unauthorized_dangerous_tool_execution"],
                "rationale": "Use the blocker traces for future eval coverage.",
                "review_instructions": "Confirm the traces are representative.",
                "conversion_guidance": "Convert into a future release control or eval case.",
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
        "annotation_recommendations": [
            {
                "recommendation_id": "annotation_recommendation.policy_preflight_missing.01",
                "source_trace_ids": ["trace_real_002"],
                "source_evidence_ids": ["span_real_002"],
                "source_finding_types": ["policy_preflight_missing"],
                "rationale": "Add a consistent reviewer annotation for this warning family.",
                "review_instructions": "Check whether the missing preflight is real or telemetry noise.",
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
        "future_control_candidates": [
            {
                "candidate_id": "future_control_candidate.unauthorized_dangerous_tool_execution.01",
                "source_trace_ids": ["trace_real_001"],
                "source_evidence_ids": ["span_real_001"],
                "source_finding_types": ["unauthorized_dangerous_tool_execution"],
                "rationale": "The blocker pattern is stable enough for a future control proposal.",
                "review_instructions": "Validate the blocker pattern before adding any new control.",
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
        "duplicate_or_noise": [
            {
                "group_id": "duplicate_or_noise.policy_preflight_missing.01",
                "source_trace_ids": ["trace_real_002"],
                "source_evidence_ids": ["span_real_002"],
                "rationale": "The warning evidence is repetitive and likely one telemetry family.",
                "recommended_action": "merge_similar_examples",
                "requires_human_review": False,
            }
        ],
    }

    validated = validate_dataset_planner_results(results, agent_review_input)

    assert validated["status"] == "candidates_found"
    assert validated["validation"]["trusted"] is True
    assert validated["validation"]["validated_dataset_candidates"] == 1
    assert validated["validation"]["validated_annotation_recommendations"] == 1
    assert validated["validation"]["validated_future_control_candidates"] == 1
    assert validated["validation"]["validated_duplicate_or_noise"] == 1
    assert validated["annotation_recommendations"][0]["recommendation_id"].startswith(
        "annotation_recommendation."
    )
    assert validated["future_control_candidates"][0]["candidate_id"].startswith(
        "future_control_candidate."
    )
    assert validated["duplicate_or_noise"][0]["group_id"].startswith("duplicate_or_noise.")


def test_dataset_planner_validation_rejects_warning_only_future_control_candidate() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_002",
                "finding_types": ["policy_preflight_missing"],
                "spans": [{"span_id": "span_real_002"}],
            }
        ]
    }
    results = {
        "status": "candidates_found",
        "future_control_candidates": [
            {
                "candidate_id": "future_control_candidate.policy_preflight_missing.01",
                "source_trace_ids": ["trace_real_002"],
                "source_evidence_ids": ["span_real_002"],
                "source_finding_types": ["policy_preflight_missing"],
                "rationale": "Promote the warning family directly into a blocker future control.",
                "review_instructions": "Review and add the control.",
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
    }

    validated = validate_dataset_planner_results(results, agent_review_input)

    assert validated["status"] == "invalid"
    assert validated["future_control_candidates"] == []
    assert (
        "future control candidates require critical blocker evidence "
        "for future_control_candidate.policy_preflight_missing.01"
    ) in validated["validation"]["errors"]


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
    assert validated["validation"]["schema_errors"] == ["missing example_traces"]
    assert validated["validation"]["reference_errors"] == []


def test_pattern_finder_validation_rejects_warning_missing_rationale() -> None:
    agent_review_input = {
        "trace_evidence": [
            {
                "trace_id": "trace_real_001",
                "spans": [{"span_id": "span_real_001"}],
            }
        ]
    }
    results = {
        "status": "no_action",
        "summary": "Only warning observations were returned.",
        "failure_patterns": [],
        "warning_observations": [
            {
                "observation_id": "warning.policy_preflight_missing",
                "title": "Policy preflight missing",
                "severity": "warning",
                "problem_summary": "A dangerous tool ran without a matching preflight span.",
                "why_it_matters": "",
                "policy_runtime_mismatch": "Runtime showed dangerous activity, but no preflight span.",
                "supporting_trace_ids": ["trace_real_001"],
                "supporting_evidence_ids": ["span_real_001"],
                "example_traces": [{"trace_id": "trace_real_001"}],
            }
        ],
    }

    validated = validate_pattern_finder_results(results, agent_review_input)

    assert validated["status"] == "invalid"
    assert validated["warning_observations"] == []
    assert validated["validation"]["trusted"] is False
    assert "missing why_it_matters" in validated["validation"]["errors"]


def test_release_check_keeps_deterministic_verdict_when_pattern_finder_output_is_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    def invalid_pattern_results(**_: object) -> dict[str, object]:
        return {
            "agent": "pattern_finder",
            "status": "patterns_found",
            "summary": "Broken output",
            "failure_patterns": [
                {
                    "pattern_id": "pattern.unauthorized_dangerous_tool_execution",
                    "supporting_trace_ids": ["trace_fake_999"],
                    "supporting_evidence_ids": ["span_fake_999"],
                    "example_traces": [{"trace_id": "trace_fake_999"}],
                }
            ],
        }

    monkeypatch.setattr(
        "backend.agentgate.release.agentic_review._pattern_finder_results",
        invalid_pattern_results,
    )

    result = run_release_check(evidence, output_dir, agentic_review_enabled=True)
    decision = _read_json(output_dir / "release_decision.json")
    pattern_results = _read_json(output_dir / "pattern_finder_results.json")
    dataset_results = _read_json(output_dir / "dataset_planner_results.json")
    html = (output_dir / "release_report.html").read_text(encoding="utf-8")

    assert result["decision"] == "BLOCKED"
    assert decision["decision"] == "BLOCKED"
    assert decision["agentic_review"]["status"] == "partial_failure"
    assert all(
        "agentic review" not in str(reason).lower() for reason in decision["decision_reasons"]
    )
    assert pattern_results["status"] == "invalid"
    assert pattern_results["validation"]["trusted"] is False
    assert pattern_results["validation"]["reference_errors"]
    assert dataset_results["status"] == "candidates_found"
    assert dataset_results["validation"]["trusted"] is True
    assert "Pattern Finder failed validation and was not trusted." in html


def test_release_check_records_partial_agent_failure_without_corrupting_other_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    def fail_dataset_planner(**_: object) -> dict[str, object]:
        raise RuntimeError("dataset planner schema parse failed")

    monkeypatch.setattr(
        "backend.agentgate.release.agentic_review._dataset_planner_results",
        fail_dataset_planner,
    )

    result = run_release_check(evidence, output_dir, agentic_review_enabled=True)
    decision = _read_json(output_dir / "release_decision.json")
    pattern_results = _read_json(output_dir / "pattern_finder_results.json")
    dataset_results = _read_json(output_dir / "dataset_planner_results.json")
    html = (output_dir / "release_report.html").read_text(encoding="utf-8")

    assert result["decision"] == "BLOCKED"
    assert decision["decision"] == "BLOCKED"
    assert decision["agentic_review"]["status"] == "partial_failure"
    assert pattern_results["status"] == "patterns_found"
    assert pattern_results["validation"]["trusted"] is True
    assert dataset_results["status"] == "failed"
    assert dataset_results["failure"]["failure_mode"] == "agent_execution_failed"
    assert "dataset planner schema parse failed" in dataset_results["failure"]["message"]
    assert dataset_results["validation"]["trusted"] is False
    assert "Dataset Planner failed; deterministic release decision still used metrics and policy."
    assert (
        "Dataset Planner failed; deterministic release decision still used metrics and policy."
        in html
    )


def test_agent_review_no_action_for_approved_release_without_warning_evidence(
    tmp_path: Path,
) -> None:
    config = ReleaseCheckConfig()
    pack = config.load_pack()
    records = load_evidence_jsonl(_seed("v2.1", tmp_path))

    artifacts = build_agent_review_artifacts(
        base={
            "schema_version": "day4.metrics.v1",
            "agent_id": "stability_ops_ai",
            "agent_version": "v2.1",
        },
        pack=pack,
        records=records,
        evidence_source={
            "type": "local_jsonl",
            "dangerous_trace_ids": [],
            "dangerous_traces": [],
            "coverage": {"span_count": 1},
        },
        dangerous_sessions={
            "critical_findings": [],
            "indeterminate_findings": [],
            "reviewed_safe": [],
            "high_risk_activity_log": [],
        },
        metrics_summary={
            "metrics": [
                {
                    "name": "technical_tool_success_rate",
                    "passes_threshold": True,
                    "decision_impact": "warning",
                },
                {
                    "name": "crash_analysis_format_compliance",
                    "passes_threshold": True,
                    "decision_impact": "warning",
                },
            ]
        },
        gate_binding=pack.load_gate_binding(),
    )

    assert artifacts["agent_review_input"]["agent_review"]["status"] == "no_action"
    assert artifacts["agent_review_input"]["trace_evidence"] == []
    assert artifacts["pattern_finder_results"]["status"] == "no_action"
    assert artifacts["pattern_finder_results"]["warning_observations"] == []
    assert artifacts["dataset_planner_results"]["status"] == "no_action"
    assert artifacts["dataset_planner_results"]["dataset_candidates"] == []
    assert artifacts["dataset_planner_results"]["annotation_recommendations"] == []
    assert artifacts["dataset_planner_results"]["future_control_candidates"] == []


def test_agent_review_input_sanitizes_non_evidence_raw_fields(tmp_path: Path) -> None:
    config = ReleaseCheckConfig()
    pack = config.load_pack()
    records = load_evidence_jsonl(_seed("v2", tmp_path))
    dangerous_sessions = {
        "critical_findings": [
            {
                "trace_id": "trace_001",
                "case_id": "case_001",
                "user_role": "ops_viewer",
                "input_text": "Investigate the issue.",
                "finding_type": "unauthorized_dangerous_tool_execution",
                "severity": "critical",
                "evidence_ids": ["span_policy"],
                "attributes": {
                    "tool_name": "deep_investigate_alert",
                    "expected_allowed": False,
                    "actual_allowed": True,
                    "expected_intent_id": "ops.incident_recent_logs",
                    "selected_intent_id": "ops.alert_deep_investigation",
                },
            }
        ],
        "indeterminate_findings": [],
        "reviewed_safe": [],
        "high_risk_activity_log": [],
    }
    artifacts = build_agent_review_artifacts(
        base={
            "schema_version": "day4.metrics.v1",
            "agent_id": "stability_ops_ai",
            "agent_version": "v2",
        },
        pack=pack,
        records=records,
        evidence_source={
            "type": "phoenix_mcp",
            "dangerous_trace_ids": ["trace_001"],
            "dangerous_traces": [
                {
                    "trace_id": "trace_001",
                    "spans": [
                        {
                            "id": "span_policy",
                            "name": "policy_preflight.deep_investigate_alert",
                            "status": "ok",
                            "attributes": {
                                "tool_name": "deep_investigate_alert",
                                "expected_allowed": False,
                                "actual_allowed": True,
                                "selected_intent_id": "ops.alert_deep_investigation",
                                "expected_intent_id": "ops.incident_recent_logs",
                                "tool.args": "{\"raw\": true}",
                                "llm.prompt": "very long prompt",
                                "openinference.input": "raw provider payload",
                            },
                        }
                    ],
                }
            ],
            "coverage": {"span_count": 1},
        },
        dangerous_sessions=dangerous_sessions,
        metrics_summary={"metrics": []},
        gate_binding=pack.load_gate_binding(),
    )

    span = artifacts["agent_review_input"]["trace_evidence"][0]["spans"][0]

    assert "tool.args" not in span["attributes"]
    assert "llm.prompt" not in span["attributes"]
    assert "openinference.input" not in span["attributes"]
    assert span["attributes"]["tool_name"] == "deep_investigate_alert"
    assert span["attributes"]["actual_allowed"] is True


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


def test_release_report_includes_bounded_dataset_planner_queue_cards(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir, agentic_review_enabled=True)
    _rewrite_json(
        output_dir / "dataset_planner_results.json",
        lambda payload: payload.update(
            {
                "annotation_recommendations": [
                    {
                        "recommendation_id": "annotation_recommendation.policy_preflight_missing.01",
                        "source_trace_ids": ["trace_008"],
                        "source_evidence_ids": ["span_008_policy"],
                        "source_finding_types": ["policy_preflight_missing"],
                        "rationale": "Add reviewer guidance for missing preflight warnings.",
                        "review_instructions": "Check whether this is a telemetry gap or real policy issue.",
                        "requires_human_review": True,
                        "review_status": "pending_review",
                    }
                ],
                "future_control_candidates": [
                    {
                        "candidate_id": "future_control_candidate.unauthorized_dangerous_tool_execution.01",
                        "source_trace_ids": ["trace_008"],
                        "source_evidence_ids": ["span_008_policy"],
                        "source_finding_types": ["unauthorized_dangerous_tool_execution"],
                        "rationale": "The blocker family is stable enough for future control review.",
                        "review_instructions": "Confirm blocker severity before adding a future control.",
                        "requires_human_review": True,
                        "review_status": "pending_review",
                    }
                ],
                "duplicate_or_noise": [
                    {
                        "group_id": "duplicate_or_noise.policy_preflight_missing.01",
                        "source_trace_ids": ["trace_010"],
                        "source_evidence_ids": ["span_010_tool"],
                        "rationale": "Similar warnings should be merged before dataset work.",
                        "recommended_action": "merge_similar_examples",
                        "requires_human_review": False,
                    }
                ],
            }
        ),
    )
    render_standalone_release_report_html(output_dir)
    html = (output_dir / "release_report.html").read_text(encoding="utf-8")
    context = build_report_context(output_dir)
    visible_cards = context["agent_review"]["dataset_planner"]["visible_candidate_cards"]
    agent_review_chunk = html.split('id="agent-review"', 1)[1].split('id="evidence-summary"', 1)[0]

    assert len(visible_cards) == 3
    assert agent_review_chunk.count("agent-review-planner-card") == 3
    assert visible_cards[0]["candidate_type"] == "Future control candidate"
    assert "Approve / reject candidate" in html
    assert "Review candidate" in html
    assert ">Details</summary>" in html
    assert "dataset_planner_results.json" in html
    assert "duplicate_or_noise.policy_preflight_missing.01" not in html


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
