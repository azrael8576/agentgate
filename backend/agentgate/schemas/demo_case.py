from pydantic import BaseModel, ConfigDict


class DemoCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    case_id: str
    agent_version: str
    user_role: str
    input_text: str
    expected_intent_id: str
    expected_allowed: bool
    expected_tool_name: str | None
    security_test_case: bool = False
    attack_type: str | None = None
