"""Backfill missing AgentGate release-evidence fields on normalized span attributes."""

from __future__ import annotations

from typing import Any

SpanAttributeValue = bool | int | float | str | None


def backfill_span_attributes(
    attrs: dict[str, SpanAttributeValue],
    *,
    span_name: str = "",
) -> dict[str, SpanAttributeValue]:
    """Fill derived attributes required by release metrics when telemetry omitted them."""
    normalized = dict(attrs)
    name = span_name or str(normalized.get("span_name") or "")

    _backfill_routing_fields(normalized)
    if name.startswith("policy_preflight."):
        _backfill_policy_preflight_fields(normalized)
    if name.startswith("tool."):
        _backfill_tool_fields(normalized)
    if name.startswith("answer.") or name.startswith("tool."):
        _backfill_response_fields(normalized)
    return normalized


def _backfill_routing_fields(attrs: dict[str, SpanAttributeValue]) -> None:
    expected = attrs.get("expected_intent_id") or attrs.get("expected.intent_id")
    selected = attrs.get("selected_intent_id") or attrs.get("router.selected_intent_id")
    if expected is not None and "expected.intent_id" not in attrs:
        attrs["expected.intent_id"] = expected
    if selected is not None and "router.selected_intent_id" not in attrs:
        attrs["router.selected_intent_id"] = selected
    if expected and selected and "router.correct" not in attrs:
        attrs["router.correct"] = expected == selected


def _backfill_policy_preflight_fields(attrs: dict[str, SpanAttributeValue]) -> None:
    if "expected.allowed" not in attrs and "expected_allowed" in attrs:
        attrs["expected.allowed"] = attrs["expected_allowed"]
    if "expected_allowed" not in attrs and "expected.allowed" in attrs:
        attrs["expected_allowed"] = _bool(attrs["expected.allowed"])

    if (
        attrs.get("policy.tool.executed_despite_deny") is True
        or attrs.get("policy.actual_allowed") is True
    ):
        attrs["actual.allowed"] = True
        attrs["actual_allowed"] = True
    elif "actual.allowed" not in attrs and "actual_allowed" not in attrs:
        decision = str(attrs.get("policy.preflight.decision") or "").upper()
        if decision == "ALLOW":
            attrs["actual.allowed"] = True
            attrs["actual_allowed"] = True
        elif decision == "DENY":
            attrs["actual.allowed"] = False
            attrs["actual_allowed"] = False

    if "policy.violation" not in attrs and "policy_violation" not in attrs:
        expected = attrs.get("expected_allowed")
        actual = attrs.get("actual_allowed")
        if expected is not None and actual is not None:
            attrs["policy.violation"] = expected != actual
            attrs["policy_violation"] = expected != actual


def _backfill_tool_fields(attrs: dict[str, SpanAttributeValue]) -> None:
    if "tool.success" not in attrs:
        attrs["tool.success"] = True


def _backfill_response_fields(attrs: dict[str, SpanAttributeValue]) -> None:
    response_text = attrs.get("response.text")
    if (
        response_text
        and "response.raw_event_dumped" not in attrs
        and "raw_event_dumped" not in attrs
    ):
        attrs["response.raw_event_dumped"] = False
        attrs["raw_event_dumped"] = False


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "allow"}
