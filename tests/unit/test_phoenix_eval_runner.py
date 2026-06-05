from backend.agentgate.evals.phoenix_eval_runner import (
    _evaluate_with_retry,
    _is_rate_limit_error,
)
from backend.agentgate.release.evidence_backfill import backfill_span_attributes


def test_backfill_policy_preflight_actual_allowed_from_deny() -> None:
    attrs = backfill_span_attributes(
        {"policy.preflight.decision": "DENY", "expected.allowed": False},
        span_name="policy_preflight.deep_investigate_alert",
    )
    assert attrs["actual.allowed"] is False
    assert attrs["actual_allowed"] is False


def test_is_rate_limit_error_detects_429() -> None:
    assert _is_rate_limit_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert not _is_rate_limit_error(RuntimeError("invalid json"))


def test_evaluate_with_retry_sleeps_on_429(monkeypatch) -> None:
    sleeps: list[float] = []

    class FlakyEvaluator:
        def __init__(self) -> None:
            self.calls = 0

        def evaluate(self, _payload: dict[str, str]) -> list[str]:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("429 RESOURCE_EXHAUSTED")
            return ["ok"]

    monkeypatch.setattr(
        "backend.agentgate.evals.phoenix_eval_runner.get_eval_llm_max_retries",
        lambda: 3,
    )
    monkeypatch.setattr(
        "backend.agentgate.evals.phoenix_eval_runner.get_eval_llm_retry_base_seconds",
        lambda: 0.01,
    )
    monkeypatch.setattr(
        "backend.agentgate.evals.phoenix_eval_runner.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = _evaluate_with_retry(FlakyEvaluator(), {"input": "x", "output": "y", "context": ""})
    assert result == ["ok"]
    assert sleeps == [0.01]
