"""One shared lifecycle pattern (start -> inbound -> outbound -> stop)
exercised against every channel adapter. The network-touching adapters
(telegram, discord, slack, whatsapp) get their underlying client/process
injected as a lightweight fake -- see each adapter's constructor -- so
the exact same wiring gets tested without a real socket anywhere.
"""

from __future__ import annotations

import asyncio
import json

from hermclaw.body.channels.base import IncomingMessage, OutgoingMessage
from hermclaw.body.channels.cli_channel import CliChannel
from hermclaw.body.channels.discord import DiscordChannel
from hermclaw.body.channels.slack import SlackChannel
from hermclaw.body.channels.telegram import TelegramChannel
from hermclaw.body.channels.whatsapp import WhatsAppChannel


async def test_cli_channel_lifecycle() -> None:
    received = []

    async def on_receive(msg):
        received.append(msg)

    lines = iter(["hello there", "  ", "second message", None])

    async def fake_reader():
        return next(lines)

    outputs = []
    channel = CliChannel(reader=fake_reader, writer=outputs.append)
    channel.on_receive = on_receive

    await channel.start()
    await asyncio.sleep(0.05)
    await channel.send(OutgoingMessage(text="hi back", reply_to="local"))
    await channel.stop()

    assert outputs == ["hi back"]
    assert len(received) == 2
    assert received[0].text == "hello there"
    assert received[1].text == "second message"
    assert channel.health().connected is False


async def test_web_channel_lifecycle() -> None:
    from fastapi.testclient import TestClient

    from hermclaw.body.channels.web import WebChannel

    received = []

    async def on_receive(msg):
        received.append(msg)

    channel = WebChannel()
    channel.on_receive = on_receive
    await channel.start()
    assert channel.health().connected is True

    client = TestClient(channel.app)
    assert client.get("/").status_code == 200

    with client.websocket_connect("/ws") as ws:
        ws.send_text("hello from browser")
        import time

        time.sleep(0.1)
        assert len(received) == 1
        conn_id = received[0].external_user_id
        await channel.send(OutgoingMessage(text="hi back", reply_to=conn_id))
        assert ws.receive_text() == "hi back"

    await channel.stop()
    assert channel.health().connected is False


class _FakeUpdater:
    def __init__(self):
        self.polling_started = False
        self.stopped = False

    async def start_polling(self):
        self.polling_started = True

    async def stop(self):
        self.stopped = True


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


class _FakeTelegramApp:
    def __init__(self):
        self.handlers = []
        self.updater = _FakeUpdater()
        self.bot = _FakeBot()

    def add_handler(self, h):
        self.handlers.append(h)

    async def initialize(self):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    async def shutdown(self):
        pass


async def test_telegram_channel_lifecycle() -> None:
    received = []

    async def on_receive(msg):
        received.append(msg)

    fake_app = _FakeTelegramApp()
    channel = TelegramChannel(bot_token="fake-token", application=fake_app)
    channel.on_receive = on_receive

    await channel.start()
    assert fake_app.updater.polling_started
    assert len(fake_app.handlers) == 1

    callback = fake_app.handlers[0].callback

    class FakeChat:
        id = 555

    class FakeMsg:
        text = "hi from telegram"

    class FakeUpdate:
        message = FakeMsg()
        effective_chat = FakeChat()

    await callback(FakeUpdate(), None)
    await channel.send(OutgoingMessage(text="reply", reply_to="555"))
    await channel.stop()

    assert fake_app.updater.stopped
    assert fake_app.bot.sent == [(555, "reply")]
    assert received[0].text == "hi from telegram"
    assert received[0].external_user_id == "555"


class _FakeDiscordChannelObj:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


class _FakeDiscordClient:
    def __init__(self):
        self.user = None
        self._channel = _FakeDiscordChannelObj()
        self.closed = False
        self._on_message = None

    def event(self, fn):
        self._on_message = fn
        return fn

    async def start(self, token):
        await asyncio.sleep(3600)

    async def close(self):
        self.closed = True

    def get_channel(self, cid):
        return self._channel


