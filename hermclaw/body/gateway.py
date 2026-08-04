"""Gateway: the one long-running process `hermclaw serve` starts. Owns
the HTTP control API, every enabled channel adapter, and the scheduler.
Binds loopback by default; token-authenticates every request except
/health. Watches hermclaw.yaml and hot-reloads affected subsystems only
-- see _apply_config for exactly what can and can't be changed live.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
from pathlib import Path
from typing import Any, Optional

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hermclaw.body.agents_registry import AgentsRegistry
from hermclaw.body.channels import build_enabled_channels
from hermclaw.body.channels.base import ChannelAdapter, IncomingMessage, OutgoingMessage
from hermclaw.body.channels.web import WebChannel
from hermclaw.body.scheduler import HermclawScheduler, ProfileRuntime
from hermclaw.config import (
    ConfigLoadResult,
    ConfigWatcher,
    HermclawConfig,
    default_config_path,
    load_config,
)
from hermclaw.brain.profiles import ProfileManager
from hermclaw.runtime import AgentRuntime, build_agent_runtime, gateway_token
from hermclaw.security.secrets import redact, resolve_env_ref

logger = structlog.get_logger(__name__)

CHANNEL_NAMES = ("cli", "web", "telegram", "discord", "slack", "whatsapp")


def _enabled_channel_names(channels_config: Any) -> set[str]:
    return {name for name in CHANNEL_NAMES if getattr(channels_config, name).enabled}


def _channel_config_for(channels_config: Any, name: str) -> Any:
    return getattr(channels_config, name)


class Gateway:
    def __init__(self, config_path: Optional[Path] = None, profile_manager: Optional[ProfileManager] = None) -> None:
        self.config_path = config_path or default_config_path()
        self.pm = profile_manager or ProfileManager()
        self.app = FastAPI(title="Hermclaw Gateway")
        self.config: Optional[HermclawConfig] = None
        self.channels: dict[str, ChannelAdapter] = {}
        self.scheduler = HermclawScheduler()
        self.agents_registry: Optional[AgentsRegistry] = None
        self.runtimes: dict[str, AgentRuntime] = {}
        self._last_contact: dict[str, tuple[str, str]] = {}  # profile -> (channel, external_user_id)
        self._watcher: Optional[ConfigWatcher] = None
        self._watcher_task: Optional[asyncio.Task] = None
        self._started_at: Optional[datetime.datetime] = None
        self._register_routes()

    # ------------------------------------------------------------------
    # HTTP control API
    # ------------------------------------------------------------------

    def _register_routes(self) -> None:
        @self.app.middleware("http")
        async def auth_middleware(request: Request, call_next: Any) -> Any:
            if request.url.path == "/health" or request.url.path.startswith("/ws"):
                return await call_next(request)
            expected = gateway_token(self.config) if self.config else None
            if expected:
                header = request.headers.get("authorization", "")
                if header != f"Bearer {expected}":
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

        @self.app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @self.app.get("/status")
        async def status_endpoint() -> dict[str, Any]:
            return self.status_snapshot()

        @self.app.get("/config")
        async def get_config() -> dict[str, Any]:
            if self.config is None:
                return {}
            return redact(self.config.model_dump(by_alias=True))

        @self.app.post("/config")
        async def post_config(request: Request) -> JSONResponse:
            from hermclaw.config import _validate_dict, _yaml, save_config_text, ConfigWriteRefused

            raw_text = (await request.body()).decode("utf-8")
            try:
                parsed = dict(_yaml.load(raw_text) or {})
            except Exception as exc:
                return JSONResponse({"accepted": False, "errors": [f"YAML parse error: {exc}"]}, status_code=422)

            new_config, errors = _validate_dict(parsed)
            if new_config is None:
                return JSONResponse({"accepted": False, "errors": errors}, status_code=422)

            try:
                save_config_text(raw_text, self.config_path)
            except ConfigWriteRefused as exc:
                return JSONResponse({"accepted": False, "errors": [str(exc)]}, status_code=422)

            previous = self.config
            self.config = new_config
            await self._apply_config(new_config, previous)
            return JSONResponse({"accepted": True, "errors": []})

    def status_snapshot(self) -> dict[str, Any]:
        uptime_s = (
            (datetime.datetime.now(datetime.timezone.utc) - self._started_at).total_seconds()
            if self._started_at else 0
        )
        return {
            "uptime_s": uptime_s,
            "channels": {name: dataclasses.asdict(ch.health()) for name, ch in self.channels.items()},
            "profiles": sorted(self.runtimes.keys()),
            "config_path": str(self.config_path),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        result = load_config(self.config_path)
        if not result.valid:
            raise RuntimeError(
                f"Cannot start Hermclaw: config is invalid and no last-known-good copy is available.\n"
                f"Errors: {result.errors}\nRun `hermclaw doctor` for details."
            )
        self.config = result.config
        assert self.config is not None
        await self._apply_config(self.config, previous=None)
        self.scheduler.start()
        self._started_at = datetime.datetime.now(datetime.timezone.utc)
        self._watcher = ConfigWatcher(self.config_path, self._on_config_reload)
        self._watcher_task = asyncio.create_task(self._watcher.run())
        logger.info("gateway.started", config_path=str(self.config_path), channels=list(self.channels.keys()))

    async def stop(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
        if self._watcher_task is not None:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except (asyncio.CancelledError, Exception):
                pass
        for adapter in list(self.channels.values()):
            await adapter.stop()
        for runtime in list(self.runtimes.values()):
            await runtime.aclose()
        self.scheduler.shutdown()
        logger.info("gateway.stopped")

    async def _on_config_reload(self, result: ConfigLoadResult) -> None:
        if not result.valid:
            logger.error("gateway.config_reload_invalid", errors=result.errors, detail="keeping the previously running config")
            return
        previous = self.config
        self.config = result.config
        assert self.config is not None
        await self._apply_config(self.config, previous)

    # ------------------------------------------------------------------
    # Hot reload: restart only what actually changed
    # ------------------------------------------------------------------

    async def _apply_config(self, new_config: HermclawConfig, previous: Optional[HermclawConfig]) -> None:
        self.agents_registry = AgentsRegistry(new_config.agent)

        await self._apply_channels(new_config, previous)
        await self._apply_profiles(new_config, previous)
        self._apply_scheduler(new_config, previous)

        if previous is not None and new_config.body.gateway != previous.body.gateway:
            logger.warning(
                "gateway.restart_required",
                detail="body.gateway.* (host/port/auth) changed -- restart the gateway process to apply it",
            )

    async def _apply_channels(self, new_config: HermclawConfig, previous: Optional[HermclawConfig]) -> None:
        enabled_now = _enabled_channel_names(new_config.body.channels)
        enabled_before = _enabled_channel_names(previous.body.channels) if previous else set()

        for name in enabled_before - enabled_now:
            await self.channels[name].stop()
            del self.channels[name]

        changed = set()
        if previous:
            for name in enabled_now & enabled_before:
                if _channel_config_for(new_config.body.channels, name) != _channel_config_for(previous.body.channels, name):
                    changed.add(name)
        for name in changed:
            await self.channels[name].stop()

        to_start = (enabled_now - enabled_before) | changed
        if not to_start:
            return

        fresh = build_enabled_channels(new_config.body.channels, resolve_env_ref)
        for name in to_start:
            adapter = fresh.get(name)
            if adapter is None:
                continue
            if name == "web":
                adapter = WebChannel(app=self.app)  # share the gateway's one HTTP server/port
            adapter.on_receive = self._make_on_receive(name)
            await adapter.start()
            self.channels[name] = adapter
            logger.info("gateway.channel_started", channel=name)

    async def _apply_profiles(self, new_config: HermclawConfig, previous: Optional[HermclawConfig]) -> None:
        assert self.agents_registry is not None
        needed = set(self.agents_registry.profiles_in_use())

        for profile in list(self.runtimes.keys()):
            if profile not in needed:
                await self.runtimes[profile].aclose()
                self.scheduler.unregister_profile(profile)
                del self.runtimes[profile]

        rebuild_all = (
            previous is None
            or new_config.brain != previous.brain
            or new_config.tools != previous.tools
            or new_config.skills != previous.skills
        )
        for profile in needed:
            if profile in self.runtimes and not rebuild_all:
                continue
            if profile in self.runtimes:
                await self.runtimes[profile].aclose()
            self.runtimes[profile] = await build_agent_runtime(profile, new_config, self.pm)
            logger.info("gateway.profile_ready", profile=profile)

    def _apply_scheduler(self, new_config: HermclawConfig, previous: Optional[HermclawConfig]) -> None:
        assert self.agents_registry is not None
        heartbeat_interval_only = (
            previous is not None
            and new_config.body.scheduler.jobs == previous.body.scheduler.jobs
            and new_config.body.scheduler.heartbeat.enabled == previous.body.scheduler.heartbeat.enabled
            and new_config.body.scheduler.heartbeat.show_ok == previous.body.scheduler.heartbeat.show_ok
            and new_config.body.scheduler.heartbeat.show_alerts == previous.body.scheduler.heartbeat.show_alerts
            and new_config.body.scheduler.heartbeat.every != previous.body.scheduler.heartbeat.every
        )

        for entry in self.agents_registry.all_agents():
            runtime = self.runtimes.get(entry.profile)
            if runtime is None:
                continue
            prof_runtime = ProfileRuntime(
                profile=entry.profile, agent=runtime.agent, channels=self.channels,
                default_channel=self._default_channel_name(),
                default_reply_to=self._default_reply_to(entry.profile),
            )
            if heartbeat_interval_only and entry.profile in self.scheduler._profiles:
                self.scheduler._profiles[entry.profile] = prof_runtime
                self.scheduler.update_heartbeat_interval(entry.profile, new_config.body.scheduler.heartbeat.every)
            else:
                self.scheduler.register_profile(prof_runtime, new_config.body.scheduler.heartbeat, new_config.body.scheduler.jobs)

    # ------------------------------------------------------------------
    # Message routing
    # ------------------------------------------------------------------

    def _default_channel_name(self) -> str:
        for name in CHANNEL_NAMES:
            if name in self.channels:
                return name
        return "cli"

    def _default_reply_to(self, profile: str) -> str:
        contact = self._last_contact.get(profile)
        return contact[1] if contact else ""

    def _make_on_receive(self, channel_name: str) -> Any:
        async def on_receive(msg: IncomingMessage) -> None:
            assert self.agents_registry is not None
            agent_entry = self.agents_registry.resolve_for_message(channel_name, msg.account)
            self._last_contact[agent_entry.profile] = (channel_name, msg.external_user_id)

            runtime = self.runtimes.get(agent_entry.profile)
            if runtime is None:
                logger.warning("gateway.no_runtime_for_profile", profile=agent_entry.profile, channel=channel_name)
                return

            session_id = await runtime.memory_store.a_create_session(
                channel=channel_name, model=runtime.agent.model_config.model_name,
            )
            result = await runtime.agent.run_turn(session_id, msg.text)
            if result.text.strip():
                await self.channels[channel_name].send(OutgoingMessage(text=result.text, reply_to=msg.external_user_id))

        return on_receive
