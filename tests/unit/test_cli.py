from pathlib import Path

from typer.testing import CliRunner

from tests.fixtures.paths import (
    DEMO_POLICY_PATH,
    DEMO_PROFILE_PATH,
    DEMO_SEED_V2_PATH,
    DEMO_SEED_V21_PATH,
    DEMO_SUITE_PATH,
)

from backend.agentgate.cli import app


def test_configs_validate_cli() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["configs", "validate"])

    assert result.exit_code == 0
    assert "AgentGate agent pack is valid." in result.output
    assert "stability_ops_ai" in result.output


def test_profiles_validate_cli() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "profiles",
            "validate",
            "--profile",
            str(DEMO_PROFILE_PATH),
        ],
    )

    assert result.exit_code == 0
    assert "AgentGate agent profile is valid." in result.output


def test_suites_validate_cli() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "suites",
            "validate",
            "--suite",
            str(DEMO_SUITE_PATH),
        ],
    )

    assert result.exit_code == 0
    assert "AgentGate eval suite is valid." in result.output
    assert "mode=controlled" in result.output


def test_gate_check_cli_validates_controlled_suite_contract() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "gate",
            "check",
            "--suite",
            str(DEMO_SUITE_PATH),
            "--agent-version",
            "v2",
        ],
    )

    assert result.exit_code == 0
    assert "AgentGate gate contract check complete." in result.output
    assert "status=contract_valid" in result.output
    assert "mapped=2" in result.output
    assert "not_implemented=0" in result.output


def test_release_check_cli_accepts_policy_suite_profile(tmp_path: Path) -> None:
    runner = CliRunner()
    output_dir = tmp_path / "release" / "v2"

    result = runner.invoke(
        app,
        [
            "release",
            "check",
            "--source",
            "local",
            "--evidence",
            str(DEMO_SEED_V2_PATH),
            "--output-dir",
            str(output_dir),
            "--policy",
            str(DEMO_POLICY_PATH),
            "--suite",
            str(DEMO_SUITE_PATH),
            "--profile",
            str(DEMO_PROFILE_PATH),
        ],
    )

    assert result.exit_code == 0
    assert "AgentGate release check complete." in result.output
    assert "decision=BLOCKED" in result.output
    assert (output_dir / "eval_suite.json").exists()
    assert (output_dir / "agent_profile.json").exists()


def test_release_check_cli_fail_on_block_exits_nonzero_for_blocked(tmp_path: Path) -> None:
    runner = CliRunner()
    output_dir = tmp_path / "release" / "v2"

    result = runner.invoke(
        app,
        [
            "release",
            "check",
            "--source",
            "local",
            "--evidence",
            str(DEMO_SEED_V2_PATH),
            "--output-dir",
            str(output_dir),
            "--policy",
            str(DEMO_POLICY_PATH),
            "--suite",
            str(DEMO_SUITE_PATH),
            "--profile",
            str(DEMO_PROFILE_PATH),
            "--fail-on-block",
        ],
    )

    assert result.exit_code == 1
    assert "decision=BLOCKED" in result.output
    assert "--fail-on-block" in result.output


def test_release_check_cli_fail_on_block_exits_zero_for_approved(tmp_path: Path) -> None:
    runner = CliRunner()
    output_dir = tmp_path / "release" / "v21"

    result = runner.invoke(
        app,
        [
            "release",
            "check",
            "--source",
            "local",
            "--evidence",
            str(DEMO_SEED_V21_PATH),
            "--output-dir",
            str(output_dir),
            "--agent-pack",
            str(DEMO_SEED_V21_PATH.parent.parent),
            "--fail-on-block",
        ],
    )

    assert result.exit_code == 0
    assert "decision=APPROVED" in result.output
