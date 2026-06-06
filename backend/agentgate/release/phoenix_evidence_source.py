from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from backend.agentgate.release.phoenix_mcp_client import (
    PhoenixMCPClient,
    PhoenixMCPConfig,
)
from backend.agentgate.release.phoenix_normalizer import resolve_supported_span_names
from backend.agentgate.settings import get_max_dangerous_traces


class PhoenixToolClient(Protocol):
    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


@dataclass(frozen=True)
class PhoenixEvidenceQuery:
    project_identifier: str
    agent_version: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    last_n_minutes: int | None = 24 * 60
    limit: int = 1000
    include_annotations: bool = True
    max_dangerous_traces: int | None = None

    @property
    def resolved_max_dangerous_traces(self) -> int:
        if self.max_dangerous_traces is not None:
            return self.max_dangerous_traces
        return get_max_dangerous_traces()


def query_phoenix_spans(
    query: PhoenixEvidenceQuery,
    client: PhoenixToolClient,
    *,
    supported_span_names: set[str] | None = None,
) -> dict[str, Any]:
    spans, fetch_stats = _get_all_spans(query, client, supported_span_names=supported_span_names)
    return {
        "spans": spans,
        "query": _query_metadata(query, fetch_stats),
    }


def pull_phoenix_traces(
    client: PhoenixToolClient,
    *,
    project_identifier: str,
    trace_ids: list[str],
    include_annotations: bool = True,
) -> list[dict[str, Any]]:
    return [
        _get_trace(
            client,
            project_identifier=project_identifier,
            trace_id=trace_id,
            include_annotations=include_annotations,
        )
        for trace_id in trace_ids
    ]


def pull_phoenix_traces_with_failures(
    client: PhoenixToolClient,
    *,
    project_identifier: str,
    trace_ids: list[str],
    include_annotations: bool = True,
) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    missing_trace_ids: list[str] = []
    failures: list[dict[str, str]] = []

    for trace_id in trace_ids:
        try:
            traces.append(
                _get_trace(
                    client,
                    project_identifier=project_identifier,
                    trace_id=trace_id,
                    include_annotations=include_annotations,
                )
            )
        except Exception as exc:
            missing_trace_ids.append(trace_id)
            failures.append(
                {
                    "trace_id": trace_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )

    return {
        "traces": traces,
        "status": "failed" if failures else "completed",
        "requested_trace_ids": list(trace_ids),
        "missing_trace_ids": missing_trace_ids,
        "failures": failures,
        "pulled_trace_count": len(traces),
    }


def _get_trace(
    client: PhoenixToolClient,
    *,
    project_identifier: str,
    trace_id: str,
    include_annotations: bool,
) -> dict[str, Any]:
    return client.call_tool(
        "get-trace",
        {
            "project_identifier": project_identifier,
            "trace_id": trace_id,
            "include_annotations": include_annotations,
        },
    )


def query_phoenix_evidence(
    query: PhoenixEvidenceQuery,
    client: PhoenixToolClient,
) -> dict[str, Any]:
    """Backward-compatible spans-only query. Dangerous trace pulls happen after session selection."""
    payload = query_phoenix_spans(query, client)
    return {
        **payload,
        "dangerous_traces": [],
        "dangerous_trace_ids": [],
    }


def query_phoenix_evidence_with_config(
    config: PhoenixMCPConfig,
    query: PhoenixEvidenceQuery,
) -> dict[str, Any]:
    with PhoenixMCPClient(config) as client:
        return query_phoenix_evidence(query, client)


def query_phoenix_spans_with_config(
    config: PhoenixMCPConfig,
    query: PhoenixEvidenceQuery,
) -> dict[str, Any]:
    with PhoenixMCPClient(config) as client:
        return query_phoenix_spans(query, client)


def _query_metadata(query: PhoenixEvidenceQuery, fetch_stats: dict[str, int]) -> dict[str, Any]:
    return {
        "project_identifier": query.project_identifier,
        "agent_version": query.agent_version,
        "start_time": _resolved_start_time(query),
        "end_time": query.end_time,
        "last_n_minutes": query.last_n_minutes,
        "limit": query.limit,
        "include_annotations": query.include_annotations,
        "max_dangerous_traces": query.resolved_max_dangerous_traces,
        "fetch_stats": fetch_stats,
    }


def _get_all_spans(
    query: PhoenixEvidenceQuery,
    client: PhoenixToolClient,
    *,
    supported_span_names: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    span_names = resolve_supported_span_names(supported_span_names)
    cursor: str | None = None
    spans: list[dict[str, Any]] = []
    raw_span_count = 0
    while True:
        arguments: dict[str, Any] = {
            "project_identifier": query.project_identifier,
            "names": sorted(span_names),
            "limit": min(query.limit, 1000),
            "include_annotations": query.include_annotations,
        }
        start_time = _resolved_start_time(query)
        if start_time:
            arguments["start_time"] = start_time
        if query.end_time:
            arguments["end_time"] = query.end_time
        if cursor:
            arguments["cursor"] = cursor

        payload = client.call_tool("get-spans", arguments)
        batch = _spans_from_payload(payload)
        raw_span_count += len(batch)
        if query.agent_version:
            batch = [
                span
                for span in batch
                if _attribute(span, "agent.version") == query.agent_version
                or _attribute(span, "agent_version") == query.agent_version
            ]
        spans.extend(batch)
        cursor = _next_cursor(payload)
        if not cursor:
            return spans, {
                "raw_span_count": raw_span_count,
                "matched_span_count": len(spans),
            }


def _resolved_start_time(query: PhoenixEvidenceQuery) -> str | None:
    if query.start_time:
        return query.start_time
    if query.last_n_minutes is None:
        return None
    start = datetime.now(UTC) - timedelta(minutes=query.last_n_minutes)
    return start.isoformat().replace("+00:00", "Z")


def _spans_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [span for span in payload if isinstance(span, dict)]
    if isinstance(payload, dict):
        for key in ("spans", "data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [span for span in value if isinstance(span, dict)]
    return []


def _next_cursor(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("nextCursor") or payload.get("next_cursor")
    return str(value) if value else None


def _attribute(span: dict[str, Any], key: str) -> Any:
    attrs = span.get("attributes")
    if isinstance(attrs, dict):
        return attrs.get(key)
    if isinstance(attrs, list):
        for item in attrs:
            if isinstance(item, dict) and item.get("key") == key:
                value = item.get("value")
                if isinstance(value, dict):
                    for value_key in (
                        "stringValue",
                        "intValue",
                        "doubleValue",
                        "boolValue",
                    ):
                        if value_key in value:
                            return value[value_key]
                    return value.get("value")
                return value
    return None
