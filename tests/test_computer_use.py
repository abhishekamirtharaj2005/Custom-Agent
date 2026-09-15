"""Tests for ComputerUseTool: screen awareness, mouse, keyboard, window management."""

from __future__ import annotations

import platform
from unittest.mock import MagicMock, patch
import pytest

from hermclaw.tools.code_exec import ComputerUseTool, ensure_default_desktop
from hermclaw.brain.agent_loop import _KEYWORD_TOOLS


@pytest.mark.asyncio
async def test_computer_use_tool_spec():
    tool = ComputerUseTool()
    spec = tool.spec()

    assert spec.name == "computer"
    assert spec.requires_approval_gate is True
    assert "Live Awareness" in spec.description
    assert "Mouse Control" in spec.description
    assert "Keyboard Control" in spec.description

    actions = spec.parameters["properties"]["action"]["enum"]
    expected_actions = [
        "see_screen",
        "screenshot",
        "click",
        "double_click",
        "right_click",
        "move_mouse",
        "drag",
        "scroll",
        "type",
        "paste",
        "key",
        "hotkey",
        "focus_window",
        "list_windows",
        "open_app",
    ]
    for action in expected_actions:
        assert action in actions


@pytest.mark.asyncio
async def test_see_screen_mocked():
    tool = ComputerUseTool()

    fake_pyautogui = MagicMock()
    fake_pyautogui.size.return_value = (1920, 1080)
    fake_pyautogui.position.return_value = MagicMock(x=500, y=300)
    fake_img = MagicMock()
    fake_pyautogui.screenshot.return_value = fake_img

    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        res = await tool.execute({"action": "see_screen"})
        assert res.ok is True
        assert "1920 x 1080" in res.output
        assert "500" in res.output or "x=500" in res.output


@pytest.mark.asyncio
async def test_mouse_actions():
    tool = ComputerUseTool()

    fake_pyautogui = MagicMock()
    fake_pyautogui.position.return_value = MagicMock(x=100, y=200)

    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui}):
        # Click
        res = await tool.execute({"action": "click", "x": 150, "y": 250, "button": "left"})
        assert res.ok is True
        assert "Clicked left button" in res.output
        fake_pyautogui.click.assert_called_with(x=150, y=250, button="left", clicks=1)

        # Double click
        res = await tool.execute({"action": "double_click", "x": 300, "y": 400})
        assert res.ok is True
        assert "Double-clicked at (300, 400)" in res.output
        fake_pyautogui.doubleClick.assert_called_with(x=300, y=400)

        # Right click
        res = await tool.execute({"action": "right_click", "x": 350, "y": 450})
        assert res.ok is True
        assert "Right-clicked at (350, 450)" in res.output
        fake_pyautogui.rightClick.assert_called_with(x=350, y=450)

        # Move mouse
        res = await tool.execute({"action": "move_mouse", "x": 600, "y": 700, "duration": 0.1})
        assert res.ok is True
        assert "Moved mouse to (600, 700)" in res.output
        fake_pyautogui.moveTo.assert_called_with(600, 700, duration=0.1)

        # Drag
        res = await tool.execute({"action": "drag", "x": 100, "y": 100, "to_x": 500, "to_y": 500})
        assert res.ok is True
        assert "Dragged mouse to (500, 500)" in res.output
        fake_pyautogui.dragTo.assert_called_with(500, 500, duration=0.3, button="left")

        # Scroll
        res = await tool.execute({"action": "scroll", "direction": "up", "clicks": 5})
        assert res.ok is True
        assert "Scrolled up 5 clicks" in res.output
        fake_pyautogui.scroll.assert_called_with(5)


@pytest.mark.asyncio
async def test_keyboard_actions():
    tool = ComputerUseTool()

    fake_pyautogui = MagicMock()
    fake_pyperclip = MagicMock()

    with patch.dict("sys.modules", {"pyautogui": fake_pyautogui, "pyperclip": fake_pyperclip}):
        # Type
        res = await tool.execute({"action": "type", "text": "Hello world!"})
        assert res.ok is True
        assert "Typed 12 characters" in res.output
        fake_pyautogui.typewrite.assert_called_with("Hello world!", interval=0.02)

        # Key press
        res = await tool.execute({"action": "key", "key": "enter"})
        assert res.ok is True
        assert "Pressed key: 'enter'" in res.output
        fake_pyautogui.press.assert_called_with("enter")

        # Hotkey
        res = await tool.execute({"action": "hotkey", "keys": "ctrl+shift+s"})
        assert res.ok is True
        assert "ctrl+shift+s" in res.output
        fake_pyautogui.hotkey.assert_called_with("ctrl", "shift", "s")

        # Paste
        res = await tool.execute({"action": "paste", "text": "Hi from Hermclaw! 💬"})
        assert res.ok is True
        assert "Pasted from clipboard" in res.output
        fake_pyperclip.copy.assert_called_with("Hi from Hermclaw! 💬")


@pytest.mark.asyncio
async def test_open_app_and_focus():
    tool = ComputerUseTool()

    with patch("subprocess.Popen") as mock_popen:
        # Launch WhatsApp
        res = await tool.execute({"action": "open_app", "target": "whatsapp"})
        assert res.ok is True
        assert "whatsapp" in res.output.lower()

        # Launch generic app
        res = await tool.execute({"action": "open_app", "target": "notepad"})
        assert res.ok is True
        assert "notepad" in res.output


def test_keyword_tool_routing():
    """Verify that screen, mouse, keyboard, and messaging keywords route to 'computer'."""
    assert "computer" in _KEYWORD_TOOLS.get("whatsapp", [])
    assert "computer" in _KEYWORD_TOOLS.get("mouse", [])
    assert "computer" in _KEYWORD_TOOLS.get("keyboard", [])
    assert "computer" in _KEYWORD_TOOLS.get("screen", [])
    assert "computer" in _KEYWORD_TOOLS.get("type", [])
    assert "computer" in _KEYWORD_TOOLS.get("paste", [])
    assert "computer" in _KEYWORD_TOOLS.get("window", [])
    assert "computer" in _KEYWORD_TOOLS.get("hotkey", [])
    assert "computer" in _KEYWORD_TOOLS.get("click", [])


@pytest.mark.asyncio
async def test_live_window_listing():
    """Live test that exercises real window listing without errors."""
    tool = ComputerUseTool()
    res = await tool.execute({"action": "list_windows"})
    assert res.ok is True
    assert "Open Windows" in res.output or "No visible windows" in res.output

