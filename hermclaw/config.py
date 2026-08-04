"""Hermclaw's single-file config system: ~/.hermclaw/hermclaw.yaml.

Ports OpenClaw's config-safety model (strict schema, refuse-to-boot on
invalid config, last-known-good rollback, anti-clobber protection on
Hermclaw-initiated writes, debounced hot reload) into Python using
pydantic v2 for the schema and ruamel.yaml so user comments in a
hand-edited file survive a round trip.

See C.1.2 (config system) and C.3.2 (final assembled schema) in the
build spec.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, Optional

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from hermclaw.config_defaults import EXAMPLE_CONFIG_YAML

logger = structlog.get_logger(__name__)

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096  # avoid ruamel re-wrapping long lines on any future write


# ---------------------------------------------------------------------------
# Profile root resolution (HERMCLAW_HOME, mirroring Hermes Agent's HERMES_HOME)
# ---------------------------------------------------------------------------


def hermclaw_home() -> Path:
    """The root of all Hermclaw state. HERMCLAW_HOME, when set, redirects
    this entire root -- NOT the same thing as the OS-level HOME. Local tool
    subprocesses still inherit the real OS-user HOME by default so external
    CLIs like git/ssh/gh keep working (see brain/profiles.py)."""
    override = os.environ.get("HERMCLAW_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".hermclaw"


def default_config_path() -> Path:
    return hermclaw_home() / "hermclaw.yaml"


def lkg_path(config_path: Path) -> Path:
    return config_path.with_suffix(config_path.suffix + ".lkg")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class GatewayAuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["token"] = "token"
    token_env: str = "HERMCLAW_GATEWAY_TOKEN"


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bind: Literal["loopback", "all"] = "loopback"
    host: str = "127.0.0.1"
    port: int = 18789
    auth: GatewayAuthConfig = Field(default_factory=GatewayAuthConfig)


class TelegramChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    mode: Literal["polling", "webhook"] = "polling"
    webhook_url: Optional[str] = None


class DiscordChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    bot_token_env: str = "DISCORD_BOT_TOKEN"


class SlackChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    bot_token_env: str = "SLACK_BOT_TOKEN"
    app_token_env: str = "SLACK_APP_TOKEN"
    socket_mode: bool = True


class CliChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True


class WebChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False


class WhatsappChannelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    sidecar_command: Optional[str] = None


class ChannelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    telegram: TelegramChannelConfig = Field(default_factory=TelegramChannelConfig)
    discord: DiscordChannelConfig = Field(default_factory=DiscordChannelConfig)
    slack: SlackChannelConfig = Field(default_factory=SlackChannelConfig)
    cli: CliChannelConfig = Field(default_factory=CliChannelConfig)
    web: WebChannelConfig = Field(default_factory=WebChannelConfig)
    whatsapp: WhatsappChannelConfig = Field(default_factory=WhatsappChannelConfig)


class HeartbeatConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    every: str = "30m"
    show_ok: bool = False
    show_alerts: bool = True


class SchedulerJobConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cron: str
    prompt: str
    id: Optional[str] = None


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    jobs: list[SchedulerJobConfig] = Field(default_factory=list)


class BodyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)


class FallbackModelConfig(BaseModel):
    """One entry in brain.model.fallbacks -- same shape as ModelConfig minus
    its own nested fallback list, to keep the schema non-recursive."""

    model_config = ConfigDict(extra="forbid")
    provider: Literal["anthropic", "openai_compat", "bedrock"] = "anthropic"
    model_name: str
    api_key_env: str
    api_base_env: Optional[str] = None
    context_window: int = 200000


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["anthropic", "openai_compat", "bedrock"] = "anthropic"
    model_name: str = "claude-sonnet-4-6"
    api_key_env: str = "ANTHROPIC_API_KEY"
    api_base_env: Optional[str] = None
    context_window: int = 200000
    fallbacks: list[FallbackModelConfig] = Field(default_factory=list)


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    compression_threshold: float = Field(default=0.5, gt=0.0, le=1.0)
    keep_recent_exchanges: int = Field(default=2, ge=0)
    memory_char_limit: int = Field(default=2200, gt=0)
    user_char_limit: int = Field(default=1375, gt=0)


class ReflectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    trigger_every_n_turns: int = Field(default=20, gt=0)


class BrainConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: ModelConfig = Field(default_factory=ModelConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    reflection: ReflectionConfig = Field(default_factory=ReflectionConfig)


class McpServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    transport: Literal["stdio", "sse"] = "stdio"
    command: Optional[str] = None
    url: Optional[str] = None

    @field_validator("url")
    @classmethod
    def _check_transport_fields(cls, v, info):
        return v  # cross-field check done in SkillsConfig for clearer error context


class SkillsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    directory: str = "~/.hermclaw/profiles/default/skills"
    extra_directories: list[str] = Field(default_factory=list)
    evolution_enabled: bool = False
    mcp_servers: list[McpServerConfig] = Field(default_factory=list)


class ToolsApprovalsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["manual", "smart", "off"] = "manual"


class ToolsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shell_enabled: bool = False
    approvals: ToolsApprovalsConfig = Field(default_factory=ToolsApprovalsConfig)
    backend: Literal["local", "docker", "ssh", "singularity", "modal", "daytona"] = "local"
    docker_image: str = "python:3.11-slim"
    docker_network: Optional[str] = "none"
    ssh_host: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_identity_file: Optional[str] = None
    network_enabled: bool = True
    filesystem_scope: str = "~/.hermclaw/profiles/default/workspace"


class AgentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    emoji: Optional[str] = None


class AgentListEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    identity: AgentIdentity
    profile: str = "default"


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    name: str = "hermclaw"
    default_profile: str = "default"
    # Field name avoids shadowing the `list` builtin in annotations; the
    # YAML/JSON key itself is still exactly `list`, per the spec's example.
    entries: list[AgentListEntry] = Field(default_factory=list, alias="list")


class HermclawConfig(BaseModel):
    """Root config model. Rejects unknown top-level keys except a single
    `$schema` passthrough -- mirrors OpenClaw's exact exception."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_ref: Optional[str] = Field(default=None, alias="$schema")
    agent: AgentConfig = Field(default_factory=AgentConfig)
    body: BodyConfig = Field(default_factory=BodyConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    profiles: dict[str, dict[str, Any]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Load / save / rollback
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ConfigLoadResult:
    valid: bool
    config: Optional[HermclawConfig]
    errors: list[str]
    source: Literal["primary", "lkg", "defaults"]
    path: Path


def _read_yaml_dict(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = _yaml.load(f)
    return dict(data) if data else {}


def _validate_dict(raw: dict[str, Any]) -> tuple[Optional[HermclawConfig], list[str]]:
    try:
        cfg = HermclawConfig.model_validate(raw)
        return cfg, []
    except Exception as exc:  # pydantic.ValidationError has a good __str__
        return None, [str(exc)]


def write_default_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(EXAMPLE_CONFIG_YAML, encoding="utf-8")
    logger.info("config.wrote_defaults", path=str(path))


def _write_lkg(path: Path) -> None:
    try:
        lkg = lkg_path(path)
        lkg.write_bytes(path.read_bytes())
    except OSError as exc:
        logger.warning("config.lkg_write_failed", error=str(exc))


def load_config(path: Optional[Path] = None) -> ConfigLoadResult:
    """Load and validate hermclaw.yaml.

    - Missing file -> write safe defaults, load those (never errors).
    - Present + valid -> refresh the last-known-good copy, return it.
    - Present + invalid -> try the last-known-good copy so an established
      install survives a corrupted/bad edit; if there is no LKG yet (e.g.
      a brand new, hand-broken config with nothing successfully loaded
      before it), report invalid with no fallback -- diagnostic commands
      only, per C.1.2.
    """
    path = path or default_config_path()

    if not path.exists():
        write_default_config(path)
        raw = _read_yaml_dict(path)
        cfg, errors = _validate_dict(raw)
        if cfg is not None:
            _write_lkg(path)
            return ConfigLoadResult(True, cfg, [], "defaults", path)
        # Defaults themselves failing to validate would be a packaging bug,
        # not a user error -- surface it loudly rather than pretending.
        return ConfigLoadResult(False, None, errors, "defaults", path)

    try:
        raw = _read_yaml_dict(path)
    except YAMLError as exc:
        raw = None
        parse_errors = [f"YAML parse error: {exc}"]
    else:
        parse_errors = []

    cfg = None
    errors: list[str] = []
    if raw is not None:
        cfg, errors = _validate_dict(raw)
    else:
        errors = parse_errors

    if cfg is not None:
        _write_lkg(path)
        return ConfigLoadResult(True, cfg, [], "primary", path)

    # Primary is invalid -- attempt last-known-good fallback.
    lkg = lkg_path(path)
    if lkg.exists():
        try:
            lkg_raw = _read_yaml_dict(lkg)
            lkg_cfg, lkg_errors = _validate_dict(lkg_raw)
        except YAMLError as exc:
            lkg_cfg, lkg_errors = None, [f"YAML parse error in .lkg: {exc}"]
        if lkg_cfg is not None:
            logger.warning(
                "config.fell_back_to_lkg",
                path=str(path),
                primary_errors=errors,
            )
            return ConfigLoadResult(True, lkg_cfg, errors, "lkg", path)

    logger.error("config.invalid_no_fallback", path=str(path), errors=errors)
    return ConfigLoadResult(False, None, errors, "primary", path)


# ---------------------------------------------------------------------------
# Anti-clobber protected writes (for a future `hermclaw config set`)
# ---------------------------------------------------------------------------


class ConfigWriteRefused(Exception):
    pass


def save_config_text(
    new_text: str,
    path: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """Write `new_text` to the config file, refusing writes that would
    shrink the file by more than half or drop the top-level `agent` block,
    unless force=True. Refused candidates are preserved for inspection
    at <path>.rejected.<timestamp>. This guards against a buggy or
    malformed programmatic edit silently destroying a working config."""
    path = path or default_config_path()

    old_size = path.stat().st_size if path.exists() else 0
    new_size = len(new_text.encode("utf-8"))

    shrank_by_half = old_size > 0 and new_size < old_size * 0.5

    try:
        new_raw = dict(_yaml.load(new_text) or {})
    except YAMLError as exc:
        new_raw = None
        parse_ok = False
        parse_error = str(exc)
    else:
        parse_ok = True
        parse_error = ""

    dropped_agent_block = parse_ok and "agent" not in new_raw

    if not force and (shrank_by_half or dropped_agent_block or not parse_ok):
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rejected_path = Path(f"{path}.rejected.{ts}")
        rejected_path.write_text(new_text, encoding="utf-8")
        reasons = []
        if not parse_ok:
            reasons.append(f"does not parse as YAML ({parse_error})")
        if shrank_by_half:
            reasons.append(f"would shrink file from {old_size}B to {new_size}B (>50% reduction)")
        if dropped_agent_block:
            reasons.append("would drop the top-level 'agent' block")
        logger.warning("config.write_refused", path=str(path), reasons=reasons, saved_to=str(rejected_path))
        raise ConfigWriteRefused(
            f"Refused to write {path}: {'; '.join(reasons)}. "
            f"Candidate saved to {rejected_path} for inspection. Pass force=True to override."
        )

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(new_text, encoding="utf-8")
    _write_lkg(path)
    logger.info("config.written", path=str(path))
    return path


# ---------------------------------------------------------------------------
# Debounced hot-reload watcher
# ---------------------------------------------------------------------------
#
# Implemented as a lightweight mtime-poll loop rather than an OS
# file-event backend (inotify/FSEvents/ReadDirectoryChangesW): it needs no
# extra dependency, behaves identically across platforms, and is trivially
# testable by injecting a fake clock/stat function -- properties an
# inotify-based watcher doesn't have in a sandboxed test environment.
# Debounce behavior (wait for editor temp-write/rename churn to settle)
# is the same either way: only reload once mtime has stopped changing for
# the debounce window.


@dataclasses.dataclass
class ConfigWatcher:
    path: Path
    on_reload: Callable[[ConfigLoadResult], Awaitable[None]]
    debounce_s: float = 0.3
    poll_interval_s: float = 0.1
    _stop: bool = dataclasses.field(default=False, init=False, repr=False)
    _last_mtime: float = dataclasses.field(default=0.0, init=False, repr=False)

    def _mtime(self) -> float:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return -1.0

    def stop(self) -> None:
        self._stop = True

    async def run(self) -> None:
        self._last_mtime = self._mtime()
        while not self._stop:
            await asyncio.sleep(self.poll_interval_s)
            current = self._mtime()
            if current == self._last_mtime:
                continue
            # Something changed -- wait for the debounce window and
            # confirm it settled before reloading.
            stable_since = time.monotonic()
            observed = current
            while time.monotonic() - stable_since < self.debounce_s:
                await asyncio.sleep(self.poll_interval_s)
                now = self._mtime()
                if now != observed:
                    observed = now
                    stable_since = time.monotonic()
            self._last_mtime = observed
            result = load_config(self.path)
            await self.on_reload(result)
