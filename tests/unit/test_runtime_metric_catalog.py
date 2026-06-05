from backend.agentgate.core.agent_pack import get_default_agent_pack
from backend.agentgate.release.runtime_metric_catalog import RuntimeMetricCatalog


def test_runtime_metric_catalog_concentrates_metric_facts() -> None:
    catalog = RuntimeMetricCatalog(get_default_agent_pack().effective_metrics)

    assert catalog.is_implemented("unauthorized_dangerous_tool_attempt_rate")
    assert catalog.primary_eval_label("hallucination_rate") == "groundedness"
    assert "policy.preflight.decision" in catalog.required_span_attributes(
        "dangerous_tool_policy_violation_rate"
    )
    assert "response_format_ok" in catalog.required_eval_labels(
        "crash_analysis_format_compliance"
    )


def test_runtime_metric_catalog_requires_configured_aggregator_key() -> None:
    catalog = RuntimeMetricCatalog(())

    assert not catalog.is_implemented("hallucination_rate")
    assert catalog.primary_eval_label("hallucination_rate") == "groundedness"
