from __future__ import annotations

from typing import Any

from backend.agentgate.settings import configure_vertex_environment, get_adk_model_name

configure_vertex_environment()
_MODEL_NAME = get_adk_model_name()
PATTERN_FINDER_AGENT_NAME = "agentgate_pattern_finder_agent"
PATTERN_FINDER_AGENT_INSTRUCTION = (
    "You are Pattern Finder for AgentGate release checks. "
    "Review shared trace evidence, identify release-safety failure patterns, "
    "and cite only real trace IDs and evidence IDs from the packet. "
    "You do not approve or block releases. The deterministic release gate decides."
)


def build_pattern_finder_agent() -> Any | None:
    try:
        from google.adk.agents import Agent
        from google.adk.models import Gemini
        from google.genai import types
    except ImportError:
        return None

    return Agent(
        name=PATTERN_FINDER_AGENT_NAME,
        model=Gemini(
            model=_MODEL_NAME,
            retry_options=types.HttpRetryOptions(attempts=3),
        ),
        instruction=PATTERN_FINDER_AGENT_INSTRUCTION,
        tools=[],
    )
