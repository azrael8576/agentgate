import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.agentgate.core.agent_pack import (
    LoadedAgentPack,
    RegressionGateCatalog,
    get_default_agent_pack,
    resolve_agent_pack_for_artifacts,
)
from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.release.regression_gate_verifier import (
    future_verification_api_summary,
)

WEB_DIR = Path(__file__).parent
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

CORE_ARTIFACT_FILENAMES = {
    "release_decision.json",
    "metrics_summary.json",
    "dangerous_sessions.json",
    "regression_gates.json",
}
ARTIFACT_FILENAMES = CORE_ARTIFACT_FILENAMES | {
    "agent_profile.json",
    "eval_suite.json",
    "audit_manifest.json",
    "control_verification_results.json",
}
HTML_ARTIFACT_FILENAME = "release_report.html"
REMEDIATION_VISIBLE_LIMIT = 4
SERVABLE_ARTIFACT_FILENAMES = ARTIFACT_FILENAMES | {HTML_ARTIFACT_FILENAME}

CONTROL_DEFINITIONS: dict[str, dict[str, str]] = {}

RELEASE_CONTROL_DISPLAY_TITLES: dict[str, str] = {
    "critical_tools_must_pass_policy_preflight": "Critical tools must pass policy preflight",
    "non_developer_must_not_run_deep_investigation": "Non-developer must not run deep investigation",
    "crash_analysis_must_not_dump_raw_events": "Crash analysis must not dump raw events",
    "ambiguous_incident_question_must_not_escalate_to_deep_investigation": (
        "Ambiguous incident question must not escalate"
    ),
}


def control_definitions(pack: Any | None = None) -> dict[str, dict[str, str]]:
    resolved = pack or get_default_agent_pack()
    return resolved.control_definitions()


ARTIFACT_PURPOSES: dict[str, dict[str, str]] = {
    "release_decision.json": {
        "purpose": "Final decision, policy version, decision reasons, diagnosis metadata.",
        "format": "JSON",
    },
    "metrics_summary.json": {
        "purpose": "Computed control values and supporting counts.",
        "format": "JSON",
    },
    "dangerous_sessions.json": {
        "purpose": "Trace-level dangerous and high-risk activity evidence.",
        "format": "JSON",
    },
    "regression_gates.json": {
        "purpose": "Technical artifact backing generated release controls for the next candidate.",
        "format": "JSON",
    },
    "control_verification_results.json": {
        "purpose": "Per-control PASS/FAIL verification against inherited release controls from a prior blocked run.",
        "format": "JSON",
    },
    HTML_ARTIFACT_FILENAME: {
        "purpose": "Offline audit report export.",
        "format": "HTML",
    },
}

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def read_json_artifact(output_dir: Path, filename: str) -> dict[str, Any]:
    if filename not in ARTIFACT_FILENAMES:
        raise ValueError(f"Unsupported artifact filename: {filename}")
    path = output_dir / filename
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def latest_artifacts_exist(output_dir: Path) -> bool:
    return all((output_dir / filename).exists() for filename in CORE_ARTIFACT_FILENAMES)


def artifact_links() -> list[dict[str, str]]:
    links = [
        {
            "name": "release_decision",
            "filename": "release_decision.json",
            "href": "/artifacts/release_decision.json",
        },
        {
            "name": "metrics_summary",
            "filename": "metrics_summary.json",
            "href": "/artifacts/metrics_summary.json",
        },
        {
            "name": "dangerous_sessions",
            "filename": "dangerous_sessions.json",
            "href": "/artifacts/dangerous_sessions.json",
        },
        {
            "name": "regression_gates",
            "filename": "regression_gates.json",
            "href": "/artifacts/regression_gates.json",
        },
        {
            "name": "control_verification_results",
            "filename": "control_verification_results.json",
            "href": "/artifacts/control_verification_results.json",
        },
        {
            "name": "agent_profile",
            "filename": "agent_profile.json",
            "href": "/artifacts/agent_profile.json",
        },
        {
            "name": "eval_suite",
            "filename": "eval_suite.json",
            "href": "/artifacts/eval_suite.json",
        },
        {
            "name": "audit_manifest",
            "filename": "audit_manifest.json",
            "href": "/artifacts/audit_manifest.json",
        },
        {
            "name": "release_report",
            "filename": HTML_ARTIFACT_FILENAME,
            "href": f"/artifacts/{HTML_ARTIFACT_FILENAME}",
            "label": "Download HTML report",
            "kind": "html",
        },
    ]
    return [{**link, **ARTIFACT_PURPOSES.get(link["filename"], {})} for link in links]


def render_standalone_release_report_html(output_dir: Path) -> Path:
    context = build_report_context(output_dir)
    embedded_css = (STATIC_DIR / "dashboard.css").read_text(encoding="utf-8")
    html = _jinja_env.get_template("release_report_standalone.html").render(**context)
    html = html.replace(
        "<!-- agentgate:embedded-css -->",
        f"<style>\n{embedded_css}\n</style>",
        1,
    )
    html_path = output_dir / HTML_ARTIFACT_FILENAME
    html_path.write_text(html, encoding="utf-8")
    return html_path


def update_release_decision_artifact_paths(
    output_dir: Path, artifact_paths: dict[str, str]
) -> None:
    decision_path = output_dir / "release_decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["artifact_paths"] = artifact_paths
    decision_path.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _update_audit_manifest_artifact_hashes(output_dir, artifact_paths)


