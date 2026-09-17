"""Tests for ScreenVisionTool: UI element finding, screen watching, macro recording/playback."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from hermclaw.tools.screen_vision import ScreenVisionTool


@pytest.mark.asyncio
async def test_screen_vision_spec():
    tool = ScreenVisionTool()
    spec = tool.spec()
    assert spec.name == "screen_vision"
    assert spec.requires_approval_gate is True
    actions = spec.parameters["properties"]["action"]["enum"]
    assert "find_element" in actions
    assert "click_element" in actions
    assert "watch_screen" in actions
    assert "record_macro" in actions
    assert "stop_macro" in actions
    assert "play_macro" in actions
    assert "export_macro_skill" in actions


@pytest.mark.asyncio
async def test_find_and_click_element_mocked():
    tool = ScreenVisionTool()

    fake_match = {
        "text": "Send Message",
        "window": "WhatsApp",
        "bounds": [100, 200, 80, 30],
        "center_x": 140,
        "center_y": 215,
        "confidence": 1.0,
    }

    with patch.object(tool, "_search_ui_text", return_value=[fake_match]):
        # Test find_element
        res_find = await tool.execute({"action": "find_element", "target_text": "Send Message"})
        assert res_find.ok is True
        assert "Found 1 match" in res_find.output
        assert "(140, 215)" in res_find.output

        # Test click_element with mocked pyautogui
        fake_pyautogui = MagicMock()
        with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
            res_click = await tool.execute({"action": "click_element", "target_text": "Send Message"})
            assert res_click.ok is True
            assert "Successfully clicked 'Send Message'" in res_click.output
            fake_pyautogui.click.assert_called_with(140, 215)


@pytest.mark.asyncio
async def test_watch_screen_detects_target():
    tool = ScreenVisionTool()

    fake_match = {
        "text": "Download Complete",
        "window": "Browser",
        "bounds": [0, 0, 500, 400],
        "center_x": 250,
        "center_y": 200,
        "confidence": 1.0,
    }

    with patch.object(tool, "_search_ui_text", return_value=[fake_match]):
        res = await tool.execute({
            "action": "watch_screen",
            "target_text": "Download Complete",
            "timeout_seconds": 2.0,
            "poll_interval": 0.1,
        })
        assert res.ok is True
        assert "detected after" in res.output


@pytest.mark.asyncio
async def test_macro_record_play_and_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    tool = ScreenVisionTool()

    # 1. Start recording
    rec_res = await tool.execute({"action": "record_macro", "macro_name": "test_flow"})
    assert rec_res.ok is True
    assert "Started macro recording" in rec_res.output

    # 2. Stop recording
    stop_res = await tool.execute({"action": "stop_macro"})
    assert stop_res.ok is True
    assert "recorded" in stop_res.output

    # 3. Play macro with event JSON
    events = [
        {"type": "move", "x": 100, "y": 200, "delay": 0.01},
        {"type": "click", "x": 100, "y": 200, "delay": 0.01},
        {"type": "type", "text": "test", "delay": 0.01},
    ]
    fake_pyautogui = MagicMock()
    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        play_res = await tool.execute({
            "action": "play_macro",
            "events": json.dumps(events),
            "speed": 2.0,
        })
        assert play_res.ok is True
        assert "Successfully replayed 3 events" in play_res.output

    # 4. Export skill
    export_res = await tool.execute({"action": "export_macro_skill", "macro_name": "test_flow"})
    assert export_res.ok is True
    assert "Exported macro as skill" in export_res.output
