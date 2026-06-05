from pathlib import Path
from typing import Any

from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.evals.annotation_loader import load_eval_labels_from_phoenix
from backend.agentgate.evals.coverage_report import build_coverage_report
from backend.agentgate.evals.phoenix_client_config import load_phoenix_client
from backend.agentgate.evals.phoenix_eval_runner import run_phoenix_eval_job
from backend.agentgate.release.artifact_writer import write_release_artifacts
from backend.agentgate.release.audit_session_report import build_audit_session_report
from backend.agentgate.release.dangerous_evidence_classifier import (
    prioritize_trace_ids_for_pull,
)
from backend.agentgate.release.decision_engine import decide_release
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
)
from backend.agentgate.release.phoenix_mcp_client import (
    PhoenixMCPClient,
    load_phoenix_mcp_config,
)
from backend.agentgate.release.phoenix_normalizer import (
    load_phoenix_spans_json,
    normalize_phoenix_spans,
)
from backend.agentgate.release.regression_gate_verifier import (
    build_future_verification_decision_fields,
    run_future_verification,
)
from backend.agentgate.release.report_export import (
    export_release_report_html,
    sync_decision_artifact_paths,
)
from backend.agentgate.release.runtime_metric_catalog import EVAL_DEPENDENT_METRICS
from backend.agentgate.settings import get_pull_reviewed_safe_traces


def run_release_check(
    evidence_path: Path,
    output_dir: Path,
    diagnosis_mode: DiagnosisMode = "deterministic",
    release_config: ReleaseCheckConfig | None = None,
    release_controls_ref: Path | None = None,
    agentic_review_enabled: bool = False,
) -> dict[str, Any]:
    records = load_evidence_jsonl(evidence_path)
    return run_release_check_from_records(
        records,
        output_dir,
        evidence_source={
            "type": "local_jsonl",
            "path": str(evidence_path),
        },
        diagnosis_mode=diagnosis_mode,
        release_config=_with_release_controls_ref(release_config, release_controls_ref),
        agentic_review_enabled=agentic_review_enabled,
    )


def run_release_check_from_phoenix_spans(
    spans_json_path: Path,
    output_dir: Path,
    diagnosis_mode: DiagnosisMode = "deterministic",
    release_config: ReleaseCheckConfig | None = None,
    agentic_review_enabled: bool = False,
) -> dict[str, Any]:
    records = load_phoenix_spans_json(spans_json_path)
    return run_release_check_from_records(
        records,
        output_dir,
        evidence_source={
            "type": "phoenix_mcp_spans_json",
            "path": str(spans_json_path),
        },
        diagnosis_mode=diagnosis_mode,
        release_config=release_config,
        agentic_review_enabled=agentic_review_enabled,
    )


def run_release_check_from_phoenix_mcp(
    output_dir: Path,
    project_identifier: str | None = None,
    agent_version: str | None = None,
    last_n_minutes: int | None = 24 * 60,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 1000,
    client: PhoenixToolClient | None = None,
    diagnosis_mode: DiagnosisMode = "deterministic",
    eval_first: bool = False,
    require_eval_complete: bool = False,
    release_config: ReleaseCheckConfig | None = None,
    agentic_review_enabled: bool = True,
) -> dict[str, Any]:
    if eval_first:
        if agent_version is None:
            raise ValueError("--eval-first requires --agent-version.")
        run_phoenix_eval_job(
            agent_version=agent_version,
            project_identifier=project_identifier,
            last_n_minutes=last_n_minutes,
            output_dir=output_dir / "eval",
        )

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
        with PhoenixMCPClient(config) as managed_client:
            return _run_release_check_from_phoenix_client(
                output_dir=output_dir,
                query=query,
                client=managed_client,
                diagnosis_mode=diagnosis_mode,
                require_eval_complete=require_eval_complete,
                release_config=release_config,
                agentic_review_enabled=agentic_review_enabled,
            )

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
    return _run_release_check_from_phoenix_client(
        output_dir=output_dir,
        query=query,
        client=client,
        diagnosis_mode=diagnosis_mode,
        require_eval_complete=require_eval_complete,
        release_config=release_config,
        agentic_review_enabled=agentic_review_enabled,
    )


