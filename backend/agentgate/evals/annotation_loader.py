"""Load Phoenix span annotations as AgentGate eval labels."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.evals.annotation_parser import eval_labels_from_annotations, eval_labels_from_span_payloads
from backend.agentgate.evals.phoenix_client_config import load_phoenix_client
from backend.agentgate.release.phoenix_span_identity import resolve_otel_span_id, resolve_otel_trace_id
from backend.agentgate.settings import eval_local_summary_fallback_enabled

logger = logging.getLogger(__name__)

_ANNOTATION_SPAN_ID_COLUMNS = ("context.span_id", "span_id", "spanId", "id")
_ANNOTATION_TRACE_ID_COLUMNS = ("context.trace_id", "trace_id", "traceId")


def load_eval_labels_from_phoenix(
    query: Any,
    spans: list[dict[str, Any]],
    client: Any | None = None,
) -> list[EvalLabel]:
    labels = eval_labels_from_span_payloads(spans)
    if labels:
        return labels

    if client is None:
        client = load_phoenix_client()

    try:
        import pandas as pd

        spans_df = _prepare_spans_dataframe_for_annotations(pd.DataFrame(spans))
        if spans_df.empty or "context.span_id" not in spans_df.columns:
            return _load_eval_labels_from_local_summary(query)
        annotations_df = client.spans.get_span_annotations_dataframe(
            spans_dataframe=spans_df,
            project_identifier=query.project_identifier,
        )
        if annotations_df is None or annotations_df.empty:
            return _load_eval_labels_from_local_summary(query)
        labels = eval_labels_from_annotations(_annotations_df_to_records(annotations_df))
        if labels:
            return labels
    except KeyError:
        logger.info(
            "Phoenix span annotations REST lookup skipped; using local eval summary fallback."
        )
    except Exception as exc:
        if exc.__class__.__name__ == "HTTPStatusError":
            logger.info(
                "Phoenix span annotations REST lookup returned %s; using local eval summary fallback.",
                getattr(getattr(exc, "response", None), "status_code", "error"),
            )
        else:
            logger.warning(
                "Phoenix span annotations REST lookup failed; using local eval summary fallback.",
                exc_info=True,
            )

    return _load_eval_labels_from_local_summary(query)


def _prepare_spans_dataframe_for_annotations(spans_df: Any) -> Any:
    if spans_df.empty:
        return spans_df

    df = spans_df.copy()
    if "context" in df.columns:
        if "context.span_id" not in df.columns:
            df["context.span_id"] = df["context"].map(
                lambda value: resolve_otel_span_id({"context": value}) if isinstance(value, dict) else None
            )
        if "context.trace_id" not in df.columns:
            df["context.trace_id"] = df["context"].map(
                lambda value: resolve_otel_trace_id({"context": value}) if isinstance(value, dict) else None
            )

    if "context.span_id" not in df.columns:
        for column in _ANNOTATION_SPAN_ID_COLUMNS[1:]:
            if column in df.columns:
                df["context.span_id"] = df[column]
                break
    if "context.trace_id" not in df.columns:
        for column in _ANNOTATION_TRACE_ID_COLUMNS[1:]:
            if column in df.columns:
                df["context.trace_id"] = df[column]
                break
    return df


def _load_eval_labels_from_local_summary(query: Any) -> list[EvalLabel]:
    if not eval_local_summary_fallback_enabled():
        return []

    agent_version = str(getattr(query, "agent_version", "") or "").strip()
    if not agent_version:
        return []

    summary_path = Path("artifacts/eval") / agent_version / "eval_run_summary.json"
    if not summary_path.is_file():
        return []

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read local eval summary: %s", summary_path)
        return []

    labels: list[EvalLabel] = []
    for item in payload.get("labels_preview") or []:
        if not isinstance(item, dict) or item.get("record_type") != "eval_label":
            continue
        try:
            label = EvalLabel.model_validate(item)
            if label.agent_version in {"", "unknown"}:
                label = label.model_copy(update={"agent_version": agent_version})
            labels.append(label)
        except Exception:
            logger.warning("Skip invalid eval label row in %s", summary_path)
    if labels:
        logger.info(
            "Loaded %s eval labels from local summary fallback: %s",
            len(labels),
            summary_path,
        )
    return labels


def _annotations_df_to_records(annotations_df: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in annotations_df.to_dict(orient="records")]
