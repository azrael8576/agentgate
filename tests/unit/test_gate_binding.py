from backend.agentgate.core.config import load_demo_release_policy
from backend.agentgate.release.gate_binding import (
    resolve_release_gate_binding,
    validate_suite_required_metrics,
)


def test_release_gate_binding_resolves_pack_metric_bindings() -> None:
    gate_binding = {
        "gate_id": "custom_gate_v1",
        "blocking": True,
        "metric_bindings": [
            {
                "suite_metric": "suite_policy_mismatch",
                "runtime_metric": "dangerous_tool_policy_violation_rate",
            },
            {
                "suite_metric": "future_suite_score",
                "runtime_metric": None,
            },
        ],
        "required_metrics": ["suite_policy_mismatch", "future_suite_score"],
    }

    resolved = resolve_release_gate_binding(gate_binding)

    assert resolved is not None
    assert resolved["runtime_blocker_metrics"] == ["dangerous_tool_policy_violation_rate"]
    assert resolved["not_implemented_suite_metrics"] == ["future_suite_score"]
    assert resolved["suite_metrics"] == [
        {
            "suite_metric": "suite_policy_mismatch",
            "runtime_metric": "dangerous_tool_policy_violation_rate",
            "status": "mapped",
        },
        {
            "suite_metric": "future_suite_score",
            "runtime_metric": None,
            "status": "not_implemented",
        },
    ]


def test_gate_validation_uses_pack_metric_bindings() -> None:
    gate_binding = {
        "metric_bindings": [
            {
                "suite_metric": "suite_policy_mismatch",
                "runtime_metric": "dangerous_tool_policy_violation_rate",
            }
        ],
        "required_metrics": ["suite_policy_mismatch"],
    }

    validation = validate_suite_required_metrics(
        ["suite_policy_mismatch"],
        load_demo_release_policy(),
        gate_binding=gate_binding,
    )

    assert validation["contract_valid"] is True
    assert validation["checks"] == [
        {
            "suite_metric": "suite_policy_mismatch",
            "runtime_metric": "dangerous_tool_policy_violation_rate",
            "status": "mapped",
        }
    ]
