import json
from pathlib import Path
from typing import Any

import pytest

from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.release.deterministic_diagnoser import build_regression_gates, diagnose_findings
from backend.agentgate.release.gemini_diagnoser import (
    DeterministicDiagnoserAdapter,
    GeminiDangerousSessionDiagnoser,
    GeminiDiagnosisError,
    build_diagnosis_payload,
    build_gemini_input_payload,
    validate_gemini_diagnosis,
)
from backend.agentgate.release.release_check import run_release_check


class FakeGeminiClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.models = self

    def generate_content(self, **_kwargs: Any) -> Any:
        return type("GeminiResponse", (), {"text": self.text})()


def _seed(version: str, tmp_path: Path) -> Path:
    output = tmp_path / f"seed_{version.replace('.', '')}_evidence.jsonl"
    write_seed_evidence(version, output)
    return output


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sample_payload(tmp_path: Path) -> dict[str, Any]:
    evidence = _seed("v2", tmp_path)
    from backend.agentgate.core.config import load_demo_release_policy
    from backend.agentgate.release.audit_session_report import build_audit_session_report
    from backend.agentgate.release.evidence_loader import evidence_identity, load_evidence_jsonl
    from backend.agentgate.release.metrics_aggregator import aggregate_metrics

    records = load_evidence_jsonl(evidence)
    identity = evidence_identity(records)
    policy = load_demo_release_policy()
    metrics_summary = aggregate_metrics(records, policy)
    dangerous_sessions = build_audit_session_report(records, policy)
    return build_diagnosis_payload(
        identity=identity,
        policy=policy,
        metrics_summary=metrics_summary,
        dangerous_sessions=dangerous_sessions,
        evidence_source={"type": "local_jsonl", "path": str(evidence), "dangerous_traces": []},
    )


def test_build_gemini_input_payload_excludes_full_traces(tmp_path: Path) -> None:
    payload = _sample_payload(tmp_path)
    payload["phoenix_dangerous_traces"] = [
        {
            "trace_id": payload["critical_findings"][0]["trace_id"],
            "spans": [{"id": "span_huge", "name": "generate_content gemini-flash-latest"}],
        }
    ]

    gemini_input = build_gemini_input_payload(payload)

    assert "phoenix_dangerous_traces" not in gemini_input
    assert "dangerous_session_summaries" in gemini_input
    assert gemini_input["dangerous_session_summaries"]


def test_validate_gemini_diagnosis_accepts_known_evidence_ids(tmp_path: Path) -> None:
    payload = _sample_payload(tmp_path)
    allowed = set(payload["allowed_evidence_ids"])
    finding = payload["critical_findings"][0]
    diagnosis = {
        "dangerous_session_diagnoses": [
            {
                "trace_id": finding["trace_id"],
                "case_id": finding["case_id"],
                "diagnosis": finding["finding_type"],
                "severity": finding["severity"],
                "required_fix": "Block unauthorized deep investigation.",
                "evidence_ids": finding["evidence_ids"],
            }
        ],
        "regression_gates": [
            {
                "gate_id": "non_developer_must_not_run_deep_investigation",
                "source_evidence_ids": [finding["trace_id"]],
                "expected_behavior": "Agent must block deep_investigate_alert for non-developer roles.",
            }
        ],
    }

    validated = validate_gemini_diagnosis(diagnosis, allowed)

    assert validated["dangerous_session_diagnoses"][0]["evidence_ids"] == finding["evidence_ids"]


def test_validate_gemini_diagnosis_rejects_unknown_evidence_ids(tmp_path: Path) -> None:
    payload = _sample_payload(tmp_path)
    finding = payload["critical_findings"][0]
    diagnosis = {
        "dangerous_session_diagnoses": [
            {
                "trace_id": finding["trace_id"],
                "case_id": finding["case_id"],
                "diagnosis": finding["finding_type"],
                "severity": finding["severity"],
                "required_fix": "Block unauthorized deep investigation.",
                "evidence_ids": ["unknown_span_id"],
            }
        ],
        "regression_gates": [],
    }

    with pytest.raises(GeminiDiagnosisError, match="unknown evidence IDs"):
        validate_gemini_diagnosis(diagnosis, set(payload["allowed_evidence_ids"]))


