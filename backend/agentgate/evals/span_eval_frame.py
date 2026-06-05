"""Build evaluation rows from AgentGate evidence records."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.release.evidence_loader import (
    EvidenceRecord,
    group_records_by_trace,
)
from backend.agentgate.schemas.evidence import SpanEvent


def build_eval_dataframe(records: list[EvidenceRecord]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trace_id, trace_records in group_records_by_trace(records).items():
        spans = [record for record in trace_records if isinstance(record, SpanEvent)]
        labels = [record for record in trace_records if isinstance(record, EvalLabel)]
        if not spans:
            continue
        router = next(
            (span for span in spans if span.event_type == "router.intent_classification"),
            spans[0],
        )
        response_span = _select_response_span(spans)
        row = {
            "trace_id": trace_id,
            "span_id": response_span.span_id if response_span else router.span_id,
            "case_id": router.case_id,
            "agent_id": router.agent_id,
            "agent_version": router.agent_version,
            "user_role": router.user_role,
            "input": router.input_text or router.attributes.get("input.text", ""),
            "output": _response_text(response_span),
            "context": _build_context(spans),
            "expected_intent_id": router.attributes.get("expected_intent_id"),
            "selected_intent_id": router.attributes.get("selected_intent_id"),
            "expected_allowed": router.attributes.get("expected_allowed"),
            "intent_routing_correct": _intent_routing_correct(router),
        }
        row.update(_label_overrides(labels))
        rows.append(row)
    return pd.DataFrame(rows)


def _select_response_span(spans: list[SpanEvent]) -> SpanEvent | None:
    tool_spans = [span for span in spans if span.event_type.startswith("tool.")]
    if tool_spans:
        return tool_spans[-1]
    return next((span for span in spans if span.event_type == "answer.static"), None)


def _response_text(span: SpanEvent | None) -> str:
    if span is None:
        return ""
    return str(span.attributes.get("response.text") or "")


def _build_context(spans: list[SpanEvent]) -> str:
    parts: list[str] = []
    for span in spans:
        if span.event_type.startswith("tool."):
            args = span.attributes.get("tool.args")
            if args:
                parts.append(f"tool_args={args}")
        if span.attributes.get("answer.source"):
            parts.append(f"answer_source={span.attributes.get('answer.source')}")
    return "\n".join(parts)


def _intent_routing_correct(router: SpanEvent) -> bool | None:
    expected = router.attributes.get("expected_intent_id")
    selected = router.attributes.get("selected_intent_id")
    if expected is None or selected is None:
        return None
    return expected == selected


def _label_overrides(labels: list[EvalLabel]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for label in labels:
        overrides[label.label_name] = label.label_value
    return overrides
