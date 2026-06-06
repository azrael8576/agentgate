from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Callable

from backend.agentgate.core.agent_pack import LoadedAgentPack
from backend.agentgate.release.dangerous_evidence_classifier import finding_priority
from backend.agentgate.release.evidence_loader import (
    EvidenceRecord,
    group_records_by_trace,
)
from backend.agentgate.schemas.evidence import SpanEvent

AGENT_REVIEW_STATUS_DISABLED = "disabled"
AGENT_REVIEW_STATUS_FAILED = "failed"
AGENT_REVIEW_STATUS_INVALID = "invalid"
AGENT_REVIEW_STATUS_NO_ACTION = "no_action"
AGENT_REVIEW_STATUS_PARTIAL_FAILURE = "partial_failure"
AGENT_REVIEW_STATUS_PATTERNS_FOUND = "patterns_found"
AGENT_REVIEW_STATUS_CANDIDATES_FOUND = "candidates_found"
AGENT_REVIEW_STATUS_TRACE_PULL_FAILED = "trace_pull_failed"
AGENT_REVIEW_ARTIFACT_NAMES = [
    "agent_review_input",
    "pattern_finder_plan",
    "pattern_finder_results",
    "dataset_planner_results",
]
AUTHORITY_BOUNDARY = (
    "Agents investigate and plan. The release gate still decides APPROVED or BLOCKED."
)
PATTERN_FINDER_SUMMARY = "Pattern Finder found 1 release-safety pattern."
NO_ACTION_AGENT_REVIEW_SUMMARY = "No action from agent review."
NO_ACTION_PATTERN_FINDER_SUMMARY = "No action from Pattern Finder."
NO_ACTION_DATASET_PLANNER_SUMMARY = "No action from Dataset Planner in this slice."
DATASET_PLANNER_SUMMARY = "Dataset Planner proposed 1 human-review candidate."
PARTIAL_FAILURE_AGENT_REVIEW_SUMMARY = (
    "Agent review had partial failures; deterministic release decision still used metrics and policy."
)

_PATTERN_TITLES = {
    "unauthorized_dangerous_tool_execution": "Unauthorized dangerous tool execution",
    "dangerous_tool_policy_violation": "Dangerous tool policy violation",
    "sensitive_output_violation": "Sensitive output violation",
    "dangerous_intent_misroute": "Dangerous intent misroute",
    "policy_violation_with_execution": "Policy violation with execution",
    "policy_preflight_missing": "Policy preflight missing",
}
_DATASET_CANDIDATE_ID_PATTERN = re.compile(
    r"^dataset_candidate\.([a-z0-9_]+)\.(\d{2})$"
)


