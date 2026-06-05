from backend.agentgate.core.config import load_demo_release_policy
from backend.agentgate.demo.span_event_schema import SpanEvent
from backend.agentgate.release.dangerous_evidence_semantics import (
    is_dangerous_policy_violation,
    is_policy_violation_with_execution,
    is_sensitive_output_violation,
    is_unauthorized_dangerous_execution,
)


def _span(attributes: dict[str, object]) -> SpanEvent:
    return SpanEvent(
        trace_id="trace_001",
        span_id="span_001",
        parent_span_id=None,
        case_id="case_001",
        agent_id="stability_ops_ai",
        agent_version="v2",
        user_role="general_employee",
        span_name="policy_preflight.deep_investigate_alert",
        event_type="policy_preflight.deep_investigate_alert",
        status="ok",
        input_text="investigate crash",
        attributes=attributes,
    )


def test_preflight_semantics_classify_unauthorized_execution() -> None:
    preflight = _span({"expected_allowed": False, "actual_allowed": True})

    assert is_unauthorized_dangerous_execution(preflight)
    assert is_dangerous_policy_violation(preflight)


def test_preflight_semantics_classify_indeterminate_execution_conflict() -> None:
    preflight = _span(
        {
            "expected_allowed": False,
            "actual_allowed": False,
            "policy_violation": True,
        }
    )

    assert is_policy_violation_with_execution(preflight)


def test_sensitive_output_semantics_respect_policy_toggle() -> None:
    policy = load_demo_release_policy()
    tool_span = _span({"raw_event_dumped": True})

    assert is_sensitive_output_violation(tool_span, policy)

    relaxed_policy = policy.model_copy(update={"dangerous_tool_policy": {"forbid_raw_event_dump": False}})
    assert not is_sensitive_output_violation(tool_span, relaxed_policy)