def _run_release_check_from_phoenix_client(
    *,
    output_dir: Path,
    query: PhoenixEvidenceQuery,
    client: PhoenixToolClient,
    diagnosis_mode: DiagnosisMode,
    require_eval_complete: bool = False,
    release_config: ReleaseCheckConfig | None = None,
    agentic_review_enabled: bool = True,
) -> dict[str, Any]:
    config = release_config or ReleaseCheckConfig()
    pack = config.load_pack()
    spans_payload = query_phoenix_spans(
        query,
        client,
        supported_span_names=pack.supported_span_names(),
    )
    phoenix_client = load_phoenix_client()
    extra_labels = load_eval_labels_from_phoenix(
        query, spans_payload["spans"], client=phoenix_client
    )
    records = normalize_phoenix_spans(
        {"spans": spans_payload["spans"]},
        extra_labels=extra_labels,
        supported_span_names=pack.supported_span_names(),
        dangerous_intent_ids=pack.dangerous_intent_ids(),
    )
    if not records:
        query_meta = spans_payload.get("query", {})
        fetch_stats = query_meta.get("fetch_stats", {})
        raise ValueError(
            "Phoenix MCP returned no AgentGate evidence records. "
            f"project={query_meta.get('project_identifier')!r} "
            f"agent_version={query_meta.get('agent_version')!r} "
            f"raw_spans={fetch_stats.get('raw_span_count', 0)} "
            f"matched_spans={fetch_stats.get('matched_span_count', 0)}. "
            "Replay seed evidence with `uv run agentgate telemetry replay --evidence ...` "
            "or run the configured demo agent first, then retry. "
            "To debug version filtering, omit --agent-version and inspect Phoenix span attributes."
        )

    policy = config.load_policy()
    dangerous_sessions = build_audit_session_report(records, policy)
    pull_findings = [
        *dangerous_sessions["critical_findings"],
        *dangerous_sessions.get("indeterminate_findings", []),
    ]
    dangerous_trace_ids = prioritize_trace_ids_for_pull(
        pull_findings,
        reviewed_safe=dangerous_sessions["reviewed_safe"],
        max_traces=query.resolved_max_dangerous_traces,
        include_reviewed_safe=get_pull_reviewed_safe_traces(),
    )
    dangerous_traces = pull_phoenix_traces(
        client,
        project_identifier=query.project_identifier,
        trace_ids=dangerous_trace_ids,
        include_annotations=query.include_annotations,
    )

    return run_release_check_from_records(
        records,
        output_dir,
        evidence_source={
            "type": "phoenix_mcp",
            "project_identifier": query.project_identifier,
            "query": spans_payload.get("query", {}),
            "dangerous_trace_ids": dangerous_trace_ids,
            "dangerous_traces": dangerous_traces,
            "trace_selection_strategy": "critical_findings_priority",
            "eval_label_count": len(extra_labels),
        },
        diagnosis_mode=diagnosis_mode,
        require_eval_complete=require_eval_complete,
        release_config=config,
        agentic_review_enabled=agentic_review_enabled,
    )