def build_agent_review_artifacts(
    *,
    base: dict[str, Any],
    pack: LoadedAgentPack,
    records: list[EvidenceRecord],
    evidence_source: dict[str, Any],
    dangerous_sessions: dict[str, Any],
    metrics_summary: dict[str, Any],
    gate_binding: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    critical_findings = dangerous_sessions.get("critical_findings", [])
    indeterminate_findings = dangerous_sessions.get("indeterminate_findings", [])
    reviewed_safe = dangerous_sessions.get("reviewed_safe", [])
    high_risk_activity = dangerous_sessions.get("high_risk_activity_log", [])
    trace_evidence = _build_trace_evidence(records, evidence_source, critical_findings)
    trace_pull = _trace_pull_status(evidence_source)

    pattern_status = (
        AGENT_REVIEW_STATUS_PATTERNS_FOUND
        if critical_findings and trace_evidence
        else AGENT_REVIEW_STATUS_NO_ACTION
    )
    shared_status = _shared_agent_review_status(pattern_status)
    agent_review_input = {
        **base,
        "packet_audit_id": (
            f"agent_review_packet:{base['agent_id']}:{base['agent_version']}"
        ),
        "agent_review": {
            "enabled": True,
            **shared_status,
        },
        "agent_context": _build_agent_context(pack),
        "policy_context": _build_policy_context(pack, gate_binding),
        "metric_context": _build_metric_context(pack, metrics_summary),
        "release_evidence_summary": {
            "evidence_source_type": evidence_source.get("type"),
            "critical_findings": len(critical_findings),
            "indeterminate_findings": len(indeterminate_findings),
            "reviewed_safe": len(reviewed_safe),
            "high_risk_activity": len(high_risk_activity),
            "dangerous_trace_ids": evidence_source.get("dangerous_trace_ids", []),
            "coverage_summary": _coverage_summary(evidence_source.get("coverage")),
        },
        "trace_evidence": trace_evidence,
        "trace_pull": trace_pull,
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
    pattern_finder_results = _safe_review_agent_result(
        agent="pattern_finder",
        base=base,
        items_key="failure_patterns",
        builder=lambda: _pattern_finder_results(
            base=base,
            critical_findings=critical_findings,
            trace_evidence=trace_evidence,
        ),
        validator=lambda results: validate_pattern_finder_results(
            results,
            agent_review_input,
        ),
    )
    dataset_planner_results = _safe_review_agent_result(
        agent="dataset_planner",
        base=base,
        items_key="dataset_candidates",
        builder=lambda: _dataset_planner_results(
            base=base,
            critical_findings=critical_findings,
            trace_evidence=trace_evidence,
        ),
        validator=lambda results: validate_dataset_planner_results(
            results,
            agent_review_input,
        ),
    )
    aggregate_status = _aggregate_agent_review_status(
        trace_pull=trace_pull,
        pattern_finder_results=pattern_finder_results,
        dataset_planner_results=dataset_planner_results,
    )
    agent_review_input["agent_review"]["status"] = aggregate_status["status"]
    agent_review_input["agent_review"]["summary"] = aggregate_status["summary"]
    pattern_finder_plan["status"] = aggregate_status["status"]
    pattern_finder_plan["summary"] = aggregate_status["summary"]

    return {
        "agent_review_input": agent_review_input,
        "pattern_finder_plan": pattern_finder_plan,
        "pattern_finder_results": pattern_finder_results,
        "dataset_planner_results": dataset_planner_results,
    }


def build_agentic_review_status(enabled: bool, status: str | None = None) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "status": status
        or (AGENT_REVIEW_STATUS_NO_ACTION if enabled else AGENT_REVIEW_STATUS_DISABLED),
    }


def validate_pattern_finder_results(
    results: dict[str, Any], agent_review_input: dict[str, Any]
) -> dict[str, Any]:
    return _validate_review_results(
        results=results,
        agent_review_input=agent_review_input,
        items_key="failure_patterns",
        validator=_pattern_validation_errors,
        default_summary=NO_ACTION_PATTERN_FINDER_SUMMARY,
        invalid_summary="Pattern Finder failed validation and was not trusted.",
        validated_count_key="validated_failure_patterns",
    )


def validate_dataset_planner_results(
    results: dict[str, Any], agent_review_input: dict[str, Any]
) -> dict[str, Any]:
    return _validate_review_results(
        results=results,
        agent_review_input=agent_review_input,
        items_key="dataset_candidates",
        validator=_dataset_candidate_validation_errors,
        default_summary=NO_ACTION_DATASET_PLANNER_SUMMARY,
        invalid_summary="Dataset Planner failed validation and was not trusted.",
        validated_count_key="validated_dataset_candidates",
    )


def _validate_review_results(
    *,
    results: dict[str, Any],
    agent_review_input: dict[str, Any],
    items_key: str,
    validator: Callable[[dict[str, Any], set[str], set[str]], list[str]],
    default_summary: str,
    invalid_summary: str,
    validated_count_key: str,
) -> dict[str, Any]:
    trace_ids, evidence_ids = _review_reference_ids(agent_review_input)
    validated_items: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in results.get(items_key, []):
        item_errors = validator(item, trace_ids, evidence_ids)
        if item_errors:
            errors.extend(item_errors)
            continue
        validated_items.append(item)

    trusted = not errors
    status = results.get("status", AGENT_REVIEW_STATUS_NO_ACTION)
    summary = results.get("summary", default_summary)
    if not trusted:
        status = AGENT_REVIEW_STATUS_INVALID
        summary = invalid_summary
        validated_items = []
    reference_errors, schema_errors = _split_validation_errors(errors)
    return {
        **results,
        "status": status,
        "summary": summary,
        items_key: validated_items,
        "validation": {
            "trusted": trusted,
            validated_count_key: len(validated_items),
            "errors": errors,
            "reference_errors": reference_errors,
            "schema_errors": schema_errors,
        },
    }


def _split_validation_errors(errors: list[str]) -> tuple[list[str], list[str]]:
    reference_prefixes = (
        "unknown trace_id ",
        "unknown evidence_id ",
        "unknown example trace_id ",
    )
    reference_errors = [
        error for error in errors if any(error.startswith(prefix) for prefix in reference_prefixes)
    ]
    schema_errors = [error for error in errors if error not in reference_errors]
    return reference_errors, schema_errors


def _safe_review_agent_result(
    *,
    agent: str,
    base: dict[str, Any],
    items_key: str,
    builder: Callable[[], dict[str, Any]],
    validator: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    try:
        return validator(builder())
    except Exception as exc:
        return _failed_review_results(
            base=base,
            agent=agent,
            items_key=items_key,
            message=str(exc),
        )


def _failed_review_results(
    *,
    base: dict[str, Any],
    agent: str,
    items_key: str,
    message: str,
) -> dict[str, Any]:
    agent_label = "Pattern Finder" if agent == "pattern_finder" else "Dataset Planner"
    validated_count_key = (
        "validated_failure_patterns"
        if items_key == "failure_patterns"
        else "validated_dataset_candidates"
    )
    return {
        **base,
        "agent": agent,
        "status": AGENT_REVIEW_STATUS_FAILED,
        "summary": (
            f"{agent_label} failed; deterministic release decision still used metrics and policy."
        ),
        items_key: [],
        "failure": {
            "failure_mode": "agent_execution_failed",
            "message": message,
        },
        "validation": {
            "trusted": False,
            validated_count_key: 0,
            "errors": [message],
            "reference_errors": [],
            "schema_errors": [message],
        },
    }


def _trace_pull_status(evidence_source: dict[str, Any]) -> dict[str, Any]:
    trace_pull = evidence_source.get("trace_pull")
    if isinstance(trace_pull, dict):
        return {
            "status": trace_pull.get("status", "not_requested"),
            "requested_trace_ids": list(trace_pull.get("requested_trace_ids", [])),
            "missing_trace_ids": list(trace_pull.get("missing_trace_ids", [])),
            "failures": list(trace_pull.get("failures", [])),
            "pulled_trace_count": int(trace_pull.get("pulled_trace_count", 0)),
        }
    dangerous_trace_ids = evidence_source.get("dangerous_trace_ids", [])
    return {
        "status": "not_requested" if not dangerous_trace_ids else "completed",
        "requested_trace_ids": list(dangerous_trace_ids),
        "missing_trace_ids": [],
        "failures": [],
        "pulled_trace_count": len(evidence_source.get("dangerous_traces", []) or []),
    }


def _aggregate_agent_review_status(
    *,
    trace_pull: dict[str, Any],
    pattern_finder_results: dict[str, Any],
    dataset_planner_results: dict[str, Any],
) -> dict[str, str]:
    if trace_pull.get("status") == "failed":
        missing_count = len(trace_pull.get("missing_trace_ids", []))
        trace_label = "trace" if missing_count == 1 else "traces"
        return {
            "status": AGENT_REVIEW_STATUS_TRACE_PULL_FAILED,
            "summary": f"Phoenix trace pull had gaps for {missing_count} dangerous {trace_label}.",
        }

    child_statuses = {
        str(pattern_finder_results.get("status") or ""),
        str(dataset_planner_results.get("status") or ""),
    }
    if child_statuses & {AGENT_REVIEW_STATUS_INVALID, AGENT_REVIEW_STATUS_FAILED}:
        return {
            "status": AGENT_REVIEW_STATUS_PARTIAL_FAILURE,
            "summary": PARTIAL_FAILURE_AGENT_REVIEW_SUMMARY,
        }
    if pattern_finder_results.get("status") == AGENT_REVIEW_STATUS_PATTERNS_FOUND:
        return {
            "status": AGENT_REVIEW_STATUS_PATTERNS_FOUND,
            "summary": str(pattern_finder_results.get("summary") or PATTERN_FINDER_SUMMARY),
        }
    if dataset_planner_results.get("status") == AGENT_REVIEW_STATUS_CANDIDATES_FOUND:
        return {
            "status": AGENT_REVIEW_STATUS_CANDIDATES_FOUND,
            "summary": str(dataset_planner_results.get("summary") or DATASET_PLANNER_SUMMARY),
        }
    return {
        "status": AGENT_REVIEW_STATUS_NO_ACTION,
        "summary": NO_ACTION_AGENT_REVIEW_SUMMARY,
    }


def _review_reference_ids(agent_review_input: dict[str, Any]) -> tuple[set[str], set[str]]:
    trace_evidence = agent_review_input.get("trace_evidence", [])
    trace_ids = {
        str(trace.get("trace_id"))
        for trace in trace_evidence
        if trace.get("trace_id")
    }
    evidence_ids = {
        str(span.get("span_id"))
        for trace in trace_evidence
        for span in trace.get("spans", [])
        if span.get("span_id")
    }
    return trace_ids, evidence_ids


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
    selected_findings = _selected_findings_by_type(critical_findings, trace_evidence)
    if selected_findings is None:
        return _no_action_review_results(
            base=base,
            agent="pattern_finder",
            summary=NO_ACTION_PATTERN_FINDER_SUMMARY,
            items_key="failure_patterns",
        )

    finding_type, findings = selected_findings
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
        "summary": PATTERN_FINDER_SUMMARY,
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


def _dataset_candidate_validation_errors(
    candidate: dict[str, Any], trace_ids: set[str], evidence_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    required_text_fields = (
        "candidate_id",
        "rationale",
        "review_instructions",
        "conversion_guidance",
        "review_status",
    )
    for field in required_text_fields:
        if not str(candidate.get(field) or "").strip():
            errors.append(f"missing {field}")
    source_trace_ids = [str(item) for item in candidate.get("source_trace_ids", [])]
    source_evidence_ids = [str(item) for item in candidate.get("source_evidence_ids", [])]
    source_finding_types = [str(item) for item in candidate.get("source_finding_types", [])]
    candidate_id = str(candidate.get("candidate_id") or "")
    if not source_trace_ids:
        errors.append("missing source_trace_ids")
    if not source_evidence_ids:
        errors.append("missing source_evidence_ids")
    if not source_finding_types:
        errors.append("missing source_finding_types")
    errors.extend(_dataset_candidate_identity_errors(candidate_id, source_finding_types))
    if candidate.get("requires_human_review") is not True:
        errors.append("requires_human_review must be true")
    for trace_id in source_trace_ids:
        if trace_id not in trace_ids:
            errors.append(f"unknown trace_id {trace_id}")
    for evidence_id in source_evidence_ids:
        if evidence_id not in evidence_ids:
            errors.append(f"unknown evidence_id {evidence_id}")
    return errors


def _dataset_planner_results(
    *,
    base: dict[str, Any],
    critical_findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_findings = _selected_findings_by_type(critical_findings, trace_evidence)
    if selected_findings is None:
        return _no_action_review_results(
            base=base,
            agent="dataset_planner",
            summary=NO_ACTION_DATASET_PLANNER_SUMMARY,
            items_key="dataset_candidates",
        )

    finding_type, findings = selected_findings
    source_trace_ids = sorted({str(finding["trace_id"]) for finding in findings})
    source_evidence_ids = sorted(
        {
            str(evidence_id)
            for finding in findings
            for evidence_id in finding.get("evidence_ids", [])
        }
    )
    tool_name = _dataset_candidate_tool_name(trace_evidence, source_trace_ids)
    return {
        **base,
        "agent": "dataset_planner",
        "status": AGENT_REVIEW_STATUS_CANDIDATES_FOUND,
        "summary": DATASET_PLANNER_SUMMARY,
        "dataset_candidates": [
            {
                "candidate_id": _dataset_candidate_id(finding_type, 1),
                "source_trace_ids": source_trace_ids,
                "source_evidence_ids": source_evidence_ids,
                "source_finding_types": [finding_type],
                "rationale": (
                    f"Use the repeated {finding_type.replace('_', ' ')} evidence around "
                    f"{tool_name} as a human-reviewed dataset candidate for future release "
                    "coverage."
                ),
                "review_instructions": (
                    "Confirm the cited traces are representative before converting them into "
                    "a controlled eval or release-control candidate. Check the trace story, "
                    "span path, and supporting evidence IDs against the pulled Phoenix trace."
                ),
                "conversion_guidance": (
                    f"After human review, convert the cited {tool_name} failure into a future "
                    "eval case or release control candidate. Do not add it directly to a "
                    "golden dataset."
                ),
                "requires_human_review": True,
                "review_status": "pending_review",
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
        grouped_records = group_records_by_trace(records)
        traces: list[dict[str, Any]] = []
        for trace in dangerous_traces:
            trace_id = str(trace.get("trace_id") or trace.get("id") or "")
            if trace_id not in findings_by_trace:
                continue
            findings = findings_by_trace[trace_id]
            record_spans = [
                _normalize_record_span(record)
                for record in grouped_records.get(trace_id, [])
                if isinstance(record, SpanEvent)
            ]
            spans = [
                _normalize_trace_span(span)
                for span in trace.get("spans", [])
                if isinstance(span, dict)
            ]
            spans = _merge_trace_spans(spans, record_spans)
            traces.append(
                _trace_evidence_entry(
                    trace_id=trace_id,
                    findings=findings,
                    spans=[span for span in spans if span["span_id"] or span["span_name"]],
                )
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
        traces.append(_trace_evidence_entry(trace_id=trace_id, findings=findings, spans=spans))
    return traces


def _shared_agent_review_status(status: str) -> dict[str, str]:
    return {
        "status": status,
        "summary": (
            PATTERN_FINDER_SUMMARY
            if status == AGENT_REVIEW_STATUS_PATTERNS_FOUND
            else NO_ACTION_AGENT_REVIEW_SUMMARY
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def _trace_evidence_entry(
    *,
    trace_id: str,
    findings: list[dict[str, Any]],
    spans: list[dict[str, Any]],
) -> dict[str, Any]:
    first_finding = findings[0]
    trace_context = _trace_context(first_finding, spans)
    span_path = " -> ".join(span["span_name"] for span in spans if span.get("span_name"))
    return {
        "trace_audit_id": f"trace:{trace_id}",
        "trace_id": trace_id,
        "trace_story": _trace_story(findings, spans),
        "user_request": first_finding.get("input_text"),
        "expected_intent_id": trace_context["expected_intent_id"],
        "selected_intent_id": trace_context["selected_intent_id"],
        "policy_expectation": _policy_expectation(
            trace_context["tool_name"],
            trace_context["expected_allowed"],
        ),
        "runtime_behavior": _runtime_behavior(
            trace_context["tool_name"],
            trace_context["actual_allowed"],
            spans,
        ),
        "span_path": span_path,
        "risk_summary": _risk_summary(findings),
        "spans": spans,
        "supporting_evidence_ids": sorted(
            {
                str(evidence_id)
                for finding in findings
                for evidence_id in finding.get("evidence_ids", [])
            }
        ),
        "finding_types": sorted({finding["finding_type"] for finding in findings}),
        "case_id": first_finding.get("case_id"),
        "user_role": first_finding.get("user_role"),
        "input_text": first_finding.get("input_text"),
    }


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
    span_id = str(span.get("id") or span.get("span_id") or "")
    span_name = str(span.get("name") or span.get("span_name") or "")
    sanitized_attributes = _sanitize_span_attributes(flattened)
    return {
        "span_audit_id": f"span:{span_id}" if span_id else "",
        "span_id": span_id,
        "parent_span_id": str(span.get("parent_span_id") or span.get("parentId") or ""),
        "span_name": span_name,
        "event_type": span_name,
        "status": span.get("status"),
        "attributes": sanitized_attributes,
        "plain_language_summary": _span_plain_language_summary(span_name, sanitized_attributes),
    }


def _normalize_record_span(span: SpanEvent) -> dict[str, Any]:
    sanitized_attributes = _sanitize_span_attributes(span.attributes)
    return {
        "span_audit_id": f"span:{span.span_id}",
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id or "",
        "span_name": span.span_name,
        "event_type": span.event_type,
        "status": span.status,
        "attributes": sanitized_attributes,
        "plain_language_summary": _span_plain_language_summary(
            span.span_name, sanitized_attributes
        ),
    }


def _trace_story(findings: list[dict[str, Any]], spans: list[dict[str, Any]]) -> str:
    first = findings[0]
    role = first.get("user_role") or "unknown role"
    request = first.get("input_text") or "unknown request"
    finding_types = ", ".join(sorted({finding["finding_type"] for finding in findings}))
    trace_context = _trace_context(first, spans)
    supporting_evidence_ids = sorted(
        {
            str(evidence_id)
            for finding in findings
            for evidence_id in finding.get("evidence_ids", [])
        }
    )
    span_path = " -> ".join(span["span_name"] for span in spans if span.get("span_name"))
    return (
        f"Role {role} asked: {request}. "
        f"Expected intent: {trace_context['expected_intent_id'] or 'unknown intent'}. "
        f"Selected intent: {trace_context['selected_intent_id'] or 'unknown intent'}. "
        f"Policy expectation for {trace_context['tool_name'] or 'the high-risk tool path'}: "
        f"{trace_context['expected_allowed']}. "
        f"Runtime behavior: {trace_context['actual_allowed']}. "
        f"AgentGate marked this trace for {finding_types}. "
        f"Observed span path: {span_path}. "
        f"Supporting evidence IDs: {', '.join(supporting_evidence_ids)}."
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


def _first_nonempty_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _trace_context(
    finding: dict[str, Any], spans: list[dict[str, Any]]
) -> dict[str, Any]:
    attributes = finding.get("attributes", {})
    return {
        "expected_intent_id": _first_nonempty_value(
            attributes.get("expected_intent_id"),
            *[span.get("attributes", {}).get("expected_intent_id") for span in spans],
        ),
        "selected_intent_id": _first_nonempty_value(
            attributes.get("selected_intent_id"),
            *[span.get("attributes", {}).get("selected_intent_id") for span in spans],
        ),
        "tool_name": _first_nonempty_value(
            attributes.get("tool_name"),
            *[span.get("attributes", {}).get("tool_name") for span in spans],
        ),
        "expected_allowed": _first_nonempty_value(
            attributes.get("expected_allowed"),
            *[span.get("attributes", {}).get("expected_allowed") for span in spans],
        ),
        "actual_allowed": _first_nonempty_value(
            attributes.get("actual_allowed"),
            *[span.get("attributes", {}).get("actual_allowed") for span in spans],
        ),
    }


def _selected_findings_by_type(
    critical_findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]] | None:
    if not critical_findings or not trace_evidence:
        return None

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in critical_findings:
        grouped[str(finding.get("finding_type") or "unknown")].append(finding)
    finding_type = min(grouped, key=finding_priority)
    return finding_type, grouped[finding_type]


def _dataset_candidate_id(finding_type: str, index: int) -> str:
    return f"dataset_candidate.{finding_type}.{index:02d}"


def _dataset_candidate_identity_errors(
    candidate_id: str, source_finding_types: list[str]
) -> list[str]:
    candidate_id_match = _DATASET_CANDIDATE_ID_PATTERN.match(candidate_id)
    if not candidate_id_match:
        return [f"invalid candidate_id {candidate_id}"]
    if source_finding_types and candidate_id_match.group(1) not in source_finding_types:
        return [
            "candidate_id finding type does not match source_finding_types "
            f"for {candidate_id}"
        ]
    return []


def _dataset_candidate_tool_name(
    trace_evidence: list[dict[str, Any]], source_trace_ids: list[str]
) -> str:
    example_trace = next(
        (
            trace
            for trace in trace_evidence
            if str(trace.get("trace_id") or "") in source_trace_ids
        ),
        {},
    )
    tool_name = _first_nonempty_value(
        *[
            span.get("attributes", {}).get("tool_name")
            for span in example_trace.get("spans", [])
            if isinstance(span, dict)
        ]
    )
    return str(tool_name or "the dangerous tool path")


def _no_action_review_results(
    *,
    base: dict[str, Any],
    agent: str,
    summary: str,
    items_key: str,
) -> dict[str, Any]:
    return {
        **base,
        "agent": agent,
        "status": AGENT_REVIEW_STATUS_NO_ACTION,
        "summary": summary,
        items_key: [],
    }


def _build_agent_context(pack: LoadedAgentPack) -> dict[str, Any]:
    return {
        "agent_audit_id": f"agent:{pack.agent_id}",
        "agent_id": pack.agent_id,
        "display_name": pack.profile.display_name,
        "domain": pack.profile.domain,
        "description": pack.profile.description,
        "current_runtime": pack.profile.current_runtime,
        "risk_summary": pack.profile.risk_summary,
    }


def _build_policy_context(
    pack: LoadedAgentPack, gate_binding: dict[str, Any] | None
) -> dict[str, Any]:
    intents_by_id = {
        intent.intent_id: intent
        for intent in (pack.intents.intents if pack.intents is not None else [])
    }
    tool_risk_catalog = []
    for tool in pack.profile.tool_manifest:
        matched_intents = [
            intent
            for intent in intents_by_id.values()
            if getattr(intent, "tool_name", None) == tool.tool_id
        ]
        tool_risk_catalog.append(
            {
                "tool_audit_id": f"tool:{tool.tool_id}",
                "tool_id": tool.tool_id,
                "risk_level": tool.risk_level,
                "side_effect_type": tool.side_effect_type,
                "intent_ids": [intent.intent_id for intent in matched_intents],
                "intent_descriptions": [intent.description for intent in matched_intents],
            }
        )

    role_policy_summary = []
    for role, allowed_intents in sorted(pack.release_policy.role_policy.items()):
        dangerous_tools = sorted(
            {
                intent.tool_name
                for intent_id in allowed_intents
                for intent in [intents_by_id.get(intent_id)]
                if intent is not None
                and getattr(intent, "tool_name", None) in pack.release_policy.dangerous_tools
            }
        )
        role_policy_summary.append(
            {
                "role": role,
                "allowed_intents": list(allowed_intents),
                "allowed_high_risk_tools": dangerous_tools,
                "summary": (
                    f"Role {role} may use intents {', '.join(allowed_intents)}"
                    + (
                        f" and high-risk tools {', '.join(dangerous_tools)}."
                        if dangerous_tools
                        else " and no dangerous tools."
                    )
                ),
            }
        )

    return {
        "policy_audit_id": f"policy:{pack.release_policy.policy_id}",
        "policy_id": pack.release_policy.policy_id,
        "policy_version": pack.release_policy.policy_version,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "dangerous_tools": list(pack.release_policy.dangerous_tools),
        "tool_risk_catalog": tool_risk_catalog,
        "role_policy_summary": role_policy_summary,
        "failed_control_meaning": (
            "Agent review can explain evidence and plan follow-up work, but only the "
            "deterministic gate binding decides APPROVED or BLOCKED."
        ),
        "gate_binding": gate_binding or {},
    }


def _build_metric_context(
    pack: LoadedAgentPack, metrics_summary: dict[str, Any]
) -> dict[str, Any]:
    control_definitions = pack.control_definitions()
    metrics = []
    for metric in metrics_summary.get("metrics", []):
        metric_id = str(metric.get("name") or metric.get("metric_id") or "")
        control = control_definitions.get(metric_id, {})
        metrics.append(
            {
                "metric_audit_id": f"metric:{metric_id}",
                "metric_id": metric_id,
                "display_name": control.get("name", metric_id),
                "definition": control.get("definition", ""),
                "formula": control.get("formula", ""),
                "decision_impact": metric.get("decision_impact"),
                "threshold_key": metric.get("threshold_key"),
                "threshold": metric.get("threshold"),
                "value": metric.get("value"),
                "status": metric.get("status"),
                "passes_threshold": metric.get("passes_threshold"),
            }
        )
    return {"metrics": metrics}


def _coverage_summary(coverage: Any) -> dict[str, Any]:
    if not isinstance(coverage, dict):
        return {}
    return {
        "missing_required_attributes": coverage.get("missing_required_attributes", 0),
        "missing_eval_labels": coverage.get("missing_eval_labels", 0),
        "span_count": coverage.get("span_count", 0),
    }


def _policy_expectation(tool_name: Any, expected_allowed: Any) -> str:
    target = str(tool_name or "the high-risk path")
    if expected_allowed is True:
        return f"Policy expected ALLOW for {target}."
    if expected_allowed is False:
        return f"Policy expected DENY for {target}."
    return f"Policy expectation for {target} was not fully recorded."


def _runtime_behavior(tool_name: Any, actual_allowed: Any, spans: list[dict[str, Any]]) -> str:
    target = str(tool_name or "the high-risk path")
    tool_executed = any(span.get("span_name", "").startswith("tool.") for span in spans)
    if actual_allowed is True:
        return f"Runtime allowed {target}" + (" and executed it." if tool_executed else ".")
    if actual_allowed is False:
        return f"Runtime denied {target}."
    if tool_executed:
        return f"Runtime executed {target}, but the policy decision was unclear."
    return f"Runtime evidence for {target} was incomplete."


def _risk_summary(findings: list[dict[str, Any]]) -> str:
    finding_types = ", ".join(sorted({str(finding.get("finding_type")) for finding in findings}))
    return f"Trace is relevant because AgentGate classified it as {finding_types}."


def _sanitize_span_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in attributes.items():
        normalized_key = str(key)
        if _is_non_evidence_attribute(normalized_key, value):
            continue
        sanitized[normalized_key] = value
    return sanitized


def _is_non_evidence_attribute(key: str, value: Any) -> bool:
    if isinstance(value, (dict, list)):
        return True
    if key in {
        "tool.args",
        "input.value",
        "output.value",
        "llm.input_messages",
        "llm.output_messages",
        "llm.prompt",
        "llm.completion",
        "openinference.input",
        "openinference.output",
    }:
        return True
    lowered = key.lower()
    return lowered.startswith(("llm.", "openinference.", "gen_ai.")) or lowered.endswith(
        (".prompt", ".completion", ".messages")
    )


def _span_plain_language_summary(span_name: str, attributes: dict[str, Any]) -> str:
    tool_name = attributes.get("tool_name")
    if span_name.startswith("router."):
        return (
            "Router selected "
            f"{attributes.get('selected_intent_id', 'an intent')} for this request."
        )
    if span_name.startswith("policy_preflight."):
        return (
            f"Policy preflight checked {tool_name or 'the tool'} and recorded "
            f"expected_allowed={attributes.get('expected_allowed')} and "
            f"actual_allowed={attributes.get('actual_allowed')}."
        )
    if span_name.startswith("tool."):
        return f"Tool execution span for {tool_name or span_name} finished with status evidence."
    return f"Observed span {span_name} in the trace."


def _merge_trace_spans(
    pulled_trace_spans: list[dict[str, Any]], record_spans: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    record_by_span_id = {
        span["span_id"]: span for span in record_spans if span.get("span_id")
    }
    merged: list[dict[str, Any]] = []
    seen_span_ids: set[str] = set()
    for span in pulled_trace_spans:
        span_id = str(span.get("span_id") or "")
        record_span = record_by_span_id.get(span_id)
        if record_span is None:
            merged.append(span)
        else:
            merged.append(
                {
                    **record_span,
                    **span,
                    "attributes": {
                        **record_span.get("attributes", {}),
                        **span.get("attributes", {}),
                    },
                    "plain_language_summary": span.get("plain_language_summary")
                    or record_span.get("plain_language_summary", ""),
                }
            )
        if span_id:
            seen_span_ids.add(span_id)
    merged.extend(
        span for span in record_spans if span.get("span_id") not in seen_span_ids
    )
    return merged
