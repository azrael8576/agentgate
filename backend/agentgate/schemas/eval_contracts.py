from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EvaluationMode = Literal["controlled", "observed"]
SampleTier = Literal["demo", "directional", "release_candidate", "gold"]
Lifecycle = Literal["capability", "regression"]
DecisionImpact = Literal["blocker", "warning", "informational"]
RiskLevel = Literal["low", "medium", "high", "critical"]
GraderType = Literal["deterministic", "state", "sequence", "llm_judge", "human"]


class GraderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    grader_id: str
    grader_type: GraderType
    rubric_version: str | None = None
    calibration_status: Literal["not_required", "not_calibrated", "calibrated"] = "not_required"

    @model_validator(mode="after")
    def require_llm_governance(self) -> "GraderSpec":
        if self.grader_type == "llm_judge":
            if not self.rubric_version:
                raise ValueError("llm_judge graders require rubric_version")
            if self.calibration_status == "not_required":
                raise ValueError("llm_judge graders require calibration_status")
        return self


class EvalTask(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str
    suite_id: str
    user_goal: str
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    expected_outcome: dict[str, Any]
    graders: list[GraderSpec]
    priority: Literal["p0", "p1", "p2", "p3"]
    lifecycle: Lifecycle = "capability"
    tags: list[str] = Field(default_factory=list)


class EvalSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    suite_id: str
    agent_id: str
    purpose: str
    risk_level: RiskLevel
    evaluation_mode: EvaluationMode
    sample_tier: SampleTier
    tags: list[str] = Field(default_factory=list)
    tasks: list[EvalTask]
    release_gate_binding: dict[str, Any]


class TranscriptEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal[
        "user_message",
        "assistant_message",
        "tool_call",
        "tool_result",
        "policy_preflight",
        "retrieval",
        "error",
        "side_effect",
        "final_answer",
    ]
    evidence_id: str | None = None
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Transcript(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    trial_id: str
    trace_id: str
    events: list[TranscriptEvent]
    side_effects: dict[str, Any] = Field(default_factory=dict)
    final_answer: str | None = None


class GraderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    grader_id: str
    grader_type: GraderType
    label: str
    score: float
    passed: bool
    reason: str
    evidence_ids: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Trial(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    trial_id: str
    task_id: str
    agent_version: str
    model: str
    prompt_version: str
    tool_version: str
    status: Literal["completed", "failed", "error", "not_available"]
    transcript_ref: str
    cost: dict[str, float] = Field(default_factory=dict)
    latency: dict[str, float] = Field(default_factory=dict)
    grader_results: list[GraderResult] = Field(default_factory=list)


class MetricProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_backend: Literal["phoenix", "local_jsonl"]
    evidence_query: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)


class MetricThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def require_single_bound(self) -> "MetricThreshold":
        if (self.min is None) == (self.max is None):
            raise ValueError("metric threshold requires exactly one of min or max")
        return self


class MetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    metric_id: str
    formula: str
    source_grader_ids: list[str]
    denominator: str
    threshold: MetricThreshold
    blocking_behavior: Literal["block_release", "warn", "informational"]
    provenance: MetricProvenance
    evaluation_mode: EvaluationMode
    sample_tier: SampleTier
    decision_impact: DecisionImpact
    unavailable_reason: str | None = None

    @model_validator(mode="after")
    def require_blocker_provenance(self) -> "MetricDefinition":
        if self.decision_impact == "blocker":
            if not self.denominator:
                raise ValueError("blocker metrics require denominator")
            if not self.source_grader_ids:
                raise ValueError("blocker metrics require source_grader_ids")
            if not (self.provenance.evidence_query or self.provenance.evidence_ids):
                raise ValueError("blocker metrics require evidence_query or evidence_ids")
        return self


class ReleaseGateMetricStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    metric_id: str
    status: Literal["computed", "not_available"]
    decision_impact: DecisionImpact
    evaluation_mode: EvaluationMode
    blocking_behavior: Literal["block_release", "warn", "informational"]


class ReleaseGate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    gate_id: str
    agent_id: str
    required_metrics: list[str]
    p0_blockers: list[str] = Field(default_factory=list)


class ReleaseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent_id: str
    candidate_version: str
    decision: Literal["APPROVED", "WARNING", "BLOCKED"]
    blocking_reasons: list[dict[str, Any]] = Field(default_factory=list)
    metric_summary: list[dict[str, Any]] = Field(default_factory=list)
    critical_findings: list[dict[str, Any]] = Field(default_factory=list)
    regression_gates: list[dict[str, Any]] = Field(default_factory=list)
    artifact_refs: dict[str, str] = Field(default_factory=dict)


class ExperimentRun(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    experiment_id: str
    baseline_version: str
    candidate_version: str
    dataset: str
    evaluators: list[str]
    results: dict[str, Any]
    regressions: list[dict[str, Any]] = Field(default_factory=list)
    improvements: list[dict[str, Any]] = Field(default_factory=list)


def decide_metric_statuses(
    metric_statuses: list[ReleaseGateMetricStatus],
) -> ReleaseDecision:
    blocking_reasons: list[dict[str, Any]] = []
    warning_reasons: list[dict[str, Any]] = []
    for metric in metric_statuses:
        if (
            metric.status == "not_available"
            and metric.evaluation_mode == "controlled"
            and metric.decision_impact == "blocker"
            and metric.blocking_behavior == "block_release"
        ):
            blocking_reasons.append(
                {
                    "metric_id": metric.metric_id,
                    "reason": "Required controlled blocker metric is not available.",
                }
            )
        elif (
            metric.status == "not_available"
            and metric.evaluation_mode == "observed"
            and metric.decision_impact == "blocker"
        ):
            warning_reasons.append(
                {
                    "metric_id": metric.metric_id,
                    "reason": "Observed blocker-like finding requires a controlled regression task.",
                }
            )
    decision = "BLOCKED" if blocking_reasons else "WARNING" if warning_reasons else "APPROVED"
    return ReleaseDecision(
        agent_id="contract_check",
        candidate_version="contract_check",
        decision=decision,
        blocking_reasons=blocking_reasons or warning_reasons,
    )
