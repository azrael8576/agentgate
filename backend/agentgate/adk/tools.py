from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.release.audit_session_report import build_audit_session_report
from backend.agentgate.release.dangerous_evidence_classifier import (
    prioritize_trace_ids_for_pull,
)
from backend.agentgate.release.evidence_loader import (
    EvidenceRecord,
    evidence_identity,
    load_evidence_jsonl,
)
from backend.agentgate.release.gemini_diagnoser import (
    DiagnosisMode,
    build_diagnosis_payload,
    create_diagnoser,
)
from backend.agentgate.release.metrics_aggregator import aggregate_metrics
from backend.agentgate.release.phoenix_evidence_source import (
    PhoenixEvidenceQuery,
    PhoenixToolClient,
    pull_phoenix_traces,
    query_phoenix_spans,
    query_phoenix_spans_with_config,
)
from backend.agentgate.release.phoenix_mcp_client import load_phoenix_mcp_config
from backend.agentgate.release.release_check import run_release_check_from_records


def _release_config() -> ReleaseCheckConfig:
    return ReleaseCheckConfig()


def query_phoenix_spans_tool(
    *,
    project_identifier: str | None = None,
    agent_version: str | None = None,
    last_n_minutes: int | None = 24 * 60,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 1000,
    client: PhoenixToolClient | None = None,
) -> dict[str, Any]:
    if client is None:
        config = load_phoenix_mcp_config(project_identifier=project_identifier)
        query = PhoenixEvidenceQuery(
            project_identifier=config.project_identifier,
            agent_version=agent_version,
            last_n_minutes=last_n_minutes,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return query_phoenix_spans_with_config(config, query)

    if project_identifier is None:
        raise ValueError("project_identifier is required when injecting a Phoenix MCP client.")
    query = PhoenixEvidenceQuery(
        project_identifier=project_identifier,
        agent_version=agent_version,
        last_n_minutes=last_n_minutes,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return query_phoenix_spans(query, client)


def pull_dangerous_traces(
    trace_ids: list[str],
    *,
    project_identifier: str | None = None,
    include_annotations: bool = True,
    client: PhoenixToolClient | None = None,
) -> list[dict[str, Any]]:
    if not trace_ids:
        return []
    if client is None:
        config = load_phoenix_mcp_config(project_identifier=project_identifier)
        from backend.agentgate.release.phoenix_mcp_client import PhoenixMCPClient

        with PhoenixMCPClient(config) as managed_client:
            return pull_phoenix_traces(
                managed_client,
                project_identifier=config.project_identifier,
                trace_ids=trace_ids,
                include_annotations=include_annotations,
            )
    if project_identifier is None:
        raise ValueError("project_identifier is required when injecting a Phoenix MCP client.")
    return pull_phoenix_traces(
        client,
        project_identifier=project_identifier,
        trace_ids=trace_ids,
        include_annotations=include_annotations,
    )


def compute_release_metrics(records: list[EvidenceRecord]) -> dict[str, Any]:
    release_config = _release_config()
    pack = release_config.load_pack()
    policy = release_config.load_policy()
    return aggregate_metrics(
        records,
        policy,
        metric_graders=pack.metric_graders(),
        metric_decision_impact=pack.metric_decision_impact(),
        effective_metrics=pack.effective_metrics,
    )


def diagnose_dangerous_sessions(
    *,
    records: list[EvidenceRecord],
    evidence_source: dict[str, Any],
    diagnosis_mode: DiagnosisMode = "deterministic",
) -> dict[str, Any]:
    release_config = _release_config()
    pack = release_config.load_pack()
    identity = evidence_identity(records)
    policy = release_config.load_policy()
    metrics_summary = aggregate_metrics(
        records,
        policy,
        metric_graders=pack.metric_graders(),
        metric_decision_impact=pack.metric_decision_impact(),
        effective_metrics=pack.effective_metrics,
    )
    dangerous_sessions = build_audit_session_report(records, policy)
    diagnosis_payload = build_diagnosis_payload(
        identity=identity,
        policy=policy,
        metrics_summary=metrics_summary,
        dangerous_sessions=dangerous_sessions,
        evidence_source=evidence_source,
        regression_gate_catalog=pack.regression_gate_catalog(),
    )
    diagnoses, diagnosis_metadata = create_diagnoser(diagnosis_mode).diagnose(diagnosis_payload)
    return {
        "dangerous_sessions": dangerous_sessions,
        "diagnoses": diagnoses,
        "diagnosis_metadata": diagnosis_metadata,
    }


def render_release_report(output_dir: Path) -> dict[str, str]:
    artifact_names = (
        "metrics_summary.json",
        "dangerous_sessions.json",
        "regression_gates.json",
        "release_decision.json",
        "release_report.html",
    )
    return {
        artifact_name.rsplit(".", 1)[0]: str(output_dir / artifact_name)
        for artifact_name in artifact_names
        if (output_dir / artifact_name).exists()
    }


def run_release_evidence_workflow(
    *,
    records: list[EvidenceRecord],
    output_dir: Path,
    evidence_source: dict[str, Any],
    diagnosis_mode: DiagnosisMode = "deterministic",
) -> dict[str, Any]:
    return run_release_check_from_records(
        records,
        output_dir,
        evidence_source=evidence_source,
        diagnosis_mode=diagnosis_mode,
    )


def load_local_evidence_records(evidence_path: Path) -> list[EvidenceRecord]:
    return load_evidence_jsonl(evidence_path)


def select_prioritized_dangerous_trace_ids(
    records: list[EvidenceRecord],
    *,
    max_traces: int | None = None,
) -> list[str]:
    release_config = _release_config()
    policy = release_config.load_policy()
    dangerous_sessions = build_audit_session_report(records, policy)
    query = PhoenixEvidenceQuery(project_identifier="unused", max_dangerous_traces=max_traces)
    return prioritize_trace_ids_for_pull(
        dangerous_sessions["critical_findings"],
        reviewed_safe=dangerous_sessions["reviewed_safe"],
        max_traces=query.resolved_max_dangerous_traces,
    )
