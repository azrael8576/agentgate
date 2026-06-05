import json
from pathlib import Path

from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.release.audit_session_report import build_audit_session_report
from backend.agentgate.release.deterministic_diagnoser import build_regression_gates
from backend.agentgate.release.evidence_loader import load_evidence_jsonl
from backend.agentgate.release.metrics_aggregator import aggregate_metrics
from backend.agentgate.core.config import load_demo_release_policy
from backend.agentgate.release.release_check import run_release_check


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v2_audit_report_includes_activity_log_and_violations(tmp_path: Path) -> None:
    records = load_evidence_jsonl(_seed("v2", tmp_path))
    policy = load_demo_release_policy()
    report = build_audit_session_report(records, policy)

    assert report["critical_findings"]
    assert report["high_risk_activity_log"]
    assert any(entry["verdict"] == "violation" for entry in report["high_risk_activity_log"])
    assert any(entry["verdict"] == "authorized" for entry in report["high_risk_activity_log"])


def test_v21_audit_report_has_authorized_high_risk_activity_only(tmp_path: Path) -> None:
    records = load_evidence_jsonl(_seed("v2.1", tmp_path))
    policy = load_demo_release_policy()
    report = build_audit_session_report(records, policy)

    assert report["critical_findings"] == []
    assert report["indeterminate_findings"] == []
    assert report["high_risk_activity_log"]
    assert all(entry["verdict"] == "authorized" for entry in report["high_risk_activity_log"])


def test_release_check_writes_remediation_controls_for_failed_metrics(tmp_path: Path) -> None:
    output_dir = tmp_path / "release" / "v2"
    run_release_check(_seed("v2", tmp_path), output_dir)

    sessions = _read_json(output_dir / "dangerous_sessions.json")
    gates = _read_json(output_dir / "regression_gates.json")["regression_gates"]

    assert sessions["high_risk_activity_log"]
    assert gates
    assert any(gate["gate_id"] == "critical_tools_must_pass_policy_preflight" for gate in gates)
    assert any(gate["gate_id"] == "non_developer_must_not_run_deep_investigation" for gate in gates)


def test_build_regression_gates_links_failed_controls_to_trace_ids(tmp_path: Path) -> None:
    records = load_evidence_jsonl(_seed("v2", tmp_path))
    policy = load_demo_release_policy()
    metrics_summary = aggregate_metrics(records, policy)
    report = build_audit_session_report(records, policy)

    gates = build_regression_gates(
        critical_findings=report["critical_findings"],
        indeterminate_findings=report["indeterminate_findings"],
        metrics_summary=metrics_summary,
        high_risk_activity_log=report["high_risk_activity_log"],
    )

    policy_gate = next(gate for gate in gates if gate["gate_id"] == "critical_tools_must_pass_policy_preflight")
    assert policy_gate["source_evidence_ids"]
