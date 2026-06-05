import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agentgate.core.product_config import ReleaseCheckConfig

SCHEMA_VERSION = "day4.metrics.v1"


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

    paths = {
        "metrics_summary": output_dir / "metrics_summary.json",
        "dangerous_sessions": output_dir / "dangerous_sessions.json",
        "regression_gates": output_dir / "regression_gates.json",
        "release_decision": output_dir / "release_decision.json",
    }
    if "control_verification_results" in artifacts:
        paths["control_verification_results"] = output_dir / "control_verification_results.json"
    if "agent_profile" in artifacts:
        paths["agent_profile"] = output_dir / "agent_profile.json"
    if "eval_suite" in artifacts:
        paths["eval_suite"] = output_dir / "eval_suite.json"
    paths["audit_manifest"] = output_dir / "audit_manifest.json"
    artifacts["audit_manifest"] = {
        **base,
        "product_surface": "release_authority",
        "evaluation_mode": "controlled",
        "sample_tier": "demo",
        "decision_reproducible_without_llm_rerun": True,
        "llm_rerun_required": False,
        "phoenix_required_for_offline_decision": False,
        "decision_inputs": [
            "metrics_summary",
            "dangerous_sessions",
            "regression_gates",
            "control_verification_results",
            "release_decision",
            "agent_profile",
            "eval_suite",
        ],
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
