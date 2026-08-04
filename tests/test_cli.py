from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hermclaw.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _fake_api_key(anthropic_key_env):
    yield


def test_help_lists_exactly_five_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("chat", "serve", "doctor", "reflect", "skills"):
        assert cmd in result.output


def test_doctor_init_writes_config_and_is_idempotent() -> None:
    result = runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    assert result.exit_code == 0
    assert "Wrote a default config" in result.output

    result2 = runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    assert result2.exit_code == 0
    assert "idempotent" in result2.output


def test_doctor_reports_missing_gateway_token_as_failure() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "gateway auth token" in result.output


def test_doctor_json_output_is_valid_json() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["--json", "doctor"])
    data = json.loads(result.output)
    assert "checks" in data
    assert isinstance(data["checks"], list)


def test_doctor_fix_creates_state_db() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["doctor", "--fix"])
    assert "state.db" in result.output
    assert "PASS" in result.output


def test_skills_list_empty() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["skills", "list"])
    assert result.exit_code == 0
    assert "no skills yet" in result.output


def test_skills_validate_empty_passes() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["skills", "validate"])
    assert result.exit_code == 0


def test_skills_show_unknown_skill_gives_clean_error() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["skills", "show", "does-not-exist"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "No skill named" in result.output


def test_reflect_on_profile_with_zero_sessions() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["reflect"])
    assert result.exit_code == 0
    assert "reviewed 0 session" in result.output


def test_reflect_all_profiles_with_no_profiles_yet() -> None:
    runner.invoke(app, ["doctor", "--init"], input="anthropic\n")
    result = runner.invoke(app, ["reflect", "--all-profiles"])
    assert result.exit_code == 0
    assert "nothing to reflect" in result.output.lower()


def test_invalid_config_gives_clean_error_not_traceback(tmp_path) -> None:
    bad_cfg = tmp_path / "hermclaw.yaml"
    bad_cfg.write_text("agent:\n  totally_bogus_field: true\n")
    result = runner.invoke(app, ["--config", str(bad_cfg), "chat"], input="\n")
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "invalid" in result.output.lower()


def test_missing_config_path_gets_defaults_written(tmp_path) -> None:
    """A path that simply doesn't exist yet is not an error -- Hermclaw
    writes safe defaults there, same as the real default location."""
    fresh_path = tmp_path / "brand-new" / "hermclaw.yaml"
    result = runner.invoke(app, ["--config", str(fresh_path), "doctor"])
    assert fresh_path.exists()
