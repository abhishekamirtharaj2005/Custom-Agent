"""Scheduler: runs the heartbeat (a periodic "check in on things" agent
turn) and any user-configured cron jobs, via APScheduler's AsyncIOScheduler.

Each tick runs one real HermclawAgent turn -- the same loop, same tools,
same memory as an interactive chat -- in a dedicated session so it never
pollutes a user's actual conversation history. The heartbeat's result is
classified into three outcomes so routine ticks don't spam the user:

  - "ok"         nothing needed attention -> suppressed unless show_ok
  - "background" the agent did something via tools, nothing to relay ->
                 suppressed unless show_ok (logged either way)
  - "alert"      the agent has something for the user -> delivered
                 unless show_alerts is off

Regular scheduler.jobs entries have no such suppression: they're an
explicit, user-authored instruction, so their output is always delivered.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from hermclaw.body.channels.base import ChannelAdapter, OutgoingMessage
from hermclaw.brain.agent_loop import HermclawAgent

logger = structlog.get_logger(__name__)

_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
BUILTIN_DEFAULT_HEARTBEAT_S = 1800  # 30m, matches the documented built-in default

HEARTBEAT_INSTRUCTION = (
    "[This is a scheduled heartbeat check, not a message from the user -- they can't see this prompt. "
    "Use your available tools to review anything pending. Reply with exactly HEARTBEAT_OK if nothing needs "
    "attention. If you did routine background work with nothing the user needs to know, prefix your reply "
    "with '[background]'. Otherwise, write a brief message for the user -- it will be delivered to them "
    "directly, so write it as if speaking to them.]"
)


def parse_duration(text: str) -> int:
    match = _DURATION_RE.match(text.strip())
    if not match:
        raise ValueError(f"Invalid duration {text!r} -- expected e.g. '30m', '2h', '45s', '1d'")
    value, unit = match.groups()
    return int(value) * _UNIT_SECONDS[unit]


def resolve_heartbeat_interval_s(
    channel_default: Any,
    profile_override: Optional[Any] = None,
    channel_override: Optional[Any] = None,
    account_override: Optional[Any] = None,
) -> int:
    """Precedence: per-account > per-channel > profile > global default >
    built-in fallback. Only the global tier (body.scheduler.heartbeat) is
    populated by Hermclaw's current config schema; the per-channel and
    per-account parameters are accepted as forward-compatible hooks for a
    future config extension -- see MERGE_DECISIONS.md."""
    for cfg in (account_override, channel_override, profile_override, channel_default):
        if cfg is not None and getattr(cfg, "every", None):
            return parse_duration(cfg.every)
    return BUILTIN_DEFAULT_HEARTBEAT_S


def classify_heartbeat_response(text: str) -> tuple[str, str]:
    stripped = (text or "").strip()
    if not stripped or stripped == "HEARTBEAT_OK":
        return "ok", ""
    if stripped.startswith("[background]"):
        return "background", stripped[len("[background]"):].strip()
    return "alert", stripped


@dataclasses.dataclass
class ProfileRuntime:
    """Everything the scheduler needs to run a turn for one profile and
    deliver the result somewhere."""

    profile: str
    agent: HermclawAgent
    channels: dict[str, ChannelAdapter]
    default_channel: str
    default_reply_to: str


class HermclawScheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._profiles: dict[str, ProfileRuntime] = {}
        self._heartbeat_job_ids: dict[str, str] = {}

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def register_profile(self, runtime: ProfileRuntime, heartbeat_config: Any, jobs: list[Any]) -> None:
        self._profiles[runtime.profile] = runtime

        if heartbeat_config.enabled:
            interval_s = resolve_heartbeat_interval_s(heartbeat_config)
            job_id = f"heartbeat:{runtime.profile}"
            self._scheduler.add_job(
                self._run_heartbeat, "interval", seconds=interval_s,
                args=[runtime.profile, heartbeat_config], id=job_id, replace_existing=True,
            )
            self._heartbeat_job_ids[runtime.profile] = job_id

        for i, job_cfg in enumerate(jobs):
            job_id = job_cfg.id or f"job:{runtime.profile}:{i}"
            self._scheduler.add_job(
                self._run_scheduled_job, CronTrigger.from_crontab(job_cfg.cron),
                args=[runtime.profile, job_cfg], id=job_id, replace_existing=True,
            )

    def update_heartbeat_interval(self, profile: str, new_every: str) -> None:
        """Hot-reload support (C.1.2/C.1.4): a config edit that only
        changes the heartbeat interval reschedules in place, no gateway
        restart required."""
        job_id = self._heartbeat_job_ids.get(profile)
        if not job_id:
            return
        self._scheduler.reschedule_job(job_id, trigger="interval", seconds=parse_duration(new_every))

    def unregister_profile(self, profile: str) -> None:
        job_id = self._heartbeat_job_ids.pop(profile, None)
        if job_id:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        self._profiles.pop(profile, None)

    async def _run_heartbeat(self, profile: str, heartbeat_config: Any) -> None:
        runtime = self._profiles.get(profile)
        if runtime is None:
            return
        try:
            session_id = await runtime.agent.memory_store.a_create_session(
                channel="heartbeat", model=runtime.agent.model_config.model_name,
            )
            result = await runtime.agent.run_turn(session_id, HEARTBEAT_INSTRUCTION)
            status, payload = classify_heartbeat_response(result.text)
            logger.info("scheduler.heartbeat_tick", profile=profile, status=status)
            if status == "alert" and heartbeat_config.show_alerts:
                await self._deliver(runtime, payload)
            elif status in ("ok", "background") and heartbeat_config.show_ok:
                await self._deliver(runtime, payload or "heartbeat OK")
        except Exception:
            logger.exception("scheduler.heartbeat_failed", profile=profile)

    async def _run_scheduled_job(self, profile: str, job_cfg: Any) -> None:
        runtime = self._profiles.get(profile)
        if runtime is None:
            return
        try:
            session_id = await runtime.agent.memory_store.a_create_session(
                channel="scheduled_job", model=runtime.agent.model_config.model_name,
            )
            result = await runtime.agent.run_turn(session_id, job_cfg.prompt)
            if result.text.strip():
                await self._deliver(runtime, result.text)
        except Exception:
            logger.exception("scheduler.job_failed", profile=profile, job_id=getattr(job_cfg, "id", None))

    async def _deliver(self, runtime: ProfileRuntime, text: str) -> None:
        channel = runtime.channels.get(runtime.default_channel)
        if channel is None:
            logger.warning("scheduler.no_delivery_channel", profile=runtime.profile, default_channel=runtime.default_channel)
            return
        await channel.send(OutgoingMessage(text=text, reply_to=runtime.default_reply_to))
