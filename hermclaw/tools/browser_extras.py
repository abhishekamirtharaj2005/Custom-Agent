"""Browser automation, DevTools, anti-detection, and web access policy.

Implements:
- Chrome DevTools Protocol (CDP) integration
- Anti-detection browser (Camofox-style)
- Browser session supervisor
- Browser dialog handling
- Website access policy (domain allow/deny)
- Image source resolution
- fal.ai image generation
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Chrome DevTools Protocol
# ---------------------------------------------------------------------------


class CDPClient:
    """Chrome DevTools Protocol client for low-level browser automation."""

    def __init__(self, debug_url: str = "http://localhost:9222") -> None:
        self._debug_url = debug_url
        self._ws = None
        self._msg_id = 0
        self._client = httpx.AsyncClient(timeout=10.0)

    async def list_targets(self) -> list[dict]:
        """List all available browser targets (tabs)."""
        try:
            resp = await self._client.get(f"{self._debug_url}/json/list")
            return resp.json()
        except Exception as exc:
            logger.error("cdp.list_failed", error=str(exc)[:100])
            return []

    async def send_command(self, method: str, params: dict | None = None) -> dict:
        """Send a CDP command and wait for response."""
        if not self._ws:
            targets = await self.list_targets()
            if not targets:
                return {"error": "No browser targets available"}
            ws_url = targets[0].get("webSocketDebuggerUrl", "")
            if not ws_url:
                return {"error": "No WebSocket URL for target"}

            try:
                import websockets
                self._ws = await websockets.connect(ws_url)
            except ImportError:
                return {"error": "websockets package not installed"}

        self._msg_id += 1
        message = {"id": self._msg_id, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(message))
        response = await self._ws.recv()
        return json.loads(response)

    async def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript in the browser."""
        result = await self.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        return result.get("result", {}).get("result", {}).get("value")

    async def screenshot(self, output_path: str = "") -> Optional[str]:
        """Take a screenshot via CDP."""
        result = await self.send_command("Page.captureScreenshot", {"format": "png"})
        data = result.get("result", {}).get("data", "")
        if data:
            import base64
            if not output_path:
                output_path = str(Path.home() / ".hermclaw" / "screenshots" / f"cdp_{uuid.uuid4().hex[:8]}.png")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(base64.b64decode(data))
            return output_path
        return None

    async def navigate(self, url: str) -> dict:
        """Navigate to a URL."""
        return await self.send_command("Page.navigate", {"url": url})

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Anti-detection browser (Camofox)
# ---------------------------------------------------------------------------


class AntiDetectionBrowser:
    """Anti-detection browser wrapper (Camofox-style).

    Applies fingerprint randomization to avoid bot detection:
    - User-agent rotation
    - WebGL/Canvas fingerprint noise
    - Navigator property masking
    - Timezone randomization
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    ]

    ANTI_DETECT_SCRIPTS = [
        # Hide webdriver
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
        # Mock plugins
        "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});",
        # Mock languages
        "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});",
        # Hide automation
        "window.chrome = {runtime: {}};",
    ]

    def __init__(self) -> None:
        self._browser = None
        self._context = None

    async def launch(self, headless: bool = True) -> Any:
        """Launch anti-detection browser via Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("camofox.playwright_not_installed")
            return None

        import random

        pw = await async_playwright().start()
        ua = random.choice(self.USER_AGENTS)

        self._browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        self._context = await self._browser.new_context(
            user_agent=ua,
            viewport={"width": random.choice([1366, 1440, 1920]), "height": random.choice([768, 900, 1080])},
            locale="en-US",
        )

        # Inject anti-detection scripts
        await self._context.add_init_script("\n".join(self.ANTI_DETECT_SCRIPTS))

        logger.info("camofox.launched", headless=headless, ua=ua[:50])
        return self._context

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()


# ---------------------------------------------------------------------------
# Browser session supervisor
# ---------------------------------------------------------------------------


