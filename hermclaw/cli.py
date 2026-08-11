"""Hermclaw's unified CLI: exactly five subcommands (chat, serve, doctor,
reflect, skills) -- a hard constraint per the build spec, not a starting
point to expand from. `status`-shaped functionality (job list, channel
connectivity, token/cost totals) lives inside `doctor` and its --json
output rather than as a sixth top-level verb; see MERGE_DECISIONS.md.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import secrets as secretslib
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from hermclaw.body.agents_registry import AgentsRegistry
from hermclaw.brain.profiles import ProfileManager
from hermclaw.brain.reflection import reflect as run_reflection
from hermclaw.brain.transports import MissingCredentialsError
from hermclaw.config import (
    ConfigWriteRefused,
    default_config_path,
    hermclaw_home,
    load_config,
    write_default_config,
)
from hermclaw.observability import configure_logging
from hermclaw.runtime import build_agent_runtime, gateway_token
from hermclaw.security.permissions import check_file_permissions
from hermclaw.security.secrets import resolve_env_ref
from hermclaw.skills.registry import SkillRegistry

app = typer.Typer(name="hermclaw", help="Hermclaw: a unified, self-improving personal AI agent.", no_args_is_help=True)
skills_app = typer.Typer(help="Skill management: list, validate, and inspect skills for a profile.")
app.add_typer(skills_app, name="skills")

console = Console()
err_console = Console(stderr=True)


class CleanExit(Exception):
    """Raised anywhere in a command's async body to print one clean line
    and exit(1) -- never a raw stack trace for an expected failure mode
    (bad config, missing credentials, etc.)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _run(coro: "asyncio.Future") -> None:
    try:
        asyncio.run(coro)
    except CleanExit as exc:
        err_console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(code=1)
    except MissingCredentialsError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except ConfigWriteRefused as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        raise typer.Exit(code=130)


@app.callback()
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(None, "--config", help="Path to hermclaw.yaml (default: ~/.hermclaw/hermclaw.yaml)"),
    profile: str = typer.Option("default", "--profile", help="Profile to operate on"),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output for every subcommand"),
) -> None:
    # Load .env from hermclaw home BEFORE anything else resolves env vars
    _load_env_file(hermclaw_home() / ".env")
    ctx.obj = {"config_path": config or default_config_path(), "profile": profile, "json": json_output}
    configure_logging(console=not json_output)


