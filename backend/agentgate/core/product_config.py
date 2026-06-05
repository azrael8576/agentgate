import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.agentgate.core.agent_pack import (
    DEFAULT_AGENT_PACK_PATH,
    LoadedAgentPack,
    load_agent_pack,
    resolve_agent_pack_path,
)
from backend.agentgate.schemas import AgentProfile, EvalSuite, ReleasePolicy

ModelT = TypeVar("ModelT", bound=BaseModel)

# Deprecated paths — kept for backward-compatible CLI flags.
DEFAULT_RELEASE_POLICY_PATH = DEFAULT_AGENT_PACK_PATH / "policy_custom.json"
DEFAULT_EVAL_SUITE_PATH = DEFAULT_AGENT_PACK_PATH / "suite.json"
DEFAULT_AGENT_PROFILE_PATH = DEFAULT_AGENT_PACK_PATH / "profile.json"


def load_json_model(path: Path, model: type[ModelT]) -> ModelT:
    with path.open("r", encoding="utf-8") as config_file:
        payload = json.load(config_file)
    return model.model_validate(payload)


def load_agent_profile(path: Path) -> AgentProfile:
    return load_json_model(path, AgentProfile)


def load_eval_suite(path: Path) -> EvalSuite:
    return load_json_model(path, EvalSuite)


def load_release_policy(path: Path) -> ReleasePolicy:
    return load_json_model(path, ReleasePolicy)


@dataclass(frozen=True)
class ReleaseCheckConfig:
    agent_pack_path: Path = field(default_factory=resolve_agent_pack_path)
    policy_path: Path | None = None
    suite_path: Path | None = None
    profile_path: Path | None = None
    release_controls_ref: Path | None = None
    release_controls_resolution_source: str | None = None

    def load_pack(self) -> LoadedAgentPack:
        return load_agent_pack(self.agent_pack_path)

    def load_policy(self) -> ReleasePolicy:
        if self.policy_path is not None:
            return load_release_policy(self.policy_path)
        return self.load_pack().release_policy

    def load_suite(self) -> EvalSuite:
        if self.suite_path is not None:
            return load_eval_suite(self.suite_path)
        return self.load_pack().suite

    def load_profile(self) -> AgentProfile:
        if self.profile_path is not None:
            return load_agent_profile(self.profile_path)
        return self.load_pack().profile

    @property
    def resolved_profile_path(self) -> Path:
        return self.profile_path or (self.agent_pack_path / "profile.json")

    @property
    def resolved_suite_path(self) -> Path:
        return self.suite_path or (self.agent_pack_path / "suite.json")

    def load_gate_binding(self, agent_id: str) -> dict[str, Any] | None:
        suite = self.load_suite()
        if suite.agent_id != agent_id:
            return None
        gate_binding = suite.release_gate_binding
        return gate_binding if isinstance(gate_binding, dict) else None


def load_gate_binding_from_suite(suite_path: Path, agent_id: str) -> dict[str, Any] | None:
    if not suite_path.exists():
        return None
    suite_payload = json.loads(suite_path.read_text(encoding="utf-8"))
    if suite_payload.get("agent_id") != agent_id:
        return None
    gate_binding = suite_payload.get("release_gate_binding")
    return gate_binding if isinstance(gate_binding, dict) else None
