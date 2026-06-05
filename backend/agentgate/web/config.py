import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.release.gemini_diagnoser import DiagnosisMode
from backend.agentgate.settings import get_adk_model_name

DEFAULT_LATEST_ARTIFACT_DIR = Path("artifacts/release/latest")


class DashboardSettings(BaseModel):
    latest_artifact_dir: Path = DEFAULT_LATEST_ARTIFACT_DIR
    project_identifier: str | None = None
    agent_version: str = "v1"
    candidate_versions: tuple[str, ...] = ("v1",)
    last_n_minutes: int = Field(default=24 * 60, ge=1)
    diagnosis_mode: DiagnosisMode = "gemini"
    diagnosis_model_name: str = "gemini-flash-latest"
    local_evidence_path: Path | None = None
    public_dashboard_url: str | None = None


def load_dashboard_settings() -> DashboardSettings:
    project_identifier = os.getenv("AGENTGATE_PHOENIX_PROJECT") or os.getenv("PHOENIX_PROJECT_NAME")
    release_config = ReleaseCheckConfig()
    pack = release_config.load_pack()
    demo_versions = pack.demo.get("candidate_versions", [])
    if isinstance(demo_versions, list) and demo_versions:
        candidate_versions = tuple(str(version) for version in demo_versions)
    else:
        candidate_versions = ("v1",)
    default_version = candidate_versions[0]
    seed_path = pack.seed_path(default_version)
    default_local_evidence = seed_path
    return DashboardSettings(
        latest_artifact_dir=Path(
            os.getenv("AGENTGATE_LATEST_ARTIFACT_DIR", str(DEFAULT_LATEST_ARTIFACT_DIR))
        ),
        project_identifier=project_identifier,
        agent_version=os.getenv("AGENTGATE_CANDIDATE_VERSION", default_version),
        candidate_versions=candidate_versions,
        last_n_minutes=int(os.getenv("AGENTGATE_PHOENIX_LOOKBACK_MINUTES", str(24 * 60))),
        diagnosis_mode=os.getenv("AGENTGATE_DIAGNOSIS_MODE", "gemini"),  # type: ignore[arg-type]
        diagnosis_model_name=get_adk_model_name(),
        local_evidence_path=(
            Path(os.getenv("AGENTGATE_LOCAL_EVIDENCE_PATH", str(default_local_evidence)))
            if default_local_evidence
            else None
        ),
        public_dashboard_url=os.getenv("AGENTGATE_PUBLIC_URL"),
    )


RunSource = Literal["phoenix", "local"]


try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
