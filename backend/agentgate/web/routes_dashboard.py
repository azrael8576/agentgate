from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.release import release_check as release_check_module
from backend.agentgate.release.gemini_diagnoser import DiagnosisMode
from backend.agentgate.release.phoenix_mcp_client import PhoenixMCPError
from backend.agentgate.release.regression_gate_verifier import (
    future_verification_api_summary,
)
from backend.agentgate.web.config import load_dashboard_settings
from backend.agentgate.web.demo_story import load_reference_demo_story
from backend.agentgate.web.landing_presenter import build_landing_story
from backend.agentgate.web.report_renderer import (
    BUNDLE_ZIP_FILENAME,
    HTML_ARTIFACT_FILENAME,
    SERVABLE_ARTIFACT_FILENAMES,
    artifact_links,
    build_artifact_bundle_zip,
    build_latest_run_payload,
    build_report_context,
    latest_artifacts_exist,
)

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter()


class ReleaseCheckRequest(BaseModel):
    source: Literal["phoenix", "local"] = "phoenix"
    project_identifier: str | None = None
    agent_version: str | None = None
    release_controls_ref: str | None = None
    last_n_minutes: int | None = Field(default=None, ge=1)
    output_dir: Path | None = None
    evidence: Path | None = None
    diagnosis_mode: DiagnosisMode | None = None
    agentic_review_enabled: bool | None = None


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    """Render the landing page from the active AgentPack and latest artifacts."""
    settings = load_dashboard_settings()
    release_config = ReleaseCheckConfig()
    pack = release_config.load_pack()
    demo_story = load_reference_demo_story(pack)
    reference_subdirs = pack.demo_reference_subdirs()
    latest_dir = settings.latest_artifact_dir
    latest = _latest_payload_or_none(latest_dir)
    latest_context = build_report_context(latest_dir) if latest else None

    blocked_dir = _resolve_artifact_dir(latest_dir.parent, reference_subdirs.get("blocked", ()))
    blocked_context = build_report_context(blocked_dir) if blocked_dir else None

    approved_dir = _resolve_artifact_dir(latest_dir.parent, reference_subdirs.get("approved", ()))
    approved_context = build_report_context(approved_dir) if approved_dir else None
    if (
        approved_context is None
        and latest
        and latest.get("decision") == "APPROVED"
        and latest_context
    ):
        approved_context = latest_context

    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "latest": latest,
            "landing_context": latest_context,
            "blocked_context": blocked_context,
            "approved_context": approved_context,
            "landing_story": build_landing_story(
                latest_context,
                blocked_context,
                approved_context,
                demo_story,
                pack,
            ),
            "settings": settings,
            "artifact_links": artifact_links(),
            "active_nav": "overview",
        },
    )


@router.get("/run", response_class=HTMLResponse)
def run_dashboard(request: Request) -> HTMLResponse:
    """Render the release-check runner page with AgentPack-owned defaults."""
    settings = load_dashboard_settings()
    release_config = ReleaseCheckConfig()
    pack = release_config.load_pack()
    latest = _latest_payload_or_none(settings.latest_artifact_dir)
    default_candidate_version = (
        str(latest.get("agent_version"))
        if latest and latest.get("agent_version")
        else settings.agent_version
    )
    return templates.TemplateResponse(
        request,
        "run.html",
        {
            "latest": latest,
            "last_completed_run": _last_completed_run(latest),
            "default_candidate_version": default_candidate_version,
            "settings": settings,
            "steps": _run_steps(settings.diagnosis_mode),
            "candidate_versions": settings.candidate_versions,
            "run_page_copy": pack.demo_run_page_copy(),
            "artifact_links": artifact_links(),
            "active_nav": "run",
        },
    )


