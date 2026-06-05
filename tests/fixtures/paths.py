"""Canonical paths for DefaultDemoPack fixtures used across unit tests."""

from pathlib import Path

DEMO_AGENT_PACK_DIR = Path("configs/agents/stability_ops")
DEMO_SUITE_PATH = DEMO_AGENT_PACK_DIR / "suite.json"
DEMO_PROFILE_PATH = DEMO_AGENT_PACK_DIR / "profile.json"
DEMO_POLICY_PATH = DEMO_AGENT_PACK_DIR / "policy_custom.json"
DEMO_SEED_V2_PATH = DEMO_AGENT_PACK_DIR / "seed/v2_evidence.jsonl"
DEMO_SEED_V21_PATH = DEMO_AGENT_PACK_DIR / "seed/v21_evidence.jsonl"
