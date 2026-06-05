from backend.agentgate.demo.demo_cases_loader import (
    load_demo_cases,
    validate_demo_cases,
)
from backend.agentgate.schemas import DemoCase

__all__ = ["get_demo_cases", "validate_demo_cases"]


def get_demo_cases(pack=None) -> list[DemoCase]:
    return load_demo_cases(pack)