def _load_env_file(env_path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ.
    Doesn't overwrite existing env vars. No external dependency needed."""
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:  # never overwrite existing
                os.environ[key] = value
    except Exception:
        pass  # .env loading is best-effort


def _load_or_die(config_path: Path):
    result = load_config(config_path)
    if not result.valid:
        prefix = "Config is invalid, and running on the last-known-good copy" if result.source == "lkg" else "Config is invalid with no last-known-good copy available"
        raise CleanExit(f"{prefix}:\n  " + "\n  ".join(result.errors[:5]) + "\n\nRun `hermclaw doctor` for a full report, or `hermclaw doctor --init` to start fresh.")
    return result


# =============================================================================
# chat
# =============================================================================


@app.command()
def chat(ctx: typer.Context) -> None:
    """Interactive chat for one profile. Doesn't start the gateway, the
    scheduler, or any other channel -- just this one conversation."""
    _run(_chat_impl(ctx.obj["config_path"], ctx.obj["profile"]))


async def _chat_impl(config_path: Path, profile: str) -> None:
    from hermclaw.brain.model_catalog import CostTracker, ModelCatalog
    from hermclaw.brain.post_processing import sanitize_response
    from hermclaw.brain.transports.openai_compat import ChatCompletionsTransport

    result = _load_or_die(config_path)
    runtime = await build_agent_runtime(profile, result.config)

    catalog = ModelCatalog()
    cost_tracker = CostTracker()

    model_name = result.config.brain.model.model_name
    console.print(f"[bold]Hermclaw[/bold] -- profile: [cyan]{profile}[/cyan], model: {model_name}")
    console.print("Type a message and press Enter. Ctrl-D or Ctrl-C to exit.")
    console.print("[dim]Commands: /model <name>, /models, /cost, /exit[/dim]\n")

    session_id = await runtime.memory_store.a_create_session(channel="cli", model=model_name)

    # Wire up streaming callback
    streaming_enabled = True
    if isinstance(runtime.agent.transport, ChatCompletionsTransport):
        def _on_chunk(chunk: str) -> None:
            console.print(chunk, end="", highlight=False)
        runtime.agent.transport.on_stream_chunk = _on_chunk

    try:
        loop = asyncio.get_running_loop()
        while True:
            try:
                user_input = await loop.run_in_executor(None, input, "you> ")
            except (EOFError, OSError, KeyboardInterrupt):
                break
            if not user_input.strip():
                continue

            # --- Slash commands ---
            stripped = user_input.strip()
            if stripped.lower() in ("/exit", "/quit", "/q"):
                break

            if stripped.lower() == "/models":
                console.print(catalog.format_table())
                continue

            if stripped.lower() == "/cost":
                console.print(f"[dim]{cost_tracker.summary()}[/dim]")
                continue

            if stripped.lower().startswith("/model "):
                new_model = stripped[7:].strip()
                info = catalog.resolve(new_model)
                if info:
                    console.print(f"[green]Switched to {info.name}[/green] ({info.description})")
                    # Re-build transport for the new model
                    from hermclaw.brain.transports import build_transport
                    from hermclaw.config import ModelConfig
                    new_cfg = ModelConfig(
                        provider=info.provider,
                        model_name=info.name,
                        api_base_env=f"HERMCLAW_API_BASE_{info.provider.upper()}" if info.api_base else result.config.brain.model.api_base_env,
                        api_key_env=result.config.brain.model.api_key_env,
                    )
                    # For Ollama models with known api_base, set the env
                    if info.api_base:
                        os.environ[f"HERMCLAW_API_BASE_{info.provider.upper()}"] = info.api_base
                        new_cfg.api_base_env = f"HERMCLAW_API_BASE_{info.provider.upper()}"
                    try:
                        runtime.agent.transport = build_transport(new_cfg)
                        runtime.agent.model_config = new_cfg
                        if isinstance(runtime.agent.transport, ChatCompletionsTransport):
                            runtime.agent.transport.on_stream_chunk = _on_chunk
                    except Exception as exc:
                        console.print(f"[red]Failed to switch: {exc}[/red]")
                else:
                    console.print(f"[red]Unknown model: {new_model}[/red]. Use /models to see available.")
                continue

            # --- Regular message ---
            if streaming_enabled and isinstance(runtime.agent.transport, ChatCompletionsTransport):
                # Track what the streaming callback actually printed
                streamed_chars = 0
                _original_on_chunk = runtime.agent.transport.on_stream_chunk
                def _tracking_on_chunk(chunk: str) -> None:
                    nonlocal streamed_chars
                    streamed_chars += len(chunk)
                    console.print(chunk, end="", highlight=False)
                runtime.agent.transport.on_stream_chunk = _tracking_on_chunk

                console.print("[bold cyan]hermclaw>[/bold cyan] ", end="")
                turn_result = await runtime.agent.run_turn(session_id, user_input, stream=True)

                # After tool calls, the final response is NOT streamed --
                # it only lives in turn_result.text. Print it if streaming
                # didn't already output it.
                if turn_result.text and streamed_chars == 0:
                    clean_text = sanitize_response(turn_result.text)
                    console.print(clean_text)
                elif streamed_chars > 0:
                    console.print("")  # newline after streamed text
                else:
                    # Model returned empty text (shouldn't happen, but be safe)
                    console.print("[dim](no response)[/dim]")
                console.print("")  # blank line separator
            else:
                with console.status("[dim]thinking...[/dim]"):
                    turn_result = await runtime.agent.run_turn(session_id, user_input)
                clean_text = sanitize_response(turn_result.text)
                console.print(f"[bold cyan]hermclaw>[/bold cyan] {clean_text}\n")

            # Track costs
            cost_tracker.record(
                model_name=runtime.agent.model_config.model_name,
                input_tokens=turn_result.usage.input_tokens,
                output_tokens=turn_result.usage.output_tokens,
                catalog=catalog,
            )
    finally:
        console.print(f"\n[dim]{cost_tracker.summary()}[/dim]")
        await runtime.aclose()


# =============================================================================
# run (one-shot mode)
# =============================================================================


@app.command()
def run(
    ctx: typer.Context,
    prompt: str = typer.Argument(..., help="The prompt to send to the agent"),
) -> None:
    """One-shot mode: send a single prompt, get a response, and exit.
    Perfect for scripting and automation."""
    _run(_run_impl(ctx.obj["config_path"], ctx.obj["profile"], prompt))


async def _run_impl(config_path: Path, profile: str, prompt: str) -> None:
    from hermclaw.brain.post_processing import sanitize_response

    result = _load_or_die(config_path)
    runtime = await build_agent_runtime(profile, result.config)

    session_id = await runtime.memory_store.a_create_session(
        channel="cli-oneshot", model=result.config.brain.model.model_name
    )
    try:
        turn_result = await runtime.agent.run_turn(session_id, prompt)
        clean_text = sanitize_response(turn_result.text)
        # In one-shot mode, print just the response text (no formatting)
        # so it can be piped to other commands
        print(clean_text)
    finally:
        await runtime.aclose()


# =============================================================================
# serve
# =============================================================================


@app.command()
def serve(
    ctx: typer.Context,
    daemonize: bool = typer.Option(False, "--daemonize", help="Run detached in the background (POSIX only)"),
) -> None:
    """Start the gateway: every enabled channel, the heartbeat/job
    scheduler, and the HTTP control API. Foreground by default."""
    if daemonize:
        _daemonize_serve(ctx.obj["config_path"])
        return
    _run(_serve_impl(ctx.obj["config_path"]))


def _daemonize_serve(config_path: Path) -> None:
    import subprocess

    if sys.platform == "win32":
        raise CleanExit(
            "--daemonize isn't supported on Windows -- run `hermclaw serve` in the foreground "
            "(e.g. under a Windows service wrapper) instead."
        )

    home = hermclaw_home()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    pid_file = home / "gateway.pid"
    log_file = home / "logs" / "gateway.daemon.log"
    log_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    if pid_file.exists():
        try:
            existing_pid = int(pid_file.read_text().strip())
            os.kill(existing_pid, 0)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
        else:
            raise CleanExit(f"Gateway already appears to be running (pid {existing_pid}). Stop it first, or remove {pid_file} if that's stale.")

    with open(log_file, "ab") as log_fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "hermclaw.cli", "serve", "--config", str(config_path)],
            stdout=log_fh, stderr=log_fh, stdin=subprocess.DEVNULL, start_new_session=True,
        )
    pid_file.write_text(str(proc.pid))
    console.print(f"Gateway started in the background (pid {proc.pid}). Logs: {log_file}")


