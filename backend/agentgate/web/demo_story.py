from typing import Any

from backend.agentgate.core.agent_pack import LoadedAgentPack, get_default_agent_pack


def load_reference_demo_story(pack: LoadedAgentPack | None = None) -> dict[str, Any]:
    resolved = pack or get_default_agent_pack()
    payload = resolved.demo_story()
    if not payload:
        return {}
    return dict(payload)