def _format_metric_label(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        return "metric"
    return name.replace("_", " ").strip()


def _metric_channel(metric: dict[str, Any]) -> dict[str, str]:
    source = str(metric.get("metric_source") or "unknown")
    grader_ids = metric.get("grader_ids") or []
    if source == "phoenix_eval_automation":
        channel = "Phoenix eval"
        if any("judge" in str(grader_id) for grader_id in grader_ids):
            detail = "Phoenix labels + LLM grader"
        else:
            detail = "Phoenix labels + deterministic grader"
    elif source == "span_aggregate":
        channel = "Policy trace"
        detail = "Aggregated from trace policy attributes"
    else:
        channel = "Metric"
        detail = source.replace("_", " ")
    return {
        "channel": channel,
        "channel_detail": detail,
        "channel_class": {
            "phoenix_eval_automation": "channel-phoenix",
            "span_aggregate": "channel-policy",
        }.get(source, "channel-neutral"),
    }


def _metric_sort_key(metric: dict[str, Any]) -> tuple[int, int, str]:
    failed = 0 if metric.get("passes_threshold") is False else 1
    blocker = 0 if metric.get("decision_impact") == "blocker" else 1
    return (failed, blocker, str(metric.get("control_id") or ""))


def _gate_binding_rows(release_decision: dict[str, Any]) -> list[dict[str, Any]]:
    gate_binding = release_decision.get("gate_binding")
    if not isinstance(gate_binding, dict):
        return []
    rows = gate_binding.get("suite_metrics")
    if isinstance(rows, list) and rows:
        return rows
    required = gate_binding.get("required_suite_metrics") or []
    runtime_blockers = gate_binding.get("runtime_blocker_metrics") or []
    paired = zip(required, runtime_blockers, strict=False)
    return [
        {
            "suite_metric": suite_metric,
            "runtime_metric": runtime_metric,
            "status": "mapped",
        }
        for suite_metric, runtime_metric in paired
    ]


def _artifact_fingerprints(audit_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = audit_manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return []
    fingerprints: list[dict[str, Any]] = []
    for name, payload in sorted(artifacts.items()):
        if not isinstance(payload, dict):
            continue
        sha256 = payload.get("sha256")
        if not sha256:
            continue
        fingerprints.append(
            {
                "name": name,
                "filename": Path(str(payload.get("path", ""))).name or f"{name}.json",
                "sha256_short": f"{sha256[:12]}…{sha256[-8:]}",
                "sha256": sha256,
                "required": payload.get("required_for_offline_audit", False),
            }
        )
    return fingerprints


def _decision_brief(release_decision: dict[str, Any], audit_summary: dict[str, int]) -> str:
    agent_version = release_decision.get("agent_version", "candidate")
    decision = release_decision.get("decision", "UNKNOWN")
    if decision == "APPROVED":
        if audit_summary.get("failed_controls", 0) > 0:
            return f"{agent_version} is APPROVED with warning-only variance still under review."
        return f"{agent_version} is APPROVED for release."
    if decision == "BLOCKED":
        return f"{agent_version} is BLOCKED before production."
    return f"{agent_version} returned {decision}. Review evidence coverage before acting."


def _blocking_metric_names(release_decision: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for reason in release_decision.get("decision_reasons") or []:
        metric = reason.get("metric")
        if isinstance(metric, str) and metric.strip():
            names.add(metric)
    gate_binding = release_decision.get("gate_binding")
    if isinstance(gate_binding, dict):
        for metric in gate_binding.get("runtime_blocker_metrics") or []:
            if isinstance(metric, str) and metric.strip():
                names.add(metric)
    return names


def _blocking_driver_rows(
    release_decision: dict[str, Any],
    failing_metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metric_by_name = {str(metric.get("name") or ""): metric for metric in failing_metrics}
    rows: list[dict[str, Any]] = []
    for reason in release_decision.get("decision_reasons") or []:
        metric_name = str(reason.get("metric") or "")
        metric = metric_by_name.get(metric_name, {})
        evidence_ids = reason.get("evidence_ids") or []
        rows.append(
            {
                "metric": metric_name,
                "display_name": metric.get("display_name") or _format_metric_label(metric_name),
                "control_id": metric.get("control_id") or "AG-RG-000",
                "reason": reason.get("reason") or f"{metric_name} failed release threshold.",
                "display_value": _format_percent(reason.get("value"))
                if reason.get("value") is not None
                else metric.get("display_value", "n/a"),
                "display_threshold": _format_percent(reason.get("threshold"))
                if reason.get("threshold") is not None
                else metric.get("display_threshold", "n/a"),
                "evidence_count": len(evidence_ids),
                "evidence_ids_preview": evidence_ids[:3],
                "evidence_ids_more": max(len(evidence_ids) - 3, 0),
            }
        )
    return rows


def _failure_at_a_glance(
    failing_metrics: list[dict[str, Any]],
    blocking_metric_names: set[str],
) -> list[dict[str, str]]:
    glance: list[dict[str, str]] = []
    for metric in failing_metrics:
        metric_name = str(metric.get("name") or "")
        glance.append(
            {
                "control_id": str(metric.get("control_id") or ""),
                "label": str(metric.get("display_name") or metric_name or "control"),
                "value": str(metric.get("display_value") or "n/a"),
                "threshold": str(metric.get("display_threshold") or "n/a"),
                "drives_release_block": metric_name in blocking_metric_names,
                "anchor_id": f"control-{metric.get('control_id') or metric_name}",
            }
        )
    return glance


def _executive_verdict(
    release_decision: dict[str, Any],
    audit_summary: dict[str, int],
    *,
    regression_gates: list[dict[str, Any]],
    decision_copy: dict[str, str] | None = None,
) -> dict[str, Any]:
    copy = decision_copy or {}
    decision = release_decision.get("decision", "UNKNOWN")
    agent_version = release_decision.get("agent_version", "candidate")
    basis = release_decision.get("decision_basis") or "deterministic_release_gate"
    if decision == "APPROVED":
        if audit_summary.get("failed_controls", 0) > 0:
            return {
                "headline": "Approved, not perfect.",
                "risk": "All inherited blocker controls passed.",
                "actions": [
                    "Non-blocking release variance remains under review.",
                    "Archive this report with the release record.",
                ],
                "footnote": f"Decision basis: {basis}. Gemini text is explanatory only.",
            }
        approved_risk = copy.get("approved_risk_template")
        if approved_risk:
            risk = approved_risk.format(
                high_risk_activity_records=audit_summary["high_risk_activity_records"]
            )
        else:
            risk = (
                f"{audit_summary['high_risk_activity_records']} high-risk sessions were logged for audit; "
                "none triggered a gate-bound block."
            )
        return {
            "headline": f"{agent_version} can ship after this evidence window.",
            "risk": risk,
            "actions": [
                "Archive this report with the release record.",
                "Keep the artifact bundle for offline replay and SHA verification.",
            ],
            "footnote": f"Decision basis: {basis}. Gemini text is explanatory only.",
        }
    if decision == "BLOCKED":
        actions = [
            gate.get(
                "expected_behavior",
                "Promote this trace pattern into a generated release control.",
            )
            for gate in regression_gates[:3]
        ]
        if not actions:
            actions = [
                "Fix gate-bound policy metrics before the next candidate review.",
                "Review blocker findings and promote top traces into generated release controls.",
            ]
        actions.append("Rerun release check on the candidate after fixes land.")
        return {
            "headline": "Do not promote this candidate to production.",
            "risk": copy.get(
                "blocked_risk",
                "Gate-bound policy metrics failed on controlled release evidence.",
            ),
            "actions": actions,
            "footnote": (
                f"{audit_summary['failed_controls']} controls failed in this window; "
                f"only gate-bound metrics block release under {basis}."
            ),
        }
    return {
        "headline": f"{agent_version} needs evidence review before release action.",
        "risk": "Evidence coverage or policy thresholds are incomplete for a production gate.",
        "actions": ["Confirm Phoenix evidence coverage, then rerun the candidate review."],
        "footnote": f"Decision basis: {basis}.",
    }


def _next_action_bullets(
    release_decision: dict[str, Any],
    *,
    regression_gates: list[dict[str, Any]],
) -> list[str]:
    decision = release_decision.get("decision", "UNKNOWN")
    if decision == "APPROVED":
        if regression_gates:
            return [
                "Non-blocking release variance remains under review.",
                "Keep artifact SHA fingerprints with the change ticket.",
            ]
        return [
            "Archive this report with the release record.",
            "Keep artifact SHA fingerprints with the change ticket.",
        ]
    if decision == "BLOCKED":
        bullets = [
            gate.get("expected_behavior", "")
            for gate in regression_gates[:2]
            if gate.get("expected_behavior")
        ]
        if bullets:
            bullets.append("Rerun release check after fixes land.")
            return bullets
        return [
            "Fix gate-bound controls and blocker findings.",
            "Promote top traces into generated release controls, then rerun release check.",
        ]
    return ["Review evidence completeness and policy thresholds before acting."]


def _verdict_panel(
    release_decision: dict[str, Any],
    audit_summary: dict[str, int],
    *,
    blocking_drivers: list[dict[str, Any]],
) -> dict[str, Any]:
    decision = str(release_decision.get("decision") or "UNKNOWN")
    agent_version = release_decision.get("agent_version", "candidate")
    basis = release_decision.get("decision_basis") or "deterministic_release_gate"
    blocker = blocking_drivers[0] if blocking_drivers else None
    if decision == "BLOCKED":
        if blocker:
            reason = (
                f"{blocker['control_id']} is gate-bound and exceeded threshold: "
                f"{blocker['display_value']} > {blocker['display_threshold']}."
            )
        else:
            reason = "At least one gate-bound metric failed the release threshold."
        return {
            "headline": f"{agent_version} is BLOCKED before production.",
            "summary": reason,
            "action": (
                f"{audit_summary.get('regression_gate_count', 0)} generated release control(s) must pass; "
                "rerun release check after fixes land."
            ),
            "basis": basis,
            "class": "blocked",
        }
    if decision == "APPROVED":
        if audit_summary.get("failed_controls", 0) > 0:
            return {
                "headline": "Approved, not perfect.",
                "summary": "All inherited blocker controls passed.",
                "action": "Non-blocking warnings remain visible for review.",
                "basis": basis,
                "class": "approved",
            }
        return {
            "headline": f"{agent_version} is APPROVED for release.",
            "summary": "All gate-bound metrics passed for this evidence window.",
            "action": "Archive this report and keep artifact fingerprints with the release record.",
            "basis": basis,
            "class": "approved",
        }
    return {
        "headline": f"{agent_version} returned {decision}.",
        "summary": "Evidence coverage or policy thresholds need review before production action.",
        "action": "Confirm evidence completeness, then rerun the candidate review.",
        "basis": basis,
        "class": "unknown",
    }


def _why_blocked(
    release_decision: dict[str, Any],
    *,
    blocking_drivers: list[dict[str, Any]],
    failing_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    non_blocking = [
        {
            "control_id": str(metric.get("control_id") or ""),
            "name": str(metric.get("display_name") or _format_metric_label(metric.get("name"))),
            "value": str(metric.get("display_value") or "n/a"),
            "threshold": str(metric.get("display_threshold") or "n/a"),
            "channel": str(metric.get("channel") or "Metric"),
            "channel_class": str(metric.get("channel_class") or "channel-neutral"),
        }
        for metric in failing_metrics
        if not metric.get("drives_release_block")
    ]
    decision = release_decision.get("decision")
    if decision == "BLOCKED" and blocking_drivers:
        summary = "One gate-bound control blocked release. Other failed controls are warnings for this decision."
        section_title = "Why blocked"
        section_subcopy = summary
    elif decision == "APPROVED":
        if non_blocking:
            summary = "Non-blocking warning controls remain visible for review."
            section_title = "Approved, not perfect"
            section_subcopy = (
                "All inherited blocker controls passed. "
                "Non-blocking warnings remain visible for review."
            )
        else:
            summary = "No gate-bound controls blocked this candidate."
            section_title = "Release gate"
            section_subcopy = "All gate-bound metrics passed for this evidence window."
    else:
        summary = "Review failed controls and evidence completeness before acting."
        section_title = "Release gate"
        section_subcopy = summary
    return {
        "summary": summary,
        "section_title": section_title,
        "section_subcopy": section_subcopy,
        "blocking_drivers": blocking_drivers,
        "non_blocking_failures": non_blocking,
        "non_blocking_count": len(non_blocking),
        "pass_attestation": (
            "All inherited blocker controls passed."
            if decision == "APPROVED" and non_blocking
            else "No gate-bound decision reasons. All release blockers passed for this evidence window."
        ),
    }


def _future_verification_summary_counts(
    future: dict[str, Any],
    control_verification: dict[str, Any],
) -> dict[str, int]:
    summary = control_verification.get("summary") or {}
    return {
        "blocking_failed": int(
            future.get("blocking_failed")
            if future.get("blocking_failed") is not None
            else summary.get("blocking_failed", 0)
        ),
        "failed": int(
            future.get("failed") if future.get("failed") is not None else summary.get("failed", 0)
        ),
    }


_WARNING_ONLY_GATE_IDS = frozenset(
    {
        "intent_routing_accuracy_within_threshold",
        "crash_analysis_format_compliance_within_threshold",
        "technical_tool_success_rate_within_threshold",
        "hallucination_rate_within_threshold",
    }
)


def _future_verification_row_decision_impact(row: dict[str, Any]) -> dict[str, str]:
    gate_id = str(row.get("gate_id") or "")
    if row.get("blocking"):
        return {
            "decision_impact_label": "Blocking requirement",
            "decision_impact_class": "inherited-blocking",
        }
    if gate_id in _WARNING_ONLY_GATE_IDS:
        return {
            "decision_impact_label": "Warning only",
            "decision_impact_class": "inherited-warning",
        }
    return {
        "decision_impact_label": "Non-blocking",
        "decision_impact_class": "inherited-neutral",
    }


def _sort_future_verification_rows(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
        status = row.get("verification_status", "")
        is_fail = 0 if status == "FAIL" else 1
        is_blocking_fail = 0 if status == "FAIL" and row.get("blocking") else 1
        return (is_fail, is_blocking_fail, str(row.get("gate_id") or ""))

    return sorted(results, key=sort_key)


def _future_verification_table_rows(
    control_verification: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _sort_future_verification_rows(control_verification.get("results", [])):
        matched = row.get("matched_metric_ids") or []
        candidate_evidence = (
            ", ".join(matched)
            if matched
            else _format_candidate_evidence(row.get("candidate_values", {}))
        )
        verification_status = row.get("verification_status", "NOT_AVAILABLE")
        impact = _future_verification_row_decision_impact(row)
        gate_id = str(row.get("gate_id") or "")
        release_control = (
            RELEASE_CONTROL_DISPLAY_TITLES.get(gate_id) or row.get("control_title") or gate_id
        )
        rows.append(
            {
                "release_control": release_control,
                "candidate_evidence": candidate_evidence,
                "status": verification_status,
                "status_class": str(verification_status).lower(),
                "gate_id": row.get("gate_id"),
                **impact,
            }
        )
    return rows


def _future_verification_section(
    release_decision: dict[str, Any],
    control_verification: dict[str, Any],
) -> dict[str, Any]:
    future = release_decision.get("future_verification") or {}
    status = future.get("status") or control_verification.get("status") or "not_available"
    counts = _future_verification_summary_counts(future, control_verification)
    failed = counts["failed"]
    resolution = future.get("resolution_source") or ""

    if status == "not_applicable":
        return {
            "title": "Future Verification",
            "status_label": "Not applicable",
            "status_class": "not-applicable",
            "copy": (
                "Future Verification is not applicable for this source failure. "
                "This blocked candidate generated release controls that the follow-up candidate must verify."
            ),
            "secondary_copy": "",
            "resolution_note": "",
            "rows": [],
            "show_table": False,
        }

    if status == "not_available":
        return {
            "title": "Future Verification",
            "status_label": "Not available",
            "status_class": "not-available",
            "copy": (
                "No previous regression_gates.json was found. "
                "This decision is based on current gate-bound blocker metrics only."
            ),
            "secondary_copy": "",
            "resolution_note": "",
            "rows": [],
            "show_table": False,
        }

    rows = _future_verification_table_rows(control_verification)

    if status == "failed":
        return {
            "title": "Future Verification",
            "status_label": "Failed",
            "status_class": "failed",
            "copy": (
                "At least one inherited blocker release control failed. "
                "This candidate is blocked because a previously generated release requirement reproduced."
            ),
            "secondary_copy": "",
            "resolution_note": "",
            "rows": rows,
            "show_table": bool(rows),
        }

    source_version = control_verification.get("source_release", {}).get("agent_version") or "v2"
    agent_version = release_decision.get("agent_version", "candidate")
    copy = (
        f"{agent_version} verified the release controls generated by the blocked {source_version} run. "
        "All inherited blocker controls passed."
    )
    secondary_copy = "Non-blocking warnings remain visible for review." if failed > 0 else ""
    resolution_note = ""
    if resolution == "bundled_reference_fallback":
        resolution_note = "Verified from bundled reference controls."

    return {
        "title": "Future Verification",
        "status_label": "Verified",
        "status_class": "verified",
        "copy": copy,
        "secondary_copy": secondary_copy,
        "resolution_note": resolution_note,
        "rows": rows,
        "show_table": bool(rows),
    }


def future_verification_run_card_copy(
    future_verification: dict[str, Any] | None,
) -> dict[str, str]:
    """Human-readable copy for the run page future-verification result card."""
    future = future_verification or {}
    status = future.get("status") or "not_available"
    blocking_failed = int(future.get("blocking_failed") or 0)
    failed = int(future.get("failed") or 0)

    if status == "not_applicable":
        return {
            "summary": "No previous release controls were expected for this candidate.",
        }
    if status == "not_available":
        return {
            "summary": (
                "Future verification not available. "
                "Decision is based on current blocker metrics only."
            ),
        }
    if status == "verified" and blocking_failed == 0 and failed > 0:
        return {
            "summary": ("Inherited blocker controls passed. Non-blocking controls remain visible."),
        }
    if status == "verified" and blocking_failed == 0:
        return {"summary": "Inherited blocker controls passed."}
    if status == "failed":
        return {
            "summary": "At least one inherited blocker release control failed.",
        }
    return {
        "summary": "Future verification status is unavailable for this run.",
    }


def _format_candidate_evidence(candidate_values: dict[str, Any]) -> str:
    if not candidate_values:
        return "n/a"
    parts = [f"{metric_id}={value}" for metric_id, value in candidate_values.items()]
    return ", ".join(parts)


def _fix_now(
    release_decision: dict[str, Any],
    *,
    regression_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    decision = release_decision.get("decision", "UNKNOWN")
    bridge_note = (
        "regression_gates.json is the technical artifact backing generated release controls."
    )
    if decision == "APPROVED":
        return {
            "eyebrow": "Release controls status",
            "headline": "Release controls status",
            "summary": "No new release controls were generated for this evidence window.",
            "bridge_note": bridge_note,
            "tasks": [],
            "rerun_label": "Keep artifact SHA fingerprints with the release record.",
        }
    if regression_gates:
        return {
            "eyebrow": "Future release controls",
            "headline": "Release controls generated from this blocked failure",
            "summary": (
                "These are not debug notes. They are future release requirements for the next candidate."
            ),
            "bridge_note": bridge_note,
            "tasks": regression_gates,
            "rerun_label": "Rerun release check after fixes land.",
        }
    return {
        "eyebrow": "Future release controls",
        "headline": "Release controls generated from this blocked failure",
        "summary": "No generated release controls were captured; promote blocker findings into controlled tests before rerunning.",
        "bridge_note": bridge_note,
        "tasks": [],
        "rerun_label": "Rerun release check after fixes land.",
    }


def _audit_archive_summary(
    *,
    release_decision: dict[str, Any],
    evidence_source: dict[str, Any],
    audit_scope: dict[str, Any],
    gate_binding_rows: list[dict[str, Any]],
    artifact_fingerprints: list[dict[str, Any]],
    evaluation_mode: Any,
    sample_tier: Any,
    generated_at_display: str,
    suite_id: str,
) -> dict[str, Any]:
    coverage = (
        evidence_source.get("coverage") if isinstance(evidence_source.get("coverage"), dict) else {}
    )
    ready = coverage.get("ready_for_release_gate")
    missing = coverage.get("missing_count")
    present = coverage.get("present_count")
    if ready is True:
        coverage_label = "ready"
    elif ready is False:
        coverage_label = "incomplete"
    else:
        coverage_label = "not recorded"
    if present is not None and missing is not None:
        coverage_detail = f"{present}/{present + missing} required fields present"
    else:
        coverage_detail = "coverage field counts not recorded"
    return {
        "headline": "Audit archive summary",
        "fields": [
            {
                "label": "Evidence source",
                "value": evidence_source.get("type") or "unknown",
            },
            {
                "label": "Eval mode",
                "value": f"{evaluation_mode or 'unknown'} / {sample_tier or 'unknown'}",
            },
            {"label": "Coverage", "value": coverage_label, "detail": coverage_detail},
            {
                "label": "Gate binding",
                "value": f"{len(gate_binding_rows)} mapped metric(s)",
            },
            {
                "label": "Fingerprints",
                "value": f"{len(artifact_fingerprints)} artifact hash(es)",
            },
            {"label": "Generated", "value": generated_at_display},
            {
                "label": "Policy",
                "value": f"{release_decision.get('policy_id', 'unknown')} / {release_decision.get('policy_version', 'unknown')}",
            },
            {"label": "Suite", "value": suite_id},
            {
                "label": "Phoenix project",
                "value": audit_scope.get("project_identifier") or "unknown",
            },
        ],
    }


def _appendix_sections(
    *,
    release_decision: dict[str, Any],
    failing_metrics: list[dict[str, Any]],
    passing_metrics: list[dict[str, Any]],
    high_risk_supplemental: list[dict[str, Any]],
    indeterminate_findings: list[dict[str, Any]],
    dangerous_session_diagnoses: list[dict[str, Any]],
) -> dict[str, str]:
    return {
        "decision_evidence": str(len(release_decision.get("decision_reasons") or [])),
        "controls": f"{len(failing_metrics)} failed, {len(passing_metrics)} passed",
        "high_risk": str(len(high_risk_supplemental)),
        "indeterminate": str(len(indeterminate_findings)),
        "gemini": str(len(dangerous_session_diagnoses)),
    }


def _gemini_diagnosis_themes(
    diagnoses: list[dict[str, Any]], *, samples_per_theme: int = 2
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for diagnosis in diagnoses:
        finding_type = str(diagnosis.get("finding_type") or "session_diagnosis")
        buckets.setdefault(finding_type, []).append(diagnosis)
    themes: list[dict[str, Any]] = []
    for finding_type, items in sorted(buckets.items(), key=lambda item: -len(item[1])):
        sample = items[0]
        themes.append(
            {
                "finding_type": finding_type.replace("_", " "),
                "count": len(items),
                "sample_case_id": sample.get("case_id", "n/a"),
                "sample_diagnosis": str(sample.get("diagnosis") or "")[:280],
                "samples": items[:samples_per_theme],
            }
        )
    return themes


def _high_risk_supplemental(
    high_risk_non_authorized: list[dict[str, Any]],
    critical_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocker_traces = {
        finding.get("trace_id") for finding in critical_findings if finding.get("trace_id")
    }
    return [
        entry for entry in high_risk_non_authorized if entry.get("trace_id") not in blocker_traces
    ]


def _eval_representation_warning(evaluation_mode: str, sample_tier: str) -> str | None:
    if evaluation_mode == "controlled" and sample_tier == "demo":
        return (
            "This review used controlled demo sampling. Treat metrics as a release gate rehearsal, "
            "not full production traffic coverage."
        )
    return None


def _bundle_agent_profile(output_dir: Path, fallback: Any) -> dict[str, Any]:
    artifact = _read_optional_json_artifact(output_dir, "agent_profile.json")
    profile = artifact.get("profile")
    if isinstance(profile, dict):
        return profile
    return fallback.model_dump() if hasattr(fallback, "model_dump") else dict(fallback)


def _percent_metric(metric: dict[str, Any], *, pack: Any | None = None) -> dict[str, Any]:
    value = metric.get("value")
    threshold = metric.get("threshold")
    threshold_key = metric.get("threshold_key")
    metric_source = metric.get("metric_source") or "unknown"
    name = str(metric.get("name") or "")
    control = control_definitions(pack).get(
        name,
        {
            "control_id": "AG-RG-000",
            "name": _format_metric_label(name),
            "definition": "Control definition is unavailable for this metric.",
            "formula": "Calculation basis is unavailable.",
        },
    )
    result = "insufficient_data"
    if metric.get("passes_threshold") is True:
        result = "pass"
    elif metric.get("passes_threshold") is False:
        result = "fail"
    return {
        **metric,
        "control_id": control["control_id"],
        "display_name": control["name"],
        "definition": control["definition"],
        "formula": control["formula"],
        "result": result,
        "display_value": _format_percent(value),
        "display_threshold": _format_percent(threshold),
        "display_ratio": _format_ratio(metric.get("numerator"), metric.get("denominator")),
        "display_threshold_label": _format_threshold_label(threshold_key),
        "display_metric_source": metric_source.replace("_", " "),
        "display_decision_impact": str(metric.get("decision_impact") or "informational").replace(
            "_", " "
        ),
        "display_evaluation_mode": str(metric.get("evaluation_mode") or "unknown").replace(
            "_", " "
        ),
        "display_sample_tier": str(metric.get("sample_tier") or "unknown").replace("_", " "),
        "display_grader_ids": ", ".join(metric.get("grader_ids") or []) or "not recorded",
        "display_grader_source": metric.get("grader_source") or "not recorded",
        "display_evidence_ids": ", ".join(metric.get("evidence_ids") or []) or "not recorded",
        "display_unavailable_reason": metric.get("unavailable_reason") or "",
        "metric_source_badge_class": _metric_source_badge_class(metric),
        **_metric_channel(metric),
        "is_blocker_impact": str(metric.get("decision_impact") or "") == "blocker",
    }


def _metric_source_badge_class(metric: dict[str, Any]) -> str:
    source = str(metric.get("metric_source") or "unknown")
    if source in {"not_available", "seed_fallback"}:
        return "warning"
    if metric.get("status") == "not_available":
        return "warning"
    return "neutral"


def _format_threshold_label(threshold_key: Any) -> str:
    if not isinstance(threshold_key, str) or not threshold_key.strip():
        return "threshold"
    normalized = threshold_key.replace("_", " ").strip()
    if normalized.endswith(" min"):
        return "minimum"
    if normalized.endswith(" max"):
        return "maximum"
    return normalized


def _format_percent(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{value * 100:.1f}%"
    return "n/a"


def _format_ratio(numerator: Any, denominator: Any) -> str:
    if numerator is None or denominator is None:
        return "not available"
    return f"{numerator}/{denominator}"


def format_display_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "unknown"
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _resolve_report_pack(output_dir: Path) -> Any:
    config = ReleaseCheckConfig()
    return resolve_agent_pack_for_artifacts(output_dir, fallback=config.agent_pack_path)


def build_report_context(output_dir: Path) -> dict[str, Any]:
    pack = _resolve_report_pack(output_dir)
    release_decision = read_json_artifact(output_dir, "release_decision.json")
    metrics_summary = read_json_artifact(output_dir, "metrics_summary.json")
    dangerous_sessions = _normalize_audit_sessions(
        read_json_artifact(output_dir, "dangerous_sessions.json")
    )
    regression_gates = read_json_artifact(output_dir, "regression_gates.json")
    control_verification = _read_optional_json_artifact(
        output_dir, "control_verification_results.json"
    )
    audit_manifest = _read_optional_json_artifact(output_dir, "audit_manifest.json")
    eval_suite_artifact = _read_optional_json_artifact(output_dir, "eval_suite.json")
    fallback_profile = pack.profile
    agent_profile = _bundle_agent_profile(output_dir, fallback_profile)
    intent_manifest = pack.intents.model_dump() if pack.intents else {}
    release_policy = pack.release_policy.model_dump()

    metrics = sorted(
        [_percent_metric(metric, pack=pack) for metric in metrics_summary.get("metrics", [])],
        key=_metric_sort_key,
    )
    failing_metrics = [metric for metric in metrics if metric.get("passes_threshold") is False]
    passing_metrics = [metric for metric in metrics if metric.get("passes_threshold") is True]
    high_risk_activity_log = [
        _normalize_activity_entry(entry)
        for entry in dangerous_sessions.get("high_risk_activity_log", [])
    ]
    activity_by_trace = {
        entry.get("trace_id"): entry for entry in high_risk_activity_log if entry.get("trace_id")
    }
    critical_findings = [
        _normalize_finding(
            finding,
            release_decision=release_decision,
            activity_entry=activity_by_trace.get(finding.get("trace_id")),
        )
        for finding in dangerous_sessions.get("critical_findings", [])
    ]
    indeterminate_findings = [
        _normalize_finding(
            finding,
            release_decision=release_decision,
            activity_entry=activity_by_trace.get(finding.get("trace_id")),
        )
        for finding in dangerous_sessions.get("indeterminate_findings", [])
    ]
    dangerous_diagnoses = [
        _normalize_diagnosis(
            diagnosis, release_decision=release_decision, findings=critical_findings
        )
        for diagnosis in release_decision.get("dangerous_session_diagnoses", [])
    ]
    diagnosis_metadata = release_decision.get("diagnosis_metadata", {})
    evidence_source = release_decision.get("evidence_source", {})
    eval_suite = eval_suite_artifact.get("suite", {}) if eval_suite_artifact else {}
    suite_id = eval_suite.get("suite_id") or pack.suite.suite_id
    evaluation_mode = audit_manifest.get("evaluation_mode") or _first_metric_value(
        metrics_summary, "evaluation_mode"
    )
    sample_tier = audit_manifest.get("sample_tier") or _first_metric_value(
        metrics_summary, "sample_tier"
    )
    audit_summary = _audit_summary(
        release_decision=release_decision,
        failing_metrics=failing_metrics,
        critical_findings=critical_findings,
        indeterminate_findings=indeterminate_findings,
        high_risk_activity_log=high_risk_activity_log,
    )
    regression_gate_list = _apply_regression_gate_catalog(
        regression_gates.get("regression_gates", []),
        pack.regression_gate_catalog(),
    )
    audit_summary["regression_gate_count"] = len(regression_gate_list)

    high_risk_non_authorized = [
        entry for entry in high_risk_activity_log if str(entry.get("verdict")) != "authorized"
    ]
    gate_binding = (
        release_decision.get("gate_binding")
        if isinstance(release_decision.get("gate_binding"), dict)
        else {}
    )
    blocking_metric_names = _blocking_metric_names(release_decision)
    for metric in failing_metrics:
        metric["drives_release_block"] = str(metric.get("name") or "") in blocking_metric_names
    normalized_regression_gates = [
        _normalize_regression_gate(
            gate, release_decision=release_decision, findings=critical_findings
        )
        for gate in regression_gate_list
    ]
    blocking_drivers = _blocking_driver_rows(release_decision, failing_metrics)
    reproducibility_recipe = audit_manifest.get("reproducibility_recipe") or []
    generated_at_display = format_display_timestamp(release_decision.get("generated_at"))
    gate_binding_rows = _gate_binding_rows(release_decision)
    artifact_fingerprints = _artifact_fingerprints(audit_manifest)
    audit_scope = _audit_scope(release_decision, evidence_source, output_dir)
    gemini_diagnosis_themes = _gemini_diagnosis_themes(dangerous_diagnoses)
    high_risk_supplemental = _high_risk_supplemental(high_risk_non_authorized, critical_findings)
    appendix_sections = _appendix_sections(
        release_decision=release_decision,
        failing_metrics=failing_metrics,
        passing_metrics=passing_metrics,
        high_risk_supplemental=high_risk_supplemental,
        indeterminate_findings=indeterminate_findings,
        dangerous_session_diagnoses=dangerous_diagnoses,
    )

    return {
        "agent_profile": agent_profile,
        "intent_manifest": intent_manifest,
        "release_policy": release_policy,
        "release_decision": release_decision,
        "audit_manifest": audit_manifest,
        "eval_suite": eval_suite,
        "suite_id": suite_id,
        "evaluation_mode": evaluation_mode or "unknown",
        "sample_tier": sample_tier or "unknown",
        "generated_at_display": generated_at_display,
        "metrics_summary": metrics_summary,
        "metrics": metrics,
        "failing_metrics": failing_metrics,
        "passing_metrics": passing_metrics,
        "failure_at_a_glance": _failure_at_a_glance(failing_metrics, blocking_metric_names),
        "blocking_drivers": blocking_drivers,
        "blocking_metric_names": sorted(blocking_metric_names),
        "gate_binding_rows": gate_binding_rows,
        "gate_binding": gate_binding,
        "artifact_fingerprints": artifact_fingerprints,
        "high_risk_non_authorized": high_risk_non_authorized,
        "high_risk_supplemental": high_risk_supplemental,
        "decision_brief": _decision_brief(release_decision, audit_summary),
        "executive_verdict": _executive_verdict(
            release_decision,
            audit_summary,
            regression_gates=regression_gate_list,
            decision_copy=pack.decision_copy(),
        ),
        "next_action_bullets": _next_action_bullets(
            release_decision,
            regression_gates=regression_gate_list,
        ),
        "eval_representation_warning": _eval_representation_warning(
            evaluation_mode or "unknown", sample_tier or "unknown"
        ),
        "reproducibility_recipe": reproducibility_recipe,
        "confidence_label": release_decision.get("confidence_label") or "unknown",
        "gemini_diagnosis_themes": gemini_diagnosis_themes,
        "authority_note": _authority_note(pack),
        "policy_snapshot_note": _policy_snapshot_note(pack, release_decision),
        "dangerous_sessions": dangerous_sessions,
        "critical_findings": critical_findings,
        "indeterminate_findings": indeterminate_findings,
        "high_risk_activity_log": high_risk_activity_log,
        "audit_summary": audit_summary,
        "regression_gates": regression_gate_list,
        "normalized_regression_gates": normalized_regression_gates,
        "diagnosis_metadata": diagnosis_metadata,
        "dangerous_session_diagnoses": dangerous_diagnoses,
        "evidence_source": evidence_source,
        "audit_scope": audit_scope,
        "verdict_panel": _verdict_panel(
            release_decision,
            audit_summary,
            blocking_drivers=blocking_drivers,
        ),
        "why_blocked": _why_blocked(
            release_decision,
            blocking_drivers=blocking_drivers,
            failing_metrics=failing_metrics,
        ),
        "fix_now": _fix_now(
            release_decision,
            regression_gates=normalized_regression_gates,
        ),
        "future_verification": _future_verification_section(
            release_decision,
            control_verification,
        ),
        "control_verification": control_verification,
        "audit_archive_summary": _audit_archive_summary(
            release_decision=release_decision,
            evidence_source=evidence_source,
            audit_scope=audit_scope,
            gate_binding_rows=gate_binding_rows,
            artifact_fingerprints=artifact_fingerprints,
            evaluation_mode=evaluation_mode,
            sample_tier=sample_tier,
            generated_at_display=generated_at_display,
            suite_id=suite_id,
        ),
        "appendix_sections": appendix_sections,
        "developer_remediation": _developer_remediation_context(
            release_decision=release_decision,
            critical_findings=critical_findings,
            failing_metrics=failing_metrics,
            normalized_regression_gates=normalized_regression_gates,
        ),
        "artifact_cards": artifact_links(),
        "artifact_links": artifact_links(),
        "recommended_next_tasks": _recommended_next_tasks(regression_gate_list, critical_findings),
        "source_is_local": evidence_source.get("type") == "local_jsonl",
        "summary": _executive_summary(release_decision, audit_summary),
    }


def build_latest_run_payload(output_dir: Path) -> dict[str, Any]:
    context = build_report_context(output_dir)
    decision = context["release_decision"]
    metrics_summary = context["metrics_summary"]
    dangerous_sessions = context["dangerous_sessions"]
    dangerous_trace_count = len(
        {
            finding.get("trace_id")
            for finding in context["critical_findings"]
            if finding.get("trace_id")
        }
    )
    agent_profile = context.get("agent_profile", {})
    agent_display_name = (
        agent_profile.get("display_name")
        or agent_profile.get("agent_name")
        or decision.get("agent_id")
    )
    return {
        "status": "ready",
        "agent_id": decision.get("agent_id"),
        "agent_display_name": agent_display_name,
        "agent_version": decision.get("agent_version"),
        "generated_at": decision.get("generated_at"),
        "generated_at_display": format_display_timestamp(decision.get("generated_at")),
        "decision": decision.get("decision"),
        "confidence": decision.get("confidence"),
        "confidence_label": decision.get("confidence_label"),
        "decision_basis": decision.get("decision_basis"),
        "policy_id": decision.get("policy_id"),
        "policy_version": decision.get("policy_version"),
        "decision_reasons": decision.get("decision_reasons", []),
        "metrics": metrics_summary.get("metrics", []),
        "supporting_counts": metrics_summary.get("supporting_counts", {}),
        "critical_findings": len(dangerous_sessions.get("critical_findings", [])),
        "dangerous_trace_count": dangerous_trace_count,
        "indeterminate_findings": len(dangerous_sessions.get("indeterminate_findings", [])),
        "high_risk_activity_count": len(dangerous_sessions.get("high_risk_activity_log", [])),
        "reviewed_safe": len(dangerous_sessions.get("reviewed_safe", [])),
        "diagnosis_metadata": decision.get("diagnosis_metadata", {}),
        "evidence_source": decision.get("evidence_source", {}),
        "artifact_links": artifact_links(),
        "report_url": "/reports/latest",
        "future_verification": future_verification_api_summary(decision.get("future_verification")),
    }


def _normalize_audit_sessions(dangerous_sessions: dict[str, Any]) -> dict[str, Any]:
    activity_log = dangerous_sessions.get("high_risk_activity_log")
    if activity_log is None:
        activity_log = _legacy_activity_log(
            dangerous_sessions.get("critical_findings", []),
            dangerous_sessions.get("reviewed_safe", []),
        )
    return {
        **dangerous_sessions,
        "indeterminate_findings": dangerous_sessions.get("indeterminate_findings", []),
        "high_risk_activity_log": activity_log,
    }


def _read_optional_json_artifact(output_dir: Path, filename: str) -> dict[str, Any]:
    path = output_dir / filename
    if not path.exists():
        return {}
    return read_json_artifact(output_dir, filename)


def _first_metric_value(metrics_summary: dict[str, Any], key: str) -> Any:
    for metric in metrics_summary.get("metrics", []):
        value = metric.get(key)
        if value:
            return value
    return None


def _recommended_next_tasks(
    regression_gates: list[dict[str, Any]],
    critical_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tasks = [
        {
            "task_id": gate.get("gate_id", "release_control"),
            "recommendation": gate.get(
                "expected_behavior",
                "Promote the failed finding into a generated release control.",
            ),
            "source_evidence_ids": gate.get("source_evidence_ids", []),
        }
        for gate in regression_gates[:5]
    ]
    if not tasks and critical_findings:
        tasks.extend(
            {
                "task_id": f"task_from_{finding.get('finding_type', 'finding')}",
                "recommendation": "Create a generated release control for this blocker finding before the next release check.",
                "source_evidence_ids": finding.get("evidence_ids", []),
            }
            for finding in critical_findings[:5]
        )
    return tasks


def _apply_regression_gate_catalog(
    regression_gates: list[dict[str, Any]],
    catalog: RegressionGateCatalog,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for gate in regression_gates:
        template = _regression_gate_template(gate, catalog)
        if template is None:
            enriched.append(gate)
            continue
        enriched.append(
            {
                **gate,
                "expected_behavior": template.get("expected_behavior")
                or gate.get("expected_behavior"),
                "required_fix": template.get("required_fix") or gate.get("required_fix"),
            }
        )
    return enriched


def _regression_gate_template(
    gate: dict[str, Any],
    catalog: RegressionGateCatalog,
) -> dict[str, str] | None:
    trigger = str(gate.get("trigger") or "")
    trigger_kind, _, trigger_name = trigger.partition(":")
    if trigger_kind in {"material_violation", "indeterminate_session"}:
        return catalog.findings.get(trigger_name)
    if trigger_kind == "control_failed":
        return catalog.metrics.get(trigger_name)
    return None


def _update_audit_manifest_artifact_hashes(
    output_dir: Path, artifact_paths: dict[str, str]
) -> None:
    manifest_path = output_dir / "audit_manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.setdefault("artifacts", {})
    for artifact_name, artifact_path in artifact_paths.items():
        if artifact_name == "audit_manifest":
            continue
        path = Path(artifact_path)
        if not path.exists():
            continue
        artifacts.setdefault(
            artifact_name,
            {
                "path": str(path),
                "required_for_offline_audit": artifact_name != "release_report",
            },
        )
        artifacts[artifact_name]["path"] = str(path)
        artifacts[artifact_name]["sha256"] = _sha256_file(path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _short(value: Any, prefix: int = 8, suffix: int = 4) -> str:
    text = str(value or "")
    if len(text) <= prefix + suffix + 1:
        return text or "n/a"
    return f"{text[:prefix]}...{text[-suffix:]}"


def _attr(source: dict[str, Any], key: str, default: Any = None) -> Any:
    attributes = source.get("attributes")
    if isinstance(attributes, dict) and key in attributes:
        return attributes[key]
    return source.get(key, default)


def _first_tool_name(entry: dict[str, Any] | None) -> Any:
    if not entry:
        return None
    tool_names = entry.get("tool_names")
    if isinstance(tool_names, list) and tool_names:
        return tool_names[0]
    return entry.get("tool_name")


def _normalize_activity_entry(entry: dict[str, Any]) -> dict[str, Any]:
    trace_id = entry.get("trace_id")
    return {
        **entry,
        "trace_short": _short(trace_id),
        "tool_name": _first_tool_name(entry),
    }


def _normalize_finding(
    finding: dict[str, Any],
    *,
    release_decision: dict[str, Any],
    activity_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected_intent_id = _attr(
        finding,
        "expected_intent_id",
        _attr(finding, "expected.intent_id", "n/a"),
    )
    selected_intent_id = _attr(
        finding,
        "selected_intent_id",
        _attr(finding, "router.selected_intent_id", _attr(finding, "intent.id", "n/a")),
    )
    router_confidence = _attr(finding, "confidence", _attr(finding, "router.confidence", "n/a"))
    merged = {
        **finding,
        "trace_short": _short(finding.get("trace_id")),
        "tool_name": _attr(
            finding,
            "tool.name",
            _first_tool_name(activity_entry) or _attr(finding, "tool_name", "unknown"),
        ),
        "intent_id": _attr(finding, "intent.id", selected_intent_id),
        "expected_intent_id": expected_intent_id,
        "selected_intent_id": selected_intent_id,
        "router_confidence": router_confidence,
        "routing_summary": (
            f"{expected_intent_id} → {selected_intent_id}"
            if expected_intent_id not in {None, "n/a", "unknown"}
            and selected_intent_id not in {None, "n/a", "unknown"}
            and expected_intent_id != selected_intent_id
            else str(selected_intent_id)
        ),
        "summary_line": (
            f"{finding.get('case_id', 'case')} · {finding.get('user_role', 'role')} · "
            f"{_attr(finding, 'tool.name', _first_tool_name(activity_entry) or _attr(finding, 'tool_name', 'tool'))}"
        ),
        "allowed_roles": _attr(finding, "intent.allowed_roles", "unknown"),
        "risk_level": _attr(finding, "tool.risk_level", "unknown"),
        "query_backend": _attr(finding, "tool.query_backend", "unknown"),
        "expected_allowed": _attr(
            finding,
            "expected.allowed",
            activity_entry.get("expected_allowed")
            if activity_entry
            else _attr(finding, "expected_allowed", "unknown"),
        ),
        "actual_allowed": _attr(
            finding,
            "actual.allowed",
            activity_entry.get("actual_allowed")
            if activity_entry
            else _attr(finding, "actual_allowed", "unknown"),
        ),
        "policy_preflight_decision": _attr(
            finding,
            "policy.preflight.decision",
            activity_entry.get("preflight_decision") if activity_entry else "unknown",
        ),
        "policy_violation_reason": _attr(finding, "policy.violation.reason", "unknown"),
    }
    merged["debug_prompt"] = build_ide_debug_prompt(merged, release_decision=release_decision)
    return merged


def _normalize_diagnosis(
    diagnosis: dict[str, Any],
    *,
    release_decision: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    matching_finding = next(
        (finding for finding in findings if finding.get("trace_id") == diagnosis.get("trace_id")),
        None,
    )
    base = {**(matching_finding or {}), **diagnosis}
    base["trace_short"] = _short(base.get("trace_id"))
    base["debug_prompt"] = build_ide_debug_prompt(base, release_decision=release_decision)
    return base


def _normalize_regression_gate(
    gate: dict[str, Any],
    *,
    release_decision: dict[str, Any],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_ids = set(gate.get("source_evidence_ids") or [])
    matching_finding = next(
        (
            finding
            for finding in findings
            if evidence_ids.intersection(set(finding.get("evidence_ids") or []))
            or finding.get("trace_id") in evidence_ids
        ),
        None,
    )
    gate_id = str(gate.get("gate_id") or "")
    display_title = RELEASE_CONTROL_DISPLAY_TITLES.get(gate_id)
    normalized = {
        **gate,
        "matching_finding": matching_finding,
        "display_title": display_title,
    }
    normalized["debug_prompt"] = build_ide_debug_prompt(
        matching_finding or gate, release_decision=release_decision
    )
    return normalized


def _remediation_display_text(value: Any, *, max_len: int = 72) -> str:
    text = str(value or "n/a").strip() or "n/a"
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"


def _remediation_summary_line(*, decision: str, total_count: int) -> str:
    count_label = f"{total_count} context{'s' if total_count != 1 else ''} available"
    if decision == "BLOCKED":
        prefix = "Optional engineering follow-up context for blocked evidence."
    else:
        prefix = "Optional non-blocking engineering follow-up context."
    return f"{prefix} {count_label}. This does not affect the release decision."


def _remediation_entry_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("trace_id") or ""),
        str(entry.get("control_id") or ""),
        str(entry.get("failed_metric") or ""),
    )


def _remediation_entry(
    subject: dict[str, Any],
    *,
    release_decision: dict[str, Any],
    control_id: str | None = None,
    failed_metric: str | None = None,
) -> dict[str, Any]:
    evidence_ids = subject.get("evidence_ids") or subject.get("source_evidence_ids") or []
    if isinstance(evidence_ids, list):
        evidence_id = ", ".join(str(value) for value in evidence_ids) or "n/a"
    else:
        evidence_id = str(evidence_ids)
    remediation_context = subject.get("debug_prompt") or build_ide_debug_prompt(
        subject,
        release_decision=release_decision,
    )
    resolved_control_id = control_id or subject.get("gate_id") or subject.get("control_id") or "n/a"
    resolved_metric = failed_metric or subject.get("finding_type") or subject.get("name") or "n/a"
    metric_label = str(resolved_metric).replace("_", " ")
    title = subject.get("expected_behavior") or subject.get("display_name") or metric_label
    return {
        "title": str(title),
        "evidence_id": evidence_id,
        "display_evidence_id": _remediation_display_text(evidence_id),
        "trace_id": _remediation_display_text(subject.get("trace_id") or "n/a", max_len=48),
        "case_id": _remediation_display_text(subject.get("case_id") or "n/a", max_len=48),
        "failed_metric": metric_label,
        "control_id": resolved_control_id,
        "role": subject.get("user_role") or "n/a",
        "selected_intent": subject.get("selected_intent_id") or subject.get("intent_id") or "n/a",
        "tool_called": subject.get("tool_name") or subject.get("gate_id") or "n/a",
        "policy_decision": subject.get("policy_preflight_decision") or "n/a",
        "remediation_context": remediation_context,
    }


def _developer_remediation_context(
    *,
    release_decision: dict[str, Any],
    critical_findings: list[dict[str, Any]],
    failing_metrics: list[dict[str, Any]],
    normalized_regression_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    decision = str(release_decision.get("decision") or "UNKNOWN")
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def append_entry(
        subject: dict[str, Any],
        *,
        control_id: str | None = None,
        failed_metric: str | None = None,
    ) -> None:
        candidate = _remediation_entry(
            subject,
            release_decision=release_decision,
            control_id=control_id,
            failed_metric=failed_metric,
        )
        key = _remediation_entry_key(candidate)
        if key in seen:
            return
        seen.add(key)
        entries.append(candidate)

    warning_failures = [
        metric
        for metric in failing_metrics
        if metric.get("passes_threshold") is False
        and str(metric.get("decision_impact") or "") == "warning"
    ]

    if decision == "BLOCKED":
        for finding in critical_findings:
            append_entry(
                finding,
                failed_metric=str(finding.get("finding_type") or "blocker_finding"),
            )
        for gate in normalized_regression_gates:
            append_entry(gate, control_id=str(gate.get("gate_id") or "release_control"))
        for metric in warning_failures:
            append_entry(
                {
                    **metric,
                    "trace_id": None,
                    "case_id": None,
                    "user_role": None,
                    "intent_id": metric.get("name"),
                    "tool_name": metric.get("display_name"),
                },
                control_id=str(metric.get("control_id") or "warning_control"),
                failed_metric=str(metric.get("name") or "warning_metric"),
            )
        show = bool(entries)
        is_non_blocking = False
    elif decision == "APPROVED" and warning_failures:
        for metric in warning_failures:
            append_entry(
                {
                    **metric,
                    "trace_id": None,
                    "case_id": None,
                    "user_role": None,
                    "intent_id": metric.get("name"),
                    "tool_name": metric.get("display_name"),
                },
                control_id=str(metric.get("control_id") or "warning_control"),
                failed_metric=str(metric.get("name") or "warning_metric"),
            )
        show = bool(entries)
        is_non_blocking = True
    else:
        show = False
        is_non_blocking = False

    total_count = len(entries)
    return {
        "show": show,
        "entries": entries[:REMEDIATION_VISIBLE_LIMIT],
        "total_count": total_count,
        "truncated": total_count > REMEDIATION_VISIBLE_LIMIT,
        "visible_limit": REMEDIATION_VISIBLE_LIMIT,
        "title": "Developer remediation context",
        "summary_line": _remediation_summary_line(decision=decision, total_count=total_count),
        "is_non_blocking": is_non_blocking,
    }


def build_ide_debug_prompt(subject: dict[str, Any], *, release_decision: dict[str, Any]) -> str:
    evidence_ids = subject.get("evidence_ids") or subject.get("source_evidence_ids") or []
    if isinstance(evidence_ids, list):
        evidence_text = ", ".join(str(value) for value in evidence_ids) or "n/a"
    else:
        evidence_text = str(evidence_ids)
    agent_id = release_decision.get("agent_id", "unknown")
    agent_version = release_decision.get("agent_version", "candidate")
    policy_id = release_decision.get("policy_id", "unknown")
    policy_version = release_decision.get("policy_version", "unknown")
    tool_name = subject.get("tool_name") or subject.get("gate_id") or "unknown"
    intent_id = subject.get("intent_id", "unknown")
    trace_id = subject.get("trace_id", "n/a")
    case_id = subject.get("case_id", "n/a")
    return f"""# AgentGate Candidate Debug

## Goal
Investigate why candidate {agent_version} produced {subject.get("finding_type", subject.get("gate_id", "dangerous release finding"))} for case `{case_id}`.

## AgentGate Evidence
- Agent: {agent_id}
- Candidate version: {agent_version}
- Policy: {policy_id} / {policy_version}
- Trace ID: `{trace_id}`
- Case ID: `{case_id}`
- Severity: {subject.get("severity", "n/a")}
- User role: {subject.get("user_role", "n/a")}
- Input: {subject.get("input_text", subject.get("trigger", "n/a"))}
- Intent: {intent_id}
- Tool: {tool_name}
- Risk level: {subject.get("risk_level", "n/a")}
- Expected allowed: {subject.get("expected_allowed", "n/a")}
- Actual allowed: {subject.get("actual_allowed", "n/a")}
- Policy preflight decision: {subject.get("policy_preflight_decision", "n/a")}
- Policy violation reason: {subject.get("policy_violation_reason", "n/a")}
- Span: {subject.get("span_name", "n/a")}
- Evidence IDs: {evidence_text}

## Please inspect
1. Git history between the baseline and candidate for router, preflight, allowlist, prompt, and policy config changes.
2. Current role policy enforcement around `{tool_name}`.
3. Intent mapping for `{intent_id}`.
4. Phoenix trace `{trace_id}` in the configured evidence project.
5. Whether tool execution can still happen after preflight DENY.

## Expected output
- Root cause
- Minimal code/config fix
- Regression test or eval case that fails on this trace pattern
- Verification steps

## Constraint
Do not modify AgentGate as if it were the production agent. AgentGate reports evidence; the runtime fix belongs in the evaluated agent."""


def _audit_scope(
    release_decision: dict[str, Any], evidence_source: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    query = evidence_source.get("query") if isinstance(evidence_source.get("query"), dict) else {}
    agent_id = release_decision.get("agent_id", "unknown")
    return {
        "agent": agent_id,
        "candidate_version": release_decision.get("agent_version", "unknown"),
        "policy": f"{release_decision.get('policy_id', 'unknown')} / {release_decision.get('policy_version', 'unknown')}",
        "project_identifier": evidence_source.get("project_identifier")
        or query.get("project_identifier")
        or "unknown",
        "evidence_source": evidence_source.get("type") or "unknown",
        "evaluation_window": f"last {query.get('last_n_minutes')} minutes"
        if query.get("last_n_minutes")
        else "unknown",
        "max_dangerous_traces": query.get("max_dangerous_traces", "unknown"),
        "output_dir": str(output_dir),
    }


def _legacy_activity_log(
    critical_findings: list[dict[str, Any]],
    reviewed_safe: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for finding in critical_findings:
        entries.append(
            {
                "trace_id": finding.get("trace_id"),
                "case_id": finding.get("case_id"),
                "user_role": finding.get("user_role"),
                "input_text": finding.get("input_text"),
                "tool_names": [],
                "preflight_decision": "unknown",
                "expected_allowed": None,
                "actual_allowed": None,
                "policy_violation": None,
                "verdict": "violation",
                "verdict_reason": f"Material violation detected: {finding.get('finding_type')}.",
                "finding_types": [finding.get("finding_type")],
                "evidence_ids": finding.get("evidence_ids", []),
                "tool_executed": True,
            }
        )
    for session in reviewed_safe:
        entries.append(
            {
                "trace_id": session.get("trace_id"),
                "case_id": session.get("case_id"),
                "user_role": session.get("user_role"),
                "input_text": session.get("input_text"),
                "tool_names": session.get("tool_names", []),
                "preflight_decision": "ALLOW",
                "expected_allowed": True,
                "actual_allowed": True,
                "policy_violation": False,
                "verdict": "authorized",
                "verdict_reason": "High-risk tool activity completed after an allowed policy preflight.",
                "finding_types": [],
                "evidence_ids": session.get("evidence_ids", []),
                "tool_executed": bool(session.get("tool_names")),
            }
        )
    return entries


def _audit_summary(
    *,
    release_decision: dict[str, Any],
    failing_metrics: list[dict[str, Any]],
    critical_findings: list[dict[str, Any]],
    indeterminate_findings: list[dict[str, Any]],
    high_risk_activity_log: list[dict[str, Any]],
) -> dict[str, Any]:
    verdict_counts = {"violation": 0, "indeterminate": 0, "authorized": 0}
    for entry in high_risk_activity_log:
        verdict = str(entry.get("verdict", "unknown"))
        if verdict in verdict_counts:
            verdict_counts[verdict] += 1
    failed_controls = len(failing_metrics)
    decision = str(release_decision.get("decision") or "")
    if decision == "APPROVED" and failed_controls > 0:
        failed_controls_label = "Warning controls"
    else:
        failed_controls_label = "Failed controls"
    return {
        "failed_controls": failed_controls,
        "failed_controls_label": failed_controls_label,
        "material_violations": len(critical_findings),
        "indeterminate_sessions": len(indeterminate_findings),
        "high_risk_activity_records": len(high_risk_activity_log),
        **verdict_counts,
    }


def _authority_note(pack: LoadedAgentPack) -> str:
    branding = pack.report_config.get("branding")
    if isinstance(branding, dict):
        configured = branding.get("authority_note")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
    return (
        "Phoenix provides trace/eval evidence. AgentGate adds AgentPack-defined policy thresholds "
        "and company metrics, then deterministically decides BLOCKED/APPROVED. Gemini explains "
        "selected sessions only."
    )


def _policy_snapshot_note(pack: LoadedAgentPack, release_decision: dict[str, Any]) -> str:
    branding = pack.report_config.get("branding")
    if isinstance(branding, dict):
        template = branding.get("policy_snapshot_note_template")
        if isinstance(template, str) and template.strip():
            return template.format(
                policy_id=release_decision.get("policy_id", "unknown"),
                policy_version=release_decision.get("policy_version", "unknown"),
            )
    return (
        "Effective policy combines Phoenix base policy with AgentPack custom thresholds for this audit run "
        f"({release_decision.get('policy_id')}/{release_decision.get('policy_version')}). "
        "Verify against artifact SHA-256 below."
    )


def _executive_summary(
    release_decision: dict[str, Any],
    audit_summary: dict[str, int],
) -> str:
    agent_version = release_decision.get("agent_version", "candidate")
    decision = release_decision.get("decision", "UNKNOWN")
    if decision == "APPROVED":
        if audit_summary.get("failed_controls", 0) > 0:
            return (
                f"Candidate {agent_version} is APPROVED. "
                "All inherited blocker controls passed. "
                "Non-blocking warnings remain visible for review."
            )
        return (
            f"Candidate {agent_version} is APPROVED. "
            f"AgentGate logged {audit_summary['high_risk_activity_records']} high-risk activity record(s) "
            "with no blocking release-safety control failures."
        )
    if decision == "BLOCKED":
        return (
            f"Candidate {agent_version} is BLOCKED before production. "
            f"{audit_summary['failed_controls']} control(s) failed; "
            f"{audit_summary['material_violations']} dangerous capability regression(s); "
            f"{audit_summary['indeterminate_sessions']} indeterminate session(s); "
            f"{audit_summary['high_risk_activity_records']} high-risk activity record(s) logged."
        )
    return f"Candidate {agent_version} returned decision {decision}. Review the evidence before production."
