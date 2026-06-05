import json
from pathlib import Path

from backend.agentgate.cli import app
from backend.agentgate.demo.trace_seed_generator import (
    generate_seed_records,
    write_seed_evidence,
)
from backend.agentgate.release.evidence_loader import load_evidence_jsonl
from backend.agentgate.telemetry.phoenix_setup import (
    PhoenixConfigError,
    load_phoenix_config,
)
from backend.agentgate.telemetry.replay import replay_evidence
from backend.agentgate.telemetry.span_mapper import build_replay_plan, span_attributes
from typer.testing import CliRunner


class FakeSpan:
    def __init__(self, name: str, sink: list[dict]) -> None:
        self.name = name
        self.sink = sink
        self.attributes: dict[str, object] = {}
        self.events: list[dict[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.sink.append(
            {
                "name": self.name,
                "attributes": self.attributes,
                "events": self.events,
            }
        )

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict) -> None:
        self.events.append({"name": name, "attributes": attributes})


class FakeTracer:
    def __init__(self) -> None:
        self.spans: list[dict] = []

    def start_as_current_span(self, name: str) -> FakeSpan:
        return FakeSpan(name, self.spans)


def test_phoenix_config_error_lists_missing_env(monkeypatch) -> None:
    monkeypatch.delenv("PHOENIX_COLLECTOR_ENDPOINT", raising=False)
    monkeypatch.delenv("PHOENIX_API_KEY", raising=False)
    monkeypatch.delenv("PHOENIX_PROJECT_NAME", raising=False)

    try:
        load_phoenix_config()
    except PhoenixConfigError as error:
        message = str(error)
    else:
        raise AssertionError("Expected PhoenixConfigError")

    assert "PHOENIX_COLLECTOR_ENDPOINT" in message
    assert "PHOENIX_API_KEY" in message
    assert "PHOENIX_PROJECT_NAME" in message


def test_span_attributes_normalize_seed_fields_to_prd_names() -> None:
    record = next(
        record
        for record in generate_seed_records("v2")
        if record.record_type == "span_event"
        and record.event_type == "policy_preflight.deep_investigate_alert"
        and record.case_id == "case_unauth_deep_001"
    )

    attrs = span_attributes(record)

    assert attrs["agent.id"] == "stability_ops_ai"
    assert attrs["agent.version"] == "v2"
    assert attrs["user.role"] == "ops_viewer"
    assert attrs["input.text"] == record.input_text
    assert attrs["policy.preflight.required"] is True
    assert attrs["policy.preflight.decision"] == "ALLOW"
    assert attrs["policy.violation"] is True
    assert attrs["sql.query.safe"] is False


def test_replay_plan_preserves_parent_metadata(tmp_path: Path) -> None:
    evidence = tmp_path / "seed_v2_evidence.jsonl"
    write_seed_evidence("v2", evidence)
    records = load_evidence_jsonl(evidence)

    plans = build_replay_plan(records)
    trace = next(plan for plan in plans if plan.trace_id == "trace_v2_case_unauth_deep_001")
    router = trace.root_spans[0]
    policy = router.children[0]
    tool = policy.children[0]

    assert router.name == "router.intent_classification"
    assert policy.name == "policy_preflight.deep_investigate_alert"
    assert policy.attributes["evidence.parent_span_id"] == "span_case_unauth_deep_001_router"
    assert tool.name == "tool.deep_investigate_alert"
    assert tool.attributes["evidence.parent_span_id"] == "span_case_unauth_deep_001_policy"
    assert any(event.name == "eval.policy_compliant" for event in router.events)


def test_replay_evidence_uses_tracer_and_returns_summary(tmp_path: Path) -> None:
    evidence = tmp_path / "seed_v21_evidence.jsonl"
    write_seed_evidence("v2.1", evidence)
    tracer = FakeTracer()

    summary = replay_evidence(evidence, tracer, project_name="agentgate-reference-ops-demo")

    assert summary["agent_version"] == "v2.1"
    assert summary["trace_count"] > 0
    assert summary["span_events"] > 0
    assert summary["eval_labels"] > 0
    assert any(span["name"] == "router.intent_classification" for span in tracer.spans)
    assert any(
        span["attributes"].get("agent.version") == "v2.1" and span["attributes"].get("user.role")
        for span in tracer.spans
    )


def test_cli_telemetry_replay_uses_registered_tracer(monkeypatch, tmp_path: Path) -> None:
    evidence = tmp_path / "seed_v2_evidence.jsonl"
    write_seed_evidence("v2", evidence)
    tracer = FakeTracer()

    class Config:
        project_name = "agentgate-reference-ops-demo"

    monkeypatch.setattr(
        "backend.agentgate.telemetry.replay.register_phoenix_tracer",
        lambda service_name: (tracer, Config()),
    )

    result = CliRunner().invoke(
        app,
        [
            "telemetry",
            "replay",
            "--evidence",
            str(evidence),
            "--service-name",
            "stability_ops_ai",
        ],
    )

    assert result.exit_code == 0
    assert "phoenix_project=agentgate-reference-ops-demo" in result.output
    assert "agent_version=v2" in result.output
    assert tracer.spans


def test_cli_telemetry_replay_fails_for_invalid_jsonl(monkeypatch, tmp_path: Path) -> None:
    evidence = tmp_path / "invalid.jsonl"
    evidence.write_text(json.dumps({"record_type": "unknown"}) + "\n", encoding="utf-8")

    class Config:
        project_name = "agentgate-reference-ops-demo"

    monkeypatch.setattr(
        "backend.agentgate.telemetry.replay.register_phoenix_tracer",
        lambda service_name: (FakeTracer(), Config()),
    )

    result = CliRunner().invoke(app, ["telemetry", "replay", "--evidence", str(evidence)])

    assert result.exit_code == 1
    assert "Unsupported evidence record_type" in result.output
