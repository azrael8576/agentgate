import json
from pathlib import Path

from backend.agentgate.core.agent_pack import (
    LoadedAgentPack,
    get_default_agent_pack,
)
from backend.agentgate.schemas import DemoCase


def demo_cases_path(pack: LoadedAgentPack) -> Path:
    configured = pack.demo.get("demo_cases")
    if isinstance(configured, str) and configured.strip():
        return pack.pack_dir / configured.strip()
    return pack.pack_dir / "demo_cases.json"


def load_demo_cases(pack: LoadedAgentPack | None = None) -> list[DemoCase]:
    resolved = pack or get_default_agent_pack()
    path = demo_cases_path(resolved)
    if not path.exists():
        raise FileNotFoundError(f"Demo cases file not found for pack {resolved.pack_dir}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases", [])
    if not isinstance(raw_cases, list):
        raise ValueError(f"demo_cases.json must contain a cases array: {path}")
    cases: list[DemoCase] = []
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        cases.append(
            DemoCase(
                case_id=str(item["case_id"]),
                agent_version=str(item.get("agent_version", "v2")),
                user_role=str(item["user_role"]),
                input_text=str(item["input_text"]),
                expected_intent_id=str(item["expected_intent_id"]),
                expected_allowed=bool(item["expected_allowed"]),
                expected_tool_name=item.get("expected_tool_name"),
                security_test_case=bool(item.get("security_test_case", False)),
                attack_type=item.get("attack_type"),
            )
        )
    return cases


def validate_demo_cases(pack: LoadedAgentPack | None = None) -> list[DemoCase]:
    cases = load_demo_cases(pack)
    case_ids = [case.case_id for case in cases]
    duplicate_ids = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicate_ids:
        duplicates = ", ".join(duplicate_ids)
        raise ValueError(f"Duplicate demo case ids: {duplicates}")
    return cases