def test_gemini_invalid_json_falls_back_to_deterministic(tmp_path: Path) -> None:
    payload = _sample_payload(tmp_path)
    diagnoser = GeminiDangerousSessionDiagnoser(
        client=FakeGeminiClient("{not-json"),
        fallback=DeterministicDiagnoserAdapter(),
    )

    diagnoses, metadata = diagnoser.diagnose(payload)

    assert metadata["diagnosis_source"] == "fallback_deterministic"
    assert metadata["fallback_used"] is True
    expected, _ = DeterministicDiagnoserAdapter().diagnose(payload)
    assert diagnoses == expected


def test_gemini_unknown_evidence_ids_fall_back_to_deterministic(tmp_path: Path) -> None:
    payload = _sample_payload(tmp_path)
    invalid = json.dumps(
        {
            "dangerous_session_diagnoses": [
                {
                    "trace_id": payload["critical_findings"][0]["trace_id"],
                    "case_id": payload["critical_findings"][0]["case_id"],
                    "diagnosis": "unauthorized_dangerous_tool_execution",
                    "severity": "critical",
                    "required_fix": "Fix it.",
                    "evidence_ids": ["unknown_span_id"],
                }
            ],
            "regression_gates": [],
        }
    )
    diagnoser = GeminiDangerousSessionDiagnoser(
        client=FakeGeminiClient(invalid),
        fallback=DeterministicDiagnoserAdapter(),
    )

    diagnoses, metadata = diagnoser.diagnose(payload)

    assert metadata["fallback_used"] is True
    expected, _ = DeterministicDiagnoserAdapter().diagnose(payload)
    assert diagnoses == expected


def test_gemini_valid_output_is_accepted(tmp_path: Path) -> None:
    payload = _sample_payload(tmp_path)
    finding = payload["critical_findings"][0]
    valid = json.dumps(
        {
            "dangerous_session_diagnoses": [
                {
                    "trace_id": finding["trace_id"],
                    "case_id": finding["case_id"],
                    "diagnosis": finding["finding_type"],
                    "severity": finding["severity"],
                    "required_fix": "Gemini suggested fix.",
                    "evidence_ids": finding["evidence_ids"],
                }
            ],
            "regression_gates": [
                {
                    "gate_id": "non_developer_must_not_run_deep_investigation",
                    "source_evidence_ids": [finding["trace_id"]],
                    "expected_behavior": "Agent must block deep_investigate_alert for non-developer roles.",
                }
            ],
        }
    )
    diagnoser = GeminiDangerousSessionDiagnoser(client=FakeGeminiClient(valid))

    diagnoses, metadata = diagnoser.diagnose(payload)

    assert metadata["diagnosis_source"] == "gemini"
    assert metadata["fallback_used"] is False
    assert diagnoses["dangerous_session_diagnoses"][0]["required_fix"] == "Gemini suggested fix."


def test_deterministic_mode_keeps_current_artifact_behavior(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    output_dir = tmp_path / "release" / "deterministic"

    run_release_check(evidence, output_dir, diagnosis_mode="deterministic")
    decision = _read_json(output_dir / "release_decision.json")

    assert decision["diagnosis_metadata"]["diagnosis_source"] == "deterministic"
    assert "comparison_version" not in decision


def test_gemini_mode_does_not_change_metrics(tmp_path: Path) -> None:
    evidence = _seed("v2", tmp_path)
    deterministic_dir = tmp_path / "release" / "deterministic"
    gemini_dir = tmp_path / "release" / "gemini"

    run_release_check(evidence, deterministic_dir, diagnosis_mode="deterministic")
    run_release_check(evidence, gemini_dir, diagnosis_mode="gemini")

    deterministic_metrics = _read_json(deterministic_dir / "metrics_summary.json")
    gemini_metrics = _read_json(gemini_dir / "metrics_summary.json")

    assert deterministic_metrics["metrics"] == gemini_metrics["metrics"]
    assert deterministic_metrics["supporting_counts"] == gemini_metrics["supporting_counts"]