async def _serve_impl(config_path: Path) -> None:
    import uvicorn

    from hermclaw.body.gateway import Gateway

    gw = Gateway(config_path=config_path)
    await gw.start()
    assert gw.config is not None
    console.print(f"Hermclaw gateway listening on {gw.config.body.gateway.host}:{gw.config.body.gateway.port}")
    console.print(f"Channels: {', '.join(gw.channels.keys()) or '(none enabled)'}")

    server_config = uvicorn.Config(gw.app, host=gw.config.body.gateway.host, port=gw.config.body.gateway.port, log_config=None)
    server = uvicorn.Server(server_config)
    try:
        await server.serve()
    finally:
        await gw.stop()


# =============================================================================
# doctor
# =============================================================================


@app.command()
def doctor(
    ctx: typer.Context,
    init: bool = typer.Option(False, "--init", help="First-run setup wizard"),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix common issues automatically"),
) -> None:
    """Diagnostics: config validity, credentials, file permissions,
    skills, and a status snapshot (channels/profiles/jobs -- use --json
    for the full machine-readable snapshot). --init runs a first-run
    setup wizard; --fix repairs what it safely can."""
    _run(_doctor_impl(ctx.obj["config_path"], ctx.obj["json"], init, fix))


async def _init_wizard(config_path: Path) -> None:
    if config_path.exists():
        result = load_config(config_path)
        if result.valid:
            console.print(f"Already configured at [cyan]{config_path}[/cyan] -- `doctor --init` is idempotent, nothing to do.")
            console.print("Run `hermclaw doctor` to check its health.")
            return

    write_default_config(config_path)
    console.print(f"Wrote a default config to [cyan]{config_path}[/cyan].\n")

    provider = typer.prompt("Model provider (anthropic / openai_compat / bedrock)", default="anthropic")
    console.print(f"Using provider=[cyan]{provider}[/cyan]. Set the matching API key environment variable "
                  f"(see brain.model.api_key_env in {config_path}) before running `hermclaw chat`.\n")

    token = secretslib.token_urlsafe(32)
    console.print("Generated a gateway auth token. Set this before running `hermclaw serve`:")
    console.print(f"  [green]export HERMCLAW_GATEWAY_TOKEN={token}[/green]\n")

    console.print("Next: `hermclaw doctor` to verify everything, then `hermclaw chat` to start talking to Hermclaw.")


