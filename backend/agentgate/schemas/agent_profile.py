from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TraceBackend(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    provider: Literal["phoenix"]
    project_name: str


class ToolManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    tool_id: str
    risk_level: Literal["low", "medium", "high", "critical"]
    side_effect_type: str | None = None


class RiskPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    policy_id: str
    dangerous_tools: list[str] = Field(default_factory=list)


class AgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent_id: str
    owner: str
    agent_name: str
    domain: str
    integration_type: Literal["phoenix_openinference"]
    trace_backend: TraceBackend
    tool_manifest: list[ToolManifestEntry] = Field(default_factory=list)
    risk_policy: RiskPolicy
    description: str = ""
    display_name: str | None = None
    current_runtime: str | None = None
    demo_scope: str | None = None
    risk_summary: str | None = None

    @model_validator(mode="after")
    def fill_display_name(self) -> "AgentProfile":
        if self.display_name is None:
            self.display_name = self.agent_name
        return self
