from typing import Any

from pydantic import BaseModel, ConfigDict


class ReleasePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    policy_id: str
    policy_version: str
    agent_id: str
    dangerous_tools: list[str]
    decision_thresholds: dict[str, float]
    role_policy: dict[str, list[str]]
    dangerous_tool_policy: dict[str, bool]
    response_policy: dict[str, dict[str, Any]]
