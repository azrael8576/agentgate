"""Shared span inspection helpers for release metrics and dangerous evidence."""

from __future__ import annotations

from backend.agentgate.schemas.evidence import SpanEvent
from backend.agentgate.schemas import ReleasePolicy


def dangerous_tool_ids(policy: ReleasePolicy | None = None) -> set[str]:
    if policy and policy.dangerous_tools:
        return set(policy.dangerous_tools)
    return set()


def tool_id_from_span(span: SpanEvent) -> str | None:
    if span.attributes.get("tool_name"):
        return str(span.attributes["tool_name"])
    if span.event_type.startswith("tool."):
        return span.event_type.removeprefix("tool.")
    if span.event_type.startswith("policy_preflight."):
        return span.event_type.removeprefix("policy_preflight.")
    return None


def tool_spans(spans: list[SpanEvent]) -> list[SpanEvent]:
    return [span for span in spans if span.event_type.startswith("tool.")]


def dangerous_preflight_spans(spans: list[SpanEvent], policy: ReleasePolicy) -> list[SpanEvent]:
    dangerous_tools = dangerous_tool_ids(policy)
    return [
        span
        for span in spans
        if span.event_type.startswith("policy_preflight.") and tool_id_from_span(span) in dangerous_tools
    ]


def dangerous_tool_spans(spans: list[SpanEvent], policy: ReleasePolicy) -> list[SpanEvent]:
    dangerous_tools = dangerous_tool_ids(policy)
    return [span for span in tool_spans(spans) if tool_id_from_span(span) in dangerous_tools]


def primary_span_event_types(policy: ReleasePolicy | None = None) -> tuple[str, ...]:
    """Priority-ordered event types for audit session primary span selection."""
    event_types: list[str] = []
    for tool_id in dangerous_tool_ids(policy):
        event_types.append(f"policy_preflight.{tool_id}")
    for tool_id in dangerous_tool_ids(policy):
        event_types.append(f"tool.{tool_id}")
    event_types.append("router.intent_classification")
    return tuple(event_types)
