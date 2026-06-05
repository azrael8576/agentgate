"""Load AgentPack: Phoenix base + per-agent custom config (flat merge)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.agentgate.schemas import (
    AgentProfile,
    EvalSuite,
    IntentManifest,
    ReleasePolicy,
)

DEFAULT_AGENT_PACK_PATH = Path("configs/agents/stability_ops")
DEFAULT_PHOENIX_BASE_PATH = Path("configs/phoenix")


def _version_artifact_dir_candidates(version: str) -> tuple[str, ...]:
    compact = version.replace(".", "")
    candidates = [
        version,
        compact,
        f"reference-{version}",
        f"demo-{version}",
        f"reference-{compact}",
        f"demo-{compact}",
    ]
    return tuple(dict.fromkeys(candidates))


@dataclass(frozen=True)
class RegressionGateCatalog:
    findings: dict[str, dict[str, str]]
    metrics: dict[str, dict[str, str]]
    metric_trace_filters: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class MetricDefinitionEntry:
    metric_id: str
    aggregator_key: str
    decision_impact: str
    source_grader_ids: list[str]


@dataclass(frozen=True)
class LLMClassifierSpec:
    name: str
    prompt_template: str
    choices: dict[str, float]


@dataclass(frozen=True)
class LoadedAgentPack:
    pack_dir: Path
    agent_id: str
    display_name: str
    is_default: bool
    profile: AgentProfile
    suite: EvalSuite
    release_policy: ReleasePolicy
    effective_metrics: tuple[MetricDefinitionEntry, ...]
    span_contract: dict[str, Any]
    report_config: dict[str, Any]
    evaluator_specs: dict[str, Any]
    intents: IntentManifest | None
    demo: dict[str, Any]
    phoenix_base_dir: Path = DEFAULT_PHOENIX_BASE_PATH

    @property
    def profile_path(self) -> Path:
        return self.pack_dir / "profile.json"

    @property
    def suite_path(self) -> Path:
        return self.pack_dir / "suite.json"

    @property
    def policy_path(self) -> Path:
        return self.pack_dir / "policy_custom.json"

    def metric_graders(self) -> dict[str, list[str]]:
        return {entry.metric_id: list(entry.source_grader_ids) for entry in self.effective_metrics}

    def metric_decision_impact(self) -> dict[str, str]:
        return {entry.metric_id: entry.decision_impact for entry in self.effective_metrics}

    def control_definitions(self) -> dict[str, dict[str, str]]:
        controls: dict[str, dict[str, str]] = {}
        for control in self.report_config.get("controls", []):
            if not isinstance(control, dict):
                continue
            metric_id = str(control.get("metric_id", ""))
            if not metric_id:
                continue
            controls[metric_id] = {
                "control_id": str(control.get("control_id", "")),
                "name": str(control.get("name", metric_id)),
                "definition": str(control.get("definition", "")),
                "formula": str(control.get("formula", "")),
            }
        return controls

    def demo_story(self) -> dict[str, Any]:
        demo = self.report_config.get("demo")
        return demo if isinstance(demo, dict) else {}

    def decision_copy(self) -> dict[str, str]:
        report = self.report_config.get("report")
        if not isinstance(report, dict):
            return {}
        decision_copy = report.get("decision_copy")
        if not isinstance(decision_copy, dict):
            return {}
        return {str(key): str(value) for key, value in decision_copy.items() if value is not None}

    def seed_path(self, candidate_version: str) -> Path | None:
        seed_map = self.demo.get("seed", {})
        if not isinstance(seed_map, dict):
            return None
        relative = seed_map.get(candidate_version)
        if not relative:
            return None
        return self.pack_dir / str(relative)

    def supported_span_names(self) -> set[str]:
        static_names = self.span_contract.get("static_span_names", [])
        names = {str(name) for name in static_names} if isinstance(static_names, list) else set()
        patterns = self.span_contract.get("tool_span_patterns", {})
        if not isinstance(patterns, dict):
            return names
        tool_ids = [entry.tool_id for entry in self.profile.tool_manifest]
        for pattern_key in ("policy_preflight", "tool"):
            pattern = patterns.get(pattern_key)
            if not isinstance(pattern, str):
                continue
            for tool_id in tool_ids:
                names.add(pattern.format(tool_id=tool_id))
        return names

    def dangerous_intent_ids(self) -> set[str]:
        configured = self.span_contract.get("dangerous_intent_ids", [])
        if isinstance(configured, list):
            return {str(intent_id) for intent_id in configured if str(intent_id).strip()}
        return set()

    def regression_gate_catalog(self) -> RegressionGateCatalog:
        configured = self.report_config.get("regression_gates", {})
        if not isinstance(configured, dict):
            return RegressionGateCatalog(findings={}, metrics={}, metric_trace_filters={})

        findings_raw = configured.get("findings", {})
        metrics_raw = configured.get("metrics", {})
        filters_raw = configured.get("metric_trace_filters", {})

        findings: dict[str, dict[str, str]] = {}
        if isinstance(findings_raw, dict):
            for finding_type, template in findings_raw.items():
                if isinstance(template, dict):
                    findings[str(finding_type)] = {
                        "gate_id": str(template.get("gate_id", "")),
                        "expected_behavior": str(template.get("expected_behavior", "")),
                        "required_fix": str(template.get("required_fix", "")),
                    }

        metrics: dict[str, dict[str, str]] = {}
        if isinstance(metrics_raw, dict):
            for metric_name, template in metrics_raw.items():
                if isinstance(template, dict):
                    metrics[str(metric_name)] = {
                        "gate_id": str(template.get("gate_id", "")),
                        "expected_behavior": str(template.get("expected_behavior", "")),
                        "required_fix": str(template.get("required_fix", "")),
                    }

        metric_trace_filters: dict[str, tuple[str, ...]] = {}
        if isinstance(filters_raw, dict):
            for metric_name, finding_types in filters_raw.items():
                if isinstance(finding_types, list):
                    metric_trace_filters[str(metric_name)] = tuple(
                        str(item) for item in finding_types
                    )

        return RegressionGateCatalog(
            findings=findings,
            metrics=metrics,
            metric_trace_filters=metric_trace_filters,
        )

    def llm_classifier_specs(self) -> tuple[LLMClassifierSpec, ...]:
        configured = self.evaluator_specs.get("llm_classifiers", [])
        if not isinstance(configured, list):
            return ()

        specs: list[LLMClassifierSpec] = []
        for item in configured:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            prompt_template = str(item.get("prompt_template", "")).strip()
            raw_choices = item.get("choices", {})
            if not name or not prompt_template or not isinstance(raw_choices, dict):
                continue
            choices: dict[str, float] = {}
            for label, score in raw_choices.items():
                if not isinstance(score, int | float):
                    continue
                choices[str(label)] = float(score)
            if choices:
                specs.append(
                    LLMClassifierSpec(
                        name=name,
                        prompt_template=prompt_template,
                        choices=choices,
                    )
                )
        return tuple(specs)

    def eval_dataset_name(self) -> str:
        configured = self.demo.get("eval_dataset_name")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        return f"{self.agent_id}_release_eval_v1"

    def load_gate_binding(self) -> dict[str, Any] | None:
        gate_binding = self.suite.release_gate_binding
        return gate_binding if isinstance(gate_binding, dict) else None

    def demo_reference_subdirs(self) -> dict[str, tuple[str, ...]]:
        demo = self.demo
        configured = demo.get("reference_subdirs")
        if isinstance(configured, dict):
            blocked = configured.get("blocked")
            approved = configured.get("approved")
            result: dict[str, tuple[str, ...]] = {}
            if isinstance(blocked, list):
                result["blocked"] = tuple(str(name) for name in blocked)
            if isinstance(approved, list):
                result["approved"] = tuple(str(name) for name in approved)
            if result:
                return {
                    "blocked": result.get("blocked", ()),
                    "approved": result.get("approved", ()),
                }

        versions = demo.get("candidate_versions", [])
        if isinstance(versions, list) and len(versions) >= 2:
            return {
                "blocked": _version_artifact_dir_candidates(str(versions[0])),
                "approved": _version_artifact_dir_candidates(str(versions[1])),
            }
        return {"blocked": (), "approved": ()}

    def landing_policy_highlights(self) -> list[dict[str, str]]:
        demo = self.report_config.get("demo", {})
        if not isinstance(demo, dict):
            return []
        highlights = demo.get("policy_highlights")
        if isinstance(highlights, list):
            normalized: list[dict[str, str]] = []
            for item in highlights:
                if not isinstance(item, dict):
                    continue
                metric_id = str(item.get("metric_id", "")).strip()
                if not metric_id:
                    continue
                normalized.append(
                    {
                        "metric_id": metric_id,
                        "threshold_label": str(item.get("threshold_label", "Gate threshold")),
                    }
                )
            if normalized:
                return normalized

        controls = self.control_definitions()
        fallback: list[dict[str, str]] = []
        for entry in self.effective_metrics:
            if entry.decision_impact != "blocker":
                continue
            control = controls.get(entry.metric_id, {})
            fallback.append(
                {
                    "metric_id": entry.metric_id,
                    "threshold_label": control.get("name", entry.metric_id),
                }
            )
        return fallback[:3]


def resolve_agent_pack_path(pack_path: Path | str | None = None) -> Path:
    if pack_path is not None:
        return Path(pack_path)
    env_path = os.getenv("AGENTGATE_AGENT_PACK", "").strip()
    if env_path:
        return Path(env_path)
    return DEFAULT_AGENT_PACK_PATH


def find_agent_pack_dir_by_agent_id(
    agent_id: str,
    *,
    agents_root: Path | None = None,
) -> Path | None:
    normalized = agent_id.strip()
    if not normalized:
        return None
    root = agents_root or Path("configs/agents")
    if not root.is_dir():
        return None
    for pack_dir in sorted(root.iterdir()):
        if not pack_dir.is_dir() or pack_dir.name.startswith("_"):
            continue
        manifest_path = pack_dir / "pack.yaml"
        if not manifest_path.exists():
            continue
        manifest = _load_yaml(manifest_path)
        manifest_agent_id = str(manifest.get("agent_id", "")).strip()
        if manifest_agent_id == normalized:
            return pack_dir
    return None


def resolve_agent_pack_for_artifacts(
    output_dir: Path,
    *,
    fallback: Path | None = None,
) -> LoadedAgentPack:
    for filename in ("release_decision.json", "agent_profile.json"):
        artifact_path = output_dir / filename
        if not artifact_path.exists():
            continue
        payload = _load_json(artifact_path)
        agent_id = str(payload.get("agent_id", "")).strip()
        if not agent_id:
            continue
        pack_dir = find_agent_pack_dir_by_agent_id(agent_id)
        if pack_dir is not None:
            return load_agent_pack(pack_dir)
    if fallback is not None:
        return load_agent_pack(fallback)
    return load_agent_pack(None)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"AgentPack manifest must be a mapping: {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _merge_policy(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in custom.items():
        if key == "decision_thresholds" and isinstance(value, dict):
            thresholds = dict(merged.get("decision_thresholds", {}))
            thresholds.update(value)
            merged["decision_thresholds"] = thresholds
        else:
            merged[key] = value
    return merged


def _parse_metric_entries(payload: dict[str, Any]) -> tuple[MetricDefinitionEntry, ...]:
    metrics = payload.get("metrics", [])
    if not isinstance(metrics, list):
        return ()
    entries: list[MetricDefinitionEntry] = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        metric_id = str(item.get("metric_id", "")).strip()
        if not metric_id:
            continue
        entries.append(
            MetricDefinitionEntry(
                metric_id=metric_id,
                aggregator_key=str(item.get("aggregator_key", "")),
                decision_impact=str(item.get("decision_impact", "informational")),
                source_grader_ids=[str(g) for g in item.get("source_grader_ids", [])],
            )
        )
    return tuple(entries)


def load_phoenix_base(
    phoenix_base_dir: Path | None = None,
) -> tuple[tuple[MetricDefinitionEntry, ...], dict[str, Any]]:
    base_dir = phoenix_base_dir or DEFAULT_PHOENIX_BASE_PATH
    metrics_payload = _load_json(base_dir / "metrics.json")
    policy_payload = _load_json(base_dir / "policy.json")
    return _parse_metric_entries(metrics_payload), policy_payload


def load_agent_pack(pack_path: Path | str | None = None) -> LoadedAgentPack:
    pack_dir = resolve_agent_pack_path(pack_path)
    manifest_path = pack_dir / "pack.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"AgentPack manifest not found: {manifest_path}")

    manifest = _load_yaml(manifest_path)
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        raise ValueError(f"AgentPack files section must be a mapping: {manifest_path}")

    phoenix_relative = manifest.get("phoenix_base", "../../phoenix")
    phoenix_base_dir = (pack_dir / str(phoenix_relative)).resolve()

    phoenix_metrics, phoenix_policy = load_phoenix_base(phoenix_base_dir)
    custom_metrics = _parse_metric_entries(_load_json(pack_dir / str(files["metrics_custom"])))
    custom_policy = _load_json(pack_dir / str(files["policy_custom"]))

    effective_metrics_map: dict[str, MetricDefinitionEntry] = {
        entry.metric_id: entry for entry in phoenix_metrics
    }
    for entry in custom_metrics:
        effective_metrics_map[entry.metric_id] = entry
    effective_metrics = tuple(effective_metrics_map.values())

    effective_policy_payload = _merge_policy(phoenix_policy, custom_policy)
    release_policy = ReleasePolicy.model_validate(effective_policy_payload)

    profile = AgentProfile.model_validate(_load_json(pack_dir / str(files["profile"])))
    suite = EvalSuite.model_validate(_load_json(pack_dir / str(files["suite"])))
    span_contract = _load_json(pack_dir / str(files["span_contract"]))
    report_config = _load_json(pack_dir / str(files["report"]))
    evaluator_specs = _load_json(pack_dir / str(files["evals"])) if "evals" in files else {}

    intents: IntentManifest | None = None
    if "intents" in files:
        intents_path = pack_dir / str(files["intents"])
        if intents_path.exists():
            intents = IntentManifest.model_validate(_load_json(intents_path))

    manifest_agent_id = str(manifest.get("agent_id", profile.agent_id))
    if manifest_agent_id != profile.agent_id:
        raise ValueError(
            f"AgentPack agent_id mismatch: manifest={manifest_agent_id} profile={profile.agent_id}"
        )
    if suite.agent_id != profile.agent_id:
        raise ValueError(
            f"EvalSuite agent_id mismatch: suite={suite.agent_id} profile={profile.agent_id}"
        )
    if release_policy.agent_id != profile.agent_id:
        raise ValueError(
            f"Policy agent_id mismatch: policy={release_policy.agent_id} profile={profile.agent_id}"
        )

    demo = manifest.get("demo", {})
    if not isinstance(demo, dict):
        demo = {}

    return LoadedAgentPack(
        pack_dir=pack_dir,
        agent_id=profile.agent_id,
        display_name=str(manifest.get("display_name", profile.display_name or profile.agent_name)),
        is_default=bool(manifest.get("is_default", False)),
        profile=profile,
        suite=suite,
        release_policy=release_policy,
        effective_metrics=effective_metrics,
        span_contract=span_contract,
        report_config=report_config,
        evaluator_specs=evaluator_specs,
        intents=intents,
        demo=demo,
        phoenix_base_dir=phoenix_base_dir,
    )


@lru_cache(maxsize=4)
def get_default_agent_pack() -> LoadedAgentPack:
    return load_agent_pack(None)


def validate_agent_pack(pack_path: Path | str | None = None) -> LoadedAgentPack:
    return load_agent_pack(pack_path)
