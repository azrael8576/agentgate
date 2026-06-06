import hashlib
import io
import json
import zipfile
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
AGENT_REVIEW_ARTIFACT_FILENAMES = {
    "agent_review_input.json",
    "pattern_finder_plan.json",
    "pattern_finder_results.json",
    "dataset_planner_results.json",
}
HTML_ARTIFACT_FILENAME = "release_report.html"
BUNDLE_ZIP_FILENAME = "release_audit_bundle.zip"
BUNDLE_ZIP_HREF = f"/artifacts/{BUNDLE_ZIP_FILENAME}"
BASE_ARTIFACT_LINKS = [
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
]
AGENT_REVIEW_ARTIFACT_LINKS = [
    {
        "name": "agent_review_input",
        "filename": "agent_review_input.json",
        "href": "/artifacts/agent_review_input.json",
    },
    {
        "name": "pattern_finder_plan",
        "filename": "pattern_finder_plan.json",
        "href": "/artifacts/pattern_finder_plan.json",
    },
    {
        "name": "pattern_finder_results",
        "filename": "pattern_finder_results.json",
        "href": "/artifacts/pattern_finder_results.json",
    },
    {
        "name": "dataset_planner_results",
        "filename": "dataset_planner_results.json",
        "href": "/artifacts/dataset_planner_results.json",
    },
]
TRAILING_ARTIFACT_LINKS = [
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
ARTIFACT_FILENAMES = CORE_ARTIFACT_FILENAMES | {
    "agent_profile.json",
    "eval_suite.json",
    "audit_manifest.json",
    "control_verification_results.json",
    *AGENT_REVIEW_ARTIFACT_FILENAMES,
}
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
    "agent_review_input.json": {
        "purpose": "Shared no-action agent review packet for Pattern Finder and Dataset Planner.",
        "format": "JSON",
    },
    "pattern_finder_plan.json": {
        "purpose": "Pattern Finder workflow and current focus areas.",
        "format": "JSON",
    },
    "pattern_finder_results.json": {
        "purpose": "Pattern Finder output. Informational only; it does not approve or block releases.",
        "format": "JSON",
    },
    "dataset_planner_results.json": {
        "purpose": "Dataset Planner output. Informational only; it does not approve or block releases.",
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


def _artifact_filenames_from_manifest(manifest: dict[str, Any] | None) -> set[str]:
    artifacts = (manifest or {}).get("artifacts", {})
    if not isinstance(artifacts, dict):
        return set()
    return {name if str(name).endswith(".json") else f"{name}.json" for name in artifacts}


def artifact_links(available_artifact_names: set[str] | None = None) -> list[dict[str, str]]:
    links = [*BASE_ARTIFACT_LINKS]
    if available_artifact_names and AGENT_REVIEW_ARTIFACT_FILENAMES.issubset(
        available_artifact_names
    ):
        links.extend(AGENT_REVIEW_ARTIFACT_LINKS)
    links.extend(TRAILING_ARTIFACT_LINKS)
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


_AGENT_REVIEW_SUBTITLE = "Advisory review output."
_AGENT_REVIEW_FALLBACK = (
    "Agentic review unavailable. The deterministic release decision remains valid."
)
_RELEASE_CONTROLS_AGENT_REVIEW_BRIDGE = (
    "Generated controls are release requirements. Agent Review is advisory."
)
_COMPACT_AUTHORITY_BOUNDARY = (
    "Deterministic metrics decide BLOCKED/APPROVED; agent review is advisory."
)
_DEMO_EVIDENCE_BANNER = "Demo evidence: controlled sample data, not production traffic."
_DATASET_PLANNER_ITEM_KEYS = (
    "dataset_candidates",
    "annotation_recommendations",
    "future_control_candidates",
    "duplicate_or_noise",
)
_PLANNER_CANDIDATE_TYPES = {
    "dataset_candidates": "Dataset candidate",
    "annotation_recommendations": "Annotation recommendation",
    "future_control_candidates": "Future control candidate",
    "duplicate_or_noise": "Duplicate/noise group",
}
_PLANNER_ID_FIELDS = {
    "dataset_candidates": "candidate_id",
    "annotation_recommendations": "recommendation_id",
    "future_control_candidates": "candidate_id",
    "duplicate_or_noise": "group_id",
}
_PLANNER_DISPLAY_TYPES = {
    "Dataset candidate": "Golden dataset candidate",
    "Annotation recommendation": "Annotation recommendation",
    "Future control candidate": "Future control candidate",
    "Duplicate/noise group": "Duplicate/noise group",
}
_FINDING_TYPE_BLOCKER_METRICS = {
    "unauthorized_dangerous_tool_execution": "unauthorized_dangerous_tool_attempt_rate",
    "dangerous_tool_policy_violation": "dangerous_tool_policy_violation_rate",
    "sensitive_output_violation": "sensitive_output_violation_rate",
    "dangerous_intent_misroute": "intent_routing_accuracy",
    "policy_violation_with_execution": "dangerous_tool_policy_violation_rate",
}
_SUMMARY_TEXT_LIMIT = 160
_REVIEW_ACTION_CHARS = 80
_WHY_TEXT_CHARS = 120
_DETAILS_TEXT_CHARS = 600
_RATIONALE_PREVIEW_LIMIT = _DETAILS_TEXT_CHARS
_EVIDENCE_PREVIEW_ROW_LIMIT = 8
_EVIDENCE_CHIP_DEFAULT_LIMIT = 3
_EVIDENCE_CHIP_DETAIL_LIMIT = 10
_TRACE_PREVIEW_DEFAULT_LIMIT = 2
_TRACE_DETAIL_LIMIT = 5
_EXAMPLE_TRACE_DETAIL_LIMIT = 5
_AGENT_REVIEW_VISIBLE_PATTERN_LIMIT = 3
_AGENT_REVIEW_VISIBLE_PLANNER_LIMIT = 3
_SESSION_DIAGNOSIS_APPENDIX_EXAMPLE_LIMIT = 5
_PRIORITY_PLANNER_ITEM_KEYS = (
    "future_control_candidates",
    "dataset_candidates",
    "annotation_recommendations",
)
_ACTIONABLE_PLANNER_TYPES = frozenset(
    {
        "Dataset candidate",
        "Annotation recommendation",
        "Future control candidate",
    }
)


def truncate_text(value: str, max_chars: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def preview_list(items: list[str], *, max_items: int) -> list[str]:
    return [str(item) for item in items if item][:max_items]


def remaining_count(items: list[str], max_items: int) -> int:
    return max(0, len([str(item) for item in items if item]) - max_items)


def hide_if_zero(value: int | float | None) -> int | None:
    if value is None:
        return None
    numeric = int(value)
    return numeric if numeric != 0 else None


def _first_sentence(text: str, *, max_chars: int = _SUMMARY_TEXT_LIMIT) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    for separator in ".!?":
        index = normalized.find(separator)
        if index > 0:
            return truncate_text(normalized[: index + 1], max_chars)
    return truncate_text(normalized, max_chars)


def _humanize_token(value: str) -> str:
    return str(value or "").replace("_", " ").strip()


def _related_control_from_pattern_id(pattern_id: str) -> str | None:
    parts = str(pattern_id or "").split(".", 1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    return _humanize_token(parts[1])


def _pattern_finding_type(pattern_id: str) -> str:
    parts = str(pattern_id or "").split(".", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _linked_blocker_metric(finding_type: str) -> str | None:
    if not finding_type:
        return None
    return _FINDING_TYPE_BLOCKER_METRICS.get(finding_type)


def _related_regression_gate(
    finding_type: str, regression_gates: list[dict[str, Any]]
) -> str | None:
    if not finding_type:
        return None
    trigger = f"material_violation:{finding_type}"
    for gate in regression_gates:
        if str(gate.get("trigger") or "") == trigger:
            gate_id = str(gate.get("gate_id") or "").strip()
            if gate_id:
                return gate_id
    return None


def _preview_identifiers(
    values: list[str], *, limit: int = _EVIDENCE_CHIP_DEFAULT_LIMIT
) -> dict[str, Any]:
    cleaned = [str(value) for value in values if value]
    preview = [_short(value) for value in preview_list(cleaned, max_items=limit)]
    remaining = remaining_count(cleaned, limit)
    return {
        "preview_ids": preview,
        "remaining_count": remaining,
        "total_count": len(cleaned),
    }


def _pattern_priority_rank(card: dict[str, Any]) -> tuple[int, int, int, int, str]:
    severity_rank = {"critical": 0, "warning": 3}.get(str(card.get("severity") or ""), 2)
    blocker_linked = 0 if card.get("linked_blocker_metric") else 1
    control_linked = 0 if card.get("related_control") else 1
    return (
        severity_rank,
        blocker_linked,
        control_linked,
        -int(card.get("trace_count") or 0),
        str(card.get("title") or ""),
    )


def _sort_pattern_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(cards, key=_pattern_priority_rank)


def _planner_actionability_rank(card: dict[str, Any]) -> int:
    candidate_type = str(card.get("candidate_type") or "")
    if candidate_type == "Future control candidate":
        return 0
    if candidate_type == "Dataset candidate":
        return 1
    if candidate_type == "Annotation recommendation":
        return 2
    return 3


def _sort_planner_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        cards,
        key=lambda card: (
            _planner_actionability_rank(card),
            -int(card.get("trace_count") or 0),
            str(card.get("suggested_label") or ""),
        ),
    )


def _split_visible_agent_review_items(
    items: list[dict[str, Any]], *, limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return items[:limit], items[limit:]


def _agent_review_audit_summary(
    *,
    blocker_findings_count: int,
    review_pattern_count: int,
    review_candidate_count: int,
    counts_available: bool = True,
) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    if not counts_available:
        return {"rows": rows}
    output_parts: list[str] = []
    if review_pattern_count:
        pattern_label = "pattern" if review_pattern_count == 1 else "patterns"
        output_parts.append(f"{review_pattern_count} {pattern_label}")
    if review_candidate_count:
        candidate_label = "candidate" if review_candidate_count == 1 else "candidates"
        output_parts.append(f"{review_candidate_count} review {candidate_label}")
    if output_parts:
        rows.append({"label": "Review output", "value": " · ".join(output_parts)})
    if blocker_findings_count:
        rows.append({"label": "Source findings", "value": str(blocker_findings_count)})
    return {"rows": rows}


def _grouped_evidence_id_count(cards: list[dict[str, Any]]) -> int:
    evidence_ids = {
        evidence_id for card in cards for evidence_id in card.get("evidence_ids", []) if evidence_id
    }
    return len(evidence_ids)


def _build_planner_cards(
    dataset_planner_results: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for items_key in _PRIORITY_PLANNER_ITEM_KEYS:
        for item in _review_result_items(dataset_planner_results, items_key):
            cards.append(
                _normalize_planner_card(
                    item,
                    candidate_type=_PLANNER_CANDIDATE_TYPES[items_key],
                    id_field=_PLANNER_ID_FIELDS[items_key],
                )
            )
    if cards:
        return cards
    for item in _review_result_items(dataset_planner_results, "duplicate_or_noise"):
        cards.append(
            _normalize_planner_card(
                item,
                candidate_type=_PLANNER_CANDIDATE_TYPES["duplicate_or_noise"],
                id_field=_PLANNER_ID_FIELDS["duplicate_or_noise"],
            )
        )
    return cards


def _session_diagnosis_appendix_title(diagnosis_metadata: dict[str, Any]) -> str:
    _ = diagnosis_metadata
    return "Session diagnosis appendix"


def _session_diagnosis_appendix_note(diagnosis_metadata: dict[str, Any]) -> str:
    return (
        "Session-level diagnosis is retained for audit traceability. "
        "It is not used for APPROVED / BLOCKED."
    )


def _session_diagnosis_visible_examples(
    diagnoses: list[dict[str, Any]], *, limit: int = _SESSION_DIAGNOSIS_APPENDIX_EXAMPLE_LIMIT
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for diagnosis in diagnoses[:limit]:
        examples.append(
            {
                "case_id": diagnosis.get("case_id", "n/a"),
                "trace_id": _short(diagnosis.get("trace_id")),
                "finding_type": str(diagnosis.get("finding_type") or "session_diagnosis").replace(
                    "_", " "
                ),
                "diagnosis_preview": truncate_text(
                    str(diagnosis.get("diagnosis") or ""),
                    _SUMMARY_TEXT_LIMIT,
                ),
            }
        )
    return examples


def _pattern_reviewer_action(
    pattern: dict[str, Any], *, focus_areas: list[str], severity: str
) -> str:
    if focus_areas:
        return _first_sentence(str(focus_areas[0]))
    if str(severity) == "warning":
        return (
            "Review whether the cited warning traces need human follow-up without "
            "changing the release verdict."
        )
    return (
        "Confirm the cited traces are representative before promoting this pattern "
        "into dataset or control planning."
    )


def _normalize_pattern_card(
    pattern: dict[str, Any],
    *,
    focus_areas: list[str],
    regression_gates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pattern_id = str(pattern.get("pattern_id") or pattern.get("observation_id") or "")
    evidence_ids = [str(item) for item in pattern.get("supporting_evidence_ids", []) if item]
    trace_ids = [str(item) for item in pattern.get("supporting_trace_ids", []) if item]
    severity = str(pattern.get("severity") or "unknown")
    finding_type = _pattern_finding_type(pattern_id)
    gates = regression_gates or []
    linked_metric = _linked_blocker_metric(finding_type)
    related_control = _related_regression_gate(finding_type, gates)
    why_it_matters = truncate_text(
        str(pattern.get("why_it_matters") or pattern.get("problem_summary") or ""),
        _WHY_TEXT_CHARS,
    )
    evidence_preview = _preview_identifiers(evidence_ids, limit=_EVIDENCE_CHIP_DEFAULT_LIMIT)
    trace_preview = _preview_identifiers(trace_ids, limit=_TRACE_PREVIEW_DEFAULT_LIMIT)
    detail_evidence_ids = [
        _short(item) for item in preview_list(evidence_ids, max_items=_EVIDENCE_CHIP_DETAIL_LIMIT)
    ]
    detail_trace_ids = [
        _short(item) for item in preview_list(trace_ids, max_items=_TRACE_DETAIL_LIMIT)
    ]
    example_traces = list(pattern.get("example_traces", []))[:_EXAMPLE_TRACE_DETAIL_LIMIT]
    detail_has_more = (
        remaining_count(evidence_ids, _EVIDENCE_CHIP_DETAIL_LIMIT) > 0
        or remaining_count(trace_ids, _TRACE_DETAIL_LIMIT) > 0
        or len(pattern.get("example_traces", [])) > _EXAMPLE_TRACE_DETAIL_LIMIT
    )
    return {
        "id": pattern_id,
        "title": str(pattern.get("title") or pattern_id),
        "severity": severity,
        "evidence_count": len(evidence_ids) or len(trace_ids),
        "trace_count": len(trace_ids),
        "linked_blocker_metric": linked_metric,
        "metric_name": linked_metric,
        "related_control": related_control,
        "control_id": related_control,
        "related_topic": _related_control_from_pattern_id(pattern_id),
        "problem_summary": _first_sentence(str(pattern.get("problem_summary") or "")),
        "why_it_matters": why_it_matters,
        "reviewer_action": _first_sentence(
            _pattern_reviewer_action(pattern, focus_areas=focus_areas, severity=severity)
        ),
        "evidence_ids": evidence_ids,
        "trace_ids": trace_ids,
        "preview_evidence_ids": evidence_preview["preview_ids"],
        "remaining_evidence_count": evidence_preview["remaining_count"],
        "preview_trace_ids": trace_preview["preview_ids"],
        "remaining_trace_count": trace_preview["remaining_count"],
        "json_href": "/artifacts/pattern_finder_results.json",
        "details": {
            "problem_summary": truncate_text(
                str(pattern.get("problem_summary") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "why_it_matters": truncate_text(
                str(pattern.get("why_it_matters") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "policy_runtime_mismatch": truncate_text(
                str(pattern.get("policy_runtime_mismatch") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "reviewer_action": _first_sentence(
                _pattern_reviewer_action(pattern, focus_areas=focus_areas, severity=severity),
                max_chars=_RATIONALE_PREVIEW_LIMIT,
            ),
            "example_traces": example_traces,
            "detail_evidence_ids": detail_evidence_ids,
            "detail_trace_ids": detail_trace_ids,
            "has_more_in_json": detail_has_more,
        },
    }


def _planner_suggested_label(item: dict[str, Any], *, item_id: str) -> str:
    finding_types = [str(value) for value in item.get("source_finding_types", []) if value]
    if finding_types:
        return _humanize_token(finding_types[0]).title()
    return _humanize_token(item_id.split(".", 1)[-1]).title() or item_id


def _planner_action_line(candidate_type: str) -> str:
    _ = candidate_type
    return truncate_text("Approve / reject candidate", _REVIEW_ACTION_CHARS)


def _planner_reviewer_action(item: dict[str, Any]) -> str:
    review_instructions = _first_sentence(str(item.get("review_instructions") or ""))
    if review_instructions:
        return review_instructions
    recommended_action = _first_sentence(str(item.get("recommended_action") or ""))
    if recommended_action:
        return recommended_action
    return "Review cited traces and evidence IDs before promotion."


def _normalize_planner_card(
    item: dict[str, Any],
    *,
    candidate_type: str,
    id_field: str,
) -> dict[str, Any]:
    item_id = str(item.get(id_field) or "")
    trace_ids = [str(value) for value in item.get("source_trace_ids", []) if value]
    evidence_ids = [str(value) for value in item.get("source_evidence_ids", []) if value]
    review_status = str(item.get("review_status") or "")
    status_label = (
        "Pending review"
        if item.get("requires_human_review") is True or review_status == "pending_review"
        else _humanize_token(review_status).title() or "Pending review"
    )
    evidence_preview = _preview_identifiers(evidence_ids, limit=_EVIDENCE_CHIP_DEFAULT_LIMIT)
    trace_preview = _preview_identifiers(trace_ids, limit=_TRACE_PREVIEW_DEFAULT_LIMIT)
    shown_trace_count = min(len(trace_ids), _TRACE_PREVIEW_DEFAULT_LIMIT)
    shown_evidence_count = min(len(evidence_ids), _EVIDENCE_CHIP_DEFAULT_LIMIT)
    source_remaining_count = remaining_count(trace_ids, _TRACE_PREVIEW_DEFAULT_LIMIT) + (
        remaining_count(evidence_ids, _EVIDENCE_CHIP_DEFAULT_LIMIT)
    )
    detail_evidence_ids = [
        _short(value) for value in preview_list(evidence_ids, max_items=_EVIDENCE_CHIP_DETAIL_LIMIT)
    ]
    detail_trace_ids = [
        _short(value) for value in preview_list(trace_ids, max_items=_TRACE_DETAIL_LIMIT)
    ]
    detail_has_more = (
        remaining_count(evidence_ids, _EVIDENCE_CHIP_DETAIL_LIMIT) > 0
        or remaining_count(trace_ids, _TRACE_DETAIL_LIMIT) > 0
    )
    return {
        "id": item_id,
        "candidate_type": candidate_type,
        "display_type": _PLANNER_DISPLAY_TYPES.get(candidate_type, candidate_type),
        "suggested_label": _planner_suggested_label(item, item_id=item_id),
        "status_label": status_label,
        "action_line": _planner_action_line(candidate_type),
        "why_useful": _first_sentence(str(item.get("rationale") or "")),
        "reviewer_action": _first_sentence(_planner_reviewer_action(item)),
        "trace_ids": trace_ids,
        "trace_count": len(trace_ids),
        "evidence_ids": evidence_ids,
        "preview_evidence_ids": evidence_preview["preview_ids"],
        "remaining_evidence_count": evidence_preview["remaining_count"],
        "preview_trace_ids": trace_preview["preview_ids"],
        "remaining_trace_count": trace_preview["remaining_count"],
        "shown_trace_count": shown_trace_count,
        "shown_evidence_count": shown_evidence_count,
        "source_remaining_count": source_remaining_count,
        "json_href": "/artifacts/dataset_planner_results.json",
        "details": {
            "problem_summary": truncate_text(
                str(item.get("rationale") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "policy_runtime_mismatch": "",
            "reviewer_action": truncate_text(
                _planner_reviewer_action(item),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "rationale": truncate_text(
                str(item.get("rationale") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "review_instructions": truncate_text(
                str(item.get("review_instructions") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "conversion_guidance": truncate_text(
                str(item.get("conversion_guidance") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "recommended_action": truncate_text(
                str(item.get("recommended_action") or ""),
                _RATIONALE_PREVIEW_LIMIT,
            ),
            "review_status": review_status,
            "source_finding_types": [
                str(value) for value in item.get("source_finding_types", []) if value
            ],
            "detail_evidence_ids": detail_evidence_ids,
            "detail_trace_ids": detail_trace_ids,
            "has_more_in_json": detail_has_more,
        },
    }


def _representative_trace_count(pattern_cards: list[dict[str, Any]]) -> int:
    trace_ids = {
        trace_id for card in pattern_cards for trace_id in card.get("trace_ids", []) if trace_id
    }
    return len(trace_ids)


def _agent_review_unavailable(
    *,
    pattern_finder_results: dict[str, Any] | None,
    dataset_planner_results: dict[str, Any] | None,
) -> bool:
    if not pattern_finder_results and not dataset_planner_results:
        return True

    pattern_status = str((pattern_finder_results or {}).get("status") or "")
    planner_status = str((dataset_planner_results or {}).get("status") or "")
    if pattern_status == "failed" and planner_status == "failed":
        return True

    pattern_has_content = bool(
        (pattern_finder_results or {}).get("failure_patterns")
        or (pattern_finder_results or {}).get("warning_observations")
    )
    planner_has_content = any(
        (dataset_planner_results or {}).get(items_key) for items_key in _DATASET_PLANNER_ITEM_KEYS
    )
    if pattern_status == "failed" and not pattern_has_content and not planner_has_content:
        return True
    return bool(planner_status == "failed" and not planner_has_content and not pattern_has_content)


def _agent_review_section(
    *,
    release_decision: dict[str, Any],
    agent_review_input: dict[str, Any] | None,
    pattern_finder_plan: dict[str, Any] | None,
    pattern_finder_results: dict[str, Any] | None,
    dataset_planner_results: dict[str, Any] | None,
    blocker_findings_count: int,
    regression_gates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    decision_agentic_review = release_decision.get("agentic_review", {})
    review_payload = agent_review_input.get("agent_review", {}) if agent_review_input else {}
    trace_pull_notice = ""
    if str(decision_agentic_review.get("status") or "") == "trace_pull_failed":
        trace_pull_notice = str(
            decision_agentic_review.get("summary") or review_payload.get("summary") or ""
        )
    elif str(review_payload.get("status") or "") == "trace_pull_failed":
        trace_pull_notice = str(review_payload.get("summary") or "")
    enabled = bool(
        decision_agentic_review.get("enabled")
        or agent_review_input
        or pattern_finder_plan
        or pattern_finder_results
        or dataset_planner_results
    )
    if not enabled:
        return {
            "enabled": False,
            "headline": "Agent review disabled",
            "subtitle": _AGENT_REVIEW_SUBTITLE,
            "summary": "This run did not request agent review artifacts.",
            "audit_summary": {"rows": []},
            "pattern_finder": {"status": "disabled", "summary": "Not requested."},
            "dataset_planner": {"status": "disabled", "summary": "Not requested."},
        }

    focus_areas = pattern_finder_plan.get("focus_areas", []) if pattern_finder_plan else []
    failure_patterns = (
        pattern_finder_results.get("failure_patterns", []) if pattern_finder_results else []
    )
    warning_observations = (
        pattern_finder_results.get("warning_observations", []) if pattern_finder_results else []
    )
    gate_context = regression_gates or []
    pattern_cards = [
        _normalize_pattern_card(pattern, focus_areas=focus_areas, regression_gates=gate_context)
        for pattern in failure_patterns
    ]
    warning_cards = [
        _normalize_pattern_card(warning, focus_areas=focus_areas, regression_gates=gate_context)
        for warning in warning_observations
    ]
    dataset_candidates = _review_result_items(dataset_planner_results, "dataset_candidates")
    annotation_recommendations = _review_result_items(
        dataset_planner_results, "annotation_recommendations"
    )
    future_control_candidates = _review_result_items(
        dataset_planner_results, "future_control_candidates"
    )
    duplicate_or_noise = _review_result_items(dataset_planner_results, "duplicate_or_noise")
    planner_cards = _build_planner_cards(dataset_planner_results)

    unavailable = _agent_review_unavailable(
        pattern_finder_results=pattern_finder_results,
        dataset_planner_results=dataset_planner_results,
    )
    all_pattern_cards = _sort_pattern_cards([*pattern_cards, *warning_cards])
    visible_pattern_cards, additional_pattern_cards = _split_visible_agent_review_items(
        all_pattern_cards,
        limit=_AGENT_REVIEW_VISIBLE_PATTERN_LIMIT,
    )
    sorted_planner_cards = _sort_planner_cards(planner_cards)
    visible_planner_cards, overflow_planner_cards = _split_visible_agent_review_items(
        sorted_planner_cards,
        limit=_AGENT_REVIEW_VISIBLE_PLANNER_LIMIT,
    )
    review_pattern_count = len(all_pattern_cards)
    len(dataset_candidates)
    counts_available = not unavailable
    empty_states = {
        "human_review_queue": ("No human-review candidates were recommended for this release."),
        "dataset_candidates": "No dataset candidates recommended for this release.",
        "annotation_recommendations": "No annotation recommendations for this release.",
        "future_control_candidates": ("No future control candidates recommended by Agent Review."),
        "critical_patterns": "No critical release-safety patterns found by Pattern Finder.",
    }
    human_review_candidate_count = len(planner_cards)
    return {
        "enabled": True,
        "unavailable": unavailable,
        "headline": "Agent Review",
        "subtitle": _AGENT_REVIEW_SUBTITLE,
        "trace_pull_notice": trace_pull_notice,
        "audit_summary": _agent_review_audit_summary(
            blocker_findings_count=blocker_findings_count,
            review_pattern_count=review_pattern_count,
            review_candidate_count=human_review_candidate_count,
            counts_available=counts_available,
        ),
        "fallback_message": _AGENT_REVIEW_FALLBACK,
        "summary": review_payload.get("summary") or "No action from agent review.",
        "badges": [
            {"label": "Advisory only", "class": "advisory"},
            {"label": "Requires review", "class": "human-review"},
            {"label": "Not a decision input", "class": "no-decision"},
        ],
        "dataset_planner_headline": "Review queue",
        "dataset_planner_subcopy": "Candidates requiring reviewer approval.",
        "pattern_finder_headline": "Supporting patterns",
        "pattern_finder_subcopy": "Cross-session patterns linked to this release.",
        "empty_states": empty_states,
        "pattern_finder": {
            "status": pattern_finder_results.get("status", "unknown")
            if pattern_finder_results
            else "unknown",
            "summary": pattern_finder_results.get(
                "summary", "Pattern Finder did not return findings."
            )
            if pattern_finder_results
            else "Pattern Finder did not return findings.",
            "focus_areas": focus_areas,
            "failure_patterns": failure_patterns,
            "warning_observations": warning_observations,
            "pattern_cards": pattern_cards,
            "warning_cards": warning_cards,
            "visible_pattern_cards": visible_pattern_cards,
            "overflow_pattern_count": len(additional_pattern_cards),
            "empty_message": empty_states["critical_patterns"] if not pattern_cards else "",
        },
        "dataset_planner": {
            "status": dataset_planner_results.get("status", "unknown")
            if dataset_planner_results
            else "unknown",
            "summary": dataset_planner_results.get(
                "summary", "Dataset Planner did not return planning items."
            )
            if dataset_planner_results
            else "Dataset Planner did not return planning items.",
            "dataset_candidates": dataset_candidates,
            "annotation_recommendations": annotation_recommendations,
            "future_control_candidates": future_control_candidates,
            "duplicate_or_noise": duplicate_or_noise,
            "candidate_cards": planner_cards,
            "visible_candidate_cards": visible_planner_cards,
            "overflow_candidate_count": len(overflow_planner_cards),
            "empty_messages": {
                "dataset_candidates": empty_states["dataset_candidates"],
                "annotation_recommendations": empty_states["annotation_recommendations"],
                "future_control_candidates": empty_states["future_control_candidates"],
            },
        },
    }


def _review_result_items(
    review_results: dict[str, Any] | None, items_key: str
) -> list[dict[str, Any]]:
    if not review_results:
        return []
    return list(review_results.get(items_key, []))


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
            "status": "Failed",
            "impact": "Non-blocking",
            "impact_badge": "Failed · non-blocking",
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
                "Not applicable for this blocked source release. "
                "Future candidates must verify the generated controls."
            ),
            "secondary_copy": "",
            "resolution_note": "",
            "inherited_summary": None,
            "rows": [],
            "show_table": False,
            "compact_only": True,
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
            "inherited_summary": None,
            "rows": [],
            "show_table": False,
            "compact_only": False,
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
            "inherited_summary": _future_verification_inherited_summary(control_verification),
            "rows": rows,
            "show_table": bool(rows),
            "compact_only": False,
        }

    source_version = control_verification.get("source_release", {}).get("agent_version") or "v2"
    agent_version = release_decision.get("agent_version", "candidate")
    copy = (
        f"{agent_version} verified the release controls generated by the blocked {source_version} run. "
        "All inherited blocker controls passed."
    )
    secondary_copy = "Non-blocking warnings remain visible for review." if failed > 0 else ""
    resolution_note = ""
    if resolution in {"bundled_reference_fallback", "container_reference_fallback"}:
        resolution_note = "Verified from bundled reference controls."

    return {
        "title": "Future Verification",
        "status_label": "Verified",
        "status_class": "verified",
        "copy": copy,
        "secondary_copy": secondary_copy,
        "resolution_note": resolution_note,
        "inherited_summary": _future_verification_inherited_summary(control_verification),
        "rows": rows,
        "show_table": bool(rows),
        "compact_only": False,
    }


def _future_verification_inherited_summary(
    control_verification: dict[str, Any],
) -> dict[str, int] | None:
    summary = control_verification.get("summary") or {}
    total = int(summary.get("total_controls") or len(control_verification.get("results") or []))
    if total <= 0:
        return None
    return {
        "loaded": total,
        "passed": int(summary.get("passed") or 0),
        "blocking_failures": int(summary.get("blocking_failed") or 0),
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
    bridge_note = "Technical backing: regression_gates.json"
    agent_review_bridge_note = (
        _RELEASE_CONTROLS_AGENT_REVIEW_BRIDGE if decision == "BLOCKED" else ""
    )
    if decision == "APPROVED":
        return {
            "eyebrow": "Release controls",
            "headline": "Release controls generated",
            "summary": "",
            "bridge_note": bridge_note,
            "agent_review_bridge_note": agent_review_bridge_note,
            "tasks": [],
            "rerun_label": "",
        }
    if regression_gates:
        return {
            "eyebrow": "Release controls",
            "headline": "Release controls generated",
            "summary": "",
            "bridge_note": bridge_note,
            "agent_review_bridge_note": agent_review_bridge_note,
            "tasks": regression_gates,
            "rerun_label": "",
        }
    return {
        "eyebrow": "Release controls",
        "headline": "Release controls generated",
        "summary": "No generated release controls were captured for this run.",
        "bridge_note": bridge_note,
        "agent_review_bridge_note": agent_review_bridge_note,
        "tasks": [],
        "rerun_label": "",
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
    control_verification: dict[str, Any],
    agent_review_enabled: bool,
    available_artifact_names: set[str],
) -> dict[str, Any]:
    _ = (
        release_decision,
        evidence_source,
        audit_scope,
        gate_binding_rows,
        artifact_fingerprints,
        evaluation_mode,
        sample_tier,
        generated_at_display,
        suite_id,
    )
    return _compressed_audit_archive_summary(
        release_decision=release_decision,
        control_verification=control_verification,
        agent_review_enabled=agent_review_enabled,
        available_artifact_names=available_artifact_names,
    )


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
    return None


def _demo_evidence_banner(
    *,
    evaluation_mode: str,
    sample_tier: str,
    source_is_local: bool,
) -> str | None:
    if source_is_local or (evaluation_mode == "controlled" and sample_tier == "demo"):
        return _DEMO_EVIDENCE_BANNER
    return None


def _evidence_mode_label(evaluation_mode: str, sample_tier: str) -> str:
    mode = str(evaluation_mode or "unknown").replace("_", " ")
    tier = str(sample_tier or "unknown").replace("_", " ")
    if evaluation_mode == "controlled" and sample_tier == "demo":
        return "controlled / demo"
    return f"{mode} / {tier}"


def _artifact_bundle_download_link() -> dict[str, str]:
    return {
        "href": BUNDLE_ZIP_HREF,
        "label": "Download full report bundle",
        "filename": BUNDLE_ZIP_FILENAME,
        "purpose": (
            "ZIP archive with release_report.html and JSON audit artifacts for offline review."
        ),
    }


def bundle_artifact_filenames(output_dir: Path) -> list[str]:
    return [
        filename
        for filename in sorted(SERVABLE_ARTIFACT_FILENAMES)
        if (output_dir / filename).is_file()
    ]


def build_artifact_bundle_zip(output_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in bundle_artifact_filenames(output_dir):
            archive.write(output_dir / filename, arcname=filename)
    return buffer.getvalue()


def _compressed_audit_archive_summary(
    *,
    release_decision: dict[str, Any],
    control_verification: dict[str, Any],
    agent_review_enabled: bool,
    available_artifact_names: set[str],
) -> dict[str, Any]:
    agent_review_ready = agent_review_enabled and AGENT_REVIEW_ARTIFACT_FILENAMES.issubset(
        available_artifact_names
    )
    if control_verification:
        verification_status = str(control_verification.get("status") or "ready")
    elif "control_verification_results.json" in available_artifact_names:
        verification_status = "ready"
    else:
        verification_status = "not applicable"
    return {
        "headline": "Audit status",
        "status_cards": [
            {"label": "Decision artifact", "status": "ready", "status_class": "ready"},
            {"label": "Metrics artifact", "status": "ready", "status_class": "ready"},
            {"label": "Evidence artifact", "status": "ready", "status_class": "ready"},
            {
                "label": "Agent review artifacts",
                "status": "ready" if agent_review_ready else "not generated",
                "status_class": "ready" if agent_review_ready else "na",
            },
            {
                "label": "Control verification",
                "status": verification_status.replace("_", " "),
                "status_class": (
                    "ready"
                    if verification_status in {"verified", "ready", "passed"}
                    else "na"
                    if verification_status == "not applicable"
                    else "warning"
                ),
            },
        ],
    }


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


def _candidate_header(
    *,
    release_decision: dict[str, Any],
    agent_profile: dict[str, Any],
    evidence_source: dict[str, Any],
) -> dict[str, str]:
    policy_id = release_decision.get("policy_id") or "policy"
    policy_version = release_decision.get("policy_version") or "version"
    evidence_type = str(evidence_source.get("type") or "unknown").replace("_", " ")
    return {
        "candidate": str(release_decision.get("agent_version") or "candidate"),
        "agent": str(
            agent_profile.get("display_name") or release_decision.get("agent_id") or "agent"
        ),
        "evidence_source": evidence_type,
        "effective_policy": f"{policy_id} / {policy_version}",
        "authority_boundary": _COMPACT_AUTHORITY_BOUNDARY,
    }


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
    agent_review_input = _read_optional_json_artifact(output_dir, "agent_review_input.json")
    pattern_finder_plan = _read_optional_json_artifact(output_dir, "pattern_finder_plan.json")
    pattern_finder_results = _read_optional_json_artifact(output_dir, "pattern_finder_results.json")
    dataset_planner_results = _read_optional_json_artifact(
        output_dir, "dataset_planner_results.json"
    )
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
    available_artifact_names = _artifact_filenames_from_manifest(audit_manifest)
    links = artifact_links(available_artifact_names)
    agent_review = _agent_review_section(
        release_decision=release_decision,
        agent_review_input=agent_review_input,
        pattern_finder_plan=pattern_finder_plan,
        pattern_finder_results=pattern_finder_results,
        dataset_planner_results=dataset_planner_results,
        blocker_findings_count=len(critical_findings),
        regression_gates=regression_gate_list,
    )
    session_diagnosis_appendix = {
        "title": _session_diagnosis_appendix_title(diagnosis_metadata),
        "authority_note": _session_diagnosis_appendix_note(diagnosis_metadata),
        "session_count": len(dangerous_diagnoses),
        "themes": gemini_diagnosis_themes,
        "visible_examples": _session_diagnosis_visible_examples(dangerous_diagnoses),
    }

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
        "demo_evidence_banner": _demo_evidence_banner(
            evaluation_mode=evaluation_mode or "unknown",
            sample_tier=sample_tier or "unknown",
            source_is_local=evidence_source.get("type") == "local_jsonl",
        ),
        "evidence_mode_label": _evidence_mode_label(
            evaluation_mode or "unknown", sample_tier or "unknown"
        ),
        "reproducibility_recipe": reproducibility_recipe,
        "confidence_label": release_decision.get("confidence_label") or "unknown",
        "gemini_diagnosis_themes": gemini_diagnosis_themes,
        "session_diagnosis_appendix": session_diagnosis_appendix,
        "authority_note": _authority_note(pack),
        "candidate_header": _candidate_header(
            release_decision=release_decision,
            agent_profile=agent_profile,
            evidence_source=evidence_source,
        ),
        "policy_snapshot_note": _policy_snapshot_note(pack, release_decision),
        "dangerous_sessions": dangerous_sessions,
        "critical_findings": critical_findings,
        "evidence_preview": {
            "findings": critical_findings[:_EVIDENCE_PREVIEW_ROW_LIMIT],
            "total_count": len(critical_findings),
            "visible_limit": _EVIDENCE_PREVIEW_ROW_LIMIT,
            "truncated": len(critical_findings) > _EVIDENCE_PREVIEW_ROW_LIMIT,
        },
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
        "agent_review": agent_review,
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
            control_verification=control_verification,
            agent_review_enabled=bool(agent_review.get("enabled")),
            available_artifact_names=available_artifact_names,
        ),
        "appendix_sections": appendix_sections,
        "developer_remediation": _developer_remediation_context(
            release_decision=release_decision,
            critical_findings=critical_findings,
            failing_metrics=failing_metrics,
            normalized_regression_gates=normalized_regression_gates,
        ),
        "artifact_cards": links,
        "artifact_links": links,
        "artifact_bundle_download": _artifact_bundle_download_link(),
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
    source_ids = gate.get("source_evidence_ids") or []
    normalized["source_evidence_count"] = len(source_ids) if isinstance(source_ids, list) else 0
    behavior = str(gate.get("required_fix") or gate.get("expected_behavior") or "").strip()
    normalized["required_behavior_line"] = truncate_text(behavior, _SUMMARY_TEXT_LIMIT)
    normalized["control_title"] = display_title or gate_id
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
    elif decision == "BLOCKED":
        failed_controls_label = "Failed blocker metrics"
    else:
        failed_controls_label = "Failed controls"
    return {
        "failed_controls": failed_controls,
        "failed_controls_label": failed_controls_label,
        "material_violations": len(critical_findings),
        "indeterminate_sessions": len(indeterminate_findings),
        "show_needs_review_kpi": len(indeterminate_findings) > 0,
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
