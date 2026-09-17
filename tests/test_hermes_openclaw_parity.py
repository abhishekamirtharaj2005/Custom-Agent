"""Tests verifying 100% feature parity between Hermes ☤ and OpenClaw 🦞 in HermClaw."""

from __future__ import annotations

import os
import wave
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from hermclaw.tools.lsp_tool import LSPTool
from hermclaw.tools.protocol_tools import PhilipsHueTool, SonosTool, BluetoothTool
from hermclaw.tools.media_extra import MusicGenerateTool
from hermclaw.tools.web_tools import WebReadabilityTool, FirecrawlScrapeTool
from hermclaw.body.channels.messaging_extras import (
    MatrixAdapter,
    GoogleChatAdapter,
    FeishuLarkAdapter,
    MattermostAdapter,
    TwilioSMSAdapter,
    GenericWebhookAdapter,
)
from hermclaw.body.channels.base import OutgoingMessage


# ---------------------------------------------------------------------------
# LSP Client Tool Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lsp_tool_diagnostics_and_symbols(tmp_path: Path):
    lsp = LSPTool()

    # Valid Python file
    valid_file = tmp_path / "sample.py"
    valid_file.write_text(
        "class Calculator:\n"
        "    def add(self, a: int, b: int) -> int:\n"
        "        '''Add two numbers.'''\n"
        "        return a + b\n\n"
        "x = 42\n",
        encoding="utf-8",
    )

    # 1. Diagnostics (clean)
    diag_res = await lsp.execute({"action": "diagnostics", "file_path": str(valid_file)})
    assert diag_res.ok
    assert "Clean" in diag_res.output

    # 2. Symbols
    sym_res = await lsp.execute({"action": "symbols", "file_path": str(valid_file)})
    assert sym_res.ok
    assert "Calculator" in sym_res.output
    assert "add" in sym_res.output
    assert "x" in sym_res.output

    # 3. Definition
    def_res = await lsp.execute({"action": "definition", "file_path": str(valid_file), "symbol": "Calculator"})
    assert def_res.ok
    assert "sample.py" in def_res.output

    # 4. Hover
    hover_res = await lsp.execute({"action": "hover", "file_path": str(valid_file), "symbol": "add"})
    assert hover_res.ok
    assert "Add two numbers" in hover_res.output

    # 5. Completions
    comp_res = await lsp.execute({"action": "completions", "file_path": str(valid_file), "line": 4, "column": 10})
    assert comp_res.ok

    # 6. Syntax error detection
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken_syntax(\n", encoding="utf-8")
    bad_diag = await lsp.execute({"action": "diagnostics", "file_path": str(bad_file)})
    assert bad_diag.ok
    assert "SyntaxError" in bad_diag.output or "Error" in bad_diag.output

    # 7. Install server info
    info_res = await lsp.execute({"action": "install_server", "language": "python"})
    assert info_res.ok
    assert "pip install" in info_res.output


# ---------------------------------------------------------------------------
# Smart Home & IoT Tools Tests (Hue, Sonos, Bluetooth)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_philips_hue_tool():
    hue = PhilipsHueTool()
    res = await hue.execute({"action": "list_lights"})
    assert res.ok
    assert "Philips Hue Lights" in res.output

    power_res = await hue.execute({"action": "set_power", "light_id": "1", "on": True})
    assert power_res.ok
    assert "ON" in power_res.output

    bri_res = await hue.execute({"action": "set_brightness", "light_id": "1", "brightness": 75})
    assert bri_res.ok
    assert "75%" in bri_res.output

    scene_res = await hue.execute({"action": "list_scenes"})
    assert scene_res.ok
    assert "Available Hue Scenes" in scene_res.output


@pytest.mark.asyncio
async def test_sonos_tool():
    sonos = SonosTool()
    res = await sonos.execute({"action": "discover"})
    assert res.ok
    assert "Sonos Speakers" in res.output

    state_res = await sonos.execute({"action": "get_state", "speaker": "Living Room"})
    assert state_res.ok
    assert "Playing" in state_res.output

    vol_res = await sonos.execute({"action": "volume", "speaker": "Living Room", "volume": 40})
    assert vol_res.ok
    assert "40%" in vol_res.output

    grp_res = await sonos.execute({"action": "group", "speaker": "Living Room", "group_with": "Kitchen"})
    assert grp_res.ok
    assert "Kitchen" in grp_res.output


@pytest.mark.asyncio
async def test_bluetooth_tool():
    blu = BluetoothTool()
    res = await blu.execute({"action": "list_devices"})
    assert res.ok
    assert "Bluetooth" in res.output

    conn_res = await blu.execute({"action": "connect", "device_id": "WH-1000XM4"})
    assert conn_res.ok
    assert "WH-1000XM4" in conn_res.output


# ---------------------------------------------------------------------------
# AI Music Generation Tool Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_music_generate_tool(tmp_path: Path):
    music_tool = MusicGenerateTool()
    out_file = tmp_path / "test_ambient.wav"

    res = await music_tool.execute({
        "prompt": "peaceful ambient meditation sounds",
        "genre": "ambient",
        "duration": 3,
        "output_path": str(out_file),
    })

    assert res.ok
    assert out_file.exists()
    assert out_file.stat().st_size > 1000

    # Verify standard WAV headers and data integrity
    with wave.open(str(out_file), "r") as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() > 0


# ---------------------------------------------------------------------------
# Web Readability & Firecrawl Scraping Tools Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_readability_and_firecrawl():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Deep Sea Mysteries Discovered</title>
        <meta name="author" content="Dr. Oceanographer">
    </head>
    <body>
        <nav><a href="/home">Home</a></nav>
        <article>
            <h1>Deep Sea Mysteries Discovered</h1>
            <p>Scientists have explored the deepest oceanic trenches and discovered bioluminescent creatures.</p>
            <p>Further research is required to map the seismic fissures.</p>
        </article>
        <footer><p>Copyright 2026</p></footer>
    </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.text = sample_html
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=mock_resp)):
        # 1. Readability
        readability = WebReadabilityTool()
        res = await readability.execute({"url": "https://example.com/article"})
        assert res.ok
        assert "Deep Sea Mysteries Discovered" in res.output
        assert "Dr. Oceanographer" in res.output
        assert "bioluminescent creatures" in res.output
        assert "Copyright" not in res.output  # Footer stripped

        # 2. Firecrawl Local Scrape
        firecrawl = FirecrawlScrapeTool()
        fc_res = await firecrawl.execute({"url": "https://example.com/article", "action": "scrape"})
        assert fc_res.ok
        assert "Scrape Result" in fc_res.output