def _check_channel_credentials(config) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    channels = config.body.channels
    if channels.telegram.enabled:
        present = bool(resolve_env_ref(channels.telegram.bot_token_env))
        checks.append(("telegram credentials", present, "present" if present else f"{channels.telegram.bot_token_env} not set"))
    if channels.discord.enabled:
        present = bool(resolve_env_ref(channels.discord.bot_token_env))
        checks.append(("discord credentials", present, "present" if present else f"{channels.discord.bot_token_env} not set"))
    if channels.slack.enabled:
        bot_present = bool(resolve_env_ref(channels.slack.bot_token_env))
        app_present = bool(resolve_env_ref(channels.slack.app_token_env))
        ok = bot_present and app_present
        checks.append(("slack credentials", ok, "present" if ok else "bot_token_env and/or app_token_env not set"))
    if channels.whatsapp.enabled:
        checks.append(("whatsapp", True, "auths interactively via QR code on first connect, not an env var -- see logs on first `serve`"))
    return checks


def _print_checks(checks: list[tuple[str, bool, str]], json_output: bool) -> bool:
    if json_output:
        console.print_json(data={"checks": [{"name": n, "passed": p, "detail": d} for n, p, d in checks]})
    else:
        table = Table(title="hermclaw doctor")
        table.add_column("Check")
        table.add_column("Result")
        table.add_column("Detail")
        for name, passed, detail in checks:
            table.add_row(name, "[green]PASS[/green]" if passed else "[red]FAIL[/red]", detail)
        console.print(table)
    return all(p for _, p, _ in checks)


