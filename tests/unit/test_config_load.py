from backend.agentgate.core.config import validate_demo_configs


def test_demo_configs_validate() -> None:
    agent_profile, intent_manifest, release_policy = validate_demo_configs()

    assert agent_profile.agent_id == "stability_ops_ai"
    assert intent_manifest.agent_id == "stability_ops_ai"
    assert release_policy.agent_id == "stability_ops_ai"


def test_dangerous_tools_include_reference_ops_tools() -> None:
    _, _, release_policy = validate_demo_configs()

    assert "summarize_incident_logs" in release_policy.dangerous_tools
    assert "deep_investigate_alert" in release_policy.dangerous_tools


def test_alert_deep_investigation_is_critical() -> None:
    _, intent_manifest, _ = validate_demo_configs()

    intent = next(
        item
        for item in intent_manifest.intents
        if item.intent_id == "ops.alert_deep_investigation"
    )
    assert intent.risk_level == "critical"


def test_general_employee_cannot_deep_investigate() -> None:
    _, _, release_policy = validate_demo_configs()

    assert (
        "ops.alert_deep_investigation"
        not in release_policy.role_policy["general_employee"]
    )
