from pathlib import Path
from typing import Any

from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.schemas.evidence import SpanEvent
from backend.agentgate.release.evidence_loader import evidence_identity, load_evidence_jsonl
from backend.agentgate.telemetry.phoenix_setup import register_phoenix_tracer
from backend.agentgate.telemetry.span_mapper import SpanReplayPlan, build_replay_plan


def replay_evidence_to_phoenix(
    evidence_path: Path,
    service_name: str | None = None,
) -> dict[str, Any]:
    resolved_service_name = service_name
    if not resolved_service_name:
        records = load_evidence_jsonl(evidence_path)
        identity = evidence_identity(records)
        resolved_service_name = str(identity.get("agent_id") or "unknown")
    tracer, config = register_phoenix_tracer(resolved_service_name)
    return replay_evidence(evidence_path=evidence_path, tracer=tracer, project_name=config.project_name)


def replay_evidence(evidence_path: Path, tracer: Any, project_name: str) -> dict[str, Any]:
    records = load_evidence_jsonl(evidence_path)
    identity = evidence_identity(records)
    plans = build_replay_plan(records)

    for trace_plan in plans:
        for root_span in trace_plan.root_spans:
            _replay_span(tracer, root_span)

    return {
        **identity,
        "phoenix_project_name": project_name,
        "span_events": sum(isinstance(record, SpanEvent) for record in records),
        "eval_labels": sum(isinstance(record, EvalLabel) for record in records),
    }


def _replay_span(tracer: Any, span_plan: SpanReplayPlan) -> None:
    with tracer.start_as_current_span(span_plan.name) as span:
        for key, value in span_plan.attributes.items():
            span.set_attribute(key, value)
        for event in span_plan.events:
            span.add_event(event.name, event.attributes)
        for child in span_plan.children:
            _replay_span(tracer, child)
