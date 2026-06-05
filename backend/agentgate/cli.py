from pathlib import Path
import json

import typer

from backend.agentgate.core.config import validate_demo_configs
from backend.agentgate.core.agent_pack import (
    DEFAULT_AGENT_PACK_PATH,
    get_default_agent_pack,
    validate_agent_pack,
)
from backend.agentgate.core.product_config import (
    DEFAULT_AGENT_PROFILE_PATH,
    DEFAULT_EVAL_SUITE_PATH,
    DEFAULT_RELEASE_POLICY_PATH,
    ReleaseCheckConfig,
    load_agent_profile,
    load_eval_suite,
    load_json_model,
)
from backend.agentgate.settings import configure_vertex_environment

configure_vertex_environment()
from backend.agentgate.demo.demo_cases import validate_demo_cases
from backend.agentgate.demo.trace_seed_generator import write_seed_evidence
from backend.agentgate.evals.coverage_report import build_coverage_report
from backend.agentgate.evals.dataset_sync import sync_release_eval_dataset
from backend.agentgate.evals.phoenix_eval_runner import run_phoenix_eval_job
from backend.agentgate.release.evidence_loader import load_evidence_jsonl
from backend.agentgate.release.gate_binding import validate_suite_required_metrics
from backend.agentgate.release.release_check import (
    run_release_check,
    run_release_check_from_phoenix_mcp,
    run_release_check_from_phoenix_spans,
)
from backend.agentgate.release.gemini_diagnoser import DiagnosisMode
from backend.agentgate.release.phoenix_mcp_client import PhoenixMCPError
from backend.agentgate.telemetry.phoenix_setup import PhoenixConfigError
from backend.agentgate.telemetry.replay import replay_evidence_to_phoenix
from backend.agentgate.schemas import ReleasePolicy

app = typer.Typer(help="AgentGate release evidence agent CLI.")
configs_app = typer.Typer(help="Validate and inspect AgentGate configs.")
profiles_app = typer.Typer(help="Validate AgentGate agent profiles.")
suites_app = typer.Typer(help="Validate AgentGate eval suites.")
gate_app = typer.Typer(help="Run thin AgentGate release authority contract checks.")
demo_app = typer.Typer(help="Generate seeded production-agent evidence for demos.")
demo_cases_app = typer.Typer(help="Validate replayable demo cases.")
release_app = typer.Typer(help="Run AgentGate release checks from local evidence.")
eval_app = typer.Typer(help="Phoenix eval automation for production release metrics.")
telemetry_app = typer.Typer(help="Replay seeded evidence into Phoenix telemetry.")
app.add_typer(configs_app, name="configs")
app.add_typer(profiles_app, name="profiles")
app.add_typer(suites_app, name="suites")
app.add_typer(gate_app, name="gate")
app.add_typer(demo_app, name="demo")
demo_app.add_typer(demo_cases_app, name="cases")
app.add_typer(release_app, name="release")
app.add_typer(eval_app, name="eval")
app.add_typer(telemetry_app, name="telemetry")


@configs_app.command("validate")
def validate_configs(
    agent_pack: Path = typer.Option(
        DEFAULT_AGENT_PACK_PATH,
        "--agent-pack",
        help="Path to an AgentPack directory (Phoenix base + agent custom).",
    ),
) -> None:
    pack = validate_agent_pack(agent_pack)
    if pack.intents is None and agent_pack == DEFAULT_AGENT_PACK_PATH:
        validate_demo_configs()
    typer.echo(
        f"AgentGate agent pack is valid. agent_id={pack.agent_id} "
        f"metrics={len(pack.effective_metrics)} demo={pack.demo.get('enabled', False)}"
    )


@profiles_app.command("validate")
def validate_profile(
    profile: Path = typer.Option(..., help="Path to an AgentProfile JSON config."),
) -> None:
    agent_profile = load_agent_profile(profile)
    typer.echo(
        f"AgentGate agent profile is valid. agent_id={agent_profile.agent_id} "
        f"integration_type={agent_profile.integration_type} "
        f"trace_backend={agent_profile.trace_backend.provider}"
    )


@suites_app.command("validate")
def validate_suite(
    suite: Path = typer.Option(..., help="Path to an EvalSuite JSON config."),
) -> None:
    eval_suite = load_eval_suite(suite)
    typer.echo(
        f"AgentGate eval suite is valid. suite_id={eval_suite.suite_id} "
        f"agent_id={eval_suite.agent_id} mode={eval_suite.evaluation_mode} "
        f"tasks={len(eval_suite.tasks)}"
    )


