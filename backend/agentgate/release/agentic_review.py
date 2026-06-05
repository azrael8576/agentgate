from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.agentgate.release.dangerous_evidence_classifier import finding_priority
from backend.agentgate.release.evidence_loader import (
    EvidenceRecord,
    group_records_by_trace,
)
from backend.agentgate.schemas.evidence import SpanEvent

AGENT_REVIEW_STATUS_DISABLED = "disabled"
AGENT_REVIEW_STATUS_INVALID = "invalid"
AGENT_REVIEW_STATUS_NO_ACTION = "no_action"
AGENT_REVIEW_STATUS_PATTERNS_FOUND = "patterns_found"
AUTHORITY_BOUNDARY = (
    "Agents investigate and plan. The release gate still decides APPROVED or BLOCKED."
)

_PATTERN_TITLES = {
    "unauthorized_dangerous_tool_execution": "Unauthorized dangerous tool execution",
    "dangerous_tool_policy_violation": "Dangerous tool policy violation",
    "sensitive_output_violation": "Sensitive output violation",
    "dangerous_intent_misroute": "Dangerous intent misroute",
    "policy_violation_with_execution": "Policy violation with execution",
    "policy_preflight_missing": "Policy preflight missing",
}


def build_agent_review_artifacts(
    *,
    base: dict[str, Any],
    records: list[EvidenceRecord],
    evidence_source: dict[str, Any],
    dangerous_sessions: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    critical_findings = dangerous_sessions.get("critical_findings", [])
    indeterminate_findings = dangerous_sessions.get("indeterminate_findings", [])
    reviewed_safe = dangerous_sessions.get("reviewed_safe", [])
    high_risk_activity = dangerous_sessions.get("high_risk_activity_log", [])
    trace_evidence = _build_trace_evidence(records, evidence_source, critical_findings)

    pattern_status = (
        AGENT_REVIEW_STATUS_PATTERNS_FOUND
        if critical_findings and trace_evidence
        else AGENT_REVIEW_STATUS_NO_ACTION
    )
    shared_status = {
        "status": pattern_status,
        "summary": (
            f"Pattern Finder found {1 if critical_findings else 0} release-safety pattern."
            if critical_findings and trace_evidence
            else "No action from agent review."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    agent_review_input = {
        **base,
        "agent_review": {
            "enabled": True,
            **shared_status,
        },
        "release_evidence_summary": {
            "evidence_source_type": evidence_source.get("type"),
            "critical_findings": len(critical_findings),
            "indeterminate_findings": len(indeterminate_findings),
            "reviewed_safe": len(reviewed_safe),
            "high_risk_activity": len(high_risk_activity),
            "dangerous_trace_ids": evidence_source.get("dangerous_trace_ids", []),
        },
        "trace_evidence": trace_evidence,
    }
    pattern_finder_plan = {
        **base,
        "agent": "pattern_finder",
        **shared_status,
        "workflow": [
            "Review shared release evidence and trace stories.",
            "Group repeated critical findings into one release-safety pattern.",
            "Cite only real trace IDs and span IDs from the evidence packet.",
        ],
        "focus_areas": _pattern_focus_areas(critical_findings, trace_evidence),
    }
    pattern_finder_results = validate_pattern_finder_results(
        _pattern_finder_results(
            base=base,
            critical_findings=critical_findings,
            trace_evidence=trace_evidence,
        ),
        agent_review_input,
    )
    dataset_planner_results = {
        **base,
        "agent": "dataset_planner",
        "status": AGENT_REVIEW_STATUS_NO_ACTION,
        "summary": "No action from Dataset Planner in this slice.",
        "dataset_candidates": [],
    }
    agent_review_input["agent_review"]["status"] = pattern_finder_results["status"]
    agent_review_input["agent_review"]["summary"] = pattern_finder_results["summary"]
    pattern_finder_plan["status"] = pattern_finder_results["status"]
    pattern_finder_plan["summary"] = pattern_finder_results["summary"]

    return {
        "agent_review_input": agent_review_input,
        "pattern_finder_plan": pattern_finder_plan,
        "pattern_finder_results": pattern_finder_results,
        "dataset_planner_results": dataset_planner_results,
    }


def validate_pattern_finder_results(
    results: dict[str, Any], agent_review_input: dict[str, Any]
) -> dict[str, Any]:
    trace_ids = {
        str(trace.get("trace_id"))
        for trace in agent_review_input.get("trace_evidence", [])
        if trace.get("trace_id")
    }
    evidence_ids = {
        str(span.get("span_id"))
        for trace in agent_review_input.get("trace_evidence", [])
        for span in trace.get("spans", [])
        if span.get("span_id")
    }
    validated_patterns: list[dict[str, Any]] = []
    errors: list[str] = []
    for pattern in results.get("failure_patterns", []):
        pattern_errors = _pattern_validation_errors(pattern, trace_ids, evidence_ids)
        if pattern_errors:
            errors.extend(pattern_errors)
            continue
        validated_patterns.append(pattern)

    trusted = not errors
    status = results.get("status", AGENT_REVIEW_STATUS_NO_ACTION)
    summary = results.get("summary", "No action from Pattern Finder.")
    if not trusted:
        status = AGENT_REVIEW_STATUS_INVALID
        summary = "Pattern Finder output failed validation and was not trusted."
        validated_patterns = []
    return {
        **results,
        "status": status,
        "summary": summary,
        "failure_patterns": validated_patterns,
        "validation": {
            "trusted": trusted,
            "validated_failure_patterns": len(validated_patterns),
            "errors": errors,
        },
    }


def _pattern_validation_errors(
    pattern: dict[str, Any], trace_ids: set[str], evidence_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    required_text_fields = (
        "pattern_id",
        "title",
        "severity",
        "problem_summary",
        "why_it_matters",
        "policy_runtime_mismatch",
    )
    for field in required_text_fields:
        if not str(pattern.get(field) or "").strip():
            errors.append(f"missing {field}")
    supporting_trace_ids = [str(item) for item in pattern.get("supporting_trace_ids", [])]
    supporting_evidence_ids = [str(item) for item in pattern.get("supporting_evidence_ids", [])]
    if not supporting_trace_ids:
        errors.append("missing supporting_trace_ids")
    if not supporting_evidence_ids:
        errors.append("missing supporting_evidence_ids")
    example_traces = pattern.get("example_traces", [])
    if not example_traces:
        errors.append("missing example_traces")
    for trace_id in supporting_trace_ids:
        if trace_id not in trace_ids:
            errors.append(f"unknown trace_id {trace_id}")
    for evidence_id in supporting_evidence_ids:
        if evidence_id not in evidence_ids:
            errors.append(f"unknown evidence_id {evidence_id}")
    for example in example_traces:
        trace_id = str(example.get("trace_id") or "")
        if trace_id not in trace_ids:
            errors.append(f"unknown example trace_id {trace_id}")
    return errors


def _pattern_finder_results(
    *,
    base: dict[str, Any],
    critical_findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    if not critical_findings or not trace_evidence:
        return {
            **base,
            "agent": "pattern_finder",
            "status": AGENT_REVIEW_STATUS_NO_ACTION,
            "summary": "No action from Pattern Finder.",
            "failure_patterns": [],
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in critical_findings:
        grouped[str(finding.get("finding_type") or "unknown")].append(finding)
    finding_type = min(grouped, key=finding_priority)
    findings = grouped[finding_type]
    supporting_trace_ids = sorted({str(finding["trace_id"]) for finding in findings})
    supporting_evidence_ids = sorted(
        {
            str(evidence_id)
            for finding in findings
            for evidence_id in finding.get("evidence_ids", [])
        }
    )
    examples = [
        _example_trace(trace)
        for trace in trace_evidence
        if str(trace.get("trace_id")) in supporting_trace_ids
    ][:3]
    title = _PATTERN_TITLES.get(finding_type, finding_type.replace("_", " ").title())
    return {
        **base,
        "agent": "pattern_finder",
        "status": AGENT_REVIEW_STATUS_PATTERNS_FOUND,
        "summary": "Pattern Finder found 1 release-safety pattern.",
        "failure_patterns": [
            {
                "pattern_id": f"pattern.{finding_type}",
                "title": title,
                "severity": "critical",
                "problem_summary": _problem_summary(finding_type, findings, examples),
                "why_it_matters": _why_it_matters(finding_type),
                "policy_runtime_mismatch": _policy_runtime_mismatch(finding_type, findings),
                "supporting_trace_ids": supporting_trace_ids,
                "supporting_evidence_ids": supporting_evidence_ids,
                "example_traces": examples,
            }
        ],
    }


def _build_trace_evidence(
    records: list[EvidenceRecord],
    evidence_source: dict[str, Any],
    critical_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings_by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in critical_findings:
        findings_by_trace[str(finding.get("trace_id"))].append(finding)
    if not findings_by_trace:
        return []

    dangerous_traces = evidence_source.get("dangerous_traces")
    if isinstance(dangerous_traces, list) and dangerous_traces:
        traces: list[dict[str, Any]] = []
        for trace in dangerous_traces:
            trace_id = str(trace.get("trace_id") or trace.get("id") or "")
            if trace_id not in findings_by_trace:
                continue
            spans = [
                _normalize_trace_span(span)
                for span in trace.get("spans", [])
                if isinstance(span, dict)
            ]
            traces.append(
                {
                    "trace_id": trace_id,
                    "trace_story": _trace_story(findings_by_trace[trace_id], spans),
                    "spans": [span for span in spans if span["span_id"] or span["span_name"]],
                    "supporting_evidence_ids": sorted(
                        {
                            evidence_id
                            for finding in findings_by_trace[trace_id]
                            for evidence_id in finding.get("evidence_ids", [])
                        }
                    ),
                    "finding_types": sorted(
                        {finding["finding_type"] for finding in findings_by_trace[trace_id]}
                    ),
                    "case_id": findings_by_trace[trace_id][0].get("case_id"),
                    "user_role": findings_by_trace[trace_id][0].get("user_role"),
                    "input_text": findings_by_trace[trace_id][0].get("input_text"),
                }
            )
        if traces:
            return traces

    grouped_records = group_records_by_trace(records)
    traces = []
    for trace_id, findings in sorted(
        findings_by_trace.items(),
        key=lambda item: (finding_priority(item[1][0]["finding_type"]), item[0]),
    ):
        spans = [
            _normalize_record_span(record)
            for record in grouped_records.get(trace_id, [])
            if isinstance(record, SpanEvent)
        ]
        traces.append(
            {
                "trace_id": trace_id,
                "trace_story": _trace_story(findings, spans),
                "spans": spans,
                "supporting_evidence_ids": sorted(
                    {
                        str(evidence_id)
                        for finding in findings
                        for evidence_id in finding.get("evidence_ids", [])
                    }
                ),
                "finding_types": sorted({finding["finding_type"] for finding in findings}),
                "case_id": findings[0].get("case_id"),
                "user_role": findings[0].get("user_role"),
                "input_text": findings[0].get("input_text"),
            }
        )
    return traces


def _normalize_trace_span(span: dict[str, Any]) -> dict[str, Any]:
    attributes = span.get("attributes")
    if isinstance(attributes, list):
        flattened = {
            str(item.get("key")): item.get("value")
            for item in attributes
            if isinstance(item, dict) and item.get("key")
        }
    elif isinstance(attributes, dict):
        flattened = dict(attributes)
    else:
        flattened = {}
    return {
        "span_id": str(span.get("id") or span.get("span_id") or ""),
        "span_name": str(span.get("name") or span.get("span_name") or ""),
        "status": span.get("status"),
        "attributes": flattened,
    }


def _normalize_record_span(span: SpanEvent) -> dict[str, Any]:
    return {
        "span_id": span.span_id,
        "span_name": span.span_name,
        "status": span.status,
        "attributes": span.attributes,
    }


def _trace_story(findings: list[dict[str, Any]], spans: list[dict[str, Any]]) -> str:
    first = findings[0]
    role = first.get("user_role") or "unknown role"
    request = first.get("input_text") or "unknown request"
    finding_types = ", ".join(sorted({finding["finding_type"] for finding in findings}))
    span_path = " -> ".join(span["span_name"] for span in spans if span.get("span_name"))
    return (
        f"Role {role} asked: {request}. "
        f"AgentGate marked this trace for {finding_types}. "
        f"Observed span path: {span_path}."
    )


def _pattern_focus_areas(
    critical_findings: list[dict[str, Any]], trace_evidence: list[dict[str, Any]]
) -> list[str]:
    if not critical_findings or not trace_evidence:
        return []
    first = critical_findings[0]
    role = first.get("user_role") or "unknown role"
    return [
        "Confirm the trace story matches the cited blocker evidence.",
        f"Check whether role {role} reached a dangerous path that policy should have blocked.",
    ]


def _problem_summary(
    finding_type: str, findings: list[dict[str, Any]], examples: list[dict[str, Any]]
) -> str:
    role = findings[0].get("user_role") or "unknown role"
    if finding_type == "unauthorized_dangerous_tool_execution":
        return (
            f"{role} reached a dangerous tool path that should have been denied, but runtime "
            "evidence shows the dangerous action still executed."
        )
    if finding_type == "dangerous_tool_policy_violation":
        return "A dangerous tool path recorded a policy violation during runtime."
    if finding_type == "dangerous_intent_misroute":
        return "The router selected a dangerous intent for a request that should have stayed safer."
    if finding_type == "sensitive_output_violation":
        return "A dangerous tool response exposed output that policy treats as sensitive."
    if examples:
        return f"Release evidence shows a critical pattern: {examples[0]['trace_id']}."
    return "Release evidence shows a critical release-safety pattern."


def _why_it_matters(finding_type: str) -> str:
    if finding_type == "unauthorized_dangerous_tool_execution":
        return "Unsafe capability access by the wrong role is a release blocker."
    if finding_type == "dangerous_tool_policy_violation":
        return (
            "A policy-preflight violation means the release authority cannot trust access control."
        )
    if finding_type == "dangerous_intent_misroute":
        return "Dangerous misroutes can send ordinary requests into high-risk tool execution paths."
    if finding_type == "sensitive_output_violation":
        return "Sensitive output leakage on a dangerous path is unsafe for production."
    return "This pattern indicates release evidence that violates the gate's safety boundary."


def _policy_runtime_mismatch(finding_type: str, findings: list[dict[str, Any]]) -> str:
    attributes = findings[0].get("attributes", {})
    expected = attributes.get("expected_allowed")
    actual = attributes.get("actual_allowed")
    tool_name = attributes.get("tool_name") or "dangerous tool"
    if finding_type == "unauthorized_dangerous_tool_execution":
        return f"Policy expected {expected} for {tool_name}, but runtime recorded {actual}."
    if finding_type == "dangerous_tool_policy_violation":
        return f"Runtime flagged policy_violation=true for {tool_name}."
    if finding_type == "sensitive_output_violation":
        return f"Runtime recorded sensitive output behavior for {tool_name}."
    return f"Runtime evidence for {tool_name} diverged from the expected release policy."


def _example_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_id": trace.get("trace_id"),
        "case_id": trace.get("case_id"),
        "user_role": trace.get("user_role"),
        "input_text": trace.get("input_text"),
        "trace_story": trace.get("trace_story"),
    }
