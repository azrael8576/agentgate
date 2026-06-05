from backend.agentgate.core.agent_pack import get_default_agent_pack, load_agent_pack, validate_agent_pack
from backend.agentgate.schemas import AgentProfile, IntentManifest, ReleasePolicy


def load_default_pack_agent_profile() -> AgentProfile:
    return get_default_agent_pack().profile


def load_default_pack_intent_manifest() -> IntentManifest:
    pack = get_default_agent_pack()
    if pack.intents is None:
        raise FileNotFoundError("Default agent pack does not include an intent manifest.")
    return pack.intents


def load_default_pack_release_policy() -> ReleasePolicy:
    return get_default_agent_pack().release_policy


def validate_default_pack_configs() -> tuple[AgentProfile, IntentManifest, ReleasePolicy]:
    pack = validate_agent_pack()
    if pack.intents is None:
        raise FileNotFoundError("Default agent pack does not include an intent manifest.")
    return pack.profile, pack.intents, pack.release_policy


def load_agent_pack_demo_story() -> dict:
    return get_default_agent_pack().demo_story()


# Backward-compatible aliases for demo-era call sites.
load_demo_agent_profile = load_default_pack_agent_profile
load_demo_intent_manifest = load_default_pack_intent_manifest
load_demo_release_policy = load_default_pack_release_policy
validate_demo_configs = validate_default_pack_configs
