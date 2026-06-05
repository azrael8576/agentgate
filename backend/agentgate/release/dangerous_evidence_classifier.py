"""Shared dangerous evidence classification for session selection and trace pulls."""

from __future__ import annotations

from typing import Any

from backend.agentgate.schemas.evidence import SpanEvent
from backend.agentgate.release.dangerous_evidence_semantics import (
    expected_allowed,
    is_policy_violation_with_execution,
    is_sensitive_output_violation,
    is_unauthorized_dangerous_execution,
    is_unsafe_policy_bypass,
)
from backend.agentgate.release.evidence_span import (
    dangerous_tool_ids,
    tool_id_from_span,
)
from backend.agentgate.schemas import ReleasePolicy

FINDING_TYPE_PRIORITY: tuple[str, ...] = (
    "unauthorized_dangerous_tool_execution",
    "dangerous_tool_policy_violation",
    "sensitive_output_violation",
    "dangerous_intent_misroute",
    "policy_violation_with_execution",
    "policy_preflight_missing",
)

FINDING_TYPE_RANK = {finding_type: index for index, finding_type in enumerate(FINDING_TYPE_PRIORITY)}

SUMMARY_ATTRIBUTE_KEYS: tuple[str, ...] = (
    "tool_name",
    "expected_allowed",
    "actual_allowed",
    "misroute_to_dangerous_tool",
    "raw_event_dumped",
    "policy_violation",
    "sql_safety.classification",
    "sql_safety.block_reason",
    "expected_intent_id",
    "selected_intent_id",
    "tool.success",
    "tool.error_code",
)


def finding_priority(finding_type: str) -> int:
    return FINDING_TYPE_RANK.get(finding_type, len(FINDING_TYPE_PRIORITY))


