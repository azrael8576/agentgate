from backend.agentgate.core.agent_pack import get_default_agent_pack
from backend.agentgate.core.config import load_default_pack_release_policy
from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.evals.coverage_report import build_coverage_report
from backend.agentgate.release.evidence_loader import load_evidence_jsonl

from tests.fixtures.paths import DEMO_SEED_V2_PATH


def _coverage_report(records):
    pack = get_default_agent_pack()
    policy = load_default_pack_release_policy()
    return build_coverage_report(
        records,
        policy,
        evidence_source_type="local_jsonl",
        metric_graders=pack.metric_graders(),
        metric_decision_impact=pack.metric_decision_impact(),
        effective_metrics=pack.effective_metrics,
    )


def test_coverage_report_for_seed_evidence(tmp_path) -> None:
    evidence = tmp_path / "seed.jsonl"
    write_seed_evidence("v2", evidence)
    records = load_evidence_jsonl(evidence)
    report = _coverage_report(records)
    assert report["present_count"] > 0
    assert "metrics_summary" in report
    assert report["supporting_counts"]["eval_labels"] > 0


def test_coverage_report_accepts_flat_seed_span_aliases() -> None:
    records = load_evidence_jsonl(DEMO_SEED_V2_PATH)
    report = _coverage_report(records)

    assert report["ready_for_release_gate"] is True
    assert report["missing_count"] == 0
    assert report["missing_by_metric"] == {}