class BrowserSessionSupervisor:
    """Supervise and manage browser sessions.

    Features:
    - Track active sessions
    - Auto-close idle sessions
    - Memory usage monitoring
    - Session screenshots for debugging
    """

    def __init__(self, max_sessions: int = 5, idle_timeout_s: int = 300) -> None:
        self._max = max_sessions
        self._idle_timeout = idle_timeout_s
        self._sessions: dict[str, dict] = {}

    def register_session(self, session_id: str, context: Any) -> bool:
        if len(self._sessions) >= self._max:
            # Evict oldest idle session
            oldest = min(self._sessions, key=lambda k: self._sessions[k]["last_active"])
            self.close_session(oldest)

        self._sessions[session_id] = {
            "context": context,
            "created_at": time.time(),
            "last_active": time.time(),
            "page_count": 0,
        }
        return True

    def touch(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["last_active"] = time.time()

    def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session and session.get("context"):
            try:
                asyncio.get_event_loop().create_task(session["context"].close())
            except Exception:
                pass

    def cleanup_idle(self) -> int:
        """Close idle sessions."""
        import time
        now = time.time()
        idle = [sid for sid, s in self._sessions.items()
                if now - s["last_active"] > self._idle_timeout]
        for sid in idle:
            self.close_session(sid)
        return len(idle)

    def list_sessions(self) -> list[dict]:
        import time
        return [
            {"id": sid, "age_s": int(time.time() - s["created_at"]),
             "idle_s": int(time.time() - s["last_active"])}
            for sid, s in self._sessions.items()
        ]


# We need time at module level
import time


# ---------------------------------------------------------------------------
# Browser dialog handling
# ---------------------------------------------------------------------------


class BrowserDialogHandler:
    """Handle browser dialogs (alert, confirm, prompt, beforeunload)."""

    def __init__(self, auto_dismiss: bool = True) -> None:
        self._auto_dismiss = auto_dismiss
        self._dialog_log: list[dict] = []

    async def attach(self, page: Any) -> None:
        """Attach dialog handler to a Playwright page."""
        page.on("dialog", self._handle_dialog)

    async def _handle_dialog(self, dialog: Any) -> None:
        self._dialog_log.append({
            "type": dialog.type,
            "message": dialog.message[:200],
            "time": time.time(),
        })
        logger.info("browser.dialog", type=dialog.type, message=dialog.message[:50])
        if self._auto_dismiss:
            if dialog.type in ("confirm", "prompt"):
                await dialog.accept()
            else:
                await dialog.dismiss()

    @property
    def dialog_history(self) -> list[dict]:
        return self._dialog_log


# ---------------------------------------------------------------------------
# Website access policy
# ---------------------------------------------------------------------------


class WebsiteAccessPolicy:
    """Domain allow/deny policy for web access."""

    def __init__(self) -> None:
        self._allowed: set[str] = set()
        self._denied: set[str] = set()
        self._deny_by_default = False

        # Default denylisted domains
        self._denied.update({
            "localhost", "127.0.0.1", "0.0.0.0",
            "169.254.169.254",  # AWS metadata
            "metadata.google.internal",  # GCP metadata
        })

    def allow(self, domain: str) -> None:
        self._allowed.add(domain.lower())
        self._denied.discard(domain.lower())

    def deny(self, domain: str) -> None:
        self._denied.add(domain.lower())
        self._allowed.discard(domain.lower())

    def is_allowed(self, url: str) -> bool:
        """Check if a URL's domain is allowed."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.hostname or ""
        except Exception:
            return False

        domain = domain.lower()

        # Check explicit deny
        if domain in self._denied:
            return False

        # If deny-by-default, check explicit allow
        if self._deny_by_default:
            return domain in self._allowed or any(
                domain.endswith("." + a) for a in self._allowed
            )

        return True


# ---------------------------------------------------------------------------
# Image source resolution
# ---------------------------------------------------------------------------


class ImageSourceResolver:
    """Resolve image sources from URLs, file paths, and base64."""

    async def resolve(self, source: str) -> dict[str, Any]:
        """Resolve an image source to a usable format."""
        if source.startswith("data:image"):
            return {"type": "base64", "data": source}
        elif source.startswith(("http://", "https://")):
            return await self._resolve_url(source)
        elif Path(source).exists():
            return self._resolve_file(source)
        else:
            return {"type": "unknown", "error": f"Cannot resolve: {source[:50]}"}

    async def _resolve_url(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                content_type = resp.headers.get("content-type", "")
                if "image" in content_type:
                    import base64
                    b64 = base64.b64encode(resp.content).decode()
                    return {"type": "base64", "data": f"data:{content_type};base64,{b64}",
                            "size": len(resp.content)}
                return {"type": "url", "url": url}
        except Exception as exc:
            return {"type": "error", "error": str(exc)[:100]}

    def _resolve_file(self, path: str) -> dict:
        import base64
        import mimetypes
        mime = mimetypes.guess_type(path)[0] or "image/png"
        data = Path(path).read_bytes()
        b64 = base64.b64encode(data).decode()
        return {"type": "base64", "data": f"data:{mime};base64,{b64}", "size": len(data)}


# ---------------------------------------------------------------------------
# fal.ai image generation
# ---------------------------------------------------------------------------


class FalAIImageGenerator:
    """Generate images using fal.ai API."""

    API_URL = "https://fal.run"

    def __init__(self, api_key: str = "") -> None:
        self._key = api_key or os.environ.get("FAL_KEY", "")

    async def generate(self, prompt: str, model: str = "fal-ai/flux/schnell",
                       width: int = 1024, height: int = 1024,
                       output_path: str = "") -> dict[str, Any]:
        if not self._key:
            return {"error": "FAL_KEY not set"}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.API_URL}/{model}",
                    headers={"Authorization": f"Key {self._key}", "Content-Type": "application/json"},
                    json={
                        "prompt": prompt,
                        "image_size": {"width": width, "height": height},
                        "num_images": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            images = data.get("images", [])
            if images:
                img_url = images[0].get("url", "")
                if output_path and img_url:
                    async with httpx.AsyncClient(timeout=30.0) as dl_client:
                        img_resp = await dl_client.get(img_url)
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        Path(output_path).write_bytes(img_resp.content)
                    return {"url": img_url, "saved_to": output_path}
                return {"url": img_url}

            return {"error": "No images returned"}
        except Exception as exc:
            return {"error": f"fal.ai error: {exc}"}