def run_release_check_from_records(
    records: list[EvidenceRecord],
    output_dir: Path,
    evidence_source: dict[str, Any],
    diagnosis_mode: DiagnosisMode = "deterministic",
    require_eval_complete: bool = False,
    release_config: ReleaseCheckConfig | None = None,
    agentic_review_enabled: bool = False,
) -> dict[str, Any]:
    config = release_config or ReleaseCheckConfig()
    pack = config.load_pack()
    identity = evidence_identity(records)
    policy = config.load_policy()
    evidence_source_type = str(evidence_source.get("type") or "local_jsonl")

    metrics_summary = aggregate_metrics(
        records,
        policy,
        evidence_source_type=evidence_source_type,
        metric_graders=pack.metric_graders(),
        metric_decision_impact=pack.metric_decision_impact(),
        effective_metrics=pack.effective_metrics,
    )
    coverage = build_coverage_report(
        records,
        policy,
        evidence_source_type=evidence_source_type,
        metric_graders=pack.metric_graders(),
        metric_decision_impact=pack.metric_decision_impact(),
        effective_metrics=pack.effective_metrics,
    )
    if require_eval_complete:
        unavailable = [
            metric["name"]
            for metric in metrics_summary["metrics"]
            if metric["name"] in EVAL_DEPENDENT_METRICS and metric["status"] == "not_available"
        ]
        if unavailable:
            raise ValueError(
                "Release check requires completed Phoenix eval automation, but these metrics "
                f"are not available: {', '.join(unavailable)}. Run `uv run agentgate eval run` first."
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
    diagnoser = create_diagnoser(diagnosis_mode)
    diagnoses, diagnosis_metadata = diagnoser.diagnose(diagnosis_payload)

    control_verification = run_future_verification(
        agent_version=identity["agent_version"],
        metrics_summary=metrics_summary,
        dangerous_sessions=dangerous_sessions,
        explicit_ref=config.release_controls_ref,
        resolution_source=config.release_controls_resolution_source
        or _resolution_source_for_controls_ref(config.release_controls_ref),
    )

    gate_binding = config.load_gate_binding(identity["agent_id"])
    decision = decide_release(
        metrics_summary,
        dangerous_sessions,
        diagnoses,
        policy,
        gate_binding=gate_binding,
        control_verification=control_verification,
    )
    decision["future_verification"] = build_future_verification_decision_fields(
        control_verification,
        release_decision=decision["decision"],
    )

    artifact_paths = write_release_artifacts(
        output_dir=output_dir,
        identity=identity,
        evidence_source={**evidence_source, "coverage": coverage},
        metrics_summary=metrics_summary,
        dangerous_sessions=dangerous_sessions,
        diagnoses=diagnoses,
        decision=decision,
        diagnosis_metadata=diagnosis_metadata,
        release_config=config,
        control_verification=control_verification,
        agentic_review_enabled=agentic_review_enabled,
    )
    html_path = export_release_report_html(output_dir)
    artifact_paths["release_report"] = str(html_path)
    sync_decision_artifact_paths(output_dir, artifact_paths)

    return {
        **identity,
        "decision": decision["decision"],
        "artifact_paths": artifact_paths,
        "critical_findings": len(dangerous_sessions["critical_findings"]),
        "indeterminate_findings": len(dangerous_sessions.get("indeterminate_findings", [])),
        "high_risk_activity_count": len(dangerous_sessions.get("high_risk_activity_log", [])),
        "reviewed_safe": len(dangerous_sessions["reviewed_safe"]),
        "diagnosis_metadata": diagnosis_metadata,
        "coverage": coverage,
        "future_verification": decision.get("future_verification"),
        "agentic_review": {
            "enabled": agentic_review_enabled,
            "status": "no_action" if agentic_review_enabled else "disabled",
        },
    }


def _with_release_controls_ref(
    release_config: ReleaseCheckConfig | None,
    release_controls_ref: Path | None,
) -> ReleaseCheckConfig:
    if release_controls_ref is None:
        return release_config or ReleaseCheckConfig()
    base = release_config or ReleaseCheckConfig()
    return ReleaseCheckConfig(
        agent_pack_path=base.agent_pack_path,
        policy_path=base.policy_path,
        suite_path=base.suite_path,
        profile_path=base.profile_path,
        release_controls_ref=release_controls_ref,
        release_controls_resolution_source="cli_argument",
    )


def _resolution_source_for_controls_ref(
    release_controls_ref: Path | None,
) -> str | None:
    if release_controls_ref is None:
        return None
    return "cli_argument"
