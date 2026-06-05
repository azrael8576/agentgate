"""Runtime settings and Vertex AI environment bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]

ADK_MODEL_ENV = "ADK_MODEL"
AGENTGATE_GEMINI_MODEL_ENV = "AGENTGATE_GEMINI_MODEL"
AGENTGATE_MAX_DANGEROUS_TRACES_ENV = "AGENTGATE_MAX_DANGEROUS_TRACES"
AGENTGATE_PULL_REVIEWED_SAFE_TRACES_ENV = "AGENTGATE_PULL_REVIEWED_SAFE_TRACES"
DEFAULT_ADK_MODEL = "gemini-flash-latest"
DEFAULT_MAX_DANGEROUS_TRACES = 25
DEFAULT_CANDIDATE_VERSIONS = ("v2", "v2.1")
DEFAULT_EVAL_LLM_MODEL = "gemini-flash-latest"
DEFAULT_EVAL_LLM_COOLDOWN_SECONDS = 2.0
DEFAULT_EVAL_LLM_MAX_RETRIES = 5
DEFAULT_EVAL_LLM_RETRY_BASE_SECONDS = 8.0
DEFAULT_EVAL_ANNOTATION_COOLDOWN_SECONDS = 1.0


def load_local_env() -> None:
    """Load local .env once; Cloud Run values still come from real env vars."""
    load_dotenv(ROOT_DIR / ".env")


def configure_vertex_environment() -> None:
    """Populate ADK/Vertex compatibility env vars without changing the model."""
    load_local_env()
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.getenv("VERTEX_PROJECT_ID", ""))
    if not os.getenv("GOOGLE_CLOUD_LOCATION"):
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", os.getenv("VERTEX_LOCATION", "global"))
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


def get_adk_model_name() -> str:
    load_local_env()
    return os.getenv(AGENTGATE_GEMINI_MODEL_ENV) or os.getenv(ADK_MODEL_ENV) or DEFAULT_ADK_MODEL


def get_max_dangerous_traces() -> int:
    load_local_env()
    raw = os.getenv(AGENTGATE_MAX_DANGEROUS_TRACES_ENV)
    if raw is None:
        return DEFAULT_MAX_DANGEROUS_TRACES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_DANGEROUS_TRACES
    return max(value, 0)


def get_pull_reviewed_safe_traces() -> bool:
    load_local_env()
    raw = os.getenv(AGENTGATE_PULL_REVIEWED_SAFE_TRACES_ENV, "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_eval_dataset_name() -> str:
    load_local_env()
    configured = os.getenv("AGENTGATE_EVAL_DATASET_NAME", "").strip()
    if configured:
        return configured
    from backend.agentgate.core.agent_pack import get_default_agent_pack

    return get_default_agent_pack().eval_dataset_name()


def get_eval_llm_model() -> str:
    load_local_env()
    return (
        os.getenv("AGENTGATE_EVAL_LLM_MODEL")
        or os.getenv(AGENTGATE_GEMINI_MODEL_ENV)
        or os.getenv(ADK_MODEL_ENV)
        or DEFAULT_EVAL_LLM_MODEL
    )


def _parse_candidate_versions(raw: str) -> tuple[str, ...]:
    """Parse comma-separated versions; tolerate gcloud ``^^`` comma escaping."""
    normalized = raw.replace("^^", ",")
    versions = tuple(part.strip() for part in normalized.split(",") if part.strip())
    return versions or DEFAULT_CANDIDATE_VERSIONS


def get_candidate_versions() -> tuple[str, ...]:
    load_local_env()
    raw = os.getenv("AGENTGATE_CANDIDATE_VERSIONS")
    if not raw:
        return DEFAULT_CANDIDATE_VERSIONS
    return _parse_candidate_versions(raw)


def eval_local_summary_fallback_enabled() -> bool:
    load_local_env()
    raw = os.getenv("AGENTGATE_EVAL_LOCAL_SUMMARY_FALLBACK", "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_eval_llm_cooldown_seconds() -> float:
    load_local_env()
    return _positive_float(
        os.getenv("AGENTGATE_EVAL_LLM_COOLDOWN_SECONDS"),
        DEFAULT_EVAL_LLM_COOLDOWN_SECONDS,
    )


def get_eval_llm_max_retries() -> int:
    load_local_env()
    raw = os.getenv("AGENTGATE_EVAL_LLM_MAX_RETRIES")
    if raw is None:
        return DEFAULT_EVAL_LLM_MAX_RETRIES
    try:
        return max(int(raw), 1)
    except ValueError:
        return DEFAULT_EVAL_LLM_MAX_RETRIES


def get_eval_llm_retry_base_seconds() -> float:
    load_local_env()
    return _positive_float(
        os.getenv("AGENTGATE_EVAL_LLM_RETRY_BASE_SECONDS"),
        DEFAULT_EVAL_LLM_RETRY_BASE_SECONDS,
    )


def get_eval_annotation_cooldown_seconds() -> float:
    load_local_env()
    return _positive_float(
        os.getenv("AGENTGATE_EVAL_ANNOTATION_COOLDOWN_SECONDS"),
        DEFAULT_EVAL_ANNOTATION_COOLDOWN_SECONDS,
    )


def _positive_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return default
