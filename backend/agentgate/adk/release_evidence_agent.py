from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.agentgate.adk.tools import (
    compute_release_metrics,
    diagnose_dangerous_sessions,
    load_local_evidence_records,
    pull_dangerous_traces,
    query_phoenix_spans_tool as query_phoenix_spans,
    render_release_report,
    run_release_evidence_workflow,
)
from backend.agentgate.release.gemini_diagnoser import DiagnosisMode
from backend.agentgate.settings import configure_vertex_environment, get_adk_model_name

configure_vertex_environment()
_MODEL_NAME = get_adk_model_name()
RELEASE_EVIDENCE_AGENT_NAME = "agentgate_release_evidence_agent"
RELEASE_EVIDENCE_AGENT_INSTRUCTION = (
    "You orchestrate AgentGate release evidence workflows. "
    "Use the provided tools to query Phoenix evidence, compute deterministic metrics, "
    "diagnose only selected dangerous sessions, and write single candidate-version artifacts. "
    "Do not answer operational user questions or execute production Reference Ops AI tools."
)


def build_release_evidence_agent() -> Any | None:
    try:
        from google.adk.agents import Agent
        from google.adk.models import Gemini
        from google.genai import types
    except ImportError:
        return None

    return Agent(
        name=RELEASE_EVIDENCE_AGENT_NAME,
        model=Gemini(
            model=_MODEL_NAME,
            retry_options=types.HttpRetryOptions(attempts=3),
        ),
        instruction=RELEASE_EVIDENCE_AGENT_INSTRUCTION,
        tools=[
            query_phoenix_spans,
            pull_dangerous_traces,
            compute_release_metrics,
            diagnose_dangerous_sessions,
            render_release_report,
            run_release_evidence_workflow,
        ],
    )


def run_local_release_evidence_check(
    evidence_path: Path,
    output_dir: Path,
    diagnosis_mode: DiagnosisMode = "deterministic",
) -> dict[str, Any]:
    records = load_local_evidence_records(evidence_path)
    return run_release_evidence_workflow(
        records=records,
        output_dir=output_dir,
        evidence_source={"type": "local_jsonl", "path": str(evidence_path)},
        diagnosis_mode=diagnosis_mode,
    )