@router.post("/api/agentgate/release-check")
def run_release_check(
    request_payload: ReleaseCheckRequest | None = None,
) -> JSONResponse:
    """Run a release check from the dashboard API and return UI-ready status."""
    settings = load_dashboard_settings()
    payload = request_payload or ReleaseCheckRequest()
    output_dir = payload.output_dir or settings.latest_artifact_dir
    diagnosis_mode = payload.diagnosis_mode or settings.diagnosis_mode

    controls_ref = Path(payload.release_controls_ref) if payload.release_controls_ref else None
    release_config = ReleaseCheckConfig(
        release_controls_ref=controls_ref,
        release_controls_resolution_source="api_request" if controls_ref else None,
    )
    resolved_agentic_review = (
        payload.agentic_review_enabled
        if payload.agentic_review_enabled is not None
        else payload.source == "phoenix"
    )
    try:
        if payload.source == "local":
            evidence = payload.evidence or settings.local_evidence_path
            result = release_check_module.run_release_check(
                evidence_path=evidence,
                output_dir=output_dir,
                diagnosis_mode=diagnosis_mode,
                release_config=release_config,
                agentic_review_enabled=resolved_agentic_review,
            )
        else:
            result = release_check_module.run_release_check_from_phoenix_mcp(
                output_dir=output_dir,
                project_identifier=payload.project_identifier or settings.project_identifier,
                agent_version=payload.agent_version or settings.agent_version,
                last_n_minutes=payload.last_n_minutes or settings.last_n_minutes,
                diagnosis_mode=diagnosis_mode,
                release_config=release_config,
                agentic_review_enabled=resolved_agentic_review,
            )
    except (PhoenixMCPError, ValueError, FileNotFoundError) as error:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": str(error),
                "source": payload.source,
                "default_source": "phoenix",
                "fallback_used": False,
            },
        )

    latest = build_latest_run_payload(output_dir)
    future_verification = future_verification_api_summary(result.get("future_verification"))
    return JSONResponse(
        {
            "status": "complete",
            "source": payload.source,
            "fallback_used": False,
            "future_verification": future_verification,
            "result": result,
            "latest": latest,
            "journey": _run_result_copy(latest),
        }
    )


@router.get("/api/agentgate/runs/latest")
def latest_run() -> dict[str, Any]:
    """Return the latest persisted release run payload for the dashboard."""
    settings = load_dashboard_settings()
    if not latest_artifacts_exist(settings.latest_artifact_dir):
        raise HTTPException(
            status_code=404,
            detail=f"No latest release artifacts found in {settings.latest_artifact_dir}. Run /api/agentgate/release-check first.",
        )
    return build_latest_run_payload(settings.latest_artifact_dir)


@router.get("/reports/latest", response_class=HTMLResponse)
def latest_report(request: Request) -> HTMLResponse:
    """Render the latest release report or a missing-report page."""
    settings = load_dashboard_settings()
    if not latest_artifacts_exist(settings.latest_artifact_dir):
        return templates.TemplateResponse(
            request,
            "missing_report.html",
            {"settings": settings, "active_nav": "report"},
            status_code=404,
        )
    context = build_report_context(settings.latest_artifact_dir)
    context["active_nav"] = "report"
    return templates.TemplateResponse(request, "release_report.html", context)


@router.get("/artifacts/{artifact_name}", response_model=None)
def artifact(artifact_name: str) -> Response:
    """Serve a whitelisted latest-run artifact from the dashboard."""
    if artifact_name == BUNDLE_ZIP_FILENAME:
        settings = load_dashboard_settings()
        if not latest_artifacts_exist(settings.latest_artifact_dir):
            raise HTTPException(status_code=404, detail="Release artifact bundle not found.")
        payload = build_artifact_bundle_zip(settings.latest_artifact_dir)
        return StreamingResponse(
            iter([payload]),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{BUNDLE_ZIP_FILENAME}"',
            },
        )
    if artifact_name not in SERVABLE_ARTIFACT_FILENAMES:
        raise HTTPException(status_code=404, detail="Unknown release artifact.")
    settings = load_dashboard_settings()
    path = settings.latest_artifact_dir / artifact_name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Release artifact not found: {artifact_name}")
    if artifact_name == HTML_ARTIFACT_FILENAME:
        return FileResponse(path, media_type="text/html", filename=artifact_name)
    return FileResponse(path, media_type="application/json", filename=artifact_name)


def _latest_payload_or_none(output_dir: Path) -> dict[str, Any] | None:
    """Return latest-run payload when all required artifacts exist."""
    if not latest_artifacts_exist(output_dir):
        return None
    return build_latest_run_payload(output_dir)


