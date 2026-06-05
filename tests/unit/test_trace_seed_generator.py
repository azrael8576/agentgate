import json
from pathlib import Path

from backend.agentgate.cli import app
from backend.agentgate.demo.trace_seed_generator import generate_seed_records
from typer.testing import CliRunner


def _records(version: str) -> list[dict]:
    return [record.model_dump(mode="json") for record in generate_seed_records(version)]


def test_v2_seed_contains_production_agent_evidence_span_types() -> None:
    event_types = {
        record["event_type"] for record in _records("v2") if record["record_type"] == "span_event"
    }

    assert "router.intent_classification" in event_types
    assert "answer.static" in event_types
    assert "policy_preflight.deep_investigate_alert" in event_types
    assert "tool.deep_investigate_alert" in event_types


def test_v2_seed_contains_unauthorized_dangerous_tool_attempt() -> None:
    records = _records("v2")

    assert any(
        record["record_type"] == "span_event"
        and record["event_type"] == "policy_preflight.deep_investigate_alert"
        and record["case_id"].startswith("case_unauth_deep")
        and record["attributes"]["expected_allowed"] is False
        and record["attributes"]["actual_allowed"] is True
        for record in records
    )
    assert any(
        record["record_type"] == "span_event"
        and record["event_type"] == "tool.deep_investigate_alert"
        and record["case_id"].startswith("case_unauth_deep")
        for record in records
    )


def test_v2_seed_contains_raw_event_dump() -> None:
    records = _records("v2")

    assert any(
        record["record_type"] == "span_event"
        and record["event_type"] == "tool.deep_investigate_alert"
        and record["attributes"]["raw_event_dumped"] is True
        for record in records
    )


def test_v2_seed_contains_misroute_to_dangerous_tool() -> None:
    records = _records("v2")

    assert any(
        record["record_type"] == "span_event"
        and record["event_type"] == "router.intent_classification"
        and record["case_id"].startswith("case_misroute_dangerous")
        and record["attributes"]["expected_intent_id"] == "ops.incident_recent_logs"
        and record["attributes"]["selected_intent_id"] == "ops.alert_deep_investigation"
        and record["attributes"]["misroute_to_dangerous_tool"] is True
        for record in records
    )


def test_v21_seed_blocks_unauthorized_tool_execution() -> None:
    records = _records("v2.1")

    assert any(
        record["record_type"] == "span_event"
        and record["event_type"] == "policy_preflight.deep_investigate_alert"
        and record["case_id"].startswith("case_unauth_deep")
        and record["status"] == "blocked"
        and record["attributes"]["actual_allowed"] is False
        for record in records
    )
    assert not any(
        record["record_type"] == "span_event"
        and record["event_type"] == "tool.deep_investigate_alert"
        and record["case_id"].startswith("case_unauth_deep")
        for record in records
    )


def test_v21_seed_disables_raw_dumps() -> None:
    records = _records("v2.1")

    assert not any(
        record["record_type"] == "span_event"
        and record.get("attributes", {}).get("raw_event_dumped") is True
        for record in records
    )


def test_v21_seed_includes_warning_only_variance() -> None:
    records = _records("v2.1")

    warning_tool_spans = [
        record
        for record in records
        if record["record_type"] == "span_event"
        and record["event_type"] == "tool.analyze_public_ticker_news"
        and record["attributes"]["tool.success"] is False
    ]
    warning_format_labels = [
        record
        for record in records
        if record["record_type"] == "eval_label"
        and record["label_name"] == "response_format_ok"
        and record["label_value"] is False
    ]

    assert len(warning_tool_spans) == 1
    assert warning_tool_spans[0]["attributes"]["tool.error_code"] == "TRANSIENT_TIMEOUT"
    assert {record["case_id"] for record in warning_format_labels} == {"case_alert_bad_format_001"}
    assert len(warning_format_labels) == 4
    assert not any(
        record["record_type"] == "eval_label"
        and record["label_name"] == "sensitive_output_ok"
        and record["label_value"] is False
        for record in records
    )


def test_seed_records_do_not_emit_dev_mode_evidence() -> None:
    for version in ("v2", "v2.1"):
        records = _records(version)

        assert not any(
            "dev_mode" in key
            for record in records
            for key in record.get("attributes", {}) | record.get("metadata", {})
        )
        assert not any(
            record["record_type"] == "eval_label" and record["label_name"] == "dev_mode_enabled"
            for record in records
        )


def test_v21_seed_does_not_escalate_ambiguous_questions() -> None:
    records = _records("v2.1")

    assert all(
        record["attributes"]["selected_intent_id"] == "ops.incident_recent_logs"
        for record in records
        if record["record_type"] == "span_event"
        and record["event_type"] == "router.intent_classification"
        and record["case_id"].startswith("case_misroute_dangerous")
    )


def test_seed_records_include_phoenix_llm_judge_groundedness_labels() -> None:
    records = _records("v2")

    groundedness_labels = [
        record
        for record in records
        if record["record_type"] == "eval_label" and record["label_name"] == "groundedness"
    ]

    assert groundedness_labels
    assert any(record["label_value"] == "fail" for record in groundedness_labels)
    assert all(record["metadata"]["judge_type"] == "llm_as_judge" for record in groundedness_labels)
    assert all(record["metadata"]["human_labeled"] is False for record in groundedness_labels)


def test_seed_records_include_sql_safety_attributes() -> None:
    records = _records("v2")

    assert any(
        record["record_type"] == "span_event"
        and record["event_type"] == "policy_preflight.deep_investigate_alert"
        and "sql_safety.classification" in record["attributes"]
        and "sql_safety.read_only" in record["attributes"]
        for record in records
    )


def test_cli_seed_v2_and_v21_write_jsonl(tmp_path: Path) -> None:
    runner = CliRunner()
    v2_output = tmp_path / "seed_v2_evidence.jsonl"
    v21_output = tmp_path / "seed_v21_evidence.jsonl"

    v2_result = runner.invoke(app, ["demo", "seed-v2", "--output", str(v2_output)])
    v21_result = runner.invoke(app, ["demo", "seed-v21", "--output", str(v21_output)])

    assert v2_result.exit_code == 0
    assert v21_result.exit_code == 0
    assert v2_output.exists()
    assert v21_output.exists()
    assert (
        json.loads(v2_output.read_text(encoding="utf-8").splitlines()[0])["record_type"]
        == "span_event"
    )
    assert (
        json.loads(v21_output.read_text(encoding="utf-8").splitlines()[0])["agent_version"]
        == "v2.1"
    )
