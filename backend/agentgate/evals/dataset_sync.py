"""Sync AgentGate demo cases to a Phoenix evaluation dataset."""

from __future__ import annotations

from typing import Any

from backend.agentgate.demo.demo_cases import validate_demo_cases
from backend.agentgate.evals.phoenix_client_config import get_phoenix_project_name, load_phoenix_client
from backend.agentgate.settings import get_eval_dataset_name


def build_dataset_payload() -> dict[str, list[dict[str, Any]]]:
    cases = validate_demo_cases()
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for case in cases:
        inputs.append(
            {
                "input_text": case.input_text,
                "user_role": case.user_role,
                "case_id": case.case_id,
            }
        )
        outputs.append(
            {
                "expected_intent_id": case.expected_intent_id,
                "expected_allowed": case.expected_allowed,
                "expected_tool_name": case.expected_tool_name,
            }
        )
        metadata.append(
            {
                "agent_version": case.agent_version,
                "security_test_case": case.security_test_case,
                "attack_type": case.attack_type,
            }
        )
    return {"inputs": inputs, "outputs": outputs, "metadata": metadata}


def sync_release_eval_dataset(
    *,
    dataset_name: str | None = None,
    upsert: bool = False,
) -> dict[str, Any]:
    name = dataset_name or get_eval_dataset_name()
    payload = build_dataset_payload()
    client = load_phoenix_client()

    existing = None
    if upsert:
        for dataset in client.datasets.list():
            if dataset.get("name") == name:
                existing = dataset
                break

    if existing is not None:
        return {
            "action": "skipped_existing",
            "dataset_name": name,
            "dataset_id": existing.get("id"),
            "example_count": existing.get("example_count"),
        }

    dataset = client.datasets.create_dataset(
        name=name,
        dataset_description="AgentGate controlled release eval cases for Reference Ops AI.",
        inputs=payload["inputs"],
        outputs=payload["outputs"],
        metadata=payload["metadata"],
    )
    return {
        "action": "created",
        "dataset_name": name,
        "dataset_id": getattr(dataset, "id", None) or getattr(dataset, "name", name),
        "example_count": len(payload["inputs"]),
        "project_identifier": get_phoenix_project_name(),
    }
