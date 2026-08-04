from __future__ import annotations

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, OutgoingMessage
from hermclaw.body.scheduler import (
    HermclawScheduler,
    ProfileRuntime,
    classify_heartbeat_response,
    parse_duration,
    resolve_heartbeat_interval_s,
)
from hermclaw.brain.agent_loop import HermclawAgent
from hermclaw.brain.transports.fake import FakeTransport, text_response
from hermclaw.config import HeartbeatConfig, ModelConfig, SchedulerJobConfig
from hermclaw.tools.approvals import build_approval_gate
from hermclaw.tools.base import ToolDispatcher


class RecordingChannel(ChannelAdapter):
    def __init__(self):
        super().__init__()
        self.sent = []

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send(self, message):
        self.sent.append(message)

    def health(self):
        return ChannelHealth(connected=True)


def _build_runtime(profile_manager, profile_name, responses):
    paths = profile_manager.ensure_profile(profile_name)
    from hermclaw.brain.memory.store import MemoryStore
    from hermclaw.brain.profiles import IdentityFiles
    from hermclaw.skills.registry import SkillRegistry

    store = MemoryStore(paths.state_db)
    identity = IdentityFiles(paths)
    registry = SkillRegistry(directory=paths.skills_dir)
    registry.load()
    dispatcher = ToolDispatcher(build_approval_gate(mode="off"))
    transport = FakeTransport(responses=responses)
    agent = HermclawAgent(
        profile=profile_name, memory_store=store, identity_files=identity, skill_registry=registry,
        tool_dispatcher=dispatcher, transport=transport, model_config=ModelConfig(model_name="fake"),
    )
    channel = RecordingChannel()
    runtime = ProfileRuntime(profile=profile_name, agent=agent, channels={"cli": channel}, default_channel="cli", default_reply_to="local")
    return runtime, channel


def test_classify_heartbeat_response() -> None:
    assert classify_heartbeat_response("HEARTBEAT_OK") == ("ok", "")
    assert classify_heartbeat_response("") == ("ok", "")
    assert classify_heartbeat_response("[background] cleaned up temp files") == ("background", "cleaned up temp files")
    assert classify_heartbeat_response("Hey, your build failed!") == ("alert", "Hey, your build failed!")


def test_parse_duration() -> None:
    assert parse_duration("30m") == 1800
    assert parse_duration("2h") == 7200
    assert parse_duration("45s") == 45
    assert parse_duration("1d") == 86400


def test_heartbeat_interval_precedence() -> None:
    class FakeHB:
        def __init__(self, every):
            self.every = every

    assert resolve_heartbeat_interval_s(FakeHB("30m")) == 1800
    assert resolve_heartbeat_interval_s(FakeHB("30m"), account_override=FakeHB("5m")) == 300
    assert resolve_heartbeat_interval_s(FakeHB(None)) == 1800


async def test_heartbeat_ok_is_suppressed_by_default(profile_manager) -> None:
    runtime, channel = _build_runtime(profile_manager, "hb_ok", [text_response("HEARTBEAT_OK")])
    scheduler = HermclawScheduler()
    hb_cfg = HeartbeatConfig(enabled=True, every="30m", show_ok=False, show_alerts=True)
    scheduler.register_profile(runtime, hb_cfg, [])
    await scheduler._run_heartbeat("hb_ok", hb_cfg)
    assert channel.sent == []


async def test_heartbeat_alert_is_delivered(profile_manager) -> None:
    runtime, channel = _build_runtime(profile_manager, "hb_alert", [text_response("Your deploy failed, take a look!")])
    scheduler = HermclawScheduler()
    hb_cfg = HeartbeatConfig(enabled=True, every="30m", show_ok=False, show_alerts=True)
    scheduler.register_profile(runtime, hb_cfg, [])
    await scheduler._run_heartbeat("hb_alert", hb_cfg)
    assert len(channel.sent) == 1
    assert "deploy failed" in channel.sent[0].text


async def test_heartbeat_background_suppressed_unless_show_ok(profile_manager) -> None:
    runtime, channel = _build_runtime(profile_manager, "hb_bg", [text_response("[background] archived old logs")])
    scheduler = HermclawScheduler()
    hb_cfg = HeartbeatConfig(enabled=True, every="30m", show_ok=False, show_alerts=True)
    scheduler.register_profile(runtime, hb_cfg, [])
    await scheduler._run_heartbeat("hb_bg", hb_cfg)
    assert channel.sent == []


async def test_cron_job_always_delivered(profile_manager) -> None:
    runtime, channel = _build_runtime(profile_manager, "job_profile", [text_response("Here's your daily summary: all quiet.")])
    scheduler = HermclawScheduler()
    job_cfg = SchedulerJobConfig(cron="0 9 * * *", prompt="Summarize overnight activity", id="daily-summary")
    scheduler.register_profile(runtime, HeartbeatConfig(enabled=False), [job_cfg])
    await scheduler._run_scheduled_job("job_profile", job_cfg)
    assert len(channel.sent) == 1
    assert "daily summary" in channel.sent[0].text


async def test_heartbeat_hot_reload_reschedules_same_job(profile_manager) -> None:
    runtime, _channel = _build_runtime(profile_manager, "hb_reload", [text_response("HEARTBEAT_OK")])
    scheduler = HermclawScheduler()
    hb_cfg = HeartbeatConfig(enabled=True, every="30m", show_ok=False, show_alerts=True)
    scheduler.register_profile(runtime, hb_cfg, [])
    scheduler.start()
    try:
        job_before = scheduler._scheduler.get_job("heartbeat:hb_reload")
        scheduler.update_heartbeat_interval("hb_reload", "5m")
        job_after = scheduler._scheduler.get_job("heartbeat:hb_reload")
        assert job_before.id == job_after.id
        assert job_after.trigger.interval.total_seconds() == 300
    finally:
        scheduler.shutdown()
