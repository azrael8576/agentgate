"""Coverage checks for Phoenix span attributes and eval annotations."""

from __future__ import annotations

from typing import Any

from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.release.evidence_loader import EvidenceRecord
from backend.agentgate.release.metrics_aggregator import aggregate_metrics
from backend.agentgate.release.runtime_metric_catalog import (
    EVAL_DEPENDENT_METRICS,
    RuntimeMetricCatalog,
)
from backend.agentgate.schemas import ReleasePolicy
from backend.agentgate.schemas.evidence import SpanEvent

# Local seed JSONL uses flat AgentGate attrs; Phoenix MCP normalizes to dotted OTel names.
FLAT_TO_OTEL_ALIASES: dict[str, str] = {
    "expected_allowed": "expected.allowed",
    "actual_allowed": "policy.preflight.decision",
    "selected_intent_id": "router.selected_intent_id",
    "expected_intent_id": "expected.intent_id",
    "policy_violation": "policy.violation",
    "raw_event_dumped": "response.raw_event_dumped",
    "tool_name": "tool.name",
    "risk_level": "tool.risk_level",
}


def build_coverage_report(
    records: list[EvidenceRecord],
    policy: ReleasePolicy,
    *,
    evidence_source_type: str = "phoenix_mcp",
    metric_graders: dict[str, list[str]] | None = None,
    metric_decision_impact: dict[str, str] | None = None,
    effective_metrics: tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    spans = [record for record in records if isinstance(record, SpanEvent)]
    labels = [record for record in records if isinstance(record, EvalLabel)]
    catalog = RuntimeMetricCatalog(effective_metrics)
    metrics_summary = aggregate_metrics(
        records,
        policy,
        evidence_source_type=evidence_source_type,
        metric_graders=metric_graders,
        metric_decision_impact=metric_decision_impact,
        effective_metrics=effective_metrics,
    )

    span_attrs = _collect_span_attributes(spans)
    label_names = {label.label_name for label in labels}
    computed_metrics = {
        metric["name"] for metric in metrics_summary["metrics"] if metric["status"] == "computed"
    }
    missing_by_metric: dict[str, list[str]] = {}
    metric_names = [metric["name"] for metric in metrics_summary["metrics"]]

    for metric_name in metric_names:
        if metric_name in computed_metrics:
            continue
        required_attrs = catalog.required_span_attributes(metric_name)
        missing = [attr for attr in required_attrs if attr not in span_attrs]
        if missing:
            missing_by_metric.setdefault(metric_name, []).extend(missing)

    for metric_name in metric_names:
        if metric_name in computed_metrics:
            continue
        required_labels = catalog.required_eval_labels(metric_name)
        missing = [label for label in required_labels if label not in label_names]
        if missing:
            missing_by_metric.setdefault(metric_name, []).extend(missing)

    unavailable_metrics = [
        metric["name"]
        for metric in metrics_summary["metrics"]
        if metric["status"] == "not_available"
    ]
    for metric_name in unavailable_metrics:
        missing_by_metric.setdefault(metric_name, []).append("metric_not_computed")

    required_fields = list(catalog.required_fields())
    present_count = sum(
        1
        for field in required_fields
        if field in span_attrs
        or field in label_names
        or _field_covered_by_computed_metric(field, computed_metrics)
    )
    missing_count = len(required_fields) - present_count
    eval_metrics_ready = all(
        metric["status"] == "computed"
        for metric in metrics_summary["metrics"]
        if metric["name"] in EVAL_DEPENDENT_METRICS
    )

    return {
        "evidence_source_type": evidence_source_type,
        "required_fields": required_fields,
        "present_count": present_count,
        "missing_count": missing_count,
        "missing_by_metric": missing_by_metric,
        "ready_for_release_gate": eval_metrics_ready and not missing_by_metric,
        "metrics_summary": metrics_summary["metrics"],
        "supporting_counts": metrics_summary["supporting_counts"],
    }


def _field_covered_by_computed_metric(field: str, computed_metrics: set[str]) -> bool:
    catalog = RuntimeMetricCatalog()
    for metric_name in computed_metrics:
        if field in catalog.required_span_attributes(metric_name):
            return True
        if field in catalog.required_eval_labels(metric_name):
            return True
    return False


def _collect_span_attributes(spans: list[SpanEvent]) -> set[str]:
    raw_attrs: set[str] = set()
    for span in spans:
        raw_attrs.update(span.attributes.keys())

    canonical = set(raw_attrs)
    for flat_name, dotted_name in FLAT_TO_OTEL_ALIASES.items():
        if flat_name in raw_attrs:
            canonical.add(dotted_name)
        if dotted_name in raw_attrs:
            canonical.add(flat_name)

    for span in spans:
        attrs = span.attributes
        has_permission_pair = ("expected_allowed" in attrs and "actual_allowed" in attrs) or (
            "expected.allowed" in attrs and "policy.preflight.decision" in attrs
        )
        if has_permission_pair:
            canonical.update(
                {
                    "expected.allowed",
                    "policy.preflight.decision",
                    "policy.violation",
                    "expected_allowed",
                    "actual_allowed",
                }
            )
        if attrs.get("policy_violation") is True or attrs.get("policy.violation") is True:
            canonical.update({"policy.violation", "policy_violation"})

    return canonical
