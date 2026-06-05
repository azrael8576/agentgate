import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agentgate.core.product_config import ReleaseCheckConfig

SCHEMA_VERSION = "day4.metrics.v1"
AGENT_REVIEW_STATUS_NO_ACTION = "no_action"
AGENT_REVIEW_STATUS_DISABLED = "disabled"
DECISION_INPUT_ARTIFACT_NAMES = [
    "metrics_summary",
    "dangerous_sessions",
    "regression_gates",
    "control_verification_results",
    "release_decision",
    "agent_profile",
    "eval_suite",
]
AGENT_REVIEW_ARTIFACT_NAMES = [
    "agent_review_input",
    "pattern_finder_plan",
    "pattern_finder_results",
    "dataset_planner_results",
]


def write_release_artifacts(
    output_dir: Path,
    identity: dict[str, Any],
    evidence_source: dict[str, Any],
    metrics_summary: dict[str, Any],
    dangerous_sessions: dict[str, Any],
    diagnoses: dict[str, Any],
    decision: dict[str, Any],
    diagnosis_metadata: dict[str, Any] | None = None,
    release_config: ReleaseCheckConfig | None = None,
    control_verification: dict[str, Any] | None = None,
    agentic_review_enabled: bool = False,
    agent_review_artifacts: dict[str, dict[str, Any]] | None = None,
    agentic_review_status: dict[str, Any] | None = None,
) -> dict[str, str]:
    config = release_config or ReleaseCheckConfig()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()

    base = {
        "schema_version": SCHEMA_VERSION,
        "agent_id": identity["agent_id"],
        "agent_version": identity["agent_version"],
        "generated_at": generated_at,
    }
    artifacts = {
        "metrics_summary": {
            **base,
            **metrics_summary,
        },
        "dangerous_sessions": {
            **base,
            **dangerous_sessions,
        },
        "regression_gates": {
            **base,
            "regression_gates": diagnoses["regression_gates"],
        },
        "release_decision": {
            **base,
            **decision,
            "metrics": metrics_summary["metrics"],
            "artifact_paths": {},
            "evidence_source": evidence_source,
            "phoenix_dangerous_traces": evidence_source.get("dangerous_traces", []),
            "diagnosis_metadata": diagnosis_metadata
            or {
                "diagnosis_source": "deterministic",
                "model": None,
                "validated_evidence_ids": True,
                "fallback_used": False,
            },
        },
    }
    if control_verification is not None:
        artifacts["control_verification_results"] = {
            **base,
            **control_verification,
        }
    reference_profile = _read_json_if_exists(config.resolved_profile_path)
    reference_suite = _read_json_if_exists(config.resolved_suite_path)
    if reference_profile and reference_profile.get("agent_id") == identity["agent_id"]:
        artifacts["agent_profile"] = {
            **base,
            "profile": reference_profile,
        }
    if reference_suite and reference_suite.get("agent_id") == identity["agent_id"]:
        artifacts["eval_suite"] = {
            **base,
            "suite": reference_suite,
        }
    agent_review_artifacts = agent_review_artifacts or _build_agent_review_artifacts(
        base=base,
        evidence_source=evidence_source,
        dangerous_sessions=dangerous_sessions,
    )
    if agentic_review_enabled:
        artifacts.update(agent_review_artifacts)

    paths = {
        artifact_name: output_dir / f"{artifact_name}.json"
        for artifact_name in (
            "metrics_summary",
            "dangerous_sessions",
            "regression_gates",
            "release_decision",
        )
    }
    if "control_verification_results" in artifacts:
        paths["control_verification_results"] = output_dir / "control_verification_results.json"
    if "agent_profile" in artifacts:
        paths["agent_profile"] = output_dir / "agent_profile.json"
    if "eval_suite" in artifacts:
        paths["eval_suite"] = output_dir / "eval_suite.json"
    if agentic_review_enabled:
        paths.update(
            {
                artifact_name: output_dir / f"{artifact_name}.json"
                for artifact_name in AGENT_REVIEW_ARTIFACT_NAMES
            }
        )
    paths["audit_manifest"] = output_dir / "audit_manifest.json"
    artifacts["audit_manifest"] = {
        **base,
        "product_surface": "release_authority",
        "evaluation_mode": "controlled",
        "sample_tier": "demo",
        "decision_reproducible_without_llm_rerun": True,
        "llm_rerun_required": False,
        "phoenix_required_for_offline_decision": False,
        "decision_inputs": DECISION_INPUT_ARTIFACT_NAMES,
        "agent_review_artifacts": AGENT_REVIEW_ARTIFACT_NAMES if agentic_review_enabled else [],
        "reproducibility_recipe": [
            "Read release_decision.json for policy version, gate_binding, decision reasons, and future_verification.",
            "Read metrics_summary.json for controlled metric values, thresholds, and provenance.",
            "Read eval_suite.json for declared required_metrics; compare with release_decision.gate_binding.",
            "Read dangerous_sessions.json for blocker evidence IDs.",
            "Read regression_gates.json for generated release controls.",
            "Read control_verification_results.json for inherited release-control PASS/FAIL rows.",
            "Recompute BLOCKED/APPROVED from gate-bound runtime metrics and inherited blocker controls; do not rerun Gemini.",
        ],
        "artifacts": {
            artifact_name: {
                "path": str(path),
                "required_for_offline_audit": artifact_name
                in {
                    "metrics_summary",
                    "dangerous_sessions",
                    "regression_gates",
                    "control_verification_results",
                    "release_decision",
                },
            }
            for artifact_name, path in paths.items()
            if artifact_name != "audit_manifest"
        },
        "certified_reference": {
            "agent_id": identity["agent_id"],
            "profile_included": "agent_profile" in artifacts,
            "eval_suite_included": "eval_suite" in artifacts,
        },
    }
    artifacts["release_decision"]["decision_inputs"] = DECISION_INPUT_ARTIFACT_NAMES
    artifacts["release_decision"]["agentic_review"] = (
        agentic_review_status or _agentic_review_status(agentic_review_enabled)
    )
    artifacts["release_decision"]["artifact_paths"] = {
        artifact_name: str(path) for artifact_name, path in paths.items()
    }

    for artifact_name, path in paths.items():
        path.write_text(
            json.dumps(artifacts[artifact_name], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    _refresh_audit_manifest_hashes(output_dir)

    return {artifact_name: str(path) for artifact_name, path in paths.items()}


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _refresh_audit_manifest_hashes(output_dir: Path) -> None:
    manifest_path = output_dir / "audit_manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for artifact in manifest.get("artifacts", {}).values():
        path = Path(artifact["path"])
        if not path.exists():
            continue
        artifact["sha256"] = _sha256_file(path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_agent_review_artifacts(
    *,
    base: dict[str, Any],
    evidence_source: dict[str, Any],
    dangerous_sessions: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    critical_findings = dangerous_sessions.get("critical_findings", [])
    indeterminate_findings = dangerous_sessions.get("indeterminate_findings", [])
    reviewed_safe = dangerous_sessions.get("reviewed_safe", [])
    high_risk_activity = dangerous_sessions.get("high_risk_activity_log", [])
    shared_status = {
        "status": AGENT_REVIEW_STATUS_NO_ACTION,
        "summary": "No action from agent review.",
        "authority_boundary": (
            "Agents investigate and plan. The release gate still decides APPROVED or BLOCKED."
        ),
    }
    return {
        "agent_review_input": {
            **base,
            "agent_review": {
                "enabled": True,
                **shared_status,
            },
            "release_evidence_summary": {
                "evidence_source_type": evidence_source.get("type"),
                "critical_findings": len(critical_findings),
                "indeterminate_findings": len(indeterminate_findings),
                "reviewed_safe": len(reviewed_safe),
                "high_risk_activity": len(high_risk_activity),
                "dangerous_trace_ids": evidence_source.get("dangerous_trace_ids", []),
            },
        },
        "pattern_finder_plan": {
            **base,
            "agent": "pattern_finder",
            **shared_status,
            "workflow": [
                "Review shared release evidence.",
                "Look for repeated blocker patterns.",
                "Escalate only when evidence supports a release-safety pattern.",
            ],
            "focus_areas": [],
        },
        "pattern_finder_results": {
            **base,
            "agent": "pattern_finder",
            **shared_status,
            "failure_patterns": [],
            "warning_observations": [],
        },
        "dataset_planner_results": {
            **base,
            "agent": "dataset_planner",
            **shared_status,
            "dataset_candidates": [],
        },
    }


def _agentic_review_status(enabled: bool) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "status": AGENT_REVIEW_STATUS_NO_ACTION if enabled else AGENT_REVIEW_STATUS_DISABLED,
    }