async def _doctor_impl(config_path: Path, json_output: bool, init: bool, fix: bool) -> None:
    if init:
        await _init_wizard(config_path)
        return

    checks: list[tuple[str, bool, str]] = []
    result = load_config(config_path)
    checks.append(("config valid", result.valid, "OK" if result.valid else "; ".join(result.errors[:3])))

    if not result.valid or result.config is None:
        _print_checks(checks, json_output)
        raise CleanExit("Fix the config errors above, or run `hermclaw doctor --init` to start fresh.")

    config = result.config
    checks.extend(_check_channel_credentials(config))

    pm = ProfileManager()
    registry = AgentsRegistry(config.agent)
    for entry in registry.all_agents():
        paths = pm.ensure_profile(entry.profile)
        db_existed = paths.state_db.exists()
        if not db_existed and fix:
            from hermclaw.brain.memory.store import MemoryStore

            MemoryStore(paths.state_db).close()
            db_existed = True
        checks.append((
            f"profile '{entry.profile}' state.db", db_existed,
            "created" if (fix and db_existed) else ("exists" if db_existed else "missing (created automatically on first use)"),
        ))
        if db_existed:
            for issue in check_file_permissions(paths.state_db):
                checks.append((f"profile '{entry.profile}' state.db permissions", False, issue))

        skill_registry = SkillRegistry(directory=paths.skills_dir, extra_directories=config.skills.extra_directories)
        for validation in skill_registry.discover():
            checks.append((
                f"skill '{validation.skill_path.name}' ({entry.profile})", validation.passed,
                "OK" if validation.passed else "; ".join(validation.errors),
            ))

    token = gateway_token(config)
    if token:
        checks.append(("gateway auth token", True, "set"))
    elif fix:
        new_token = secretslib.token_urlsafe(32)
        checks.append((
            "gateway auth token", False,
            f"not set -- could not persist automatically; set {config.body.gateway.auth.token_env}={new_token} in your environment",
        ))
    else:
        checks.append(("gateway auth token", False, f"{config.body.gateway.auth.token_env} not set -- the gateway would run with no authentication"))

    all_passed = _print_checks(checks, json_output)
    if not json_output:
        console.print(f"\nConfig: {config_path}  |  Profiles in use: {', '.join(registry.profiles_in_use())}")
    if not all_passed:
        raise typer.Exit(code=1)


# =============================================================================
# reflect
# =============================================================================


@app.command()
def reflect(
    ctx: typer.Context,
    all_profiles: bool = typer.Option(False, "--all-profiles", help="Reflect for every profile with session history, not just --profile"),
) -> None:
    """Manually trigger the reflection loop (it also runs automatically
    every brain.reflection.trigger_every_n_turns)."""
    _run(_reflect_impl(ctx.obj["config_path"], ctx.obj["profile"], all_profiles, ctx.obj["json"]))


async def _reflect_impl(config_path: Path, profile: str, all_profiles: bool, json_output: bool) -> None:
    result = _load_or_die(config_path)
    assert result.config is not None
    pm = ProfileManager()
    profiles = pm.list_profiles() if all_profiles else [profile]
    if not profiles:
        console.print("No profiles found yet -- nothing to reflect on.")
        return

    results = {}
    for p in profiles:
        runtime = await build_agent_runtime(p, result.config, pm)
        try:
            results[p] = await run_reflection(
                p, runtime.memory_store, runtime.identity_files, runtime.skill_growth_engine, runtime.agent.transport,
            )
        finally:
            await runtime.aclose()

    if json_output:
        console.print_json(data={p: dataclasses.asdict(r) for p, r in results.items()})
        return
    for p, r in results.items():
        console.print(
            f"[bold]{p}[/bold]: reviewed {r.sessions_reviewed} session(s) -- "
            f"{len(r.facts_saved)} fact(s) + {len(r.user_facts_saved)} user fact(s) saved, "
            f"{len(r.draft_skills_created)} draft skill(s) created"
        )


# =============================================================================
# skills
# =============================================================================


async def _load_skill_registry(config_path: Path, profile: str) -> tuple[SkillRegistry, Path]:
    result = _load_or_die(config_path)
    assert result.config is not None
    pm = ProfileManager()
    paths = pm.ensure_profile(profile)
    registry = SkillRegistry(directory=paths.skills_dir, extra_directories=result.config.skills.extra_directories)
    registry.load()
    return registry, paths.skills_dir


@skills_app.command("list")
def skills_list(ctx: typer.Context) -> None:
    """List skills available to this profile -- name and description
    only, the same compact form the agent sees in its system prompt."""
    _run(_skills_list_impl(ctx.obj["config_path"], ctx.obj["profile"], ctx.obj["json"]))