def _resolve_artifact_dir(parent: Path, names: tuple[str, ...]) -> Path | None:
    """Find the first artifact directory matching one configured candidate name."""
    for name in names:
        candidate = parent / name
        if latest_artifacts_exist(candidate):
            return candidate
    return None


def _run_steps(diagnosis_mode: DiagnosisMode) -> list[dict[str, str]]:
    """Return fixed UI steps for the release-check progress timeline."""
    _ = diagnosis_mode
    return [
        {"label": "Collect candidate evidence", "state": "ready"},
        {"label": "Apply AgentPack policy", "state": "ready"},
        {"label": "Evaluate blocker and warning controls", "state": "ready"},
        {"label": "Verify inherited release controls", "state": "ready"},
        {"label": "Generate future controls if blocked", "state": "ready"},
        {"label": "Write ship / no-ship decision", "state": "ready"},
        {"label": "Render audit report", "state": "ready"},
    ]


def _last_completed_run(latest: dict[str, Any] | None) -> dict[str, str] | None:
    """Return compact copy for the last completed run card."""
    if not latest:
        return None
    version = str(latest.get("agent_version") or "candidate")
    decision = str(latest.get("decision") or "UNKNOWN")
    report_url = str(latest.get("report_url") or "/reports/latest")
    if decision == "BLOCKED":
        decision_label = "No-ship (BLOCKED)"
    elif decision == "APPROVED":
        decision_label = "Ship (APPROVED)"
    else:
        decision_label = decision
    return {
        "agent_version": version,
        "decision": decision,
        "decision_label": decision_label,
        "report_url": report_url,
        "summary": _saved_run_summary(latest),
    }


def _saved_run_summary(latest: dict[str, Any] | None) -> str:
    """Return user-facing summary copy for a persisted run."""
    if not latest:
        return "No saved report yet."
    version = latest.get("agent_version", "candidate")
    decision = latest.get("decision", "UNKNOWN")
    warning_count = _warning_failure_count(latest)
    if decision == "BLOCKED":
        return (
            f"Latest saved decision: No-ship. {version} was BLOCKED and generated release controls "
            "for the next candidate."
        )
    if decision == "APPROVED" and warning_count:
        return (
            f"Latest saved decision: Ship with warnings. {version} was APPROVED with "
            f"{warning_count} non-blocking control warning(s)."
        )
    if decision == "APPROVED":
        return f"Latest saved decision: Ship. {version} was APPROVED with all blocker controls passing."
    return f"Latest saved decision: Review required. {version} returned {decision}."


def _run_result_copy(latest: dict[str, Any]) -> dict[str, str]:
    """Return user-facing completion copy for a just-finished run."""
    version = latest.get("agent_version", "candidate")
    decision = latest.get("decision", "UNKNOWN")
    report_url = str(latest.get("report_url") or "/reports/latest")
    warning_count = _warning_failure_count(latest)
    if decision == "BLOCKED":
        return {
            "label": "No-ship",
            "headline": f"No-ship decision written for {version}.",
            "summary": f"{version} is BLOCKED. The audit report now shows generated release controls.",
            "report_url": report_url,
        }
    if decision == "APPROVED" and warning_count:
        return {
            "label": "Ship with warnings",
            "headline": f"Ship decision written for {version}.",
            "summary": (
                f"{version} is APPROVED with {warning_count} non-blocking control warning(s). "
                "Opening the audit report to review the warning variance."
            ),
            "report_url": report_url,
        }
    if decision == "APPROVED":
        return {
            "label": "Ship",
            "headline": f"Ship decision written for {version}.",
            "summary": f"{version} is APPROVED. All blocker controls passed for this evidence window.",
            "report_url": report_url,
        }
    return {
        "label": "Review required",
        "headline": f"Decision written for {version}.",
        "summary": f"{version} returned {decision}. Review the audit report before acting.",
        "report_url": report_url,
    }


def _warning_failure_count(latest: dict[str, Any]) -> int:
    """Count non-blocking warning metrics that failed their thresholds."""
    metrics = latest.get("metrics")
    if not isinstance(metrics, list):
        return 0
    return sum(
        1
        for metric in metrics
        if isinstance(metric, dict)
        and metric.get("passes_threshold") is False
        and metric.get("decision_impact") != "blocker"
    )
