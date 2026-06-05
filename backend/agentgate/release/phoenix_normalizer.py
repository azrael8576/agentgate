import json
from pathlib import Path
from typing import Any

from backend.agentgate.core.agent_pack import get_default_agent_pack
from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.evals.annotation_parser import eval_labels_from_span_payloads
from backend.agentgate.release.evidence_backfill import backfill_span_attributes
from backend.agentgate.release.evidence_loader import EvidenceRecord
from backend.agentgate.release.phoenix_span_identity import (
    resolve_otel_span_id,
    resolve_otel_trace_id,
)
from backend.agentgate.schemas.evidence import SpanAttributeValue, SpanEvent


def resolve_supported_span_names(
    supported_span_names: set[str] | None = None,
) -> set[str]:
    if supported_span_names is not None:
        return supported_span_names
    return get_default_agent_pack().supported_span_names()


def load_phoenix_spans_json(
    path: Path,
    *,
    supported_span_names: set[str] | None = None,
) -> list[EvidenceRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalize_phoenix_spans(payload, supported_span_names=supported_span_names)


def normalize_phoenix_spans(
    payload: Any,
    *,
    extra_labels: list[EvalLabel] | None = None,
    supported_span_names: set[str] | None = None,
    dangerous_intent_ids: set[str] | None = None,
) -> list[EvidenceRecord]:
    span_names = resolve_supported_span_names(supported_span_names)
    resolved_dangerous_intents = (
        dangerous_intent_ids
        if dangerous_intent_ids is not None
        else get_default_agent_pack().dangerous_intent_ids()
    )
    spans = _extract_spans(payload)
    records: list[EvidenceRecord] = []
    seen_eval_keys: set[tuple[str, str, str]] = set()
    for span in spans:
        record = _span_to_record(
            span,
            supported_span_names=span_names,
            dangerous_intent_ids=resolved_dangerous_intents,
        )
        if record is not None:
            records.append(record)
        for label in _eval_labels_from_span(span):
            dedupe_key = (label.trace_id, label.label_name, label.case_id)
            if dedupe_key in seen_eval_keys:
                continue
            seen_eval_keys.add(dedupe_key)
            records.append(label)
        for label in eval_labels_from_span_payloads([span]):
            dedupe_key = (label.trace_id, label.label_name, label.case_id)
            if dedupe_key in seen_eval_keys:
                continue
            seen_eval_keys.add(dedupe_key)
            records.append(label)
    if extra_labels:
        for label in extra_labels:
            dedupe_key = (label.trace_id, label.label_name, label.case_id)
            if dedupe_key in seen_eval_keys:
                continue
            seen_eval_keys.add(dedupe_key)
            records.append(label)
    return records


def _extract_spans(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        raise ValueError("Phoenix spans payload must be a JSON object or array.")

    for key in ("spans", "data", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    raise ValueError("Phoenix spans payload does not contain a spans/data/results/items array.")


def _span_to_record(
    span: dict[str, Any],
    *,
    supported_span_names: set[str],
    dangerous_intent_ids: set[str],
) -> SpanEvent | None:
    name = str(span.get("name") or span.get("span_name") or "")
    if name not in supported_span_names:
        return None

    attributes = _normalize_attributes(span.get("attributes", {}))
    normalized = _agentgate_attributes(
        attributes,
        span_name=name,
        dangerous_intent_ids=dangerous_intent_ids,
    )
    trace_id = resolve_otel_trace_id(span)
    span_id = resolve_otel_span_id(span)
    parent_span_id = _first_string(span, "parent_span_id", "parentSpanId", "parent_id", "parentId")

    if trace_id is None or span_id is None:
        raise ValueError(f"Phoenix span {name} is missing trace_id or span_id.")

    status = _record_status(name, span, normalized)
    return SpanEvent(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        case_id=str(
            attributes.get("test.case_id")
            or attributes.get("case_id")
            or attributes.get("session.id")
            or trace_id
        ),
        agent_id=str(attributes.get("agent.id") or attributes.get("agent_id") or "unknown"),
        agent_version=str(
            attributes.get("agent.version") or attributes.get("agent_version") or "unknown"
        ),
        user_role=str(attributes.get("user.role") or attributes.get("user_role") or "unknown"),
        span_name=name,
        event_type=name,
        status=status,
        input_text=str(attributes.get("input.text") or attributes.get("input_text") or ""),
        attributes=normalized,
    )


def _normalize_attributes(raw: Any) -> dict[str, SpanAttributeValue]:
    if isinstance(raw, dict):
        return {
            str(key): value
            for key, value in (
                (_normalize_key(key), _otel_value(value)) for key, value in raw.items()
            )
            if _is_scalar(value)
        }
    if isinstance(raw, list):
        attrs: dict[str, SpanAttributeValue] = {}
        for item in raw:
            if not isinstance(item, dict) or "key" not in item:
                continue
            value = _otel_value(item.get("value"))
            if _is_scalar(value):
                attrs[_normalize_key(item["key"])] = value
        return attrs
    return {}


def _agentgate_attributes(
    attrs: dict[str, SpanAttributeValue],
    *,
    span_name: str = "",
    dangerous_intent_ids: set[str] | None = None,
) -> dict[str, SpanAttributeValue]:
    normalized = dict(attrs)
    _promote_replay_attributes(normalized, attrs)
    _copy_attr(normalized, attrs, "router.selected_intent_id", "selected_intent_id")
    _copy_attr(normalized, attrs, "expected.intent_id", "expected_intent_id")
    _copy_attr(normalized, attrs, "router.confidence", "confidence")
    _copy_attr(normalized, attrs, "tool.name", "tool_name")
    _copy_attr(normalized, attrs, "tool.risk_level", "risk_level")
    _copy_attr(normalized, attrs, "policy.violation.reason", "sql_safety.block_reason")

    if "expected.allowed" in attrs:
        normalized["expected_allowed"] = _bool(attrs["expected.allowed"])
    if (
        attrs.get("policy.tool.executed_despite_deny") is True
        or attrs.get("policy.actual_allowed") is True
    ):
        normalized["actual_allowed"] = True
    elif "policy.preflight.decision" in attrs:
        normalized["actual_allowed"] = str(attrs["policy.preflight.decision"]).upper() == "ALLOW"
    if "policy.violation" in attrs:
        normalized["policy_violation"] = _bool(attrs["policy.violation"])
    selected = normalized.get("selected_intent_id")
    expected = normalized.get("expected_intent_id")
    if selected and expected and "misroute_to_dangerous_tool" not in normalized:
        normalized["misroute_to_dangerous_tool"] = selected != expected and str(selected) in (
            dangerous_intent_ids or set()
        )

    if "sql.safety_classification" in attrs:
        normalized["sql_safety.classification"] = attrs["sql.safety_classification"]
    elif normalized.get("policy_violation") is True and normalized.get("actual_allowed") is True:
        normalized["sql_safety.classification"] = "unsafe_policy_bypass"

    if "tool.success" in attrs:
        normalized["tool.success"] = _bool(attrs["tool.success"])
    if "response.raw_event_dumped" in attrs:
        normalized["raw_event_dumped"] = _bool(attrs["response.raw_event_dumped"])
    elif "raw_event_dumped" in attrs:
        normalized["raw_event_dumped"] = _bool(attrs["raw_event_dumped"])
    return backfill_span_attributes(normalized, span_name=span_name)


def _promote_replay_attributes(
    normalized: dict[str, SpanAttributeValue],
    attrs: dict[str, SpanAttributeValue],
) -> None:
    """Map Phoenix replay/export aliases back to AgentGate span attribute names."""
    for key, value in attrs.items():
        if not str(key).startswith("evidence.attribute."):
            continue
        canonical = str(key).removeprefix("evidence.attribute.")
        if canonical and canonical not in normalized:
            normalized[canonical] = value

    _copy_attr(
        normalized,
        attrs,
        "router.misroute_to_dangerous_tool",
        "misroute_to_dangerous_tool",
    )
    if (
        attrs.get("response.sensitive_output_violation") is True
        and "raw_event_dumped" not in normalized
    ):
        normalized["raw_event_dumped"] = True
        normalized["response.raw_event_dumped"] = True


def _copy_attr(
    target: dict[str, SpanAttributeValue],
    source: dict[str, SpanAttributeValue],
    source_key: str,
    target_key: str,
) -> None:
    if source_key in source and target_key not in target:
        target[target_key] = source[source_key]


def _record_status(
    name: str,
    span: dict[str, Any],
    attrs: dict[str, SpanAttributeValue],
) -> str:
    status_code = str(
        span.get("status_code")
        or span.get("statusCode")
        or _nested_string(span, "status", "code")
        or ""
    ).upper()
    if status_code in {"ERROR", "STATUS_CODE_ERROR"}:
        return "error"
    if name.startswith("policy_preflight.") and attrs.get("actual_allowed") is False:
        return "blocked"
    return "ok"


def _eval_labels_from_span(span: dict[str, Any]) -> list[EvalLabel]:
    span_attributes = _normalize_attributes(span.get("attributes", {}))
    trace_id = _first_string(span, "trace_id", "traceId") or _nested_string(
        span, "context", "trace_id", "traceId"
    )
    if trace_id is None:
        return []

    defaults = {
        "trace_id": trace_id,
        "case_id": str(
            span_attributes.get("test.case_id")
            or span_attributes.get("case_id")
            or span_attributes.get("session.id")
            or trace_id
        ),
        "agent_id": str(
            span_attributes.get("agent.id") or span_attributes.get("agent_id") or "unknown"
        ),
        "agent_version": str(
            span_attributes.get("agent.version")
            or span_attributes.get("agent_version")
            or "unknown"
        ),
        "user_role": str(
            span_attributes.get("user.role") or span_attributes.get("user_role") or "unknown"
        ),
    }

    labels: list[EvalLabel] = []
    for event in _extract_span_events(span):
        label = _eval_label_from_event(event, defaults)
        if label is not None:
            labels.append(label)
    return labels


def _extract_span_events(span: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for key in ("events", "span_events"):
        raw_events = span.get(key)
        if isinstance(raw_events, list):
            events.extend(item for item in raw_events if isinstance(item, dict))
    return events


def _eval_label_from_event(event: dict[str, Any], defaults: dict[str, str]) -> EvalLabel | None:
    name = str(event.get("name") or event.get("event_name") or "")
    if not name.startswith("eval."):
        return None

    attributes = _normalize_attributes(event.get("attributes", {}))
    label_name = str(attributes.get("eval.label_name") or name.removeprefix("eval."))
    if not label_name:
        return None

    label_value = attributes.get("eval.label_value")
    if label_value is None:
        return None

    metadata = {
        key.removeprefix("eval.metadata."): value
        for key, value in attributes.items()
        if key.startswith("eval.metadata.") and _is_scalar(value)
    }

    return EvalLabel(
        trace_id=str(attributes.get("evidence.trace_id") or defaults["trace_id"]),
        case_id=str(attributes.get("evidence.case_id") or defaults["case_id"]),
        agent_id=str(attributes.get("agent.id") or defaults["agent_id"]),
        agent_version=str(attributes.get("agent.version") or defaults["agent_version"]),
        user_role=str(attributes.get("user.role") or defaults["user_role"]),
        evaluator=str(attributes.get("eval.evaluator") or "phoenix_span_event"),
        label_name=label_name,
        label_value=label_value,
        rationale=str(
            attributes.get("eval.rationale") or f"Recovered from Phoenix span event {name}."
        ),
        metadata=metadata,
    )


def _otel_value(value: Any) -> SpanAttributeValue | Any:
    if not isinstance(value, dict):
        return value
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return value[key]
    if "value" in value:
        return _otel_value(value["value"])
    return value


def _normalize_key(key: Any) -> str:
    return str(key)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _first_string(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def _nested_string(payload: dict[str, Any], parent: str, *keys: str) -> str | None:
    nested = payload.get(parent)
    if not isinstance(nested, dict):
        return None
    return _first_string(nested, *keys)


def _bool(value: SpanAttributeValue) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "allow", "allowed"}
    return bool(value)