@gate_app.command("check")
def gate_check(
    suite: Path = typer.Option(..., help="Path to an EvalSuite JSON config."),
    agent_version: str = typer.Option(..., help="Candidate agent version under review."),
    agent_pack: Path = typer.Option(
        DEFAULT_AGENT_PACK_PATH,
        "--agent-pack",
        help="AgentPack directory used for default release policy.",
    ),
    policy: Path | None = typer.Option(
        None,
        help="Optional override for release policy JSON.",
    ),
) -> None:
    eval_suite = load_eval_suite(suite)
    if eval_suite.evaluation_mode != "controlled":
        typer.echo(
            "AgentGate gate check warning. observed suites cannot directly BLOCKED; "
            "create a controlled regression suite first."
        )
        raise typer.Exit(code=0)

    release_config = ReleaseCheckConfig(agent_pack_path=agent_pack, policy_path=policy)
    release_policy = release_config.load_policy()
    pack = release_config.load_pack()
    required_metrics = list(eval_suite.release_gate_binding.get("required_metrics", []))
    validation = validate_suite_required_metrics(
        required_metrics,
        release_policy,
        gate_binding=eval_suite.release_gate_binding,
        metric_graders=pack.metric_graders(),
        effective_metrics=pack.effective_metrics,
    )

    for warning in validation["warnings"]:
        typer.echo(f"AgentGate gate check warning. {warning}")

    if not validation["contract_valid"]:
        for issue in validation["blocking_issues"]:
            typer.echo(f"AgentGate gate check error. {issue}", err=True)
        raise typer.Exit(code=1)

    mapped = sum(1 for check in validation["checks"] if check["status"] == "mapped")
    not_implemented = sum(1 for check in validation["checks"] if check["status"] == "not_implemented")
    typer.echo(
        f"AgentGate gate contract check complete. suite_id={eval_suite.suite_id} "
        f"agent_version={agent_version} mode={eval_suite.evaluation_mode} "
        f"required_metrics={len(required_metrics)} mapped={mapped} "
        f"not_implemented={not_implemented} status=contract_valid"
    )


@demo_cases_app.command("validate")
def validate_cases() -> None:
    cases = validate_demo_cases()
    typer.echo(f"AgentGate demo cases are valid. total_cases={len(cases)}")


@demo_app.command("seed-v2")
def demo_seed_v2(
    output: Path | None = typer.Option(
        None,
        help="Path to write seeded evidence JSONL.",
    ),
) -> None:
    resolved_output = output or get_default_agent_pack().seed_path("v2")
    if resolved_output is None:
        typer.echo("AgentGate seed-v2 failed: default pack has no v2 seed path.", err=True)
        raise typer.Exit(code=1)
    payload = write_seed_evidence("v2", resolved_output)
    typer.echo(
        f"AgentGate seed evidence generated. agent_version={payload['agent_version']} "
        f"records={payload['total_records']} spans={payload['span_events']} "
        f"labels={payload['eval_labels']} output={resolved_output}"
    )


@demo_app.command("seed-v21")
def demo_seed_v21(
    output: Path | None = typer.Option(
        None,
        help="Path to write seeded evidence JSONL.",
    ),
) -> None:
    resolved_output = output or get_default_agent_pack().seed_path("v2.1")
    if resolved_output is None:
        typer.echo("AgentGate seed-v21 failed: default pack has no v2.1 seed path.", err=True)
        raise typer.Exit(code=1)
    payload = write_seed_evidence("v2.1", resolved_output)
    typer.echo(
        f"AgentGate seed evidence generated. agent_version={payload['agent_version']} "
        f"records={payload['total_records']} spans={payload['span_events']} "
        f"labels={payload['eval_labels']} output={resolved_output}"
    )