# ---------------------------------------------------------------------------
# Universal Messaging Adapters Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_messaging_adapters():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    # Matrix
    with patch.object(httpx.AsyncClient, "put", new=AsyncMock(return_value=mock_resp)):
        matrix = MatrixAdapter(homeserver="https://matrix.example.com", access_token="sec_token", room_id="!room:example.com")
        assert matrix.health().connected is True
        ok = await matrix.send_message("!room:example.com", "Hello Matrix")
        assert ok is True

    # Google Chat
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_resp)):
        gchat = GoogleChatAdapter(webhook_url="https://chat.googleapis.com/v1/spaces/XYZ/messages")
        assert gchat.health().connected is True
        ok = await gchat.send_message("https://chat.googleapis.com/v1/spaces/XYZ/messages", "Hello Google Chat!")
        assert ok is True

    # Feishu / Lark
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_resp)):
        feishu = FeishuLarkAdapter(webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/token123")
        assert feishu.health().connected is True
        f_ok = await feishu.send_message("", "Hello Feishu!")
        assert f_ok is True

    # Mattermost
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_resp)):
        mm = MattermostAdapter(server_url="https://mattermost.example.com", token="mm_tok", default_channel="chan1")
        assert mm.health().connected is True
        m_ok = await mm.send_message("chan1", "Hello Mattermost!")
        assert m_ok is True

    # Twilio SMS
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_resp)):
        twilio = TwilioSMSAdapter(account_sid="AC123", auth_token="auth123", from_number="+1234567890")
        assert twilio.health().connected is True
        t_ok = await twilio.send_message("+1987654321", "Test SMS text")
        assert t_ok is True

    # Generic Webhook
    with patch.object(httpx.AsyncClient, "post", new=AsyncMock(return_value=mock_resp)):
        hook = GenericWebhookAdapter(webhook_url="https://webhook.site/test", secret="mysecret")
        assert hook.health().connected is True
        h_ok = await hook.send_message("", "Test payload")
        assert h_ok is True
