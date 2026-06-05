from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvalLabelValue = str | int | float | bool | None


class EvalLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    record_type: Literal["eval_label"] = "eval_label"
    trace_id: str
    case_id: str
    agent_id: str
    agent_version: str
    user_role: str
    evaluator: str
    label_name: str
    label_value: EvalLabelValue
    rationale: str
    metadata: dict[str, EvalLabelValue] = Field(default_factory=dict)
