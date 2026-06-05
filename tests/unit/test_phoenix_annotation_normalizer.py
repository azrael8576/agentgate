from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.evals.annotation_parser import eval_labels_from_annotations
from backend.agentgate.evals.evaluator_registry import metric_source_for
from backend.agentgate.release.phoenix_normalizer import normalize_phoenix_spans


def test_eval_labels_from_phoenix_annotations() -> None:
    labels = eval_labels_from_annotations(
        [
            {
                "name": "groundedness",
                "trace_id": "trace_001",
                "span_id": "span_001",
                "annotator_kind": "LLM",
                "result": {
                    "label": "fail",
                    "score": 0.0,
                    "explanation": "unsupported RCA",
                },
            }
        ]
    )
    assert len(labels) == 1
    assert labels[0].label_name == "groundedness"
    assert labels[0].label_value == "fail"
    assert labels[0].evaluator == "phoenix_eval_automation"


def test_eval_labels_from_phoenix_rest_dataframe_shape() -> None:
    labels = eval_labels_from_annotations(
        [
            {
                "annotation_name": "groundedness",
                "annotator_kind": "LLM",
                "metadata": {
                    "trace_id": "trace_001",
                    "case_id": "case_001",
                    "agent_version": "v2",
                },
                "result.label": "fail",
                "result.score": 0.0,
                "result.explanation": "unsupported RCA",
            }
        ]
    )
    assert len(labels) == 1
    assert labels[0].label_name == "groundedness"
    assert labels[0].label_value == "fail"
    assert labels[0].trace_id == "trace_001"
    assert labels[0].case_id == "case_001"
    assert labels[0].agent_version == "v2"


def test_normalize_spans_with_embedded_annotations() -> None:
    records = normalize_phoenix_spans(
        {
            "spans": [
                {
                    "name": "router.intent_classification",
                    "trace_id": "trace_001",
                    "span_id": "span_router",
                    "attributes": {
                        "agent.id": "stability_ops_ai",
                        "agent.version": "v2",
                        "user.role": "developer",
                        "input.text": "hello",
                        "router.selected_intent_id": "app.general_intro",
                        "expected.intent_id": "app.general_intro",
                    },
                    "annotations": [
                        {
                            "name": "intent_routing_correct",
                            "result": {"label": "correct", "score": 1.0},
                        }
                    ],
                }
            ]
        }
    )
    labels = [record for record in records if isinstance(record, EvalLabel)]
    assert any(label.label_name == "intent_routing_correct" for label in labels)


def test_normalize_preflight_marks_actual_allowed_when_tool_executed_despite_deny() -> None:
    from backend.agentgate.demo.span_event_schema import SpanEvent

    records = normalize_phoenix_spans(
        {
            "spans": [
                {
                    "name": "policy_preflight.deep_investigate_alert",
                    "trace_id": "trace_unauth",
                    "span_id": "span_policy",
                    "attributes": {
                        "agent.id": "stability_ops_ai",
                        "agent.version": "v2",
                        "user.role": "ops_viewer",
                        "input.text": "deep investigate",
                        "test.case_id": "case_unauth_deep_001",
                        "expected.allowed": False,
                        "policy.preflight.decision": "DENY",
                        "policy.violation": True,
                        "policy.tool.executed_despite_deny": True,
                        "policy.actual_allowed": True,
                        "tool.name": "deep_investigate_alert",
                    },
                },
                {
                    "name": "tool.deep_investigate_alert",
                    "trace_id": "trace_unauth",
                    "span_id": "span_tool",
                    "parent_span_id": "span_policy",
                    "attributes": {
                        "agent.id": "stability_ops_ai",
                        "agent.version": "v2",
                        "user.role": "ops_viewer",
                        "input.text": "deep investigate",
                        "test.case_id": "case_unauth_deep_001",
                        "tool.name": "deep_investigate_alert",
                        "tool.success": True,
                    },
                },
            ]
        }
    )
    spans = [record for record in records if isinstance(record, SpanEvent)]
    preflight = next(span for span in spans if span.event_type.startswith("policy_preflight."))
    assert preflight.attributes["expected_allowed"] is False
    assert preflight.attributes["actual_allowed"] is True


def test_metric_source_for_seed_fallback() -> None:
    assert (
        metric_source_for(
            "hallucination_rate",
            evidence_source_type="local_jsonl",
            status="computed",
        )
        == "seed_fallback"
    )


def test_metric_source_for_phoenix_eval_automation() -> None:
    assert (
        metric_source_for(
            "hallucination_rate",
            evidence_source_type="phoenix_mcp",
            status="computed",
            label_evaluator="phoenix_eval_automation",
        )
        == "phoenix_eval_automation"
    )
