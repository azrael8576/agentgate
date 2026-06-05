import os
from typing import Any

import pytest

from backend.agentgate.settings import (
    configure_vertex_environment,
    get_adk_model_name,
    get_candidate_versions,
)


def test_configure_vertex_environment_maps_vertex_aliases(monkeypatch: Any) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setenv("VERTEX_PROJECT_ID", "agentgate-hackathon")
    monkeypatch.setenv("VERTEX_LOCATION", "global")

    configure_vertex_environment()

    assert os.environ["GOOGLE_CLOUD_PROJECT"] == "agentgate-hackathon"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"
    assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "True"


def test_configure_vertex_environment_defaults_location_to_global(monkeypatch: Any) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("VERTEX_PROJECT_ID", raising=False)
    monkeypatch.delenv("VERTEX_LOCATION", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "agentgate-hackathon")

    configure_vertex_environment()

    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_get_adk_model_name_prefers_agentgate_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("AGENTGATE_GEMINI_MODEL", "gemini-flash-latest")
    monkeypatch.setenv("ADK_MODEL", "other-model")

    assert get_adk_model_name() == "gemini-flash-latest"


def test_get_adk_model_name_falls_back_to_adk_model(monkeypatch: Any) -> None:
    monkeypatch.delenv("AGENTGATE_GEMINI_MODEL", raising=False)
    monkeypatch.setenv("ADK_MODEL", "gemini-flash-latest")

    assert get_adk_model_name() == "gemini-flash-latest"


def test_get_max_dangerous_traces_reads_env(monkeypatch: Any) -> None:
    from backend.agentgate.settings import get_max_dangerous_traces

    monkeypatch.setenv("AGENTGATE_MAX_DANGEROUS_TRACES", "100")
    assert get_max_dangerous_traces() == 100


def test_get_max_dangerous_traces_defaults_to_25(monkeypatch: Any, tmp_path: Any) -> None:
    from backend.agentgate import settings
    from backend.agentgate.settings import get_max_dangerous_traces

    monkeypatch.delenv("AGENTGATE_MAX_DANGEROUS_TRACES", raising=False)
    monkeypatch.setattr(settings, "ROOT_DIR", tmp_path)
    assert get_max_dangerous_traces() == 25


def test_get_adk_model_name_defaults_to_gemini_flash_latest(monkeypatch: Any) -> None:
    monkeypatch.delenv("AGENTGATE_GEMINI_MODEL", raising=False)
    monkeypatch.delenv("ADK_MODEL", raising=False)

    assert get_adk_model_name() == "gemini-flash-latest"


def test_get_candidate_versions_parses_gcloud_comma_escape(monkeypatch: Any) -> None:
    monkeypatch.setenv("AGENTGATE_CANDIDATE_VERSIONS", "v2^^v2.1")
    assert get_candidate_versions() == ("v2", "v2.1")


def test_get_candidate_versions_defaults_when_unset(monkeypatch: Any) -> None:
    monkeypatch.delenv("AGENTGATE_CANDIDATE_VERSIONS", raising=False)
    assert get_candidate_versions() == ("v2", "v2.1")
