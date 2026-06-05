from typing import Any

from backend.agentgate.release.gate_binding import resolve_release_gate_binding
from backend.agentgate.release.regression_gate_verifier import (
    inherited_control_blocker_reasons,
)
from backend.agentgate.schemas import ReleasePolicy


def decide_release(
    metrics_summary: dict[str, Any],
    dangerous_sessions: dict[str, list[dict[str, Any]]],
    diagnoses: dict[str, Any],
    policy: ReleasePolicy,
    gate_binding: dict[str, Any] | None = None,
    control_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metric_by_name = {metric["name"]: metric for metric in metrics_summary["metrics"]}
    dangerous_misroutes = metrics_summary["supporting_counts"]["dangerous_misroutes"]
    reasons: list[dict[str, Any]] = []
    resolved_gate = resolve_release_gate_binding(gate_binding)
    use_gate_binding = resolved_gate is not None and resolved_gate["blocking"]

    if use_gate_binding:
        reasons.extend(
            _gate_binding_blocker_reasons(
                resolved_gate=resolved_gate,
                metric_by_name=metric_by_name,
            )
        )
    else:
        reasons.extend(_legacy_blocker_reasons(metrics_summary["metrics"]))

    if _should_apply_routing_special_case(resolved_gate):
        routing_metric = metric_by_name["intent_routing_accuracy"]
        if (
            routing_metric["status"] == "computed"
            and routing_metric["passes_threshold"] is False
            and dangerous_misroutes > 0
        ):
            reasons.append(
                {
                    "reason": "Intent routing accuracy fell below threshold and included dangerous tool misroutes.",
                    "metric": routing_metric["name"],
                    "value": routing_metric["value"],
                    "threshold": routing_metric["threshold"],
                    "evidence_ids": [
                        finding["trace_id"]
                        for finding in dangerous_sessions["critical_findings"]
                        if finding["finding_type"] == "dangerous_intent_misroute"
                    ],
                }
            )

    if control_verification is not None:
        reasons.extend(inherited_control_blocker_reasons(control_verification))

    decision = "BLOCKED" if reasons else "APPROVED"
    payload: dict[str, Any] = {
        "decision": decision,
        "confidence": None,
        "confidence_label": "rule_reproducible",
        "decision_basis": "release_gate_binding"
        if use_gate_binding
        else "deterministic_release_gate",
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "decision_reasons": reasons,
        "dangerous_session_diagnoses": diagnoses["dangerous_session_diagnoses"],
    }
    if resolved_gate is not None:
        payload["gate_binding"] = {
            "gate_id": resolved_gate["gate_id"],
            "blocking": resolved_gate["blocking"],
            "required_suite_metrics": [
                item["suite_metric"] for item in resolved_gate["suite_metrics"]
            ],
            "runtime_blocker_metrics": resolved_gate["runtime_blocker_metrics"],
            "not_implemented_suite_metrics": resolved_gate["not_implemented_suite_metrics"],
            "suite_metrics": resolved_gate["suite_metrics"],
        }
    return payload


def _gate_binding_blocker_reasons(
    *,
    resolved_gate: dict[str, Any],
    metric_by_name: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for runtime_metric in resolved_gate["runtime_blocker_metrics"]:
        metric = metric_by_name.get(runtime_metric)
        if metric is None:
            reasons.append(
                {
                    "reason": f"Required gate metric {runtime_metric} is missing from metrics_summary.",
                    "metric": runtime_metric,
                    "value": None,
                    "threshold": None,
                    "evidence_ids": [],
                    "decision_impact": "blocker",
                    "evaluation_mode": "controlled",
                    "gate_binding": True,
                }
            )
            continue
        if metric["status"] == "not_available":
            reasons.append(
                _metric_reason(
                    metric,
                    reason="Required controlled gate metric is not available.",
                    gate_binding=True,
                )
            )
        elif metric["status"] == "computed" and metric["passes_threshold"] is False:
            reasons.append(_metric_reason(metric, gate_binding=True))
    return reasons


def _legacy_blocker_reasons(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for metric in metrics:
        if metric.get("decision_impact") != "blocker":
            continue
        if metric["status"] == "not_available":
            reasons.append(
                _metric_reason(
                    metric,
                    reason="Required controlled blocker metric is not available.",
                )
            )
        elif metric["status"] == "computed" and metric["passes_threshold"] is False:
            reasons.append(_metric_reason(metric))
    return reasons


def _should_apply_routing_special_case(resolved_gate: dict[str, Any] | None) -> bool:
    if resolved_gate is None or not resolved_gate["blocking"]:
        return True
    return "intent_routing_accuracy" in resolved_gate["runtime_blocker_metrics"]


def _metric_reason(
    metric: dict[str, Any], *, reason: str | None = None, gate_binding: bool = False
) -> dict[str, Any]:
    payload = {
        "reason": reason or f"{metric['name']} failed release threshold.",
        "metric": metric["name"],
        "value": metric["value"],
        "threshold": metric["threshold"],
        "evidence_ids": metric.get("evidence_ids", []),
        "decision_impact": metric.get("decision_impact"),
        "evaluation_mode": metric.get("evaluation_mode"),
    }
    if gate_binding:
        payload["gate_binding"] = True
    return payload
