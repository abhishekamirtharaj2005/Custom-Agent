from __future__ import annotations

from hermclaw.security.secrets import redact, resolve_env_ref
from hermclaw.tools.approvals import build_approval_gate
from hermclaw.tools.base import ToolDispatcher, check_dangerous_command
from hermclaw.tools.shell import ShellTool


def test_dangerous_command_detection() -> None:
    is_hardline, is_dangerous, _ = check_dangerous_command("rm -rf /")
    assert is_hardline and is_dangerous  # catastrophic -- blocked even in "off" mode

    is_hardline, is_dangerous, _ = check_dangerous_command("DELETE FROM users")
    assert not is_hardline and is_dangerous  # dangerous (needs approval), but not catastrophic -- allowed in explicit "off" mode

    is_hardline, is_dangerous, _ = check_dangerous_command("ls -la")
    assert not is_hardline and not is_dangerous

    is_hardline, is_dangerous, _ = check_dangerous_command("DELETE FROM users WHERE id=1")
    assert not is_hardline and not is_dangerous  # scoped by WHERE -- not flagged at all


async def test_hardline_pattern_blocked_even_in_off_mode() -> None:
    gate = build_approval_gate(mode="off")
    dispatcher = ToolDispatcher(gate)
    dispatcher.register(ShellTool(backend="local"))
    result = await dispatcher.dispatch("shell", {"command": "rm -rf /"})
    assert result.ok is False


async def test_normal_command_executes_in_off_mode() -> None:
    gate = build_approval_gate(mode="off")
    dispatcher = ToolDispatcher(gate)
    dispatcher.register(ShellTool(backend="local"))
    result = await dispatcher.dispatch("shell", {"command": "echo security-test-marker"})
    assert result.ok is True
    assert "security-test-marker" in result.output


async def test_manual_mode_denies_without_approval_callback() -> None:
    gate = build_approval_gate(mode="manual")
    dispatcher = ToolDispatcher(gate)
    dispatcher.register(ShellTool(backend="local"))
    result = await dispatcher.dispatch("shell", {"command": "echo should-not-run"})
    # Fail-closed: no confirm callback wired up means nothing gets approved.
    assert result.ok is False


async def test_manual_mode_respects_approval_callback(monkeypatch) -> None:
    approved = {"value": False}

    async def always_approve(tool_name, args):
        approved["value"] = True
        return True

    gate = build_approval_gate(mode="manual", confirm_callback=always_approve)
    dispatcher = ToolDispatcher(gate)
    dispatcher.register(ShellTool(backend="local"))
    result = await dispatcher.dispatch("shell", {"command": "echo approved-run"})
    assert approved["value"] is True
    assert result.ok is True


def test_redact_hides_secret_looking_values() -> None:
    data = {"bot_token_env": "TELEGRAM_BOT_TOKEN", "api_key": "sk-abc123", "nested": {"password": "hunter2", "ok": "fine"}}
    redacted = redact(data)
    assert redacted["api_key"] != "sk-abc123"
    assert redacted["nested"]["password"] != "hunter2"
    assert redacted["nested"]["ok"] == "fine"


def test_resolve_env_ref_reads_actual_environment(monkeypatch) -> None:
    monkeypatch.setenv("HERMCLAW_TEST_SECRET", "the-real-value")
    assert resolve_env_ref("HERMCLAW_TEST_SECRET") == "the-real-value"
    assert resolve_env_ref("HERMCLAW_TEST_SECRET_NOT_SET") is None


def test_filesystem_scope_sets_working_directory() -> None:
    import asyncio

    async def run() -> None:
        gate = build_approval_gate(mode="off")
        dispatcher = ToolDispatcher(gate)
        import tempfile

        scope = tempfile.mkdtemp()
        dispatcher.register(ShellTool(backend="local", filesystem_scope=scope))
        result = await dispatcher.dispatch("shell", {"command": "pwd"})
        assert result.output.strip() == scope

    asyncio.run(run())


def test_shell_tool_rejects_unknown_backend() -> None:
    try:
        ShellTool(backend="not-a-real-backend")
        assert False, "expected ValueError"
    except ValueError:
        pass
