from backend.agentgate.core.config import load_demo_release_policy
from backend.agentgate.demo.span_event_schema import SpanEvent
from backend.agentgate.release.dangerous_evidence_classifier import (
    FINDING_TYPE_PRIORITY,
    classify_trace_findings,
    prioritize_trace_ids_for_pull,
)


def _preflight_span(*, expected: bool, actual: bool, tool: str = "deep_investigate_alert") -> SpanEvent:
    return SpanEvent(
        trace_id="trace_001",
        span_id="span_policy",
        parent_span_id=None,
        case_id="case_001",
        agent_id="stability_ops_ai",
        agent_version="v2",
        user_role="general_employee",
        span_name=f"policy_preflight.{tool}",
        event_type=f"policy_preflight.{tool}",
        status="blocked" if actual is False else "ok",
        input_text="investigate crash",
        attributes={
            "tool_name": tool,
            "expected_allowed": expected,
            "actual_allowed": actual,
        },
    )


def _router_span(*, intent_id: str = "ops.alert_deep_investigation") -> SpanEvent:
    return SpanEvent(
        trace_id="trace_001",
        span_id="span_router",
        parent_span_id=None,
        case_id="case_001",
        agent_id="stability_ops_ai",
        agent_version="v2",
        user_role="general_employee",
        span_name="router.intent_classification",
        event_type="router.intent_classification",
        status="ok",
        input_text="investigate crash",
        attributes={
            "selected_intent_id": intent_id,
            "expected_intent_id": intent_id,
        },
    )


def test_policy_dangerous_tools_drive_unauthorized_findings() -> None:
    policy = load_demo_release_policy()
    policy = policy.model_copy(update={"dangerous_tools": ["deep_investigate_alert"]})
    findings = classify_trace_findings(
        "trace_001",
        [_router_span(), _preflight_span(expected=False, actual=True)],
        policy,
    )

    assert any(finding["finding_type"] == "unauthorized_dangerous_tool_execution" for finding in findings)


def test_non_policy_tool_is_ignored_by_classifier() -> None:
    policy = load_demo_release_policy()
    policy = policy.model_copy(update={"dangerous_tools": ["deep_investigate_alert"]})
    findings = classify_trace_findings(
        "trace_001",
        [
            _router_span(intent_id="finance.ticker_news_summary"),
            _preflight_span(
                expected=False,
                actual=True,
                tool="analyze_public_ticker_news",
            ),
        ],
        policy,
    )

    assert findings == []


def test_prioritize_trace_ids_prefers_unauthorized_before_policy_violation() -> None:
    critical_findings = [
        {
            "trace_id": "trace_policy_only",
            "finding_type": "dangerous_tool_policy_violation",
        },
        {
            "trace_id": "trace_unauth",
            "finding_type": "unauthorized_dangerous_tool_execution",
        },
        {
            "trace_id": "trace_misroute",
            "finding_type": "dangerous_intent_misroute",
        },
    ]

    trace_ids = prioritize_trace_ids_for_pull(critical_findings, max_traces=2)

    assert trace_ids == ["trace_unauth", "trace_policy_only"]


def test_prioritize_trace_ids_uses_reviewed_safe_when_slots_remain() -> None:
    critical_findings = [
        {
            "trace_id": "trace_unauth",
            "finding_type": "unauthorized_dangerous_tool_execution",
        }
    ]
    reviewed_safe = [{"trace_id": "trace_safe_high_risk"}]

    trace_ids = prioritize_trace_ids_for_pull(
        critical_findings,
        reviewed_safe=reviewed_safe,
        max_traces=2,
        include_reviewed_safe=True,
    )

    assert trace_ids == ["trace_unauth", "trace_safe_high_risk"]


def test_prioritize_trace_ids_respects_priority_order() -> None:
    trace_ids = prioritize_trace_ids_for_pull(
        [
            {"trace_id": f"trace_{finding_type}", "finding_type": finding_type}
            for finding_type in reversed(FINDING_TYPE_PRIORITY)
        ],
        max_traces=len(FINDING_TYPE_PRIORITY),
    )

    assert trace_ids == [f"trace_{finding_type}" for finding_type in FINDING_TYPE_PRIORITY]