async def _skills_list_impl(config_path: Path, profile: str, json_output: bool) -> None:
    registry, _ = await _load_skill_registry(config_path, profile)
    if json_output:
        console.print_json(data=registry.compact_listing())
        return
    table = Table(title=f"Skills for profile '{profile}'")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Source")
    for name in registry.names():
        skill = registry.get(name)
        assert skill is not None
        table.add_row(skill.name, skill.description, "auto-generated" if skill.auto_generated else "hand-authored")
    console.print(table)
    if not registry.names():
        console.print("(no skills yet)")
    if registry.load_errors:
        err_console.print(f"\n[yellow]{len(registry.load_errors)} skill(s) failed validation and were skipped -- run `hermclaw skills validate` for details.[/yellow]")


@skills_app.command("validate")
def skills_validate(ctx: typer.Context) -> None:
    """Run the full agentskills.io validation checklist against every
    skill directory for this profile."""
    _run(_skills_validate_impl(ctx.obj["config_path"], ctx.obj["profile"], ctx.obj["json"]))


async def _skills_validate_impl(config_path: Path, profile: str, json_output: bool) -> None:
    result = _load_or_die(config_path)
    assert result.config is not None
    pm = ProfileManager()
    paths = pm.ensure_profile(profile)
    registry = SkillRegistry(directory=paths.skills_dir, extra_directories=result.config.skills.extra_directories)
    validations = registry.discover()

    if json_output:
        console.print_json(data=[{"path": str(v.skill_path), "passed": v.passed, "errors": v.errors} for v in validations])
    else:
        table = Table(title=f"Skill validation for profile '{profile}'")
        table.add_column("Skill")
        table.add_column("Result")
        table.add_column("Errors")
        for v in validations:
            table.add_row(v.skill_path.name, "[green]PASS[/green]" if v.passed else "[red]FAIL[/red]", "; ".join(v.errors))
        console.print(table)
        if not validations:
            console.print("(no skills found)")

    if any(not v.passed for v in validations):
        raise typer.Exit(code=1)


@skills_app.command("show")
def skills_show(ctx: typer.Context, name: str = typer.Argument(..., help="Skill name")) -> None:
    """Show a skill's full SKILL.md -- frontmatter and body, the same
    content the agent sees once it activates this skill."""
    _run(_skills_show_impl(ctx.obj["config_path"], ctx.obj["profile"], name, ctx.obj["json"]))


async def _skills_show_impl(config_path: Path, profile: str, name: str, json_output: bool) -> None:
    registry, _ = await _load_skill_registry(config_path, profile)
    skill = registry.get(name)
    if skill is None:
        raise CleanExit(f"No skill named '{name}' for profile '{profile}'. Run `hermclaw skills list` to see what's available.")
    if json_output:
        console.print_json(data={"name": skill.name, "description": skill.description, "auto_generated": skill.auto_generated, "body": skill.body})
        return
    console.print(f"[bold]{skill.name}[/bold]")
    console.print(skill.description)
    console.print()
    console.print(skill.body)


# =============================================================================
# sessions
# =============================================================================

sessions_app = typer.Typer(help="Session management: list, show, export, and delete sessions.")
app.add_typer(sessions_app, name="sessions")


@sessions_app.command("list")
def sessions_list(ctx: typer.Context, limit: int = typer.Option(20, help="Max sessions to show")) -> None:
    """List recent chat sessions."""
    _run(_sessions_list_impl(ctx.obj["config_path"], ctx.obj["profile"], limit))


