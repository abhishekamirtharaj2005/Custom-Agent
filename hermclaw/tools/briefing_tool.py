"""Proactive Personal Secretary: Morning Briefing, Nightly Debrief, and Ergonomics Guardian.

Provides:
- morning_briefing: Synthesizes pending tasks, goals, system health, and schedule into a polished morning standup.
- nightly_debrief: Summarizes daily accomplishments, learning progress, and tomorrow's queue.
- ergonomics_check: Tracks continuous work intervals and suggests eye/posture/hydration breaks.
- focus_mode: Toggles focus mode to protect deep work sessions.
"""

from __future__ import annotations

import datetime
import os
import platform
import time
from pathlib import Path
from typing import Any, Optional

import psutil
import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)

# State tracking for ergonomics & focus mode
_secretary_state: dict[str, Any] = {
    "session_start_time": time.time(),
    "last_break_time": time.time(),
    "focus_mode_active": False,
    "focus_until": 0.0,
}


class BriefingTool(ToolABC):
    """Proactive personal secretary for daily briefings, debriefs, and ergonomics."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="briefing",
            description=(
                "Proactive personal secretary and executive assistant. "
                "Actions: morning_briefing (curated morning standup with schedule, tasks, system status), "
                "nightly_debrief (daily summary & accomplishments), "
                "ergonomics_check (screen-time and health break reminder), "
                "focus_mode (enable or disable deep-work focus mode)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["morning_briefing", "nightly_debrief", "ergonomics_check", "focus_mode"],
                        "description": "Secretary action to perform.",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes for focus_mode (default 45).",
                    },
                    "toggle": {
                        "type": "string",
                        "enum": ["on", "off", "status"],
                        "description": "Toggle focus mode on or off. Default: on.",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args["action"]

        if action == "morning_briefing":
            return self._morning_briefing()
        elif action == "nightly_debrief":
            return self._nightly_debrief()
        elif action == "ergonomics_check":
            return self._ergonomics_check()
        elif action == "focus_mode":
            return self._focus_mode(
                args.get("toggle", "on"),
                int(args.get("duration_minutes", 45)),
            )
        else:
            return ToolResult(ok=False, output="", error=f"Unknown briefing action: {action}")

    def _morning_briefing(self) -> ToolResult:
        """Generate a curated morning briefing."""
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M %p")

        # System health
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        mem_pct = mem.percent

        battery_str = "N/A"
        try:
            battery = psutil.sensors_battery()
            if battery:
                battery_str = f"{battery.percent}% ({'Plugged in' if battery.power_plugged else 'On Battery'})"
        except Exception:
            pass

        # Check pending tasks from Hermclaw state directory
        todos: list[str] = []
        try:
            todo_file = Path.home() / ".hermclaw" / "todos.json"
            if todo_file.exists():
                import json
                data = json.loads(todo_file.read_text(encoding="utf-8"))
                for item in data.get("items", []):
                    if not item.get("done"):
                        todos.append(f"  • [ ] {item.get('title', item.get('text', 'Task'))}")
        except Exception:
            pass

        # Check goals
        goals: list[str] = []
        try:
            goals_file = Path.home() / ".hermclaw" / "goals.json"
            if goals_file.exists():
                import json
                g_data = json.loads(goals_file.read_text(encoding="utf-8"))
                for g in g_data.get("goals", [])[:3]:
                    goals.append(f"  🎯 {g.get('title', 'Goal')} ({g.get('status', 'active')})")
        except Exception:
            pass

        briefing_lines = [
            f"☀️ **Good Morning! Here is your Hermclaw Executive Briefing**",
            f"📅 **Date**: {date_str} | ⏰ **Time**: {time_str}",
            "",
            "💻 **System & Workstation Status**:",
            f"  • CPU Utilization: {cpu_pct}%",
            f"  • Memory Usage: {mem_pct}% used ({round(mem.used / (1024**3), 1)}GB / {round(mem.total / (1024**3), 1)}GB)",
            f"  • Battery: {battery_str}",
            f"  • Platform: {platform.system()} {platform.release()}",
            "",
            f"📋 **Pending Action Items ({len(todos)})**:",
        ]

        if todos:
            briefing_lines.extend(todos[:7])
        else:
            briefing_lines.append("  • No pending to-do items. Your slate is clean!")

        if goals:
            briefing_lines.append("")
            briefing_lines.append("🎯 **Active Strategic Goals**:")
            briefing_lines.extend(goals)

        briefing_lines.extend([
            "",
            "💡 **Thought for the Day**: Focus on highest-leverage actions first. Have a productive and fulfilling day!",
        ])

        return ToolResult(ok=True, output="\n".join(briefing_lines))

    def _nightly_debrief(self) -> ToolResult:
        """Generate a nightly recap of achievements and tasks."""
        now = datetime.datetime.now()
        session_mins = int((time.time() - _secretary_state["session_start_time"]) / 60)

        # Check completed tasks
        completed: list[str] = []
        try:
            todo_file = Path.home() / ".hermclaw" / "todos.json"
            if todo_file.exists():
                import json
                data = json.loads(todo_file.read_text(encoding="utf-8"))
                for item in data.get("items", []):
                    if item.get("done"):
                        completed.append(f"  ✅ {item.get('title', item.get('text', 'Task'))}")
        except Exception:
            pass

        lines = [
            f"🌙 **Hermclaw Nightly Debrief — {now.strftime('%A, %B %d')}**",
            f"⏱️ Total active session time: ~{session_mins} minutes",
            "",
            f"🏆 **Completed Deliverables Today ({len(completed)})**:",
        ]

        if completed:
            lines.extend(completed[:10])
        else:
            lines.append("  • Regular maintenance and assistance completed.")

        lines.extend([
            "",
            "🛌 **Tomorrow's Strategy**: Rest well and recharge. Hermclaw will be ready for tomorrow's standup!",
        ])
        return ToolResult(ok=True, output="\n".join(lines))

    def _ergonomics_check(self) -> ToolResult:
        """Check active work duration and advise on breaks."""
        elapsed_work = time.time() - _secretary_state["last_break_time"]
        work_mins = int(elapsed_work / 60)

        if work_mins < 30:
            return ToolResult(
                ok=True,
                output=f"Work session status: {work_mins} minutes elapsed since last break. You're in your flow zone!",
            )
        elif work_mins < 50:
            return ToolResult(
                ok=True,
                output=(
                    f"⚠️ Work session: {work_mins} minutes continuous screen time. "
                    "Remember the 20-20-20 rule: look at an object 20 feet away for 20 seconds."
                ),
            )
        else:
            # Over 50 mins: reset timer and strongly suggest break
            _secretary_state["last_break_time"] = time.time()
            return ToolResult(
                ok=True,
                output=(
                    f"🛑 **Break Reminder**: You have been working continuously for {work_mins} minutes! "
                    "Time to stand up, stretch your back, drink a glass of water, and rest your eyes for 5 minutes."
                ),
            )

    def _focus_mode(self, toggle: str, duration_minutes: int) -> ToolResult:
        """Enable or disable focus mode."""
        if toggle == "status":
            active = _secretary_state["focus_mode_active"] and time.time() < _secretary_state["focus_until"]
            remaining = max(0, int((_secretary_state["focus_until"] - time.time()) / 60))
            return ToolResult(
                ok=True,
                output=f"Focus Mode is {'ACTIVE' if active else 'OFF'}. (Remaining: {remaining}m)",
            )
        elif toggle == "off":
            _secretary_state["focus_mode_active"] = False
            _secretary_state["focus_until"] = 0.0
            return ToolResult(ok=True, output="🔕 Focus Mode disabled. Standard notifications resumed.")
        else:
            _secretary_state["focus_mode_active"] = True
            _secretary_state["focus_until"] = time.time() + (duration_minutes * 60)
            return ToolResult(
                ok=True,
                output=f"🧘 Focus Mode enabled for {duration_minutes} minutes. Deep work session protected!",
            )
