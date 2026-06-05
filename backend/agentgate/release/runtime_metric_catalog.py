"""Runtime metric catalog for AgentGate release evidence.

This module keeps metric-specific facts behind one interface: implementation
families, required evidence fields, label provenance, and metric source rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.agentgate.core.agent_pack import MetricDefinitionEntry

MetricSourceKind = Literal["eval_label", "span_aggregate"]


@dataclass(frozen=True)
class RuntimeMetricSpec:
    metric_id: str
    aggregator_key: str
    source_kind: MetricSourceKind
    primary_eval_label: str | None = None
    required_span_attributes: tuple[str, ...] = ()
    required_eval_labels: tuple[str, ...] = ()


RUNTIME_METRIC_SPECS: dict[str, RuntimeMetricSpec] = {
    "intent_routing_accuracy": RuntimeMetricSpec(
        metric_id="intent_routing_accuracy",
        aggregator_key="intent_routing",
        source_kind="eval_label",
        primary_eval_label="intent_routing_correct",
        required_span_attributes=("expected.intent_id", "router.selected_intent_id"),
        required_eval_labels=("intent_routing_correct",),
    ),
    "hallucination_rate": RuntimeMetricSpec(
        metric_id="hallucination_rate",
        aggregator_key="eval_label_rate",
        source_kind="eval_label",
        primary_eval_label="groundedness",
        required_eval_labels=("groundedness",),
    ),
    "technical_tool_success_rate": RuntimeMetricSpec(
        metric_id="technical_tool_success_rate",
        aggregator_key="tool_success",
        source_kind="span_aggregate",
        required_span_attributes=("tool.success",),
    ),
    "unauthorized_dangerous_tool_attempt_rate": RuntimeMetricSpec(
        metric_id="unauthorized_dangerous_tool_attempt_rate",
        aggregator_key="policy_preflight",
        source_kind="span_aggregate",
        required_span_attributes=("expected.allowed", "policy.preflight.decision"),
    ),
    "dangerous_tool_policy_violation_rate": RuntimeMetricSpec(
        metric_id="dangerous_tool_policy_violation_rate",
        aggregator_key="policy_preflight",
        source_kind="span_aggregate",
        required_span_attributes=("policy.preflight.decision", "policy.violation"),
    ),
    "sensitive_output_violation_rate": RuntimeMetricSpec(
        metric_id="sensitive_output_violation_rate",
        aggregator_key="eval_label_rate",
        source_kind="eval_label",
        primary_eval_label="sensitive_output_ok",
        required_span_attributes=("response.raw_event_dumped",),
        required_eval_labels=("sensitive_output_ok",),
    ),
    "crash_analysis_format_compliance": RuntimeMetricSpec(
        metric_id="crash_analysis_format_compliance",
        aggregator_key="eval_label_rate",
        source_kind="eval_label",
        primary_eval_label="response_format_ok",
        required_eval_labels=("response_format_ok",),
    ),
}

METRIC_IDS_BY_AGGREGATOR_KEY: dict[str, frozenset[str]] = {}
for spec in RUNTIME_METRIC_SPECS.values():
    metric_ids = set(METRIC_IDS_BY_AGGREGATOR_KEY.get(spec.aggregator_key, frozenset()))
    metric_ids.add(spec.metric_id)
    METRIC_IDS_BY_AGGREGATOR_KEY[spec.aggregator_key] = frozenset(metric_ids)

EVAL_DEPENDENT_METRICS = frozenset(
    metric_id
    for metric_id, spec in RUNTIME_METRIC_SPECS.items()
    if spec.source_kind == "eval_label"
)
SPAN_AGGREGATE_METRICS = frozenset(
    metric_id
    for metric_id, spec in RUNTIME_METRIC_SPECS.items()
    if spec.source_kind == "span_aggregate"
)


class RuntimeMetricCatalog:
    def __init__(self, effective_metrics: tuple[MetricDefinitionEntry, ...] | None = None) -> None:
        self._configured_aggregator_keys = {
            entry.metric_id: entry.aggregator_key for entry in effective_metrics or ()
        }

    def threshold_metric_names(self, threshold_keys: list[str] | tuple[str, ...]) -> set[str]:
        return {metric_name_from_threshold_key(threshold_key) for threshold_key in threshold_keys}

    def configured_aggregator_key(self, metric_id: str) -> str:
        return self._configured_aggregator_keys.get(metric_id, "")

    def is_implemented(self, metric_id: str) -> bool:
        aggregator_key = self.configured_aggregator_key(metric_id)
        return is_metric_implemented(metric_id, aggregator_key)

    def primary_eval_label(self, metric_id: str) -> str | None:
        spec = RUNTIME_METRIC_SPECS.get(metric_id)
        return spec.primary_eval_label if spec else None

    def required_span_attributes(self, metric_id: str) -> tuple[str, ...]:
        spec = RUNTIME_METRIC_SPECS.get(metric_id)
        return spec.required_span_attributes if spec else ()

    def required_eval_labels(self, metric_id: str) -> tuple[str, ...]:
        spec = RUNTIME_METRIC_SPECS.get(metric_id)
        return spec.required_eval_labels if spec else ()

    def required_fields(self) -> tuple[str, ...]:
        fields: set[str] = set()
        for spec in RUNTIME_METRIC_SPECS.values():
            fields.update(spec.required_span_attributes)
            fields.update(spec.required_eval_labels)
        return tuple(sorted(fields))

    def eval_dependent_metrics(self) -> frozenset[str]:
        return EVAL_DEPENDENT_METRICS


def supported_aggregator_keys() -> frozenset[str]:
    return frozenset(METRIC_IDS_BY_AGGREGATOR_KEY)


def implemented_metric_ids() -> frozenset[str]:
    return frozenset(RUNTIME_METRIC_SPECS)


def is_metric_implemented(metric_id: str, aggregator_key: str) -> bool:
    return metric_id in METRIC_IDS_BY_AGGREGATOR_KEY.get(aggregator_key, frozenset())


def metric_name_from_threshold_key(threshold_key: str) -> str:
    for suffix in ("_min", "_max"):
        if threshold_key.endswith(suffix):
            return threshold_key[: -len(suffix)]
    return threshold_key


def metric_source_for(
    metric_name: str,
    *,
    evidence_source_type: str,
    status: str,
    label_evaluator: str | None = None,
) -> str:
    if status == "not_available":
        return "not_available"
    if evidence_source_type == "local_jsonl":
        return "seed_fallback"
    if metric_name in SPAN_AGGREGATE_METRICS:
        return "span_aggregate"
    if label_evaluator and label_evaluator.startswith("phoenix"):
        return "phoenix_eval_automation"
    if metric_name in EVAL_DEPENDENT_METRICS:
        return "phoenix_eval_automation"
    return "span_aggregate"
