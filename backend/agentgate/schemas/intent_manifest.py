from typing import Literal

from pydantic import BaseModel, ConfigDict


class IntentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    enabled: bool
    priority: int
    intent_id: str
    route_type: Literal["static_answer", "tool_call"]
    tool_name: str | None
    risk_level: Literal["low", "medium", "high", "critical"]
    description: str
    example_questions: list[str]


class IntentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent_id: str
    version: str
    intents: list[IntentDefinition]