@release_app.command("check")
def release_check(
    evidence: Path | None = typer.Option(None, help="Path to local JSONL release evidence."),
    output_dir: Path = typer.Option(..., help="Directory to write release artifacts."),
    source: str | None = typer.Option(
        None,
        help="Evidence source: phoenix or local. Defaults to local when --evidence is set, otherwise phoenix.",
    ),
    project_identifier: str | None = typer.Option(
        None,
        help="Phoenix project name or ID. Defaults to PHOENIX_PROJECT/PHOENIX_PROJECT_NAME.",
    ),
    agent_version: str | None = typer.Option(
        None,
        help="Filter Phoenix spans to one agent.version, for example v2 or v2.1.",
    ),
    last_n_minutes: int | None = typer.Option(
        24 * 60,
        help="Phoenix lookback window when --source phoenix is used.",
    ),
    start_time: str | None = typer.Option(None, help="Phoenix query start time, ISO 8601."),
    end_time: str | None = typer.Option(None, help="Phoenix query end time, ISO 8601."),
    limit: int = typer.Option(1000, min=1, max=1000, help="Phoenix page size for span queries."),
    diagnosis_mode: DiagnosisMode = typer.Option(
        "deterministic",
        help="Dangerous session diagnosis mode: deterministic or gemini.",
    ),
    eval_first: bool = typer.Option(
        False,
        help="Run Phoenix eval automation before release check when --source phoenix.",
    ),
    require_eval_complete: bool = typer.Option(
        False,
        help="Fail when eval-dependent metrics are not available from Phoenix evidence.",
    ),
    agent_pack: Path = typer.Option(
        DEFAULT_AGENT_PACK_PATH,
        "--agent-pack",
        help="AgentPack directory (Phoenix base + agent custom config).",
    ),
    policy: Path | None = typer.Option(
        None,
        help="Optional override for release policy JSON.",
    ),
    suite: Path | None = typer.Option(
        None,
        help="Optional override for eval suite JSON.",
    ),
    profile: Path | None = typer.Option(
        None,
        help="Optional override for agent profile JSON.",
    ),
    fail_on_block: bool = typer.Option(
        False,
        "--fail-on-block",
        help="Exit with code 1 when the release decision is BLOCKED (for CI/CD gates).",
    ),
    release_controls: Path | None = typer.Option(
        None,
        "--release-controls",
        help="Path to a prior regression_gates.json artifact for inherited release-control verification.",
    ),
) -> None:
    release_config = ReleaseCheckConfig(
        agent_pack_path=agent_pack,
        policy_path=policy,
        suite_path=suite,
        profile_path=profile,
        release_controls_ref=release_controls,
        release_controls_resolution_source="cli_argument" if release_controls else None,
    )
    resolved_source = source or ("local" if evidence else "phoenix")
    if resolved_source == "local":
        if evidence is None:
            typer.echo("AgentGate release check failed: --evidence is required when --source local.", err=True)
            raise typer.Exit(code=1)
        payload = run_release_check(
            evidence,
            output_dir,
            diagnosis_mode=diagnosis_mode,
            release_config=release_config,
        )
    elif resolved_source == "phoenix":
        try:
            payload = run_release_check_from_phoenix_mcp(
                output_dir=output_dir,
                project_identifier=project_identifier,
                agent_version=agent_version,
                last_n_minutes=last_n_minutes,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                diagnosis_mode=diagnosis_mode,
                eval_first=eval_first,
                require_eval_complete=require_eval_complete,
                release_config=release_config,
            )
        except (PhoenixMCPError, ValueError) as error:
            typer.echo(f"AgentGate Phoenix release check failed: {error}", err=True)
            raise typer.Exit(code=1) from error
    else:
        typer.echo(f"AgentGate release check failed: unsupported --source {resolved_source}", err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"AgentGate release check complete. agent_version={payload['agent_version']} "
        f"decision={payload['decision']} critical_findings={payload['critical_findings']} "
        f"indeterminate_findings={payload.get('indeterminate_findings', 0)} "
        f"high_risk_activity={payload.get('high_risk_activity_count', 0)} "
        f"reviewed_safe={payload['reviewed_safe']} diagnosis_mode={diagnosis_mode} "
        f"source={resolved_source} output_dir={output_dir}"
    )
    if fail_on_block and payload["decision"] == "BLOCKED":
        typer.echo("AgentGate release check failed: decision=BLOCKED (--fail-on-block).", err=True)
        raise typer.Exit(code=1)


