"""Run Phoenix evaluators and write annotations back to Phoenix."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.agentgate.core.agent_pack import LoadedAgentPack
from backend.agentgate.core.product_config import ReleaseCheckConfig
from backend.agentgate.evals.annotation_parser import eval_labels_from_annotations
from backend.agentgate.evals.evaluator_registry import (
    ANNOTATION_TO_LABEL,
    build_llm_evaluators,
)
from backend.agentgate.evals.phoenix_client_config import (
    get_phoenix_project_name,
    load_phoenix_client,
)
from backend.agentgate.evals.span_eval_frame import build_eval_dataframe
from backend.agentgate.release.phoenix_evidence_source import (
    PhoenixEvidenceQuery,
    query_phoenix_spans,
)
from backend.agentgate.release.phoenix_mcp_client import (
    PhoenixMCPClient,
    load_phoenix_mcp_config,
)
from backend.agentgate.release.phoenix_normalizer import normalize_phoenix_spans
from backend.agentgate.settings import (
    get_eval_annotation_cooldown_seconds,
    get_eval_llm_cooldown_seconds,
    get_eval_llm_max_retries,
    get_eval_llm_retry_base_seconds,
)


def run_phoenix_eval_job(
    *,
    agent_version: str,
    project_identifier: str | None = None,
    last_n_minutes: int | None = 24 * 60,
    output_dir: Path | None = None,
    dry_run: bool = False,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    _emit(progress, f"Loading Phoenix config for agent_version={agent_version!r}...")
    config = load_phoenix_mcp_config(project_identifier=project_identifier)
    query = PhoenixEvidenceQuery(
        project_identifier=config.project_identifier,
        agent_version=agent_version,
        last_n_minutes=last_n_minutes,
    )
    _emit(
        progress,
        f"Querying Phoenix spans via MCP (project={query.project_identifier!r}, "
        f"lookback={last_n_minutes}m)...",
    )
    with PhoenixMCPClient(config) as client:
        spans_payload = query_phoenix_spans(query, client)
    matched_spans = len(spans_payload["spans"])
    fetch_stats = spans_payload.get("query", {}).get("fetch_stats", {})
    _emit(
        progress,
        f"Fetched {fetch_stats.get('raw_span_count', matched_spans)} raw spans, "
        f"{matched_spans} matched agent_version={agent_version!r}.",
    )
    records = normalize_phoenix_spans({"spans": spans_payload["spans"]})
    if not records:
        raise ValueError(
            f"No Phoenix spans found for agent_version={agent_version!r} "
            f"project={query.project_identifier!r}."
        )

    eval_df = build_eval_dataframe(records)
    if eval_df.empty:
        raise ValueError("No eval rows could be built from Phoenix spans.")

    _emit(
        progress,
        f"Running LLM evaluators on {len(eval_df)} traces (cooldown + retry enabled)...",
    )
    pack = ReleaseCheckConfig().load_pack()
    annotations = _run_evaluators(eval_df, pack=pack, progress=progress)
    error_count = sum(
        1 for item in annotations if str(item.get("result", {}).get("label")) == "error"
    )
    if not dry_run and annotations:
        _emit(
            progress,
            f"Writing {len(annotations)} annotations to Phoenix (one-by-one with cooldown)...",
        )
        _write_annotations_with_cooldown(annotations, progress=progress)
    elif dry_run:
        _emit(progress, "Dry run enabled; skipping Phoenix annotation write.")

    summary = {
        "agent_version": agent_version,
        "project_identifier": get_phoenix_project_name(query.project_identifier),
        "generated_at": datetime.now(UTC).isoformat(),
        "eval_rows": len(eval_df),
        "annotations_written": len(annotations),
        "annotation_errors": error_count,
        "dry_run": dry_run,
        "annotation_names": sorted({annotation["name"] for annotation in annotations}),
        "labels_preview": [
            label.model_dump(mode="json")
            for label in eval_labels_from_annotations(
                [
                    {
                        "name": annotation["name"],
                        "trace_id": _trace_id_for_span(eval_df, annotation["span_id"]),
                        "result": annotation["result"],
                        "annotator_kind": annotation.get("annotator_kind", "LLM"),
                        "metadata": annotation.get("metadata", {}),
                    }
                    for annotation in annotations
                ]
            )
        ],
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "eval_run_summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        summary["summary_path"] = str(summary_path)
    return summary


def _trace_id_for_span(eval_df: Any, span_id: str) -> str:
    matches = eval_df.loc[eval_df["span_id"] == span_id, "trace_id"]
    if matches.empty:
        return span_id
    return str(matches.iloc[0])


def _emit(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is not None:
        progress(message)


def _write_annotations_with_cooldown(
    annotations: list[dict[str, Any]],
    *,
    progress: Callable[[str], None] | None = None,
) -> None:
    phoenix_client = load_phoenix_client()
    cooldown = get_eval_annotation_cooldown_seconds()
    total = len(annotations)
    for index, annotation in enumerate(annotations, start=1):
        phoenix_client.spans.log_span_annotations(span_annotations=[annotation], sync=True)
        if index < total and cooldown > 0:
            _emit(
                progress,
                f"Wrote annotation {index}/{total}; cooling down {cooldown:.1f}s...",
            )
            time.sleep(cooldown)


def _run_evaluators(
    eval_df: Any,
    *,
    pack: LoadedAgentPack | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    llm_evaluators = build_llm_evaluators(pack=pack)
    annotations: list[dict[str, Any]] = []
    total_rows = len(eval_df)
    llm_cooldown = get_eval_llm_cooldown_seconds()

    for index, (_, row) in enumerate(eval_df.iterrows(), start=1):
        _emit(progress, f"Evaluating trace {index}/{total_rows}...")
        span_id = str(row["span_id"])
        trace_id = str(row["trace_id"])
        base = {
            "span_id": span_id,
            "annotator_kind": "LLM",
            "metadata": {
                "trace_id": trace_id,
                "case_id": row.get("case_id"),
                "agent_id": row.get("agent_id"),
                "agent_version": row.get("agent_version"),
            },
        }

        routing_correct = row.get("intent_routing_correct")
        if routing_correct is not None:
            annotations.append(
                {
                    **base,
                    "name": "intent_routing_correct",
                    "result": {
                        "label": "correct" if routing_correct else "incorrect",
                        "score": 1.0 if routing_correct else 0.0,
                    },
                }
            )

        payload = {
            "input": row.get("input") or "",
            "output": row.get("output") or "",
            "context": row.get("context") or "",
        }
        if not str(payload["output"]).strip():
            continue

        for annotation_name, evaluator in llm_evaluators.items():
            try:
                scores = _evaluate_with_retry(evaluator, payload, progress=progress)
            except Exception as exc:
                annotations.append(
                    {
                        **base,
                        "name": annotation_name,
                        "result": {
                            "label": "error",
                            "score": 0.0,
                            "explanation": str(exc),
                        },
                    }
                )
                if llm_cooldown > 0:
                    time.sleep(llm_cooldown)
                continue
            if not scores:
                if llm_cooldown > 0:
                    time.sleep(llm_cooldown)
                continue
            score = scores[0]
            label_name = ANNOTATION_TO_LABEL.get(annotation_name, annotation_name)
            normalized_label, normalized_score = _normalize_score(label_name, score)
            annotations.append(
                {
                    **base,
                    "name": annotation_name,
                    "result": {
                        "label": normalized_label,
                        "score": normalized_score,
                        "explanation": getattr(score, "explanation", None)
                        or str(getattr(score, "rationale", "")),
                    },
                }
            )
            if llm_cooldown > 0:
                time.sleep(llm_cooldown)

    return annotations


def _evaluate_with_retry(
    evaluator: Any,
    payload: dict[str, str],
    *,
    progress: Callable[[str], None] | None = None,
) -> Any:
    max_retries = get_eval_llm_max_retries()
    base_delay = get_eval_llm_retry_base_seconds()
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return evaluator.evaluate(payload)
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc) or attempt >= max_retries:
                raise
            delay = base_delay * attempt
            _emit(
                progress,
                f"Gemini 429/rate limit (attempt {attempt}/{max_retries}); cooling down {delay:.0f}s...",
            )
            time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Evaluator failed without raising an exception.")


def _is_rate_limit_error(error: Exception) -> bool:
    message = str(error).lower()
    return "429" in message or "resource_exhausted" in message or "rate limit" in message


def _normalize_score(label_name: str, score: Any) -> tuple[str, float]:
    raw_label = str(getattr(score, "label", "") or "").lower()
    raw_score = getattr(score, "score", None)
    numeric = float(raw_score) if isinstance(raw_score, int | float) else 0.0

    if label_name == "groundedness":
        if raw_label in {"unfaithful", "fail", "failed", "false"} or numeric <= 0.0:
            return "fail", numeric
        return "pass", numeric
    if label_name == "response_format_ok":
        if raw_label in {"non_compliant", "fail", "failed", "false"} or numeric <= 0.0:
            return "false", numeric
        return "true", numeric
    if label_name == "sensitive_output_ok":
        if raw_label in {"violation", "fail", "failed", "false"} or numeric <= 0.0:
            return "false", numeric
        return "true", numeric
    return raw_label or "unknown", numeric


async def run_phoenix_eval_job_async(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(run_phoenix_eval_job, **kwargs)