async def _sessions_list_impl(config_path: Path, profile: str, limit: int) -> None:
    result = _load_or_die(config_path)
    runtime = await build_agent_runtime(profile, result.config)
    try:
        sessions = await runtime.memory_store.a_get_recent_sessions(n=limit)
        if not sessions:
            console.print("No sessions found.")
            return
        table = Table(title=f"Sessions for profile '{profile}'")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Channel")
        table.add_column("Started")
        table.add_column("Tokens", justify="right")
        for s in sessions:
            table.add_row(
                s.id[:8],
                s.title or "(untitled)",
                getattr(s, "channel", "cli"),
                str(s.started_at)[:19] if s.started_at else "—",
                str(getattr(s, "total_tokens", "—")),
            )
        console.print(table)
    finally:
        await runtime.aclose()


@sessions_app.command("show")
def sessions_show(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Session ID (or prefix)"),
) -> None:
    """Show messages from a specific session."""
    _run(_sessions_show_impl(ctx.obj["config_path"], ctx.obj["profile"], session_id))


async def _sessions_show_impl(config_path: Path, profile: str, session_id: str) -> None:
    result = _load_or_die(config_path)
    runtime = await build_agent_runtime(profile, result.config)
    try:
        # Try to find session by prefix
        sessions = await runtime.memory_store.a_get_recent_sessions(n=100)
        matches = [s for s in sessions if s.id.startswith(session_id)]
        if not matches:
            raise CleanExit(f"No session matching '{session_id}'.")
        sid = matches[0].id

        messages = await runtime.memory_store.a_get_session_messages(sid, include_compressed_away=True)
        console.print(f"\n[bold]Session {sid[:8]}[/bold] ({len(messages)} messages)\n")
        for m in messages:
            if m.role == "user":
                console.print(f"[bold green]you>[/bold green] {m.content[:500]}")
            elif m.role == "assistant":
                console.print(f"[bold cyan]hermclaw>[/bold cyan] {m.content[:500]}")
            elif m.role == "tool":
                console.print(f"[dim]  (tool result: {m.content[:200]})[/dim]")
            console.print()
    finally:
        await runtime.aclose()


@sessions_app.command("export")
def sessions_export(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Session ID (or prefix)"),
    output: Path = typer.Option("session_export.json", help="Output file"),
) -> None:
    """Export a session to JSON."""
    _run(_sessions_export_impl(ctx.obj["config_path"], ctx.obj["profile"], session_id, output))


async def _sessions_export_impl(config_path: Path, profile: str, session_id: str, output: Path) -> None:
    import json as json_mod

    result = _load_or_die(config_path)
    runtime = await build_agent_runtime(profile, result.config)
    try:
        sessions = await runtime.memory_store.a_get_recent_sessions(n=100)
        matches = [s for s in sessions if s.id.startswith(session_id)]
        if not matches:
            raise CleanExit(f"No session matching '{session_id}'.")
        sid = matches[0].id

        messages = await runtime.memory_store.a_get_session_messages(sid, include_compressed_away=True)
        export = {
            "session_id": sid,
            "messages": [
                {"role": m.role, "content": m.content, "tool_calls": m.tool_calls}
                for m in messages
            ],
        }
        output.write_text(json_mod.dumps(export, indent=2), encoding="utf-8")
        console.print(f"Exported {len(messages)} messages to {output}")
    finally:
        await runtime.aclose()


# =============================================================================
# plugins
# =============================================================================

plugins_app = typer.Typer(help="Plugin management: list, install, uninstall, create plugins.")
app.add_typer(plugins_app, name="plugins")


@plugins_app.command("list")
def plugins_list(ctx: typer.Context) -> None:
    """List installed plugins."""
    from hermclaw.plugins import PluginManager

    pm = PluginManager()
    plugins = pm.list_plugins()
    if not plugins:
        console.print("No plugins installed. Use `hermclaw plugins install <git-url>` to add one.")
        return
    table = Table(title="Installed Plugins")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Enabled")
    for p in plugins:
        table.add_row(
            p["name"],
            p["version"],
            p["description"][:60],
            "[green]yes[/green]" if p["enabled"] else "[red]no[/red]",
        )
    console.print(table)


