import os
from dataclasses import dataclass

from phoenix.otel import register

REQUIRED_PHOENIX_ENV_VARS = (
    "PHOENIX_COLLECTOR_ENDPOINT",
    "PHOENIX_API_KEY",
    "PHOENIX_PROJECT_NAME",
)


class PhoenixConfigError(RuntimeError):
    """Raised when Phoenix tracing cannot be configured."""


@dataclass(frozen=True)
class PhoenixConfig:
    endpoint: str
    api_key: str
    project_name: str


def load_phoenix_config() -> PhoenixConfig:
    missing = [name for name in REQUIRED_PHOENIX_ENV_VARS if not os.getenv(name)]
    if missing:
        raise PhoenixConfigError(
            "Missing Phoenix environment variables: " + ", ".join(missing)
        )
    return PhoenixConfig(
        endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
        api_key=os.environ["PHOENIX_API_KEY"],
        project_name=os.environ["PHOENIX_PROJECT_NAME"],
    )


def register_phoenix_tracer(service_name: str):
    config = load_phoenix_config()
    tracer_provider = register(
        endpoint=config.endpoint,
        api_key=config.api_key,
        project_name=config.project_name,
        auto_instrument=True,
        batch=False,
        verbose=False,
    )
    return tracer_provider.get_tracer(service_name), config

