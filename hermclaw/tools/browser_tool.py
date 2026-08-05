"""Browser automation tool using Playwright.

Provides the agent with the ability to navigate web pages, click elements,
fill forms, take screenshots, and extract content from interactive pages.
Falls back gracefully if Playwright is not installed.
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


class BrowserTool(ToolABC):
    """Automate browser interactions via Playwright."""

    def __init__(self, headless: bool = True, timeout_ms: int = 30000) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._browser = None
        self._page = None
        self._playwright = None

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="browser",
            description=(
                "Automate browser interactions. Actions: navigate, click, type, "
                "screenshot, get_text, evaluate_js, scroll, wait, fill_form, back, forward. "
                "Use this for web scraping, form filling, testing, and any task "
                "requiring a full browser. Screenshots are saved as files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "navigate", "click", "type", "screenshot",
                            "get_text", "evaluate_js", "scroll", "wait",
                            "fill_form", "back", "forward", "close",
                        ],
                        "description": "The browser action to perform.",
                    },
                    "url": {"type": "string", "description": "URL to navigate to (for 'navigate' action)."},
                    "selector": {"type": "string", "description": "CSS selector for the target element."},
                    "text": {"type": "string", "description": "Text to type or value to fill."},
                    "script": {"type": "string", "description": "JavaScript to evaluate (for 'evaluate_js')."},
                    "path": {"type": "string", "description": "File path for screenshot output."},
                    "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction."},
                    "amount": {"type": "integer", "description": "Scroll amount in pixels (default 500)."},
                    "fields": {
                        "type": "object",
                        "description": "Key-value pairs for fill_form: {selector: value}.",
                    },
                },
                "required": ["action"],
            },
            requires_approval_gate=True,
        )

    async def _ensure_browser(self) -> None:
        """Lazily launch browser on first use."""
        if self._page is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = await context.new_page()
        self._page.set_default_timeout(self._timeout_ms)

    async def _cleanup(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "")

        if action == "close":
            await self._cleanup()
            return ToolResult(ok=True, output="Browser closed.")

        try:
            await self._ensure_browser()
        except RuntimeError as exc:
            return ToolResult(ok=False, output="", error=str(exc))

        try:
            if action == "navigate":
                url = args.get("url", "")
                if not url:
                    return ToolResult(ok=False, output="", error="'url' is required for navigate.")
                await self._page.goto(url, wait_until="domcontentloaded")
                title = await self._page.title()
                return ToolResult(ok=True, output=f"Navigated to {url}\nTitle: {title}")

            elif action == "click":
                selector = args.get("selector", "")
                if not selector:
                    return ToolResult(ok=False, output="", error="'selector' is required for click.")
                await self._page.click(selector)
                return ToolResult(ok=True, output=f"Clicked: {selector}")

            elif action == "type":
                selector = args.get("selector", "")
                text = args.get("text", "")
                if not selector:
                    return ToolResult(ok=False, output="", error="'selector' is required for type.")
                await self._page.fill(selector, text)
                return ToolResult(ok=True, output=f"Typed into {selector}: {text[:50]}...")

            elif action == "screenshot":
                save_path = args.get("path", "")
                if not save_path:
                    tmpdir = tempfile.mkdtemp(prefix="hermclaw_ss_")
                    save_path = os.path.join(tmpdir, "screenshot.png")
                await self._page.screenshot(path=save_path, full_page=False)
                return ToolResult(ok=True, output=f"Screenshot saved to: {save_path}")

            elif action == "get_text":
                selector = args.get("selector", "body")
                element = await self._page.query_selector(selector)
                if element is None:
                    return ToolResult(ok=False, output="", error=f"Element not found: {selector}")
                text = await element.inner_text()
                if len(text) > 5000:
                    text = text[:5000] + "\n... [truncated]"
                return ToolResult(ok=True, output=text)

            elif action == "evaluate_js":
                script = args.get("script", "")
                if not script:
                    return ToolResult(ok=False, output="", error="'script' is required for evaluate_js.")
                result = await self._page.evaluate(script)
                return ToolResult(ok=True, output=str(result))

            elif action == "scroll":
                direction = args.get("direction", "down")
                amount = args.get("amount", 500)
                delta = amount if direction == "down" else -amount
                await self._page.mouse.wheel(0, delta)
                return ToolResult(ok=True, output=f"Scrolled {direction} by {amount}px")

            elif action == "wait":
                selector = args.get("selector", "")
                if selector:
                    await self._page.wait_for_selector(selector)
                    return ToolResult(ok=True, output=f"Element appeared: {selector}")
                else:
                    await asyncio.sleep(2)
                    return ToolResult(ok=True, output="Waited 2 seconds.")

            elif action == "fill_form":
                fields = args.get("fields", {})
                if not fields:
                    return ToolResult(ok=False, output="", error="'fields' dict is required for fill_form.")
                filled = []
                for sel, val in fields.items():
                    await self._page.fill(sel, str(val))
                    filled.append(sel)
                return ToolResult(ok=True, output=f"Filled {len(filled)} fields: {', '.join(filled)}")

            elif action == "back":
                await self._page.go_back()
                return ToolResult(ok=True, output="Navigated back.")

            elif action == "forward":
                await self._page.go_forward()
                return ToolResult(ok=True, output="Navigated forward.")

            else:
                return ToolResult(ok=False, output="", error=f"Unknown action: {action}")

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Browser error: {exc}")