@plugins_app.command("install")
def plugins_install(
    ctx: typer.Context,
    source: str = typer.Argument(..., help="Git URL or local path"),
) -> None:
    """Install a plugin from a git repository."""
    from hermclaw.plugins import PluginManager

    pm = PluginManager()
    try:
        msg = pm.install_from_git(source)
        console.print(f"[green]{msg}[/green]")
    except Exception as exc:
        err_console.print(f"[red]Install failed: {exc}[/red]")
        raise typer.Exit(code=1)


@plugins_app.command("uninstall")
def plugins_uninstall(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Plugin name"),
) -> None:
    """Uninstall a plugin."""
    from hermclaw.plugins import PluginManager

    pm = PluginManager()
    if pm.uninstall(name):
        console.print(f"[green]Uninstalled plugin '{name}'[/green]")
    else:
        err_console.print(f"[red]Plugin '{name}' not found.[/red]")
        raise typer.Exit(code=1)


@plugins_app.command("create")
def plugins_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Plugin name"),
) -> None:
    """Create a new plugin template."""
    from hermclaw.plugins import PluginManager

    pm = PluginManager()
    path = pm.create_template(name)
    console.print(f"[green]Created plugin template at: {path}[/green]")
    console.print("Edit plugin.json and main.py to customize your plugin.")


# =============================================================================
# models
# =============================================================================


@app.command()
def models(ctx: typer.Context) -> None:
    """List all available models in the catalog."""
    from hermclaw.brain.model_catalog import ModelCatalog

    catalog = ModelCatalog()
    if ctx.obj["json"]:
        import json as json_mod
        console.print_json(data=[
            {"name": m.name, "provider": m.provider, "aliases": m.aliases,
             "context_window": m.context_window, "description": m.description}
            for m in catalog.list_all()
        ])
    else:
        table = Table(title="Available Models")
        table.add_column("Name", style="cyan")
        table.add_column("Provider")
        table.add_column("Aliases")
        table.add_column("Context", justify="right")
        table.add_column("Cost (in/out per 1M)")
        table.add_column("Description")
        for m in catalog.list_all():
            aliases = ", ".join(m.aliases) if m.aliases else "—"
            ctx_str = f"{m.context_window // 1000}K"
            cost = f"${m.input_cost_per_1m:.2f}/${m.output_cost_per_1m:.2f}" if m.input_cost_per_1m > 0 else "free/local"
            table.add_row(m.name, m.provider, aliases, ctx_str, cost, m.description[:50])
        console.print(table)


@app.command("setup")
def setup_command() -> None:
    """Interactive setup wizard — configure model provider, API keys, channels, and install."""
    from install import main as setup_main
    try:
        setup_main()
    except (ImportError, ModuleNotFoundError):
        # install.py is at project root, find it
        import importlib.util
        import inspect
        # Try relative to the project
        cli_dir = Path(inspect.getfile(inspect.currentframe())).resolve().parent.parent
        install_path = cli_dir / "install.py"
        if install_path.exists():
            spec = importlib.util.spec_from_file_location("install", str(install_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.main()
        else:
            console.print("[bold red]✗[/] Could not find install.py. Run `python install.py` from the project root instead.")
            raise typer.Exit(1)


@app.command("mcp-server")
def mcp_server_command(
    ctx: typer.Context,
) -> None:
    """Start an MCP server exposing Hermclaw tools via stdio.

    Connect from VS Code, Claude Desktop, or any MCP client.
    """
    from hermclaw.body.mcp_server import run_mcp_stdio

    async def _run_mcp() -> None:
        config = _load_config(ctx.obj["config_path"])
        runtime = await build_agent_runtime(ctx.obj["profile"], config)
        try:
            await run_mcp_stdio(runtime.tool_dispatcher)
        finally:
            await runtime.aclose()

    _run(_run_mcp())


def main_entrypoint() -> None:
    app()


if __name__ == "__main__":
    main_entrypoint()

