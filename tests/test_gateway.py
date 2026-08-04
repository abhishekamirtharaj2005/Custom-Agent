from __future__ import annotations

import json

import pytest

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage
from hermclaw.body.gateway import Gateway
from hermclaw.config import default_config_path


class SyntheticChannel(ChannelAdapter):
    """Stands in for telegram/discord/slack/whatsapp -- the routing logic
    under test (Gateway._make_on_receive) is identical for all of them."""

    def __init__(self):
        super().__init__()
        self.sent = []
        self.started = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    async def send(self, message: OutgoingMessage):
        self.sent.append(message)

    def health(self):
        return ChannelHealth(connected=self.started)


@pytest.fixture
def gateway_config_no_cli(tmp_path, monkeypatch, anthropic_key_env):
    """A validated config with the interactive cli channel disabled --
    the test process has no real TTY to safely block on."""
    from hermclaw.config import load_config

    load_config()  # seed defaults at HERMCLAW_HOME
    path = default_config_path()
    text = path.read_text().replace("cli:\n      enabled: true", "cli:\n      enabled: false")
    path.write_text(text)
    return path


async def test_gateway_starts_with_expected_channels_and_profiles(gateway_config_no_cli) -> None:
    gw = Gateway()
    await gw.start()
    try:
        assert "cli" not in gw.channels
        assert "default" in gw.runtimes
    finally:
        await gw.stop()


async def test_health_and_status_routes(gateway_config_no_cli) -> None:
    from fastapi.testclient import TestClient

    gw = Gateway()
    await gw.start()
    try:
        client = TestClient(gw.app)
        assert client.get("/health").status_code == 200
        status = client.get("/status").json()
        assert "default" in status["profiles"]
    finally:
        await gw.stop()


async def test_config_route_never_leaks_real_secret_value(gateway_config_no_cli) -> None:
    from fastapi.testclient import TestClient

    gw = Gateway()
    await gw.start()
    try:
        client = TestClient(gw.app)
        body = client.get("/config").json()
        assert {"body", "brain", "tools", "agent", "skills"} <= set(body.keys())
        assert "sk-ant-fake-for-construction-only" not in json.dumps(body)
    finally:
        await gw.stop()


async def test_message_routing_through_synthetic_channel(gateway_config_no_cli) -> None:
    from hermclaw.brain.transports.fake import FakeTransport, text_response

    gw = Gateway()
    await gw.start()
    try:
        synth = SyntheticChannel()
        synth.on_receive = gw._make_on_receive("synthetic")
        gw.channels["synthetic"] = synth
        await synth.start()

        gw.runtimes["default"].agent.transport = FakeTransport(responses=[text_response("Hello! I'm Hermclaw, happy to help.")])

        await synth._emit(IncomingMessage(channel="synthetic", external_user_id="user-42", text="hi there"))
        assert synth.sent and "Hermclaw" in synth.sent[0].text
        assert synth.sent[0].reply_to == "user-42"
        assert gw._last_contact["default"] == ("synthetic", "user-42")
    finally:
        await gw.stop()


async def test_post_config_rejects_invalid_and_leaves_running_config_untouched(gateway_config_no_cli) -> None:
    from fastapi.testclient import TestClient

    gw = Gateway()
    await gw.start()
    try:
        client = TestClient(gw.app)
        r = client.post("/config", content="agent:\n  bogus_key_not_allowed: true\n")
        assert r.status_code == 422
        assert gw.config.tools.shell_enabled is False
    finally:
        await gw.stop()


async def test_post_config_hot_reloads_heartbeat_interval(gateway_config_no_cli) -> None:
    from fastapi.testclient import TestClient

    gw = Gateway()
    await gw.start()
    try:
        client = TestClient(gw.app)
        current_text = gateway_config_no_cli.read_text()
        new_text = current_text.replace('every: "30m"', 'every: "5m"')
        assert new_text != current_text

        r = client.post("/config", content=new_text)
        assert r.status_code == 200
        assert gw.config.body.scheduler.heartbeat.every == "5m"

        job = gw.scheduler._scheduler.get_job("heartbeat:default")
        assert job.trigger.interval.total_seconds() == 300
    finally:
        await gw.stop()
