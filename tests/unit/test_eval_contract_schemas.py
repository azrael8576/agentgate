import pytest
from pydantic import ValidationError

from tests.fixtures.paths import DEMO_PROFILE_PATH, DEMO_SUITE_PATH

from backend.agentgate.core.product_config import load_agent_profile, load_eval_suite
from backend.agentgate.schemas import AgentProfile, EvalSuite, MetricDefinition
from backend.agentgate.schemas.eval_contracts import ReleaseGateMetricStatus, decide_metric_statuses


def test_generic_agent_profile_validates_without_stability_ops_fields() -> None:
    profile = AgentProfile.model_validate(
        {
            "agent_id": "support_ops_agent",
            "agent_name": "Support Ops Agent",
            "domain": "customer_support",
            "owner": "support-platform",
            "integration_type": "phoenix_openinference",
            "trace_backend": {
                "provider": "phoenix",
                "project_name": "support-agent-evals",
            },
            "tool_manifest": [
                {
                    "tool_id": "lookup_order",
                    "risk_level": "medium",
                    "side_effect_type": "read_customer_data",
                }
            ],
            "risk_policy": {
                "policy_id": "support_policy_v1",
                "dangerous_tools": [],
            },
        }
    )

    assert profile.agent_id == "support_ops_agent"
    assert profile.display_name == "Support Ops Agent"


def test_stability_ops_reference_profile_and_suite_validate() -> None:
    profile = load_agent_profile(DEMO_PROFILE_PATH)
    suite = load_eval_suite(DEMO_SUITE_PATH)

    assert profile.agent_id == "stability_ops_ai"
    assert suite.agent_id == profile.agent_id
    assert suite.evaluation_mode == "controlled"
    assert suite.tasks


def test_eval_suite_requires_evaluation_mode() -> None:
    payload = load_eval_suite(DEMO_SUITE_PATH).model_dump()
    payload.pop("evaluation_mode")

    with pytest.raises(ValidationError):
        EvalSuite.model_validate(payload)


def test_llm_judge_requires_rubric_and_calibration_status() -> None:
    payload = load_eval_suite(DEMO_SUITE_PATH).model_dump()
    payload["tasks"][0]["graders"][2].pop("rubric_version")

    with pytest.raises(ValidationError):
        EvalSuite.model_validate(payload)


def test_blocker_metric_requires_provenance_denominator_and_grader_source() -> None:
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(
            {
                "metric_id": "unauthorized_dangerous_tool_execution_rate",
                "formula": "failures / total",
                "source_grader_ids": [],
                "denominator": "",
                "threshold": {"max": 0.0},
                "blocking_behavior": "block_release",
                "provenance": {
                    "evidence_backend": "phoenix",
                    "required_fields": ["trace_id", "tool.name"],
                },
                "evaluation_mode": "controlled",
                "sample_tier": "demo",
                "decision_impact": "blocker",
            }
        )


def test_controlled_blocker_not_available_blocks_release() -> None:
    decision = decide_metric_statuses(
        [
            ReleaseGateMetricStatus(
                metric_id="unauthorized_dangerous_tool_execution_rate",
                status="not_available",
                decision_impact="blocker",
                evaluation_mode="controlled",
                blocking_behavior="block_release",
            )
        ]
    )

    assert decision.decision == "BLOCKED"
    assert decision.blocking_reasons[0]["metric_id"] == "unauthorized_dangerous_tool_execution_rate"


def test_observed_blocker_like_not_available_is_warning_not_blocked() -> None:
    decision = decide_metric_statuses(
        [
            ReleaseGateMetricStatus(
                metric_id="observed_dangerous_tool_finding",
                status="not_available",
                decision_impact="blocker",
                evaluation_mode="observed",
                blocking_behavior="block_release",
            )
        ]
    )

    assert decision.decision == "WARNING"
    assert "controlled regression task" in decision.blocking_reasons[0]["reason"]
