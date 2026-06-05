import pandas as pd
from backend.agentgate.evals.annotation_loader import (
    _prepare_spans_dataframe_for_annotations,
)
from backend.agentgate.release.phoenix_normalizer import normalize_phoenix_spans
from backend.agentgate.release.phoenix_span_identity import resolve_otel_span_id


def test_resolve_otel_span_id_prefers_context_over_mcp_id() -> None:
    span = {
        "id": "U3BhbjoyNzQ3",
        "context": {"span_id": "4e2ce0984126fc48", "trace_id": "trace_001"},
    }
    assert resolve_otel_span_id(span) == "4e2ce0984126fc48"


def test_normalize_mcp_span_uses_context_span_id() -> None:
    records = normalize_phoenix_spans(
        {
            "spans": [
                {
                    "id": "U3BhbjoyNzQ3",
                    "name": "router.intent_classification",
                    "context": {
                        "trace_id": "trace_001",
                        "span_id": "4e2ce0984126fc48",
                    },
                    "attributes": {
                        "agent.id": "stability_ops_ai",
                        "agent.version": "v2",
                        "user.role": "developer",
                        "input.text": "hello",
                    },
                }
            ]
        }
    )
    span_records = [record for record in records if hasattr(record, "span_id")]
    assert len(span_records) == 1
    assert span_records[0].span_id == "4e2ce0984126fc48"
    assert span_records[0].trace_id == "trace_001"


def test_prepare_spans_dataframe_uses_context_span_id() -> None:
    spans_df = pd.DataFrame(
        [
            {
                "id": "U3BhbjoyNzQ3",
                "context": {"span_id": "4e2ce0984126fc48", "trace_id": "trace_001"},
            }
        ]
    )
    prepared = _prepare_spans_dataframe_for_annotations(spans_df)
    assert prepared["context.span_id"].tolist() == ["4e2ce0984126fc48"]
    assert prepared["context.trace_id"].tolist() == ["trace_001"]
