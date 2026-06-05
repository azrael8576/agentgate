from backend.agentgate.core.config import load_default_pack_release_policy
from backend.agentgate.core.product_config import load_eval_suite
from backend.agentgate.release.decision_engine import decide_release
from backend.agentgate.release.metrics_aggregator import aggregate_metrics
from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.release.evidence_loader import load_evidence_jsonl
from backend.agentgate.core.agent_pack import get_default_agent_pack
from pathlib import Path

from tests.fixtures.paths import DEMO_SUITE_PATH


def _metrics_and_sessions(version: str, tmp_path: Path) -> tuple[dict, dict, dict]:
    evidence = tmp_path / f"seed_{version}.jsonl"
    write_seed_evidence(version, evidence)
    records = load_evidence_jsonl(evidence)
    pack = get_default_agent_pack()
    policy = load_default_pack_release_policy()
    metrics_summary = aggregate_metrics(
        records,
        policy,
        metric_graders=pack.metric_graders(),
        metric_decision_impact=pack.metric_decision_impact(),
        effective_metrics=pack.effective_metrics,
    )
    dangerous_sessions = {
        "critical_findings": [],
        "reviewed_safe": [],
        "high_risk_activity_log": [],
        "indeterminate_findings": [],
    }
    diagnoses = {"dangerous_session_diagnoses": [], "regression_gates": []}
    return metrics_summary, dangerous_sessions, diagnoses


def test_gate_binding_blocks_only_required_runtime_metrics(tmp_path: Path) -> None:
    metrics_summary, dangerous_sessions, diagnoses = _metrics_and_sessions("v2", tmp_path)
    suite = load_eval_suite(DEMO_SUITE_PATH)
    policy = load_default_pack_release_policy()

    decision = decide_release(
        metrics_summary,
        dangerous_sessions,
        diagnoses,
        policy,
        gate_binding=suite.release_gate_binding,
    )

    assert decision["decision"] == "BLOCKED"
    assert decision["decision_basis"] == "release_gate_binding"
    assert decision["gate_binding"]["gate_id"] == "reference_ops_release_authority_v1"
    assert decision["gate_binding"]["not_implemented_suite_metrics"] == []
    blocked_metrics = {reason["metric"] for reason in decision["decision_reasons"]}
    assert "unauthorized_dangerous_tool_attempt_rate" in blocked_metrics
    assert "dangerous_tool_policy_violation_rate" in blocked_metrics
    assert "sensitive_output_violation_rate" not in blocked_metrics
    assert "intent_routing_accuracy" not in blocked_metrics


def test_gate_binding_approves_when_required_runtime_metrics_pass(tmp_path: Path) -> None:
    metrics_summary, dangerous_sessions, diagnoses = _metrics_and_sessions("v2.1", tmp_path)
    suite = load_eval_suite(DEMO_SUITE_PATH)
    policy = load_default_pack_release_policy()

    decision = decide_release(
        metrics_summary,
        dangerous_sessions,
        diagnoses,
        policy,
        gate_binding=suite.release_gate_binding,
    )

    assert decision["decision"] == "APPROVED"
    assert decision["decision_reasons"] == []
    assert decision["gate_binding"]["runtime_blocker_metrics"] == [
        "unauthorized_dangerous_tool_attempt_rate",
        "dangerous_tool_policy_violation_rate",
    ]


def test_legacy_mode_blocks_all_policy_blockers_when_gate_binding_missing(tmp_path: Path) -> None:
    metrics_summary, dangerous_sessions, diagnoses = _metrics_and_sessions("v2", tmp_path)
    policy = load_default_pack_release_policy()

    decision = decide_release(
        metrics_summary,
        dangerous_sessions,
        diagnoses,
        policy,
        gate_binding=None,
    )

    assert decision["decision"] == "BLOCKED"
    assert decision["decision_basis"] == "deterministic_release_gate"
    assert "gate_binding" not in decision
    blocked_metrics = {reason["metric"] for reason in decision["decision_reasons"]}
    assert "sensitive_output_violation_rate" in blocked_metrics