@release_app.command("check-phoenix")
def release_check_phoenix(
    spans_json: Path = typer.Option(..., help="Path to Phoenix MCP spans JSON export."),
    output_dir: Path = typer.Option(..., help="Directory to write release artifacts."),
    agent_pack: Path = typer.Option(
        DEFAULT_AGENT_PACK_PATH,
        "--agent-pack",
        help="AgentPack directory (Phoenix base + agent custom config).",
    ),
    policy: Path | None = typer.Option(None, help="Optional override for release policy JSON."),
    suite: Path | None = typer.Option(None, help="Optional override for eval suite JSON."),
    profile: Path | None = typer.Option(None, help="Optional override for agent profile JSON."),
) -> None:
    release_config = ReleaseCheckConfig(
        agent_pack_path=agent_pack,
        policy_path=policy,
        suite_path=suite,
        profile_path=profile,
    )
    payload = run_release_check_from_phoenix_spans(
        spans_json,
        output_dir,
        release_config=release_config,
    )
    typer.echo(
        f"AgentGate Phoenix release check complete. agent_version={payload['agent_version']} "
        f"decision={payload['decision']} critical_findings={payload['critical_findings']} "
        f"indeterminate_findings={payload.get('indeterminate_findings', 0)} "
        f"high_risk_activity={payload.get('high_risk_activity_count', 0)} "
        f"reviewed_safe={payload['reviewed_safe']} output_dir={output_dir}"
    )


@eval_app.command("sync-dataset")
def eval_sync_dataset(
    dataset_name: str | None = typer.Option(None, help="Phoenix dataset name."),
    upsert: bool = typer.Option(False, help="Skip creation when dataset already exists."),
) -> None:
    try:
        payload = sync_release_eval_dataset(dataset_name=dataset_name, upsert=upsert)
    except Exception as error:
        typer.echo(f"AgentGate eval dataset sync failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"AgentGate eval dataset sync complete. action={payload['action']} "
        f"dataset={payload['dataset_name']} examples={payload.get('example_count')}"
    )


@eval_app.command("run")
def eval_run(
    agent_version: str = typer.Option(..., help="Candidate agent version to evaluate."),
    project_identifier: str | None = typer.Option(None, help="Phoenix project name or ID."),
    last_n_minutes: int | None = typer.Option(24 * 60, help="Lookback window for Phoenix spans."),
    output_dir: Path | None = typer.Option(None, help="Directory for eval_run_summary.json."),
    dry_run: bool = typer.Option(False, help="Compute eval annotations without writing to Phoenix."),
) -> None:
    resolved_output_dir = output_dir or Path("artifacts/eval") / agent_version

    def _progress(message: str) -> None:
        typer.echo(message, err=True)

    try:
        payload = run_phoenix_eval_job(
            agent_version=agent_version,
            project_identifier=project_identifier,
            last_n_minutes=last_n_minutes,
            output_dir=resolved_output_dir,
            dry_run=dry_run,
            progress=_progress,
        )
    except Exception as error:
        typer.echo(f"AgentGate eval run failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    summary_path = payload.get("summary_path")
    typer.echo(
        f"AgentGate eval run complete. agent_version={payload['agent_version']} "
        f"rows={payload['eval_rows']} annotations={payload['annotations_written']} "
        f"dry_run={payload['dry_run']}"
        + (f" summary={summary_path}" if summary_path else "")
    )


@eval_app.command("coverage")
def eval_coverage(
    evidence: Path | None = typer.Option(None, help="Local JSONL evidence for offline coverage."),
    agent_version: str | None = typer.Option(None, help="Optional label for the coverage report."),
) -> None:
    release_config = ReleaseCheckConfig()
    pack = release_config.load_pack()
    policy = release_config.load_policy()
    if evidence is None:
        typer.echo("AgentGate eval coverage requires --evidence for offline checks.", err=True)
        raise typer.Exit(code=1)
    records = load_evidence_jsonl(evidence)
    report = build_coverage_report(
        records,
        policy,
        evidence_source_type="local_jsonl",
        metric_graders=pack.metric_graders(),
        metric_decision_impact=pack.metric_decision_impact(),
        effective_metrics=pack.effective_metrics,
    )
    if agent_version:
        report["agent_version"] = agent_version
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@telemetry_app.command("replay")
def telemetry_replay(
    evidence: Path = typer.Option(..., help="Path to local JSONL release evidence."),
    service_name: str | None = typer.Option(
        None,
        help="OpenTelemetry service/tracer name. Defaults to the loaded AgentPack agent_id.",
    ),
) -> None:
    resolved_service_name = service_name or ReleaseCheckConfig().load_pack().agent_id
    try:
        payload = replay_evidence_to_phoenix(evidence, resolved_service_name)
    except (PhoenixConfigError, ValueError) as error:
        typer.echo(f"AgentGate telemetry replay failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(
        f"AgentGate telemetry replay complete. agent_version={payload['agent_version']} "
        f"traces={payload['trace_count']} spans={payload['span_events']} "
        f"eval_labels={payload['eval_labels']} phoenix_project={payload['phoenix_project_name']}"
    )
