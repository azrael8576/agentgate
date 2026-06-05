from backend.agentgate.demo.demo_cases import get_demo_cases, validate_demo_cases


def test_demo_cases_count_is_at_least_15() -> None:
    assert len(get_demo_cases()) >= 15


def test_demo_cases_case_ids_are_unique() -> None:
    cases = validate_demo_cases()
    case_ids = [case.case_id for case in cases]

    assert len(case_ids) == len(set(case_ids))
