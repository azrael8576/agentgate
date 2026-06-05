"""Resolve OpenTelemetry span/trace identifiers from Phoenix MCP payloads."""

from __future__ import annotations

import base64
from typing import Any


def resolve_otel_span_id(span: dict[str, Any]) -> str | None:
    """Return the OTEL span_id Phoenix REST expects, not the MCP base64 node id."""
    context = span.get("context")
    if isinstance(context, dict):
        for key in ("span_id", "spanId"):
            value = context.get(key)
            if value:
                return str(value)

    for key in ("span_id", "spanId"):
        value = span.get(key)
        if value:
            return str(value)

    raw_id = span.get("id")
    if raw_id and not is_phoenix_encoded_span_id(str(raw_id)):
        return str(raw_id)
    return None


def resolve_otel_trace_id(span: dict[str, Any]) -> str | None:
    context = span.get("context")
    if isinstance(context, dict):
        for key in ("trace_id", "traceId"):
            value = context.get(key)
            if value:
                return str(value)

    for key in ("trace_id", "traceId"):
        value = span.get(key)
        if value:
            return str(value)
    return None


def is_phoenix_encoded_span_id(value: str) -> bool:
    """Detect Phoenix MCP internal ids such as base64 ``Span:2747``."""
    if value.startswith("U3Bhb"):
        return True
    try:
        decoded = base64.b64decode(value + "==", validate=False).decode("utf-8", errors="ignore")
    except Exception:
        return False
    return decoded.startswith("Span:")
