from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SpanAttributeValue = str | int | float | bool | None


class SpanEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    record_type: Literal["span_event"] = "span_event"
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    case_id: str
    agent_id: str
    agent_version: str
    user_role: str
    span_name: str
    event_type: str
    status: Literal["ok", "blocked", "error"]
    input_text: str
    attributes: dict[str, SpanAttributeValue] = Field(default_factory=dict)
