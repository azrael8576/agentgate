"""Map AgentGate release metrics to Phoenix evaluators."""

from __future__ import annotations

from typing import Any

from backend.agentgate.core.agent_pack import LoadedAgentPack, get_default_agent_pack
from backend.agentgate.release.runtime_metric_catalog import (
    EVAL_DEPENDENT_METRICS,
    SPAN_AGGREGATE_METRICS,
    metric_source_for,
)

__all__ = [
    "ANNOTATION_TO_LABEL",
    "EVAL_DEPENDENT_METRICS",
    "SPAN_AGGREGATE_METRICS",
    "build_eval_llm",
    "build_llm_evaluators",
    "metric_source_for",
]

ANNOTATION_TO_LABEL = {
    "groundedness": "groundedness",
    "response_format_ok": "response_format_ok",
    "intent_routing_correct": "intent_routing_correct",
    "sensitive_output_ok": "sensitive_output_ok",
}


def build_eval_llm() -> Any:
    from phoenix.evals.llm import LLM

    from backend.agentgate.settings import (
        configure_vertex_environment,
        get_eval_llm_model,
    )

    configure_vertex_environment()
    return LLM(provider="google", model=get_eval_llm_model())


def build_llm_evaluators(pack: LoadedAgentPack | None = None) -> dict[str, Any]:
    from phoenix.evals import create_classifier
    from phoenix.evals.metrics import FaithfulnessEvaluator

    resolved_pack = pack or get_default_agent_pack()
    llm = build_eval_llm()
    evaluators: dict[str, Any] = {
        "groundedness": FaithfulnessEvaluator(llm=llm),
    }
    for spec in resolved_pack.llm_classifier_specs():
        evaluators[spec.name] = create_classifier(
            name=spec.name,
            prompt_template=spec.prompt_template,
            llm=llm,
            choices=spec.choices,
        )
    return evaluators
