from __future__ import annotations

from pathlib import Path

import pytest

from hermclaw import config


def test_missing_config_writes_safe_defaults(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    result = config.load_config(path)
    assert result.valid
    assert result.source == "defaults"
    assert result.config.agent.name == "hermclaw"
    assert result.config.tools.shell_enabled is False
    assert path.exists()


def test_valid_config_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    config.load_config(path)  # seed defaults
    result = config.load_config(path)
    assert result.valid
    assert result.source == "primary"


def test_unknown_top_level_key_rejected(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    path.write_text("agent:\n  name: test\nnot_a_real_section: true\n")
    result = config.load_config(path)
    assert not result.valid
    assert any("not_a_real_section" in e for e in result.errors)


def test_unknown_nested_key_rejected(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    path.write_text("agent:\n  name: test\n  bogus_field: 1\n")
    result = config.load_config(path)
    assert not result.valid


def test_schema_passthrough_allowed(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    path.write_text('$schema: "https://example.com/schema.json"\nagent:\n  name: test\n')
    result = config.load_config(path)
    assert result.valid
    assert result.config.schema_ref == "https://example.com/schema.json"


def test_invalid_config_falls_back_to_lkg(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    config.load_config(path)  # establishes a valid primary + .lkg
    path.write_text("agent:\n  bogus: true\n")
    result = config.load_config(path)
    assert result.valid  # falls back
    assert result.source == "lkg"
    assert result.errors  # but still reports what was wrong with the live file


def test_invalid_config_with_no_lkg_reports_invalid(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    path.write_text("agent:\n  bogus: true\n")  # never successfully loaded before -- no .lkg exists
    result = config.load_config(path)
    assert not result.valid
    assert result.config is None


def test_malformed_yaml_falls_back_to_lkg(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    config.load_config(path)
    path.write_text("agent: [unterminated\n")
    result = config.load_config(path)
    assert result.valid
    assert result.source == "lkg"


def test_save_config_text_refuses_large_shrink(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    config.load_config(path)
    tiny = "agent:\n  name: x\n"
    with pytest.raises(config.ConfigWriteRefused):
        config.save_config_text(tiny, path)
    rejected = list(tmp_path.glob("hermclaw.yaml.rejected.*"))
    assert len(rejected) == 1


def test_save_config_text_refuses_dropped_agent_block(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    original = config.load_config(path)
    full_text = path.read_text()
    # same size roughly, but drops the agent: block entirely
    without_agent = "\n".join(line for line in full_text.splitlines() if not line.startswith("agent"))
    without_agent = without_agent.replace('  default_profile: "default"\n', "").replace('  list: []', "")
    with pytest.raises(config.ConfigWriteRefused):
        config.save_config_text(without_agent, path)


def test_save_config_text_force_overrides_protection(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    config.load_config(path)
    tiny = "agent:\n  name: x\n"
    config.save_config_text(tiny, path, force=True)
    assert path.read_text() == tiny


def test_save_config_text_normal_edit_succeeds(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    config.load_config(path)
    text = path.read_text()
    edited = text.replace('port: 18789', 'port: 19999')
    config.save_config_text(edited, path)
    result = config.load_config(path)
    assert result.config.body.gateway.port == 19999


@pytest.mark.asyncio
async def test_config_watcher_debounces_and_reloads(tmp_path: Path) -> None:
    path = tmp_path / "hermclaw.yaml"
    config.load_config(path)

    reloads = []

    async def on_reload(result: config.ConfigLoadResult) -> None:
        reloads.append(result)

    watcher = config.ConfigWatcher(path, on_reload, debounce_s=0.05, poll_interval_s=0.01)
    import asyncio

    task = asyncio.create_task(watcher.run())
    await asyncio.sleep(0.03)

    text = path.read_text().replace('port: 18789', 'port: 22222')
    path.write_text(text)

    await asyncio.sleep(0.3)
    watcher.stop()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert len(reloads) == 1
    assert reloads[0].valid
    assert reloads[0].config.body.gateway.port == 22222


def test_hermclaw_home_respects_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = tmp_path / "custom-home"
    monkeypatch.setenv("HERMCLAW_HOME", str(custom))
    assert config.hermclaw_home() == custom
