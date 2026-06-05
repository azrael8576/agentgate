"""Build audit-grade high-risk session reports for release artifacts."""

from __future__ import annotations

from typing import Any, Literal

from backend.agentgate.schemas.evidence import SpanEvent
from backend.agentgate.release.dangerous_evidence_classifier import (
    classify_indeterminate_findings,
    classify_trace_findings,
    has_reviewable_high_risk_activity,
)
from backend.agentgate.release.evidence_loader import EvidenceRecord, group_records_by_trace
from backend.agentgate.release.evidence_span import dangerous_tool_ids, primary_span_event_types
from backend.agentgate.schemas import ReleasePolicy

AuditVerdict = Literal["violation", "authorized", "indeterminate"]


def build_audit_session_report(
    records: list[EvidenceRecord],
    policy: ReleasePolicy | None = None,
) -> dict[str, list[dict[str, Any]]]:
    critical_findings: list[dict[str, Any]] = []
    indeterminate_findings: list[dict[str, Any]] = []
    high_risk_activity_log: list[dict[str, Any]] = []
    reviewed_safe: list[dict[str, Any]] = []

    for trace_id, trace_records in group_records_by_trace(records).items():
        spans = [record for record in trace_records if isinstance(record, SpanEvent)]
        material_findings = classify_trace_findings(trace_id, spans, policy)
        indeterminate = classify_indeterminate_findings(trace_id, spans, policy)
        if not material_findings and not indeterminate and not has_reviewable_high_risk_activity(spans, policy):
            continue

        entry = _build_activity_entry(trace_id, spans, material_findings, indeterminate, policy)
        high_risk_activity_log.append(entry)
        critical_findings.extend(material_findings)
        indeterminate_findings.extend(indeterminate)
        if entry["verdict"] == "authorized":
            reviewed_safe.append(_authorized_session_summary(entry))

    high_risk_activity_log.sort(key=_activity_sort_key)
    return {
        "critical_findings": critical_findings,
        "indeterminate_findings": indeterminate_findings,
        "high_risk_activity_log": high_risk_activity_log,
        "reviewed_safe": reviewed_safe,
    }


def _build_activity_entry(
    trace_id: str,
    spans: list[SpanEvent],
    material_findings: list[dict[str, Any]],
    indeterminate_findings: list[dict[str, Any]],
    policy: ReleasePolicy | None = None,
) -> dict[str, Any]:
    primary = _primary_span(spans, policy)
    preflight = next((span for span in spans if span.event_type.startswith("policy_preflight.")), None)
    tool_spans = [span for span in spans if span.event_type.startswith("tool.") and span.status == "ok"]
    verdict = _resolve_verdict(material_findings, indeterminate_findings, spans, policy)
    return {
        "trace_id": trace_id,
        "case_id": primary.case_id,
        "user_role": primary.user_role,
        "input_text": primary.input_text,
        "tool_names": _tool_names(spans),
        "preflight_decision": _preflight_decision(preflight),
        "expected_allowed": _optional_bool(preflight, "expected_allowed"),
        "actual_allowed": _optional_bool(preflight, "actual_allowed"),
        "policy_violation": _optional_bool(preflight, "policy_violation"),
        "verdict": verdict,
        "verdict_reason": _verdict_reason(verdict, material_findings, indeterminate_findings, preflight, tool_spans),
        "finding_types": [finding["finding_type"] for finding in material_findings + indeterminate_findings],
        "evidence_ids": sorted(
            {
                str(evidence_id)
                for finding in material_findings + indeterminate_findings
                for evidence_id in finding.get("evidence_ids", [])
            }
            | {span.span_id for span in spans}
        ),
        "tool_executed": bool(tool_spans),
    }


def _resolve_verdict(
    material_findings: list[dict[str, Any]],
    indeterminate_findings: list[dict[str, Any]],
    spans: list[SpanEvent],
    policy: ReleasePolicy | None = None,
) -> AuditVerdict:
    if material_findings:
        return "violation"
    if indeterminate_findings:
        return "indeterminate"
    if has_reviewable_high_risk_activity(spans, policy):
        return "authorized"
    return "indeterminate"


def _verdict_reason(
    verdict: AuditVerdict,
    material_findings: list[dict[str, Any]],
    indeterminate_findings: list[dict[str, Any]],
    preflight: SpanEvent | None,
    tool_spans: list[SpanEvent],
) -> str:
    if material_findings:
        finding_types = ", ".join(sorted({finding["finding_type"] for finding in material_findings}))
        return f"Material violation detected: {finding_types}."
    if indeterminate_findings:
        finding_types = {finding["finding_type"] for finding in indeterminate_findings}
        if "policy_preflight_missing" in finding_types:
            return "High-risk tool activity recorded without a policy preflight span."
        return (
            "Policy preflight recorded a denial or violation, but telemetry alone cannot prove "
            "whether tool execution was authorized."
        )
    if preflight is None and tool_spans:
        tool_names = {
            str(span.attributes.get("tool_name"))
            for span in tool_spans
            if span.attributes.get("tool_name")
        }
        if tool_names & dangerous_tool_ids(policy):
            return "High-risk tool activity recorded without a policy preflight span."
    if preflight and tool_spans:
        return "High-risk tool activity completed after an allowed policy preflight."
    if tool_spans:
        return "High-risk tool activity recorded for telemetry audit review."
    return "High-risk activity recorded with insufficient telemetry to classify further."


def _primary_span(spans: list[SpanEvent], policy: ReleasePolicy | None = None) -> SpanEvent:
    for event_type in primary_span_event_types(policy):
        match = next((span for span in spans if span.event_type == event_type), None)
        if match is not None:
            return match
    return spans[0]


def _tool_names(spans: list[SpanEvent]) -> list[str]:
    return sorted(
        {
            str(span.attributes["tool_name"])
            for span in spans
            if "tool_name" in span.attributes and span.status == "ok"
        }
    )


def _preflight_decision(preflight: SpanEvent | None) -> str:
    if preflight is None:
        return "none"
    actual_allowed = preflight.attributes.get("actual_allowed")
    if actual_allowed is True:
        return "ALLOW"
    if actual_allowed is False:
        return "DENY"
    return "unknown"


def _optional_bool(span: SpanEvent | None, key: str) -> bool | None:
    if span is None or key not in span.attributes:
        return None
    value = span.attributes[key]
    if isinstance(value, bool):
        return value
    return None


def _authorized_session_summary(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_id": entry["trace_id"],
        "case_id": entry["case_id"],
        "user_role": entry["user_role"],
        "input_text": entry["input_text"],
        "review_status": "safe_high_risk_activity",
        "evidence_ids": entry["evidence_ids"],
        "tool_names": entry["tool_names"],
    }


def _activity_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    verdict_rank = {"violation": 0, "indeterminate": 1, "authorized": 2}
    return (verdict_rank.get(str(entry.get("verdict")), 3), str(entry.get("trace_id", "")))
