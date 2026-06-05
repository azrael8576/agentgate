"""Resolve EvalSuite release gate bindings to runtime metric names."""

from __future__ import annotations

from typing import Any

from backend.agentgate.core.agent_pack import MetricDefinitionEntry, get_default_agent_pack
from backend.agentgate.release.runtime_metric_catalog import (
    RuntimeMetricCatalog,
    metric_name_from_threshold_key,
)
from backend.agentgate.schemas import ReleasePolicy


def runtime_metric_names(policy: ReleasePolicy) -> set[str]:
    return {
        metric_name_from_threshold_key(threshold_key)
        for threshold_key in policy.decision_thresholds
    }


def validate_suite_required_metrics(
    required_metrics: list[Any],
    policy: ReleasePolicy,
    *,
    gate_binding: dict[str, Any] | None = None,
    metric_graders: dict[str, list[str]] | None = None,
    effective_metrics: tuple[MetricDefinitionEntry, ...] | None = None,
) -> dict[str, Any]:
    graders = (
        metric_graders
        if metric_graders is not None
        else get_default_agent_pack().metric_graders()
    )
    catalog = RuntimeMetricCatalog(effective_metrics or get_default_agent_pack().effective_metrics)
    runtime_names = runtime_metric_names(policy)
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    blocking_issues: list[str] = []

    for required_metric in required_metrics:
        suite_metric = _suite_metric_name(required_metric)
        runtime_metric = resolve_suite_metric_to_runtime(suite_metric, gate_binding=gate_binding)
        if runtime_metric is None:
            checks.append(
                {
                    "suite_metric": suite_metric,
                    "runtime_metric": None,
                    "status": "not_implemented",
                }
            )
            warnings.append(
                f"{suite_metric} is declared in the suite but has no runtime aggregator yet."
            )
            continue

        if runtime_metric not in runtime_names:
            checks.append(
                {
                    "suite_metric": suite_metric,
                    "runtime_metric": runtime_metric,
                    "status": "missing_runtime",
                }
            )
            blocking_issues.append(_missing_runtime_message(suite_metric, runtime_metric))
            continue

        if not catalog.is_implemented(runtime_metric):
            checks.append(
                {
                    "suite_metric": suite_metric,
                    "runtime_metric": runtime_metric,
                    "status": "missing_aggregator",
                }
            )
            blocking_issues.append(_missing_aggregator_message(suite_metric, runtime_metric))
            continue
        if runtime_metric not in graders:
            checks.append(
                {
                    "suite_metric": suite_metric,
                    "runtime_metric": runtime_metric,
                    "status": "missing_grader_config",
                }
            )
            blocking_issues.append(_missing_grader_message(suite_metric, runtime_metric))
            continue

        status = "mapped" if suite_metric != runtime_metric else "direct"
        checks.append(
            {
                "suite_metric": suite_metric,
                "runtime_metric": runtime_metric,
                "status": status,
            }
        )

    return {
        "checks": checks,
        "warnings": warnings,
        "blocking_issues": blocking_issues,
        "contract_valid": not blocking_issues,
    }


def resolve_suite_metric_to_runtime(
    suite_metric: str,
    *,
    gate_binding: dict[str, Any] | None = None,
) -> str | None:
    metric_bindings = _metric_bindings(gate_binding)
    if suite_metric in metric_bindings:
        return metric_bindings[suite_metric]
    return suite_metric


def resolve_release_gate_binding(gate_binding: dict[str, Any] | None) -> dict[str, Any] | None:
    if not gate_binding:
        return None

    required_metrics = gate_binding.get("required_metrics")
    if not isinstance(required_metrics, list) or not required_metrics:
        return None

    suite_metrics: list[dict[str, Any]] = []
    runtime_blocker_metrics: list[str] = []
    not_implemented_suite_metrics: list[str] = []

    for required_metric in required_metrics:
        suite_metric = _suite_metric_name(required_metric)
        runtime_metric = _runtime_metric_from_required_metric(required_metric)
        if runtime_metric == "":
            runtime_metric = resolve_suite_metric_to_runtime(suite_metric, gate_binding=gate_binding)

        if runtime_metric is None:
            suite_metrics.append(
                {
                    "suite_metric": suite_metric,
                    "runtime_metric": None,
                    "status": "not_implemented",
                }
            )
            not_implemented_suite_metrics.append(suite_metric)
            continue

        status = "mapped" if runtime_metric != suite_metric else "direct"
        suite_metrics.append(
            {
                "suite_metric": suite_metric,
                "runtime_metric": runtime_metric,
                "status": status,
            }
        )
        runtime_blocker_metrics.append(runtime_metric)

    return {
        "gate_id": gate_binding.get("gate_id"),
        "blocking": bool(gate_binding.get("blocking", True)),
        "suite_metrics": suite_metrics,
        "runtime_blocker_metrics": runtime_blocker_metrics,
        "not_implemented_suite_metrics": not_implemented_suite_metrics,
    }


def _metric_bindings(gate_binding: dict[str, Any] | None) -> dict[str, str | None]:
    if not gate_binding:
        return {}
    configured = gate_binding.get("metric_bindings")
    if not isinstance(configured, list):
        return {}

    bindings: dict[str, str | None] = {}
    for item in configured:
        if not isinstance(item, dict):
            continue
        suite_metric = str(item.get("suite_metric", "")).strip()
        if not suite_metric:
            continue
        runtime_metric = item.get("runtime_metric")
        if runtime_metric is None:
            bindings[suite_metric] = None
        else:
            bindings[suite_metric] = str(runtime_metric).strip()
    return bindings


def _suite_metric_name(required_metric: Any) -> str:
    if isinstance(required_metric, dict):
        return str(required_metric.get("suite_metric") or required_metric.get("metric") or "").strip()
    return str(required_metric)


def _runtime_metric_from_required_metric(required_metric: Any) -> str | None:
    if not isinstance(required_metric, dict):
        return ""
    if "runtime_metric" not in required_metric:
        return ""
    runtime_metric = required_metric.get("runtime_metric")
    if runtime_metric is None:
        return None
    return str(runtime_metric).strip()


def _missing_runtime_message(suite_metric: str, runtime_metric: str) -> str:
    return (
        f"{suite_metric} maps to {runtime_metric}, "
        "which is missing from policy decision_thresholds."
    )


def _missing_aggregator_message(suite_metric: str, runtime_metric: str) -> str:
    return (
        f"{suite_metric} maps to {runtime_metric}, "
        "which has no metrics_aggregator implementation."
    )


def _missing_grader_message(suite_metric: str, runtime_metric: str) -> str:
    return (
        f"{suite_metric} maps to {runtime_metric}, "
        "which is missing source_grader_ids in AgentPack metrics."
    )
