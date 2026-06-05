import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from backend.agentgate.demo.eval_label_schema import EvalLabel
from backend.agentgate.schemas.evidence import SpanEvent

EvidenceRecord = SpanEvent | EvalLabel


def load_evidence_jsonl(path: Path) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    with path.open("r", encoding="utf-8") as evidence_file:
        for line_number, line in enumerate(evidence_file, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            record_type = payload.get("record_type")
            if record_type == "span_event":
                records.append(SpanEvent.model_validate(payload))
            elif record_type == "eval_label":
                records.append(EvalLabel.model_validate(payload))
            else:
                raise ValueError(f"Unsupported evidence record_type at line {line_number}: {record_type}")
    return records


def group_records_by_trace(records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    grouped: dict[str, list[EvidenceRecord]] = defaultdict(list)
    for record in records:
        grouped[record.trace_id].append(record)
    return dict(grouped)


def evidence_identity(records: list[EvidenceRecord]) -> dict[str, Any]:
    if not records:
        raise ValueError("Evidence file contains no records.")

    agent_ids = {record.agent_id for record in records}
    agent_versions = {record.agent_version for record in records}
    if len(agent_ids) != 1:
        raise ValueError(f"Evidence file must contain one agent_id, got: {sorted(agent_ids)}")
    if len(agent_versions) != 1:
        raise ValueError(f"Evidence file must contain one agent_version, got: {sorted(agent_versions)}")

    return {
        "agent_id": next(iter(agent_ids)),
        "agent_version": next(iter(agent_versions)),
        "total_records": len(records),
        "trace_count": len({record.trace_id for record in records}),
    }