def classify_trace_findings(
    trace_id: str,
    spans: list[SpanEvent],
    policy: ReleasePolicy | None = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    router = next((span for span in spans if span.event_type == "router.intent_classification"), None)
    dangerous_tools = dangerous_tool_ids(policy)

    if router and router.attributes.get("misroute_to_dangerous_tool") is True:
        findings.append(_finding(trace_id, router, "dangerous_intent_misroute", "critical"))

    for preflight in (span for span in spans if span.event_type.startswith("policy_preflight.")):
        tool_id = tool_id_from_span(preflight)
        if tool_id not in dangerous_tools:
            continue
        _ensure_expected_allowed(preflight, router, policy)
        if is_unauthorized_dangerous_execution(preflight):
            findings.append(_finding(trace_id, preflight, "unauthorized_dangerous_tool_execution", "critical"))
        if is_unsafe_policy_bypass(preflight):
            findings.append(_finding(trace_id, preflight, "dangerous_tool_policy_violation", "critical"))

    for tool_span in (span for span in spans if span.event_type.startswith("tool.") and span.status == "ok"):
        tool_id = tool_id_from_span(tool_span)
        if tool_id not in dangerous_tools:
            continue
        if policy is not None and is_sensitive_output_violation(tool_span, policy):
            findings.append(_finding(trace_id, tool_span, "sensitive_output_violation", "critical"))

    return findings


def classify_indeterminate_findings(
    trace_id: str,
    spans: list[SpanEvent],
    policy: ReleasePolicy | None = None,
) -> list[dict[str, Any]]:
    """Sessions where policy telemetry conflicts with observed tool execution."""
    if classify_trace_findings(trace_id, spans, policy):
        return []

    dangerous_tools = dangerous_tool_ids(policy)
    preflight = next((span for span in spans if span.event_type.startswith("policy_preflight.")), None)
    tool_spans = [
        span
        for span in spans
        if span.event_type.startswith("tool.") and span.status == "ok" and tool_id_from_span(span) in dangerous_tools
    ]
    if not tool_spans:
        return []

    if preflight is None:
        return [_finding(trace_id, tool_spans[0], "policy_preflight_missing", "indeterminate")]

    if is_policy_violation_with_execution(preflight):
        return [
            _finding(
                trace_id,
                preflight,
                "policy_violation_with_execution",
                "indeterminate",
            )
        ]
    return []


def has_reviewable_high_risk_activity(
    spans: list[SpanEvent],
    policy: ReleasePolicy | None = None,
) -> bool:
    dangerous_tools = dangerous_tool_ids(policy)
    return any(
        (
            span.event_type.startswith("policy_preflight.")
            or (
                span.event_type.startswith("tool.")
                and tool_id_from_span(span) in dangerous_tools
            )
        )
        and span.status == "ok"
        for span in spans
    )


def _ensure_expected_allowed(
    preflight: SpanEvent,
    router: SpanEvent | None,
    policy: ReleasePolicy | None,
) -> None:
    if expected_allowed(preflight) is not None:
        return
    if policy is None:
        return
    tool_id = tool_id_from_span(preflight)
    if tool_id not in policy.dangerous_tools:
        return
    role = preflight.user_role or (router.user_role if router else None)
    if not role:
        return
    allowed_intents = policy.role_policy.get(role)
    if allowed_intents is None:
        return
    intent_id = None
    if router is not None:
        intent_id = router.attributes.get("selected_intent_id") or router.attributes.get("expected_intent_id")
    if intent_id is None:
        return
    preflight.attributes["expected_allowed"] = str(intent_id) in allowed_intents


def prioritize_trace_ids_for_pull(
    critical_findings: list[dict[str, Any]],
    *,
    reviewed_safe: list[dict[str, Any]] | None = None,
    max_traces: int = 25,
    include_reviewed_safe: bool = False,
) -> list[str]:
    ranked: dict[str, int] = {}
    for finding in critical_findings:
        trace_id = finding.get("trace_id")
        if not trace_id:
            continue
        priority = finding_priority(str(finding.get("finding_type", "")))
        current = ranked.get(str(trace_id))
        if current is None or priority < current:
            ranked[str(trace_id)] = priority

    ordered = sorted(ranked.items(), key=lambda item: (item[1], item[0]))
    trace_ids = [trace_id for trace_id, _priority in ordered[:max_traces]]

    if len(trace_ids) >= max_traces or not include_reviewed_safe:
        return trace_ids

    for session in reviewed_safe or []:
        trace_id = session.get("trace_id")
        if not trace_id or trace_id in trace_ids:
            continue
        trace_ids.append(str(trace_id))
        if len(trace_ids) >= max_traces:
            break

    return trace_ids


def build_dangerous_session_summaries(
    critical_findings: list[dict[str, Any]],
    dangerous_traces: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    traces_by_id = {
        str(trace.get("trace_id") or trace.get("id")): trace
        for trace in dangerous_traces or []
        if trace.get("trace_id") or trace.get("id")
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for finding in critical_findings:
        trace_id = str(finding["trace_id"])
        grouped.setdefault(trace_id, []).append(finding)

    summaries: list[dict[str, Any]] = []
    for trace_id in sorted(grouped, key=lambda item: (finding_priority(grouped[item][0]["finding_type"]), item)):
        findings = grouped[trace_id]
        top_finding = min(findings, key=lambda finding: finding_priority(str(finding["finding_type"])))
        evidence_ids = sorted(
            {
                str(evidence_id)
                for finding in findings
                for evidence_id in finding.get("evidence_ids", [])
            }
        )
        summaries.append(
            {
                "trace_id": trace_id,
                "case_id": top_finding.get("case_id"),
                "user_role": top_finding.get("user_role"),
                "input_text": top_finding.get("input_text"),
                "top_finding_type": top_finding.get("finding_type"),
                "severity": top_finding.get("severity"),
                "findings": [
                    {
                        "finding_type": finding.get("finding_type"),
                        "severity": finding.get("severity"),
                        "span_name": finding.get("span_name"),
                        "evidence_ids": finding.get("evidence_ids", []),
                        "key_attributes": _compact_attributes(finding.get("attributes", {})),
                    }
                    for finding in findings
                ],
                "selected_evidence_spans": _selected_evidence_spans(
                    traces_by_id.get(trace_id),
                    set(evidence_ids),
                ),
            }
        )
    return summaries


def _selected_evidence_spans(trace: dict[str, Any] | None, evidence_ids: set[str]) -> list[dict[str, Any]]:
    if not trace:
        return []
    spans = trace.get("spans")
    if not isinstance(spans, list):
        return []

    selected: list[dict[str, Any]] = []
    for span in spans:
        if not isinstance(span, dict):
            continue
        span_id = str(span.get("id") or span.get("span_id") or "")
        span_name = str(span.get("name") or span.get("span_name") or "")
        if span_id not in evidence_ids and not _is_relevant_span_name(span_name):
            continue
        if _is_llm_dump_span(span_name, span.get("attributes")):
            continue
        selected.append(
            {
                "span_id": span_id,
                "span_name": span_name,
                "status": span.get("status"),
                "attributes": _compact_span_attributes(span.get("attributes")),
            }
        )
    return selected


def _is_relevant_span_name(span_name: str) -> bool:
    return (
        span_name.startswith("router.")
        or span_name.startswith("policy_preflight.")
        or span_name.startswith("tool.")
        or span_name.startswith("answer.")
    )


def _is_llm_dump_span(span_name: str, attributes: Any) -> bool:
    if "generate_content" in span_name or span_name.startswith("call_llm"):
        return True
    if not isinstance(attributes, dict):
        return False
    return any(
        key.startswith("gcp.vertex.agent.llm_") or key.startswith("gen_ai.")
        for key in attributes
    )


def _compact_attributes(attributes: Any) -> dict[str, Any]:
    if not isinstance(attributes, dict):
        return {}
    return {key: attributes[key] for key in SUMMARY_ATTRIBUTE_KEYS if key in attributes}


def _compact_span_attributes(attributes: Any) -> dict[str, Any]:
    if isinstance(attributes, dict):
        return _compact_attributes(attributes)
    if not isinstance(attributes, list):
        return {}
    flattened: dict[str, Any] = {}
    for item in attributes:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or key not in SUMMARY_ATTRIBUTE_KEYS:
            continue
        flattened[key] = item.get("value")
    return flattened


def _finding(trace_id: str, span: SpanEvent, finding_type: str, severity: str) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "case_id": span.case_id,
        "user_role": span.user_role,
        "input_text": span.input_text,
        "finding_type": finding_type,
        "severity": severity,
        "evidence_ids": [span.span_id],
        "span_name": span.span_name,
        "attributes": span.attributes,
    }
