from dataclasses import dataclass, field
from typing import Any

from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.schemas.evidence import SpanEvent, SpanAttributeValue
from backend.agentgate.release.evidence_loader import EvidenceRecord, group_records_by_trace

AttributeValue = str | int | float | bool


@dataclass(frozen=True)
class EvalEventPlan:
    name: str
    attributes: dict[str, AttributeValue]


@dataclass
class SpanReplayPlan:
    name: str
    attributes: dict[str, AttributeValue]
    events: list[EvalEventPlan] = field(default_factory=list)
    children: list["SpanReplayPlan"] = field(default_factory=list)


@dataclass(frozen=True)
class TraceReplayPlan:
    trace_id: str
    root_spans: list[SpanReplayPlan]


def build_replay_plan(records: list[EvidenceRecord]) -> list[TraceReplayPlan]:
    plans: list[TraceReplayPlan] = []
    for trace_id, trace_records in group_records_by_trace(records).items():
        spans = [record for record in trace_records if isinstance(record, SpanEvent)]
        labels = [record for record in trace_records if isinstance(record, EvalLabel)]
        root_spans = _build_span_tree(spans)
        if root_spans and labels:
            root_spans[0].events.extend(_eval_events(labels))
        plans.append(TraceReplayPlan(trace_id=trace_id, root_spans=root_spans))
    return plans


def span_attributes(span: SpanEvent) -> dict[str, AttributeValue]:
    attrs: dict[str, AttributeValue] = {
        "evidence.trace_id": span.trace_id,
        "evidence.span_id": span.span_id,
        "evidence.case_id": span.case_id,
        "agent.id": span.agent_id,
        "agent.version": span.agent_version,
        "release.candidate": f"{span.agent_id}_{span.agent_version}",
        "session.id": span.trace_id,
        "user.role": span.user_role,
        "input.text": span.input_text,
        "test.case_id": span.case_id,
        "span.status": span.status,
        "span.name": span.span_name,
    }
    if span.parent_span_id is not None:
        attrs["evidence.parent_span_id"] = span.parent_span_id

    attrs.update(_original_attributes(span.attributes))
    attrs.update(_normalized_event_attributes(span))
    return attrs


def _build_span_tree(spans: list[SpanEvent]) -> list[SpanReplayPlan]:
    by_span_id = {
        span.span_id: SpanReplayPlan(name=span.span_name, attributes=span_attributes(span))
        for span in spans
    }
    roots: list[SpanReplayPlan] = []
    for span in spans:
        plan = by_span_id[span.span_id]
        if span.parent_span_id and span.parent_span_id in by_span_id:
            by_span_id[span.parent_span_id].children.append(plan)
        else:
            roots.append(plan)
    return roots


def _original_attributes(attributes: dict[str, SpanAttributeValue]) -> dict[str, AttributeValue]:
    return {
        f"evidence.attribute.{key}": value
        for key, value in attributes.items()
        if _is_supported_attribute_value(value)
    }


def _normalized_event_attributes(span: SpanEvent) -> dict[str, AttributeValue]:
    raw = span.attributes
    if span.event_type == "router.intent_classification":
        expected = raw.get("expected_intent_id")
        selected = raw.get("selected_intent_id")
        attrs = {
            "expected.intent_id": expected,
            "router.selected_intent_id": selected,
            "router.correct": expected == selected,
            "router.confidence": raw.get("confidence"),
            "router.misroute_to_dangerous_tool": raw.get("misroute_to_dangerous_tool"),
            "security.attack_type": raw.get("attack_type"),
        }
    elif span.event_type == "answer.static":
        attrs = {
            "intent.id": raw.get("intent_id"),
            "route.type": raw.get("answer_route"),
            "answer.source": "intent_table",
            "answer.version": "intent_table_v1",
        }
    elif span.event_type.startswith("policy_preflight."):
        actual_allowed = raw.get("actual_allowed")
        attrs = {
            "intent.id": raw.get("intent_id"),
            "tool.name": raw.get("tool_name"),
            "tool.risk_level": raw.get("risk_level"),
            "policy.id": raw.get("policy.id") or raw.get("policy_id"),
            "policy.preflight.required": True,
            "policy.preflight.decision": "ALLOW" if actual_allowed is True else "DENY",
            "policy.violation": raw.get("expected_allowed") != actual_allowed,
            "policy.violation.reason": raw.get("block_reason"),
            "sql.query.safe": raw.get("sql_safety.classification") != "unsafe_policy_bypass",
            "sql.query.type": raw.get("sql_safety.classification"),
            "sql.has_limit": raw.get("sql_safety.row_limit") is not None,
            "sql.limit": raw.get("sql_safety.row_limit"),
            "sql.query_template_id": raw.get("sql_safety.template_id"),
        }
    elif span.event_type.startswith("tool."):
        attrs = {
            "span.kind": "TOOL",
            "tool.name": raw.get("tool_name"),
            "tool.risk_level": raw.get("risk_level", "high"),
            "tool.query_backend": "bigquery" if "sql_safety.classification" in raw else "local_descriptor",
            "tool.limit": raw.get("sql_safety.row_limit"),
            "sql.query.type": raw.get("sql_safety.classification"),
            "sql.has_limit": raw.get("sql_safety.row_limit") is not None,
            "sql.limit": raw.get("sql_safety.row_limit"),
            "sql.query_template_id": raw.get("sql_safety.query_template_id"),
            "response.sensitive_output_violation": raw.get("raw_event_dumped") is True,
        }
    else:
        attrs = {}

    return {
        key: value
        for key, value in attrs.items()
        if _is_supported_attribute_value(value)
    }


def _eval_events(labels: list[EvalLabel]) -> list[EvalEventPlan]:
    return [
        EvalEventPlan(
            name=f"eval.{label.label_name}",
            attributes={
                key: value
                for key, value in {
                    "evidence.trace_id": label.trace_id,
                    "evidence.case_id": label.case_id,
                    "agent.id": label.agent_id,
                    "agent.version": label.agent_version,
                    "user.role": label.user_role,
                    "eval.evaluator": label.evaluator,
                    "eval.label_name": label.label_name,
                    "eval.label_value": label.label_value,
                    "eval.rationale": label.rationale,
                    **{
                        f"eval.metadata.{metadata_key}": metadata_value
                        for metadata_key, metadata_value in label.metadata.items()
                    },
                }.items()
                if _is_supported_attribute_value(value)
            },
        )
        for label in labels
    ]


def _is_supported_attribute_value(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and value is not None
