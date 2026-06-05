from unittest.mock import patch

from backend.agentgate.core.agent_pack import DEFAULT_AGENT_PACK_PATH, load_agent_pack
from backend.agentgate.evals.evaluator_registry import (
    EVAL_DEPENDENT_METRICS,
    SPAN_AGGREGATE_METRICS,
    build_eval_llm,
    build_llm_evaluators,
)


def test_eval_dependent_metrics_set() -> None:
    assert "hallucination_rate" in EVAL_DEPENDENT_METRICS
    assert "technical_tool_success_rate" in SPAN_AGGREGATE_METRICS


def test_build_eval_llm_uses_vertex_env() -> None:
    with patch("phoenix.evals.llm.LLM") as mock_llm:
        build_eval_llm()
    mock_llm.assert_called_once()
    assert mock_llm.call_args.kwargs["provider"] == "google"


def test_build_llm_evaluators_uses_agent_pack_classifier_specs() -> None:
    pack = load_agent_pack(DEFAULT_AGENT_PACK_PATH)
    created: dict[str, dict[str, object]] = {}

    def fake_create_classifier(**kwargs):
        created[str(kwargs["name"])] = kwargs
        return kwargs["name"]

    with (
        patch(
            "backend.agentgate.evals.evaluator_registry.build_eval_llm",
            return_value="llm",
        ),
        patch("phoenix.evals.metrics.FaithfulnessEvaluator", return_value="faithfulness"),
        patch("phoenix.evals.create_classifier", side_effect=fake_create_classifier),
    ):
        evaluators = build_llm_evaluators(pack=pack)

    assert evaluators["groundedness"] == "faithfulness"
    assert evaluators["response_format_ok"] == "response_format_ok"
    assert "RCA summary" in str(created["response_format_ok"]["prompt_template"])
    assert created["response_format_ok"]["choices"] == {
        "compliant": 1.0,
        "non_compliant": 0.0,
    }
