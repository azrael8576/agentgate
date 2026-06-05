"""Phoenix REST client configuration for eval automation."""

from __future__ import annotations

import os
from typing import Any

from backend.agentgate.settings import load_local_env


def derive_phoenix_base_url(collector_endpoint: str) -> str:
    endpoint = collector_endpoint.strip().rstrip("/")
    if endpoint.endswith("/v1/traces"):
        return endpoint[: -len("/v1/traces")]
    return endpoint


def get_phoenix_base_url() -> str:
    load_local_env()
    base_url = os.getenv("PHOENIX_BASE_URL", "").strip()
    if base_url:
        return base_url.rstrip("/")
    collector = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").strip()
    if collector:
        return derive_phoenix_base_url(collector)
    return "http://localhost:6006"


def get_phoenix_api_key() -> str:
    load_local_env()
    return os.getenv("PHOENIX_API_KEY", "").strip()


def get_phoenix_project_name(project_identifier: str | None = None) -> str:
    load_local_env()
    return (
        project_identifier
        or os.getenv("PHOENIX_PROJECT_NAME")
        or os.getenv("PHOENIX_PROJECT")
        or "agentgate-reference-ops-demo"
    ).strip()


def load_phoenix_client() -> Any:
    from phoenix.client import Client

    api_key = get_phoenix_api_key()
    kwargs: dict[str, Any] = {"base_url": get_phoenix_base_url()}
    if api_key:
        kwargs["api_key"] = api_key
    return Client(**kwargs)
