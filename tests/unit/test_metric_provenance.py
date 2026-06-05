import json
from pathlib import Path

from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.release.release_check import run_release_check


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_validate_suite_required_metrics_maps_contract_names_to_runtime() -> None:
    from backend.agentgate.core.config import load_demo_release_policy
    from backend.agentgate.release.gate_binding import validate_suite_required_metrics

    policy = load_demo_release_policy()
    gate_binding = {
        "metric_bindings": [
            {
                "suite_metric": "unauthorized_dangerous_tool_execution_rate",
                "runtime_metric": "unauthorized_dangerous_tool_attempt_rate",
            },
            {
                "suite_metric": "policy_preflight_mismatch_rate",
                "runtime_metric": "dangerous_tool_policy_violation_rate",
            },
            {
                "suite_metric": "p0_suite_pass_rate",
                "runtime_metric": None,
            },
        ]
    }
    validation = validate_suite_required_metrics(
        [
            "unauthorized_dangerous_tool_execution_rate",
            "policy_preflight_mismatch_rate",
            "p0_suite_pass_rate",
        ],
        policy,
        gate_binding=gate_binding,
    )

    assert validation["contract_valid"] is True
    assert len(validation["blocking_issues"]) == 0
    assert any(check["status"] == "mapped" for check in validation["checks"])
    assert any(check["status"] == "not_implemented" for check in validation["checks"])


def test_release_metrics_include_runtime_provenance_contract(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)
    metrics = _read_json(output_dir / "metrics_summary.json")["metrics"]

    assert metrics
    for metric in metrics:
        assert "numerator" in metric
        assert "denominator" in metric
        assert metric["evaluation_mode"] == "controlled"
        assert metric["sample_tier"] == "demo"
        assert metric["decision_impact"] in {"blocker", "warning", "informational"}
        assert isinstance(metric["grader_ids"], list)
        assert isinstance(metric["evidence_ids"], list)


def test_blocker_metrics_have_grader_and_evidence_source(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)
    metrics = _read_json(output_dir / "metrics_summary.json")["metrics"]
    blockers = [metric for metric in metrics if metric["decision_impact"] == "blocker"]

    assert blockers
    for metric in blockers:
        assert metric["evaluation_mode"] == "controlled"
        assert metric["grader_ids"]
        assert metric["denominator"] > 0
        assert metric["evidence_ids"]


def test_not_available_metric_preserves_unavailable_reason(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "v2"

    run_release_check(evidence, output_dir)
    metrics = _read_json(output_dir / "metrics_summary.json")["metrics"]

    for metric in metrics:
        if metric["status"] == "not_available":
            assert metric["value"] is None
            assert metric["unavailable_reason"]
            assert metric["denominator"] == 0
