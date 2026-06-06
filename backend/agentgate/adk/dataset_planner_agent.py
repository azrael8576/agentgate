from __future__ import annotations

from typing import Any

from backend.agentgate.settings import configure_vertex_environment, get_adk_model_name

configure_vertex_environment()
_MODEL_NAME = get_adk_model_name()
DATASET_PLANNER_AGENT_NAME = "agentgate_dataset_planner_agent"
DATASET_PLANNER_AGENT_INSTRUCTION = (
    "You are Dataset Planner for AgentGate release checks. "
    "Review shared trace evidence and propose human-reviewable dataset, annotation, "
    "or future-control planning candidates using only real trace IDs and evidence IDs. "
    "You do not approve or block releases. The deterministic release gate decides."
)


def build_dataset_planner_agent() -> Any | None:
    try:
        from google.adk.agents import Agent
        from google.adk.models import Gemini
        from google.genai import types
    except ImportError:
        return None

    return Agent(
        name=DATASET_PLANNER_AGENT_NAME,
        model=Gemini(
            model=_MODEL_NAME,
            retry_options=types.HttpRetryOptions(attempts=3),
        ),
        instruction=DATASET_PLANNER_AGENT_INSTRUCTION,
        tools=[],
    )
