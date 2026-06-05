"""Parse Phoenix span annotations into AgentGate eval labels."""

from __future__ import annotations

from typing import Any

from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.evals.evaluator_registry import ANNOTATION_TO_LABEL


def eval_labels_from_annotations(annotations: list[dict[str, Any]]) -> list[EvalLabel]:
    labels: list[EvalLabel] = []
    seen: set[tuple[str, str]] = set()
    for annotation in annotations:
        label = _annotation_to_eval_label(_normalize_annotation_record(annotation))
        if label is None:
            continue
        key = (label.trace_id, label.label_name)
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def eval_labels_from_span_payloads(spans: list[dict[str, Any]]) -> list[EvalLabel]:
    labels: list[EvalLabel] = []
    for span in spans:
        trace_id = span.get("trace_id") or span.get("traceId")
        raw_annotations = span.get("annotations") or span.get("span_annotations") or []
        if not isinstance(raw_annotations, list):
            continue
        enriched: list[dict[str, Any]] = []
        for annotation in raw_annotations:
            if not isinstance(annotation, dict):
                continue
            item = dict(annotation)
            if trace_id and not item.get("trace_id"):
                item["trace_id"] = trace_id
            enriched.append(item)
        labels.extend(eval_labels_from_annotations(enriched))
    return labels


def _normalize_annotation_record(annotation: dict[str, Any]) -> dict[str, Any]:
    item = dict(annotation)
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in ("trace_id", "case_id", "agent_version", "agent_id", "user_role"):
            if not item.get(key) and metadata.get(key) is not None:
                item[key] = metadata[key]

    if "result.label" in item or "result.score" in item or "result.explanation" in item:
        item["result"] = {
            "label": item.get("result.label"),
            "score": item.get("result.score"),
            "explanation": item.get("result.explanation"),
        }

    if item.get("annotation_name") and not item.get("name"):
        item["name"] = item["annotation_name"]
    return item


def _annotation_to_eval_label(annotation: dict[str, Any]) -> EvalLabel | None:
    name = str(
        annotation.get("annotation_name")
        or annotation.get("name")
        or annotation.get("label")
        or ""
    ).strip()
    if not name:
        return None
    label_name = ANNOTATION_TO_LABEL.get(name, name)
    result = annotation.get("result")
    if isinstance(result, dict):
        label_value = result.get("label", result.get("score"))
        rationale = str(result.get("explanation") or result.get("rationale") or "")
    else:
        label_value = annotation.get("label") or annotation.get("score")
        rationale = str(annotation.get("explanation") or annotation.get("rationale") or "")

    trace_id = str(
        annotation.get("trace_id")
        or annotation.get("context.trace_id")
        or annotation.get("traceId")
        or ""
    )
    span_id = str(annotation.get("span_id") or annotation.get("spanId") or "")
    if not trace_id:
        return None

    return EvalLabel(
        trace_id=trace_id,
        case_id=str(annotation.get("case_id") or annotation.get("metadata.case_id") or trace_id),
        agent_id=str(annotation.get("agent_id") or "unknown"),
        agent_version=str(annotation.get("agent_version") or "unknown"),
        user_role=str(annotation.get("user_role") or "unknown"),
        evaluator="phoenix_eval_automation",
        label_name=label_name,
        label_value=label_value if label_value is not None else "",
        rationale=rationale or f"Phoenix annotation {name}.",
        metadata={
            "judge_type": str(annotation.get("annotator_kind") or "llm_as_judge"),
            "human_labeled": annotation.get("annotator_kind") == "HUMAN",
            "span_id": span_id,
            "annotation_name": name,
        },
    )
