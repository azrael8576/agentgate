from backend.agentgate.web.demo_story import load_reference_demo_story
from backend.agentgate.web.landing_presenter import blocked_cards_from_findings, primary_blocker_label


def test_reference_demo_story_loads_config() -> None:
    story = load_reference_demo_story()
    assert story["section_title"] == "Reference workflow"
    assert story["max_blocked_cards"] >= 1
    assert "default" in story["blocked_card_titles"]


def test_blocked_cards_from_findings_are_dynamic() -> None:
    findings = [
        {
            "finding_type": "dangerous_tool_policy_violation",
            "user_role": "ops_viewer",
            "tool_name": "example_tool",
            "trace_id": "trace-1",
            "routing_summary": "expected → selected",
        },
        {
            "finding_type": "dangerous_tool_policy_violation",
            "user_role": "ops_viewer",
            "tool_name": "example_tool",
            "trace_id": "trace-1",
        },
    ]
    story = load_reference_demo_story()
    context = {
        "why_blocked": {
            "blocking_drivers": [
                {
                    "metric_name": "dangerous_tool_policy_violation_rate",
                    "control_id": "AG-RG-005",
                    "display_name": "Dangerous tool policy violations",
                }
            ]
        }
    }
    cards = blocked_cards_from_findings(findings, story, context)

    assert len(cards) == 1
    assert cards[0]["gate_id"] == "AG-RG-005"
    assert "ops_viewer" in cards[0]["summary"]
    assert cards[0]["title"] == "Policy deny bypass on dangerous tool"


def test_primary_blocker_prefers_blocking_driver_on_latest_blocked() -> None:
    latest_context = {
        "release_decision": {"decision": "BLOCKED"},
        "why_blocked": {
            "blocking_drivers": [
                {"control_id": "AG-RG-004", "display_name": "Unauthorized dangerous tool attempts"}
            ]
        },
    }
    label = primary_blocker_label(latest_context, [])
    assert label == "AG-RG-004 · Unauthorized dangerous tool attempts"
