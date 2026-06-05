from typing import Any

from backend.agentgate.core.agent_pack import (
    RegressionGateCatalog,
    get_default_agent_pack,
)


def _resolve_catalog(catalog: RegressionGateCatalog | None) -> RegressionGateCatalog:
    return catalog or get_default_agent_pack().regression_gate_catalog()


def diagnose_findings(
    critical_findings: list[dict[str, Any]],
    *,
    catalog: RegressionGateCatalog | None = None,
) -> dict[str, list[dict[str, Any]]]:
    gate_catalog = _resolve_catalog(catalog)
    diagnoses: list[dict[str, Any]] = []
    regression_gates: dict[str, dict[str, Any]] = {}

    for finding in critical_findings:
        template = gate_catalog.findings[finding["finding_type"]]
        diagnoses.append(
            {
                "trace_id": finding["trace_id"],
                "case_id": finding["case_id"],
                "diagnosis": finding["finding_type"],
                "severity": finding["severity"],
                "required_fix": template["required_fix"],
                "evidence_ids": finding["evidence_ids"],
            }
        )
        _upsert_gate(
            regression_gates,
            gate_id=template["gate_id"],
            expected_behavior=template["expected_behavior"],
            required_fix=template["required_fix"],
            trigger=f"material_violation:{finding['finding_type']}",
            evidence_id=str(finding["trace_id"]),
        )

    return {
        "dangerous_session_diagnoses": diagnoses,
        "regression_gates": list(regression_gates.values()),
    }


def build_regression_gates(
    *,
    critical_findings: list[dict[str, Any]],
    indeterminate_findings: list[dict[str, Any]],
    metrics_summary: dict[str, Any],
    high_risk_activity_log: list[dict[str, Any]] | None = None,
    catalog: RegressionGateCatalog | None = None,
) -> list[dict[str, Any]]:
    gate_catalog = _resolve_catalog(catalog)
    gates_by_id: dict[str, dict[str, Any]] = {
        gate["gate_id"]: gate
        for gate in diagnose_findings(critical_findings, catalog=gate_catalog)["regression_gates"]
    }

    for finding in indeterminate_findings:
        template = gate_catalog.findings[finding["finding_type"]]
        _upsert_gate(
            gates_by_id,
            gate_id=template["gate_id"],
            expected_behavior=template["expected_behavior"],
            required_fix=template["required_fix"],
            trigger=f"indeterminate_session:{finding['finding_type']}",
            evidence_id=str(finding["trace_id"]),
        )

    for metric in metrics_summary.get("metrics", []):
        if metric.get("status") != "computed" or metric.get("passes_threshold") is not False:
            continue
        if metric.get("decision_impact") != "blocker":
            continue
        template = gate_catalog.metrics.get(str(metric.get("name")))
        if template is None:
            continue
        gate_id = template["gate_id"]
        _upsert_gate(
            gates_by_id,
            gate_id=gate_id,
            expected_behavior=template["expected_behavior"],
            required_fix=template["required_fix"],
            trigger=f"control_failed:{metric['name']}",
        )
        for trace_id in _trace_ids_for_metric(
            str(metric.get("name")),
            high_risk_activity_log or [],
            gate_catalog,
        ):
            _upsert_gate(
                gates_by_id,
                gate_id=gate_id,
                expected_behavior=template["expected_behavior"],
                required_fix=template["required_fix"],
                trigger=f"control_failed:{metric['name']}",
                evidence_id=trace_id,
            )

    return list(gates_by_id.values())


def _trace_ids_for_metric(
    metric_name: str,
    activity_log: list[dict[str, Any]],
    catalog: RegressionGateCatalog,
) -> list[str]:
    finding_types = catalog.metric_trace_filters.get(metric_name, ())
    trace_ids: list[str] = []
    for entry in activity_log:
        entry_findings = set(entry.get("finding_types", []))
        verdict = str(entry.get("verdict", ""))
        if verdict == "authorized":
            continue
        if (
            finding_types
            and not entry_findings.intersection(finding_types)
            and verdict != "indeterminate"
        ):
            continue
        trace_id = str(entry.get("trace_id", ""))
        if trace_id and trace_id not in trace_ids:
            trace_ids.append(trace_id)
    return trace_ids


def _upsert_gate(
    gates_by_id: dict[str, dict[str, Any]],
    *,
    gate_id: str,
    expected_behavior: str,
    required_fix: str,
    trigger: str,
    evidence_id: str | None = None,
) -> None:
    gate = gates_by_id.setdefault(
        gate_id,
        {
            "gate_id": gate_id,
            "expected_behavior": expected_behavior,
            "required_fix": required_fix,
            "trigger": trigger,
            "source_evidence_ids": [],
        },
    )
    if evidence_id and evidence_id not in gate["source_evidence_ids"]:
        gate["source_evidence_ids"].append(evidence_id)
