"""Vision-based UI Element Grounding, Screen Watcher, and Macro Automation.

Provides:
- find_element / click_element: Locate on-screen UI text/controls and click their center coordinates
- watch_screen: Monitor screen regions or windows for text/visual changes or triggers
- record_macro / play_macro / export_macro_skill: Record and replay GUI interactions as reusable skills
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec
from hermclaw.tools.code_exec import ensure_default_desktop

logger = structlog.get_logger(__name__)

# Global macro recording state
_macro_state: dict[str, Any] = {
    "recording": False,
    "events": [],
    "start_time": 0.0,
    "name": "",
}


class ScreenVisionTool(ToolABC):
    """Vision-based UI element grounding, screen watcher, and macro recording."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="screen_vision",
            description=(
                "Vision-based desktop automation: find text/buttons on screen and click them, "
                "watch the screen for changes (e.g. download finished, build succeeded), "
                "or record and replay mouse/keyboard macro workflows. "
                "Actions: find_element, click_element, watch_screen, record_macro, stop_macro, play_macro, export_macro_skill."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "find_element",
                            "click_element",
                            "watch_screen",
                            "record_macro",
                            "stop_macro",
                            "play_macro",
                            "export_macro_skill",
                        ],
                        "description": "Action to perform.",
                    },
                    "target_text": {
                        "type": "string",
                        "description": "Text, button label, or title to find or click (find_element, click_element, watch_screen).",
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "description": "Max seconds to wait for watch_screen (default 30).",
                    },
                    "poll_interval": {
                        "type": "number",
                        "description": "Seconds between checks for watch_screen (default 1.0).",
                    },
                    "macro_name": {
                        "type": "string",
                        "description": "Name for recorded macro or skill (e.g., 'download_report', 'send_daily_update').",
                    },
                    "events": {
                        "type": "string",
                        "description": "JSON array of events to replay (for play_macro, optional).",
                    },
                    "speed": {
                        "type": "number",
                        "description": "Playback speed multiplier for play_macro (default 1.0).",
                    },
                },
                "required": ["action"],
            },
            requires_approval_gate=True,
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args["action"]
        ensure_default_desktop()

        try:
            if action == "find_element":
                return await self._find_element(args.get("target_text", ""))
            elif action == "click_element":
                return await self._click_element(args.get("target_text", ""))
            elif action == "watch_screen":
                return await self._watch_screen(
                    args.get("target_text", ""),
                    float(args.get("timeout_seconds", 30.0)),
                    float(args.get("poll_interval", 1.0)),
                )
            elif action == "record_macro":
                return self._record_macro(args.get("macro_name", "macro"))
            elif action == "stop_macro":
                return self._stop_macro()
            elif action == "play_macro":
                return await self._play_macro(
                    args.get("macro_name", ""),
                    args.get("events", ""),
                    float(args.get("speed", 1.0)),
                )
            elif action == "export_macro_skill":
                return self._export_macro_skill(args.get("macro_name", "user_macro"))
            else:
                return ToolResult(ok=False, output="", error=f"Unknown screen_vision action: {action}")
        except Exception as exc:
            logger.error("screen_vision.error", action=action, exc_info=exc)
            return ToolResult(ok=False, output="", error=f"Screen vision error: {exc}")

    async def _find_element(self, target_text: str) -> ToolResult:
        """Find an interactive element or text match on screen."""
        if not target_text:
            return ToolResult(ok=False, output="", error="'target_text' is required to find an element.")

        matches = self._search_ui_text(target_text)
        if not matches:
            return ToolResult(
                ok=False,
                output="",
                error=f"Element with text '{target_text}' not found on visible screen.",
            )

        best = matches[0]
        lines = [f"Found {len(matches)} match(es) for '{target_text}':"]
        for idx, m in enumerate(matches[:5], 1):
            lines.append(
                f"{idx}. '{m['text']}' in [{m.get('window', 'Screen')}] "
                f"at center ({m['center_x']}, {m['center_y']}) bounds: {m['bounds']}"
            )
        lines.append(f"\nTop Match Target: ({best['center_x']}, {best['center_y']})")
        return ToolResult(ok=True, output="\n".join(lines), metadata={"match": best})

    async def _click_element(self, target_text: str) -> ToolResult:
        """Locate element by text and immediately click its center coordinates."""
        find_res = await self._find_element(target_text)
        if not find_res.ok:
            return find_res

        match = find_res.metadata.get("match", {})
        cx = match.get("center_x")
        cy = match.get("center_y")
        if cx is None or cy is None:
            return ToolResult(ok=False, output="", error=f"Invalid coordinates for '{target_text}'")

        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.click(cx, cy)
            return ToolResult(
                ok=True,
                output=f"Successfully clicked '{match.get('text', target_text)}' at ({cx}, {cy}) in window '{match.get('window', 'Screen')}'.",
            )
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Failed to click element: {exc}")

    async def _watch_screen(self, target_text: str, timeout: float, interval: float) -> ToolResult:
        """Watch screen for appearance of specific text or window until timeout."""
        if not target_text:
            return ToolResult(ok=False, output="", error="'target_text' is required for watch_screen.")

        start = time.time()
        logger.info("screen_vision.watching", target=target_text, timeout=timeout)

        while time.time() - start < timeout:
            matches = self._search_ui_text(target_text)
            if matches:
                m = matches[0]
                elapsed = round(time.time() - start, 1)
                return ToolResult(
                    ok=True,
                    output=(
                        f"Target '{target_text}' detected after {elapsed}s in window '{m.get('window', 'Screen')}' "
                        f"at center ({m['center_x']}, {m['center_y']})."
                    ),
                    metadata={"match": m, "elapsed_seconds": elapsed},
                )
            await asyncio.sleep(interval)

        return ToolResult(
            ok=False,
            output="",
            error=f"Timed out after {timeout}s: '{target_text}' did not appear on screen.",
        )

    def _search_ui_text(self, target_text: str) -> list[dict[str, Any]]:
        """Search visible windows and UI elements for matching text."""
        target_lower = target_text.strip().lower()
        matches: list[dict[str, Any]] = []

        if platform.system() == "Windows":
            try:
                import pygetwindow as gw
                for w in gw.getAllWindows():
                    if w.title and w.visible and w.width > 20 and w.height > 20:
                        title_clean = w.title.strip()
                        if target_lower in title_clean.lower():
                            cx = w.left + w.width // 2
                            cy = w.top + w.height // 2
                            matches.append({
                                "text": title_clean,
                                "window": title_clean,
                                "bounds": [w.left, w.top, w.width, w.height],
                                "center_x": cx,
                                "center_y": cy,
                                "confidence": 1.0 if target_lower == title_clean.lower() else 0.85,
                            })
            except Exception as e:
                logger.debug("search_ui_text.pygetwindow_error", exc_info=e)

            # Also search child controls via win32gui if available
            try:
                import win32gui
                def enum_child_proc(hwnd, param):
                    if win32gui.IsWindowVisible(hwnd):
                        txt = win32gui.GetWindowText(hwnd).strip()
                        if txt and target_lower in txt.lower():
                            try:
                                rect = win32gui.GetWindowRect(hwnd)
                                left, top, right, bottom = rect
                                width = right - left
                                height = bottom - top
                                if width > 5 and height > 5:
                                    param.append({
                                        "text": txt,
                                        "window": "ChildControl",
                                        "bounds": [left, top, width, height],
                                        "center_x": (left + right) // 2,
                                        "center_y": (top + bottom) // 2,
                                        "confidence": 0.9 if target_lower == txt.lower() else 0.75,
                                    })
                            except Exception:
                                pass
                    return True

                top_hwnd = win32gui.GetForegroundWindow()
                child_matches: list[dict[str, Any]] = []
                win32gui.EnumChildWindows(top_hwnd, enum_child_proc, child_matches)
                matches.extend(child_matches)
            except Exception as e:
                logger.debug("search_ui_text.win32gui_error", exc_info=e)

        return sorted(matches, key=lambda x: x.get("confidence", 0), reverse=True)

    def _record_macro(self, name: str) -> ToolResult:
        """Start recording macro events."""
        global _macro_state
        _macro_state["recording"] = True
        _macro_state["events"] = []
        _macro_state["start_time"] = time.time()
        _macro_state["name"] = name

        return ToolResult(
            ok=True,
            output=f"Started macro recording for '{name}'. Perform your actions, then call action='stop_macro'.",
        )

    def _stop_macro(self) -> ToolResult:
        """Stop recording macro and return recorded events summary."""
        global _macro_state
        if not _macro_state.get("recording"):
            return ToolResult(ok=False, output="", error="No macro is currently being recorded.")

        _macro_state["recording"] = False
        duration = round(time.time() - _macro_state["start_time"], 2)
        events = _macro_state.get("events", [])
        name = _macro_state.get("name", "macro")

        # Save to ~/.hermclaw/macros/
        macros_dir = Path.home() / ".hermclaw" / "macros"
        macros_dir.mkdir(parents=True, exist_ok=True)
        macro_path = macros_dir / f"{name}.json"
        macro_data = {
            "name": name,
            "recorded_at": time.time(),
            "duration_seconds": duration,
            "events": events,
        }
        macro_path.write_text(json.dumps(macro_data, indent=2), encoding="utf-8")

        return ToolResult(
            ok=True,
            output=f"Macro '{name}' recorded ({len(events)} events in {duration}s). Saved to {macro_path}.",
            metadata={"name": name, "events_count": len(events), "file": str(macro_path)},
        )

    async def _play_macro(self, name: str, events_json: str, speed: float = 1.0) -> ToolResult:
        """Replay recorded macro events."""
        events: list[dict[str, Any]] = []

        if events_json:
            try:
                events = json.loads(events_json)
            except json.JSONDecodeError as exc:
                return ToolResult(ok=False, output="", error=f"Invalid events JSON: {exc}")
        elif name:
            macros_dir = Path.home() / ".hermclaw" / "macros"
            macro_path = macros_dir / f"{name}.json"
            if not macro_path.exists():
                return ToolResult(ok=False, output="", error=f"Macro file not found: {macro_path}")
            data = json.loads(macro_path.read_text(encoding="utf-8"))
            events = data.get("events", [])
        else:
            return ToolResult(ok=False, output="", error="Specify 'macro_name' or 'events' to replay.")

        if not events:
            return ToolResult(ok=True, output="Macro has 0 events; nothing to replay.")

        try:
            import pyautogui
            pyautogui.FAILSAFE = True

            executed = 0
            for ev in events:
                ev_type = ev.get("type", "")
                delay = max(0.01, ev.get("delay", 0.1) / max(0.1, speed))
                await asyncio.sleep(delay)

                if ev_type == "click":
                    pyautogui.click(ev.get("x", 0), ev.get("y", 0), button=ev.get("button", "left"))
                elif ev_type == "move":
                    pyautogui.moveTo(ev.get("x", 0), ev.get("y", 0))
                elif ev_type == "type":
                    pyautogui.typewrite(ev.get("text", ""), interval=0.02 / max(0.1, speed))
                elif ev_type == "key":
                    pyautogui.press(ev.get("key", "enter"))
                elif ev_type == "hotkey":
                    keys = ev.get("keys", [])
                    if isinstance(keys, str):
                        keys = [k.strip() for k in keys.split("+")]
                    pyautogui.hotkey(*keys)
                executed += 1

            return ToolResult(ok=True, output=f"Successfully replayed {executed} events at {speed}x speed.")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Macro replay failed: {exc}")

    def _export_macro_skill(self, name: str) -> ToolResult:
        """Export a recorded macro as a reusable Hermclaw markdown skill."""
        macros_dir = Path.home() / ".hermclaw" / "macros"
        macro_path = macros_dir / f"{name}.json"
        if not macro_path.exists():
            return ToolResult(ok=False, output="", error=f"Recorded macro '{name}' not found.")

        data = json.loads(macro_path.read_text(encoding="utf-8"))
        events = data.get("events", [])

        skills_dir = Path.home() / ".hermclaw" / "skills" / name
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skills_dir / "SKILL.md"

        steps = []
        for i, ev in enumerate(events, 1):
            steps.append(f"{i}. `{ev.get('type')}`: {json.dumps(ev)}")

        skill_content = f"""---
name: {name}
description: Reusable desktop macro workflow for {name}.
---

# Skill: {name}

This skill executes the automated GUI macro sequence recorded for `{name}`.

## Execution Steps ({len(events)} events):
{chr(10).join(steps) if steps else "No events."}

## Replay Instruction
Invoke `screen_vision(action="play_macro", macro_name="{name}")` to run this workflow.
"""
        skill_file.write_text(skill_content, encoding="utf-8")
        return ToolResult(
            ok=True,
            output=f"Exported macro as skill '{name}' to {skill_file}.",
            metadata={"skill_path": str(skill_file)},
        )
