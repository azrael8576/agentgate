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
WARNING_ONLY_PATTERN_FINDER_SUMMARY = "Pattern Finder found warning observations only."
INVALID_PATTERN_FINDER_SUMMARY = "Pattern Finder failed validation and was not trusted."
PARTIAL_FAILURE_AGENT_REVIEW_SUMMARY = (
    "Agent review had partial failures; deterministic release decision still used metrics and policy."
)
_REFERENCE_ERROR_PREFIXES = (
    "unknown trace_id ",
    "unknown evidence_id ",
    "unknown example trace_id ",
)
_REVIEW_AGENT_LABELS = {
    "pattern_finder": "Pattern Finder",
    "dataset_planner": "Dataset Planner",
}
_VALIDATED_COUNT_KEYS = {
    "failure_patterns": "validated_failure_patterns",
    "dataset_candidates": "validated_dataset_candidates",
}

_PATTERN_TITLES = {
    "unauthorized_dangerous_tool_execution": "Unauthorized dangerous tool execution",
    "dangerous_tool_policy_violation": "Dangerous tool policy violation",
    "sensitive_output_violation": "Sensitive output violation",
    "dangerous_intent_misroute": "Dangerous intent misroute",
    "policy_violation_with_execution": "Policy violation with execution",
    "policy_preflight_missing": "Policy preflight missing",
    "response_format_warning": "Response format warning",
    "technical_tool_failure_warning": "Technical tool failure warning",
}
_DATASET_CANDIDATE_ID_PATTERN = re.compile(
    r"^dataset_candidate\.([a-z0-9_]+)\.(\d{2})$"
)
_ANNOTATION_RECOMMENDATION_ID_PATTERN = re.compile(
    r"^annotation_recommendation\.([a-z0-9_]+)\.(\d{2})$"
)
_FUTURE_CONTROL_CANDIDATE_ID_PATTERN = re.compile(
    r"^future_control_candidate\.([a-z0-9_]+)\.(\d{2})$"
)
_DUPLICATE_OR_NOISE_GROUP_ID_PATTERN = re.compile(
    r"^duplicate_or_noise\.([a-z0-9_]+)\.(\d{2})$"
)
_DATASET_PLANNER_ITEM_KEYS = (
    "dataset_candidates",
    "annotation_recommendations",
    "future_control_candidates",
    "duplicate_or_noise",
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
    warning_findings = _warning_metric_findings(records, metrics_summary)
    trace_evidence = _build_trace_evidence(
        records,
        evidence_source,
        [*critical_findings, *indeterminate_findings, *warning_findings],
    )
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
        agent_label=_REVIEW_AGENT_LABELS["pattern_finder"],
        base=base,
        items_key="failure_patterns",
        validated_count_key=_VALIDATED_COUNT_KEYS["failure_patterns"],
        builder=lambda: _pattern_finder_results(
            base=base,
            critical_findings=critical_findings,
            indeterminate_findings=[*indeterminate_findings, *warning_findings],
            trace_evidence=trace_evidence,
        ),
        validator=lambda results: validate_pattern_finder_results(
            results,
            agent_review_input,
        ),
    )
    dataset_planner_results = _safe_review_agent_result(
        agent="dataset_planner",
        agent_label=_REVIEW_AGENT_LABELS["dataset_planner"],
        base=base,
        items_key="dataset_candidates",
        validated_count_key=_VALIDATED_COUNT_KEYS["dataset_candidates"],
        builder=lambda: _dataset_planner_results(
            base=base,
            critical_findings=critical_findings,
            warning_findings=warning_findings,
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
    trace_ids, evidence_ids = _review_reference_ids(agent_review_input)
    validated_patterns, pattern_errors = _validate_pattern_collection(
        results=results,
        items_key="failure_patterns",
        id_field="pattern_id",
        trace_ids=trace_ids,
        evidence_ids=evidence_ids,
    )
    validated_warnings, warning_errors = _validate_pattern_collection(
        results=results,
        items_key="warning_observations",
        id_field="observation_id",
        trace_ids=trace_ids,
        evidence_ids=evidence_ids,
    )
    errors = [*pattern_errors, *warning_errors]

    trusted = not errors
    status = results.get("status", AGENT_REVIEW_STATUS_NO_ACTION)
    summary = results.get("summary", NO_ACTION_PATTERN_FINDER_SUMMARY)
    if not trusted:
        status = AGENT_REVIEW_STATUS_INVALID
        summary = INVALID_PATTERN_FINDER_SUMMARY
        validated_patterns = []
        validated_warnings = []
    reference_errors, schema_errors = _split_validation_errors(errors)
    return {
        **results,
        "status": status,
        "summary": summary,
        "failure_patterns": validated_patterns,
        "warning_observations": validated_warnings,
        "validation": {
            "trusted": trusted,
            "validated_failure_patterns": len(validated_patterns),
            "validated_warning_observations": len(validated_warnings),
            "errors": errors,
            "reference_errors": reference_errors,
            "schema_errors": schema_errors,
        },
    }


def validate_dataset_planner_results(
    results: dict[str, Any], agent_review_input: dict[str, Any]
) -> dict[str, Any]:
    trace_ids, evidence_ids = _review_reference_ids(agent_review_input)
    validated_results: dict[str, list[dict[str, Any]]] = {}
    validation_counts: dict[str, int] = {}
    errors: list[str] = []
    for items_key, validated_count_key, validator in _dataset_planner_collection_specs():
        validated_items, item_errors = _validate_review_collection(
            results=results,
            items_key=items_key,
            validator=validator,
            trace_ids=trace_ids,
            evidence_ids=evidence_ids,
        )
        validated_results[items_key] = validated_items
        validation_counts[validated_count_key] = len(validated_items)
        errors.extend(item_errors)

    trusted = not errors
    status = results.get("status", AGENT_REVIEW_STATUS_NO_ACTION)
    summary = results.get("summary", NO_ACTION_DATASET_PLANNER_SUMMARY)
    if not trusted:
        status = AGENT_REVIEW_STATUS_INVALID
        summary = "Dataset Planner failed validation and was not trusted."
        validated_results = {
            items_key: [] for items_key in _DATASET_PLANNER_ITEM_KEYS
        }
        validation_counts = {
            validated_count_key: 0
            for _, validated_count_key, _ in _dataset_planner_collection_specs()
        }
    reference_errors, schema_errors = _split_validation_errors(errors)
    return {
        **results,
        "status": status,
        "summary": summary,
        **validated_results,
        "validation": {
            "trusted": trusted,
            **validation_counts,
            "errors": errors,
            "reference_errors": reference_errors,
            "schema_errors": schema_errors,
        },
    }


def _validate_review_collection(
    *,
    results: dict[str, Any],
    items_key: str,
    validator: Callable[[dict[str, Any], set[str], set[str]], list[str]],
    trace_ids: set[str],
    evidence_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    validated_items: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in results.get(items_key, []):
        item_errors = validator(item, trace_ids, evidence_ids)
        if item_errors:
            errors.extend(item_errors)
            continue
        validated_items.append(item)
    return validated_items, errors


def _split_validation_errors(errors: list[str]) -> tuple[list[str], list[str]]:
    reference_errors = [
        error for error in errors if any(error.startswith(prefix) for prefix in _REFERENCE_ERROR_PREFIXES)
    ]
    schema_errors = [error for error in errors if error not in reference_errors]
    return reference_errors, schema_errors


def _safe_review_agent_result(
    *,
    agent: str,
    agent_label: str,
    base: dict[str, Any],
    items_key: str,
    validated_count_key: str,
    builder: Callable[[], dict[str, Any]],
    validator: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    try:
        return validator(builder())
    except Exception as exc:
        return _failed_review_results(
            base=base,
            agent=agent,
            agent_label=agent_label,
            items_key=items_key,
            validated_count_key=validated_count_key,
            message=str(exc),
        )


def _failed_review_results(
    *,
    base: dict[str, Any],
    agent: str,
    agent_label: str,
    items_key: str,
    validated_count_key: str,
    message: str,
) -> dict[str, Any]:
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
    pattern: dict[str, Any],
    trace_ids: set[str],
    evidence_ids: set[str],
    *,
    id_field: str,
) -> list[str]:
    errors: list[str] = []
    required_text_fields = (
        id_field,
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


def _validate_pattern_collection(
    *,
    results: dict[str, Any],
    items_key: str,
    id_field: str,
    trace_ids: set[str],
    evidence_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    validated_items: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in results.get(items_key, []):
        item_errors = _pattern_validation_errors(
            item,
            trace_ids,
            evidence_ids,
            id_field=id_field,
        )
        if item_errors:
            errors.extend(item_errors)
            continue
        validated_items.append(item)
    return validated_items, errors


def _pattern_finder_results(
    *,
    base: dict[str, Any],
    critical_findings: list[dict[str, Any]],
    indeterminate_findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    failure_patterns = _build_review_observations(
        findings=critical_findings,
        trace_evidence=trace_evidence,
        id_field="pattern_id",
        id_prefix="pattern",
        severity="critical",
    )
    warning_observations = _build_review_observations(
        findings=indeterminate_findings,
        trace_evidence=trace_evidence,
        id_field="observation_id",
        id_prefix="warning",
        severity="warning",
    )
    if failure_patterns:
        summary = _pattern_summary(len(failure_patterns))
        status = AGENT_REVIEW_STATUS_PATTERNS_FOUND
    elif warning_observations:
        summary = WARNING_ONLY_PATTERN_FINDER_SUMMARY
        status = AGENT_REVIEW_STATUS_NO_ACTION
    else:
        summary = NO_ACTION_PATTERN_FINDER_SUMMARY
        status = AGENT_REVIEW_STATUS_NO_ACTION

    return {
        **base,
        "agent": "pattern_finder",
        "status": status,
        "summary": summary,
        "failure_patterns": failure_patterns,
        "warning_observations": warning_observations,
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


def _annotation_recommendation_validation_errors(
    recommendation: dict[str, Any], trace_ids: set[str], evidence_ids: set[str]
) -> list[str]:
    return _planner_item_validation_errors(
        recommendation,
        trace_ids,
        evidence_ids,
        id_field="recommendation_id",
        id_pattern=_ANNOTATION_RECOMMENDATION_ID_PATTERN,
        prefix_label="recommendation_id",
        required_text_fields=(
            "recommendation_id",
            "rationale",
            "review_instructions",
            "review_status",
        ),
        requires_human_review=True,
    )


def _future_control_candidate_validation_errors(
    candidate: dict[str, Any], trace_ids: set[str], evidence_ids: set[str]
) -> list[str]:
    errors = _planner_item_validation_errors(
        candidate,
        trace_ids,
        evidence_ids,
        id_field="candidate_id",
        id_pattern=_FUTURE_CONTROL_CANDIDATE_ID_PATTERN,
        prefix_label="candidate_id",
        required_text_fields=(
            "candidate_id",
            "rationale",
            "review_instructions",
            "review_status",
        ),
        requires_human_review=True,
    )
    finding_types = [str(item) for item in candidate.get("source_finding_types", [])]
    candidate_id = str(candidate.get("candidate_id") or "")
    if finding_types and not any(
        finding_type in {"unauthorized_dangerous_tool_execution", "dangerous_tool_policy_violation"}
        for finding_type in finding_types
    ):
        errors.append(
            "future control candidates require critical blocker evidence "
            f"for {candidate_id}"
        )
    return errors


def _duplicate_or_noise_validation_errors(
    group: dict[str, Any], trace_ids: set[str], evidence_ids: set[str]
) -> list[str]:
    errors: list[str] = []
    group_id = str(group.get("group_id") or "")
    group_id_match = _DUPLICATE_OR_NOISE_GROUP_ID_PATTERN.match(group_id)
    if not group_id_match:
        errors.append(f"invalid group_id {group_id}")
    for field in ("group_id", "rationale", "recommended_action"):
        if not str(group.get(field) or "").strip():
            errors.append(f"missing {field}")
    source_trace_ids = [str(item) for item in group.get("source_trace_ids", [])]
    source_evidence_ids = [str(item) for item in group.get("source_evidence_ids", [])]
    if not source_trace_ids:
        errors.append("missing source_trace_ids")
    if not source_evidence_ids:
        errors.append("missing source_evidence_ids")
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
    warning_findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped_findings = _group_findings_by_type(critical_findings, trace_evidence)
    if grouped_findings:
        primary_finding_type, primary_findings = grouped_findings[0]
        source_trace_ids = _planner_source_trace_ids(primary_findings)
        source_evidence_ids = _planner_source_evidence_ids(primary_findings)
        tool_name = _dataset_candidate_tool_name(trace_evidence, source_trace_ids)
        annotation_findings_type, annotation_findings = grouped_findings[min(1, len(grouped_findings) - 1)]
        annotation_trace_ids = _planner_source_trace_ids(annotation_findings)
        annotation_evidence_ids = _planner_source_evidence_ids(annotation_findings)
        return {
            **base,
            "agent": "dataset_planner",
            "status": AGENT_REVIEW_STATUS_CANDIDATES_FOUND,
            "summary": _dataset_planner_summary(grouped_findings),
            "dataset_candidates": [
                {
                    "candidate_id": _planner_item_id("dataset_candidate", primary_finding_type, 1),
                    "source_trace_ids": source_trace_ids,
                    "source_evidence_ids": source_evidence_ids,
                    "source_finding_types": [primary_finding_type],
                    "rationale": (
                        f"Use the repeated {primary_finding_type.replace('_', ' ')} evidence around "
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
            "annotation_recommendations": [
                {
                    "recommendation_id": _planner_item_id(
                        "annotation_recommendation", annotation_findings_type, 1
                    ),
                    "source_trace_ids": annotation_trace_ids,
                    "source_evidence_ids": annotation_evidence_ids,
                    "source_finding_types": [annotation_findings_type],
                    "rationale": (
                        "Add human-review annotation guidance so similar evidence is labeled "
                        "consistently before future dataset work."
                    ),
                    "review_instructions": (
                        "Review whether the cited traces represent one stable failure family or "
                        "multiple distinct cases before adding annotation guidance."
                    ),
                    "requires_human_review": True,
                    "review_status": "pending_review",
                }
            ],
            "future_control_candidates": [
                {
                    "candidate_id": _planner_item_id(
                        "future_control_candidate", primary_finding_type, 1
                    ),
                    "source_trace_ids": source_trace_ids,
                    "source_evidence_ids": source_evidence_ids,
                    "source_finding_types": [primary_finding_type],
                    "rationale": (
                        "The blocker evidence is strong enough to review as a possible future "
                        "release control after humans confirm scope and recurrence."
                    ),
                    "review_instructions": (
                        "Confirm the blocker pattern is stable across traces before turning it into "
                        "a future control candidate."
                    ),
                    "requires_human_review": True,
                    "review_status": "pending_review",
                }
            ],
            "duplicate_or_noise": [
                {
                    "group_id": _planner_item_id("duplicate_or_noise", annotation_findings_type, 1),
                    "source_trace_ids": annotation_trace_ids,
                    "source_evidence_ids": annotation_evidence_ids,
                    "rationale": (
                        "These traces should be merged or triaged for noise before creating extra "
                        "planning work."
                    ),
                    "recommended_action": "merge_similar_examples",
                    "requires_human_review": False,
                }
            ],
        }

    warning_grouped_findings = _group_findings_by_type(warning_findings, trace_evidence)
    if not warning_grouped_findings:
        return _no_action_review_results(
            base=base,
            agent="dataset_planner",
            summary=NO_ACTION_DATASET_PLANNER_SUMMARY,
            items_keys=_DATASET_PLANNER_ITEM_KEYS,
        )

    primary_finding_type, primary_findings = warning_grouped_findings[0]
    source_trace_ids = _planner_source_trace_ids(primary_findings)
    source_evidence_ids = _planner_source_evidence_ids(primary_findings)
    tool_name = _dataset_candidate_tool_name(trace_evidence, source_trace_ids)
    annotation_findings_type, annotation_findings = warning_grouped_findings[
        min(1, len(warning_grouped_findings) - 1)
    ]
    annotation_trace_ids = _planner_source_trace_ids(annotation_findings)
    annotation_evidence_ids = _planner_source_evidence_ids(annotation_findings)
    return {
        **base,
        "agent": "dataset_planner",
        "status": AGENT_REVIEW_STATUS_CANDIDATES_FOUND,
        "summary": _dataset_planner_summary(warning_grouped_findings),
        "dataset_candidates": [
            {
                "candidate_id": _planner_item_id("dataset_candidate", primary_finding_type, 1),
                "source_trace_ids": source_trace_ids,
                "source_evidence_ids": source_evidence_ids,
                "source_finding_types": [primary_finding_type],
                "rationale": (
                    f"Use the repeated {primary_finding_type.replace('_', ' ')} evidence around "
                    f"{tool_name} as a human-reviewed dataset candidate for warning-level follow-up."
                ),
                "review_instructions": (
                    "Confirm the cited traces are representative before converting them into "
                    "a controlled eval, reviewer checklist, or warning-only follow-up. Check "
                    "the trace story, span path, and supporting evidence IDs against the trace."
                ),
                "conversion_guidance": (
                    f"After human review, convert the cited {tool_name} warning into a future "
                    "eval case or reviewer aid. Do not promote warning-only evidence into a "
                    "blocker control without new critical evidence."
                ),
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
        "annotation_recommendations": [
            {
                "recommendation_id": _planner_item_id(
                    "annotation_recommendation", annotation_findings_type, 1
                ),
                "source_trace_ids": annotation_trace_ids,
                "source_evidence_ids": annotation_evidence_ids,
                "source_finding_types": [annotation_findings_type],
                "rationale": (
                    "Add human-review annotation guidance so similar evidence is labeled "
                    "consistently before future dataset work."
                ),
                "review_instructions": (
                    "Review whether the cited traces represent one stable failure family or "
                    "multiple distinct cases before adding annotation guidance."
                ),
                "requires_human_review": True,
                "review_status": "pending_review",
            }
        ],
        "future_control_candidates": [],
        "duplicate_or_noise": [],
    }


def _warning_metric_findings(
    records: list[EvidenceRecord],
    metrics_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    grouped_records = group_records_by_trace(records)
    warning_metrics = {
        str(metric.get("name") or "")
        for metric in metrics_summary.get("metrics", [])
        if metric.get("passes_threshold") is False
        and str(metric.get("decision_impact") or "") == "warning"
    }
    findings: list[dict[str, Any]] = []
    if "crash_analysis_format_compliance" in warning_metrics:
        findings.extend(
            _warning_findings_from_spans(
                grouped_records,
                finding_type="response_format_warning",
                predicate=lambda span: span.attributes.get("tool.output_schema_valid") is False,
            )
        )
    if "technical_tool_success_rate" in warning_metrics:
        findings.extend(
            _warning_findings_from_spans(
                grouped_records,
                finding_type="technical_tool_failure_warning",
                predicate=lambda span: span.attributes.get("tool.success") is False,
            )
        )
    return findings


def _warning_findings_from_spans(
    grouped_records: dict[str, list[EvidenceRecord]],
    *,
    finding_type: str,
    predicate: Callable[[SpanEvent], bool],
) -> list[dict[str, Any]]:
    matched_findings: list[dict[str, Any]] = []
    for trace_id, trace_records in grouped_records.items():
        matching_span = next(
            (
                record
                for record in trace_records
                if isinstance(record, SpanEvent)
                and record.event_type.startswith("tool.")
                and predicate(record)
            ),
            None,
        )
        if matching_span is None:
            continue
        matched_findings.append(
            {
                "trace_id": trace_id,
                "case_id": matching_span.case_id,
                "user_role": matching_span.user_role,
                "input_text": matching_span.input_text,
                "finding_type": finding_type,
                "severity": "warning",
                "evidence_ids": [matching_span.span_id],
                "attributes": {
                    key: matching_span.attributes.get(key)
                    for key in (
                        "tool_name",
                        "expected_allowed",
                        "actual_allowed",
                        "selected_intent_id",
                        "expected_intent_id",
                        "tool.error_code",
                        "tool.output_schema_valid",
                        "tool.success",
                    )
                    if key in matching_span.attributes
                },
            }
        )
    if len(matched_findings) < 2:
        return []
    return matched_findings


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
    repeated_types = sorted({str(finding.get("finding_type") or "") for finding in critical_findings})
    return [
        "Confirm the trace story matches the cited blocker evidence.",
        f"Check whether role {role} reached a dangerous path that policy should have blocked.",
        f"Look for repeated blocker families: {', '.join(repeated_types)}.",
    ]


def _problem_summary(
    finding_type: str, findings: list[dict[str, Any]], examples: list[dict[str, Any]]
) -> str:
    role = findings[0].get("user_role") or "unknown role"
    if finding_type == "response_format_warning":
        return (
            "Approved traces still showed repeated response-format drift on a high-risk review "
            "path, even though blocker safety controls passed."
        )
    if finding_type == "technical_tool_failure_warning":
        return (
            "Approved traces still showed repeated non-blocking tool execution failures on a "
            "high-risk review path."
        )
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
    if finding_type == "response_format_warning":
        return (
            "Recurring warning-only format drift should stay visible for human follow-up and "
            "future dataset planning."
        )
    if finding_type == "technical_tool_failure_warning":
        return (
            "Recurring warning-only tool failures can justify human-reviewed coverage work "
            "without changing the current release decision."
        )
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
    if finding_type == "response_format_warning":
        return (
            f"Policy allowed {tool_name}, but runtime still recorded response-format variance "
            "that remains warning-only."
        )
    if finding_type == "technical_tool_failure_warning":
        error_code = attributes.get("tool.error_code") or "runtime failure"
        return (
            f"Policy allowed {tool_name}, but runtime still recorded non-blocking tool failure "
            f"signals such as {error_code}."
        )
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


def _group_findings_by_type(
    findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    if not findings or not trace_evidence:
        return []

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    valid_trace_ids = {str(trace.get("trace_id") or "") for trace in trace_evidence}
    for finding in findings:
        if str(finding.get("trace_id") or "") not in valid_trace_ids:
            continue
        grouped[str(finding.get("finding_type") or "unknown")].append(finding)
    return sorted(grouped.items(), key=lambda item: (finding_priority(item[0]), item[0]))


def _selected_findings_by_type(
    findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]] | None:
    grouped = _group_findings_by_type(findings, trace_evidence)
    return grouped[0] if grouped else None


def _build_review_observations(
    *,
    findings: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
    id_field: str,
    id_prefix: str,
    severity: str,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for finding_type, grouped_findings in _group_findings_by_type(findings, trace_evidence):
        supporting_trace_ids = sorted({str(finding["trace_id"]) for finding in grouped_findings})
        supporting_evidence_ids = sorted(
            {
                str(evidence_id)
                for finding in grouped_findings
                for evidence_id in finding.get("evidence_ids", [])
            }
        )
        examples = [
            _example_trace(trace)
            for trace in trace_evidence
            if str(trace.get("trace_id")) in supporting_trace_ids
        ][:3]
        title = _PATTERN_TITLES.get(finding_type, finding_type.replace("_", " ").title())
        observations.append(
            {
                id_field: f"{id_prefix}.{finding_type}",
                "title": title,
                "severity": severity,
                "problem_summary": _problem_summary(finding_type, grouped_findings, examples),
                "why_it_matters": _why_it_matters(finding_type),
                "policy_runtime_mismatch": _policy_runtime_mismatch(
                    finding_type,
                    grouped_findings,
                ),
                "supporting_trace_ids": supporting_trace_ids,
                "supporting_evidence_ids": supporting_evidence_ids,
                "example_traces": examples,
            }
        )
    return observations


def _pattern_summary(pattern_count: int) -> str:
    label = "pattern" if pattern_count == 1 else "patterns"
    return f"Pattern Finder found {pattern_count} release-safety {label}."


def _dataset_planner_summary(grouped_findings: list[tuple[str, list[dict[str, Any]]]]) -> str:
    candidate_count = len(grouped_findings)
    label = "candidate" if candidate_count == 1 else "candidates"
    return f"Dataset Planner proposed {candidate_count} human-review {label}."


def _dataset_planner_collection_specs() -> tuple[
    tuple[str, str, Callable[[dict[str, Any], set[str], set[str]], list[str]]],
    ...,
]:
    return (
        (
            "dataset_candidates",
            "validated_dataset_candidates",
            _dataset_candidate_validation_errors,
        ),
        (
            "annotation_recommendations",
            "validated_annotation_recommendations",
            _annotation_recommendation_validation_errors,
        ),
        (
            "future_control_candidates",
            "validated_future_control_candidates",
            _future_control_candidate_validation_errors,
        ),
        (
            "duplicate_or_noise",
            "validated_duplicate_or_noise",
            _duplicate_or_noise_validation_errors,
        ),
    )


def _planner_item_id(prefix: str, finding_type: str, index: int) -> str:
    return f"{prefix}.{finding_type}.{index:02d}"


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


def _planner_source_trace_ids(findings: list[dict[str, Any]]) -> list[str]:
    return sorted({str(finding["trace_id"]) for finding in findings})


def _planner_source_evidence_ids(findings: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(evidence_id)
            for finding in findings
            for evidence_id in finding.get("evidence_ids", [])
        }
    )


def _planner_item_validation_errors(
    item: dict[str, Any],
    trace_ids: set[str],
    evidence_ids: set[str],
    *,
    id_field: str,
    id_pattern: re.Pattern[str],
    prefix_label: str,
    required_text_fields: tuple[str, ...],
    requires_human_review: bool,
) -> list[str]:
    errors: list[str] = []
    for field in required_text_fields:
        if not str(item.get(field) or "").strip():
            errors.append(f"missing {field}")
    source_trace_ids = [str(value) for value in item.get("source_trace_ids", [])]
    source_evidence_ids = [str(value) for value in item.get("source_evidence_ids", [])]
    source_finding_types = [str(value) for value in item.get("source_finding_types", [])]
    identifier = str(item.get(id_field) or "")
    if not source_trace_ids:
        errors.append("missing source_trace_ids")
    if not source_evidence_ids:
        errors.append("missing source_evidence_ids")
    if not source_finding_types:
        errors.append("missing source_finding_types")
    id_match = id_pattern.match(identifier)
    if not id_match:
        errors.append(f"invalid {prefix_label} {identifier}")
    elif source_finding_types and id_match.group(1) not in source_finding_types:
        errors.append(
            f"{prefix_label} finding type does not match source_finding_types for {identifier}"
        )
    if requires_human_review and item.get("requires_human_review") is not True:
        errors.append("requires_human_review must be true")
    for trace_id in source_trace_ids:
        if trace_id not in trace_ids:
            errors.append(f"unknown trace_id {trace_id}")
    for evidence_id in source_evidence_ids:
        if evidence_id not in evidence_ids:
            errors.append(f"unknown evidence_id {evidence_id}")
    return errors


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
    items_keys: tuple[str, ...],
) -> dict[str, Any]:
    payload = {
        **base,
        "agent": agent,
        "status": AGENT_REVIEW_STATUS_NO_ACTION,
        "summary": summary,
    }
    for items_key in items_keys:
        payload[items_key] = []
    return payload


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