async def test_discord_channel_lifecycle() -> None:
    received = []

    async def on_receive(msg):
        received.append(msg)

    fake_client = _FakeDiscordClient()
    channel = DiscordChannel(bot_token="fake-token", client=fake_client)
    channel.on_receive = on_receive

    await channel.start()
    await asyncio.sleep(0.01)
    assert fake_client._on_message is not None  # handler registration must happen even with an injected client

    class FakeAuthor:
        id = 999

    class FakeChannelRef:
        id = 42

    class FakeDiscordMsg:
        author = FakeAuthor()
        channel = FakeChannelRef()
        content = "hi from discord"

    await fake_client._on_message(FakeDiscordMsg())
    await channel.send(OutgoingMessage(text="reply", reply_to="42"))
    await channel.stop()

    assert fake_client.closed
    assert fake_client._channel.sent == ["reply"]
    assert received[0].text == "hi from discord"


class _FakeSlackClient:
    def __init__(self):
        self.posted = []

    async def chat_postMessage(self, channel, text):
        self.posted.append((channel, text))


class _FakeSlackApp:
    def __init__(self):
        self.client = _FakeSlackClient()
        self._event_handlers = {}

    def event(self, name):
        def deco(fn):
            self._event_handlers[name] = fn
            return fn

        return deco


class _FakeSocketHandler:
    def __init__(self, app, token):
        self.app = app
        self.connected = False
        self.disconnected = False

    async def connect_async(self):
        self.connected = True

    async def disconnect_async(self):
        self.disconnected = True


async def test_slack_channel_lifecycle() -> None:
    received = []

    async def on_receive(msg):
        received.append(msg)

    fake_app = _FakeSlackApp()
    fake_handler = _FakeSocketHandler(fake_app, "fake-app-token")
    channel = SlackChannel(bot_token="fake-bot", app_token="fake-app", app=fake_app, handler=fake_handler)
    channel.on_receive = on_receive

    await channel.start()
    assert fake_handler.connected
    assert "message" in fake_app._event_handlers  # handler registration must happen even with an injected app

    await fake_app._event_handlers["message"]({"text": "hi from slack", "channel": "C123"}, say=None)
    await channel.send(OutgoingMessage(text="reply", reply_to="C123"))
    await channel.stop()

    assert fake_handler.disconnected
    assert fake_app.client.posted == [("C123", "reply")]
    assert received[0].text == "hi from slack"


class _FakeStreamWriter:
    def __init__(self, on_line=None):
        self.written = []
        self._on_line = on_line

    def write(self, data):
        self.written.append(data)
        if self._on_line:
            self._on_line(data)

    async def drain(self):
        pass


class _FakeStreamReader:
    def __init__(self, initial_lines):
        self._queue: asyncio.Queue = asyncio.Queue()
        for line in initial_lines:
            self._queue.put_nowait(line)

    def push(self, line):
        self._queue.put_nowait(line)

    async def readline(self):
        return await self._queue.get()


class _FakeWhatsAppProcess:
    def __init__(self, incoming_lines):
        self.stdout = _FakeStreamReader(incoming_lines)

        def on_line(data):
            req = json.loads(data.decode())
            if req.get("method") == "send":
                resp = (json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": {"ok": True}}) + "\n").encode()
                self.stdout.push(resp)

        self.stdin = _FakeStreamWriter(on_line=on_line)

    def terminate(self):
        pass

    async def wait(self):
        return 0


async def test_whatsapp_channel_lifecycle() -> None:
    received = []

    async def on_receive(msg):
        received.append(msg)

    incoming = [
        (json.dumps({"jsonrpc": "2.0", "method": "status", "params": {"connected": True}}) + "\n").encode(),
        (json.dumps({"jsonrpc": "2.0", "method": "message", "params": {"from": "123@s.whatsapp.net", "text": "hi from whatsapp"}}) + "\n").encode(),
    ]
    fake_proc = _FakeWhatsAppProcess(incoming)
    channel = WhatsAppChannel(process=fake_proc)
    channel.on_receive = on_receive

    await channel.start()
    await asyncio.sleep(0.05)
    assert channel.health().connected is True
    assert received[0].text == "hi from whatsapp"

    await channel.send(OutgoingMessage(text="reply", reply_to="123@s.whatsapp.net"))
    sent_payload = json.loads(fake_proc.stdin.written[0].decode())
    assert sent_payload["method"] == "send"
    assert sent_payload["params"] == {"to": "123@s.whatsapp.net", "text": "reply"}

    await channel.stop()
    assert channel.health().connected is False
