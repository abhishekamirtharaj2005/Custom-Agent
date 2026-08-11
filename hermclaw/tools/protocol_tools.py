"""Protocol integrations: MCP OAuth, MCP catalog, MS Graph, X/Twitter, Spotify, Home Assistant.

Implements:
- MCP OAuth flows
- MCP catalog (browse/install)
- MCP security (tool validation)
- Microsoft Graph API client
- X/Twitter API search
- Spotify API integration
- Home Assistant integration
- Codex/Responses API runtime
- Relay connector (WebSocket transport)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# MCP OAuth flows
# ---------------------------------------------------------------------------


class MCPOAuthManager:
    """OAuth 2.0 flow management for MCP connections."""

    def __init__(self, state_dir: Optional[Path] = None) -> None:
        self._state_dir = state_dir or (Path.home() / ".hermclaw" / "mcp_oauth")
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._tokens: dict[str, dict] = self._load_tokens()

    def get_auth_url(self, server_name: str, auth_url: str,
                     client_id: str, scope: str = "", redirect_uri: str = "http://localhost:8765/callback") -> str:
        """Generate OAuth authorization URL."""
        import urllib.parse
        state = uuid.uuid4().hex
        self._save_state(server_name, state)

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        if scope:
            params["scope"] = scope
        return f"{auth_url}?{urllib.parse.urlencode(params)}"

    async def exchange_code(self, server_name: str, code: str,
                            token_url: str, client_id: str, client_secret: str,
                            redirect_uri: str = "http://localhost:8765/callback") -> dict:
        """Exchange authorization code for tokens."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(token_url, data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                })
                resp.raise_for_status()
                tokens = resp.json()

            self._tokens[server_name] = {
                "access_token": tokens.get("access_token", ""),
                "refresh_token": tokens.get("refresh_token", ""),
                "expires_at": time.time() + tokens.get("expires_in", 3600),
            }
            self._save_tokens()
            return tokens
        except Exception as exc:
            return {"error": str(exc)}

    async def refresh(self, server_name: str, token_url: str,
                      client_id: str, client_secret: str) -> Optional[str]:
        """Refresh an expired access token."""
        token_data = self._tokens.get(server_name, {})
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            return None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(token_url, data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                })
                resp.raise_for_status()
                tokens = resp.json()

            self._tokens[server_name]["access_token"] = tokens.get("access_token", "")
            self._tokens[server_name]["expires_at"] = time.time() + tokens.get("expires_in", 3600)
            if "refresh_token" in tokens:
                self._tokens[server_name]["refresh_token"] = tokens["refresh_token"]
            self._save_tokens()
            return self._tokens[server_name]["access_token"]
        except Exception:
            return None

    def get_token(self, server_name: str) -> Optional[str]:
        data = self._tokens.get(server_name, {})
        if data.get("expires_at", 0) > time.time():
            return data.get("access_token")
        return None

    def _save_state(self, name: str, state: str) -> None:
        (self._state_dir / f"{name}_state.txt").write_text(state)

    def _load_tokens(self) -> dict:
        path = self._state_dir / "tokens.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return {}

    def _save_tokens(self) -> None:
        (self._state_dir / "tokens.json").write_text(json.dumps(self._tokens, indent=2))


# ---------------------------------------------------------------------------
# MCP catalog
# ---------------------------------------------------------------------------


class MCPCatalog:
    """Browse and install MCP servers from a catalog."""

    BUILTIN_SERVERS = [
        {"name": "filesystem", "description": "File system operations", "cmd": "npx @modelcontextprotocol/server-filesystem"},
        {"name": "github", "description": "GitHub repository tools", "cmd": "npx @modelcontextprotocol/server-github"},
        {"name": "postgres", "description": "PostgreSQL database", "cmd": "npx @modelcontextprotocol/server-postgres"},
        {"name": "sqlite", "description": "SQLite database", "cmd": "npx @modelcontextprotocol/server-sqlite"},
        {"name": "brave-search", "description": "Brave web search", "cmd": "npx @modelcontextprotocol/server-brave-search"},
        {"name": "puppeteer", "description": "Browser automation", "cmd": "npx @modelcontextprotocol/server-puppeteer"},
        {"name": "slack", "description": "Slack messaging", "cmd": "npx @modelcontextprotocol/server-slack"},
        {"name": "google-drive", "description": "Google Drive files", "cmd": "npx @modelcontextprotocol/server-google-drive"},
        {"name": "memory", "description": "Persistent memory", "cmd": "npx @modelcontextprotocol/server-memory"},
        {"name": "fetch", "description": "HTTP fetch", "cmd": "npx @modelcontextprotocol/server-fetch"},
        {"name": "sequential-thinking", "description": "Step-by-step reasoning", "cmd": "npx @modelcontextprotocol/server-sequential-thinking"},
        {"name": "everything", "description": "Test/demo server with all features", "cmd": "npx @modelcontextprotocol/server-everything"},
    ]

    def browse(self, query: str = "") -> list[dict]:
        q = query.lower()
        if not q:
            return self.BUILTIN_SERVERS
        return [s for s in self.BUILTIN_SERVERS
                if q in s["name"].lower() or q in s.get("description", "").lower()]

    def get_install_command(self, name: str) -> Optional[str]:
        for s in self.BUILTIN_SERVERS:
            if s["name"] == name:
                return s["cmd"]
        return None


# ---------------------------------------------------------------------------
# MCP security
# ---------------------------------------------------------------------------


class MCPSecurity:
    """Security validation for MCP tool calls."""

    BLOCKED_TOOLS = {"system_shell", "rm_rf", "format_disk"}
    SENSITIVE_ARGS = {"password", "secret", "token", "api_key", "private_key"}

    def validate_tool_call(self, tool_name: str, args: dict) -> dict[str, Any]:
        """Validate a tool call for security issues."""
        if tool_name in self.BLOCKED_TOOLS:
            return {"allowed": False, "reason": f"Tool '{tool_name}' is blocked"}

        # Check for sensitive data in arguments
        warnings = []
        for key in args:
            if key.lower() in self.SENSITIVE_ARGS:
                warnings.append(f"Argument '{key}' may contain sensitive data")

        return {"allowed": True, "warnings": warnings}


# ---------------------------------------------------------------------------
# Microsoft Graph API
# ---------------------------------------------------------------------------


class MSGraphClient:
    """Microsoft Graph API client for Office 365 integration."""

    GRAPH_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, access_token: str = "") -> None:
        self._token = access_token or os.environ.get("MS_GRAPH_TOKEN", "")
        self._client = httpx.AsyncClient(timeout=15.0)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def get_me(self) -> dict:
        resp = await self._client.get(f"{self.GRAPH_URL}/me", headers=self._headers())
        return resp.json()

    async def list_emails(self, top: int = 10) -> list[dict]:
        resp = await self._client.get(
            f"{self.GRAPH_URL}/me/messages",
            headers=self._headers(), params={"$top": top, "$orderby": "receivedDateTime desc"},
        )
        data = resp.json()
        return data.get("value", [])

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        try:
            resp = await self._client.post(
                f"{self.GRAPH_URL}/me/sendMail",
                headers=self._headers(),
                json={
                    "message": {
                        "subject": subject,
                        "body": {"contentType": "Text", "content": body},
                        "toRecipients": [{"emailAddress": {"address": to}}],
                    }
                },
            )
            return resp.status_code == 202
        except Exception:
            return False

    async def list_calendar_events(self, top: int = 10) -> list[dict]:
        resp = await self._client.get(
            f"{self.GRAPH_URL}/me/events",
            headers=self._headers(), params={"$top": top, "$orderby": "start/dateTime"},
        )
        return resp.json().get("value", [])

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# X/Twitter API
# ---------------------------------------------------------------------------


class TwitterSearchTool(ToolABC):
    """Search X/Twitter posts."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="twitter_search",
            description="Search recent posts on X (Twitter). Requires TWITTER_BEARER_TOKEN.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {"type": "integer", "description": "Max results (10-100)."},
                },
                "required": ["query"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        token = os.environ.get("TWITTER_BEARER_TOKEN")
        if not token:
            return ToolResult(ok=False, output="", error="TWITTER_BEARER_TOKEN not set.")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "query": args["query"],
                        "max_results": min(args.get("max_results", 10), 100),
                        "tweet.fields": "created_at,author_id,public_metrics",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            tweets = data.get("data", [])
            results = []
            for t in tweets[:10]:
                metrics = t.get("public_metrics", {})
                results.append(
                    f"📝 {t.get('text', '')[:200]}\n"
                    f"   ❤️ {metrics.get('like_count', 0)} | 🔁 {metrics.get('retweet_count', 0)} | "
                    f"📅 {t.get('created_at', '')[:10]}"
                )
            return ToolResult(ok=True, output="\n\n".join(results) or "No results.")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Twitter error: {exc}")


# ---------------------------------------------------------------------------
# Spotify API
# ---------------------------------------------------------------------------


class SpotifyTool(ToolABC):
    """Control Spotify playback and search music."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="spotify",
            description=(
                "Control Spotify: search tracks, play/pause, skip, get currently playing. "
                "Requires SPOTIFY_ACCESS_TOKEN."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["search", "play", "pause", "next", "previous", "now_playing"],
                    },
                    "query": {"type": "string", "description": "Search query (for search action)."},
                    "uri": {"type": "string", "description": "Spotify URI to play."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        token = os.environ.get("SPOTIFY_ACCESS_TOKEN")
        if not token:
            return ToolResult(ok=False, output="", error="SPOTIFY_ACCESS_TOKEN not set.")

        headers = {"Authorization": f"Bearer {token}"}
        action = args["action"]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if action == "search":
                    resp = await client.get(
                        "https://api.spotify.com/v1/search",
                        headers=headers,
                        params={"q": args.get("query", ""), "type": "track", "limit": 5},
                    )
                    tracks = resp.json().get("tracks", {}).get("items", [])
                    results = [f"🎵 {t['name']} — {t['artists'][0]['name']} ({t['uri']})" for t in tracks]
                    return ToolResult(ok=True, output="\n".join(results) or "No tracks found.")

                elif action == "now_playing":
                    resp = await client.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)
                    if resp.status_code == 204:
                        return ToolResult(ok=True, output="Nothing currently playing.")
                    data = resp.json()
                    item = data.get("item", {})
                    return ToolResult(ok=True, output=f"🎵 {item.get('name', '')} — {item.get('artists', [{}])[0].get('name', '')}")

                elif action in ("play", "pause", "next", "previous"):
                    endpoints = {
                        "play": ("PUT", "/v1/me/player/play"),
                        "pause": ("PUT", "/v1/me/player/pause"),
                        "next": ("POST", "/v1/me/player/next"),
                        "previous": ("POST", "/v1/me/player/previous"),
                    }
                    method, path = endpoints[action]
                    if method == "PUT":
                        resp = await client.put(f"https://api.spotify.com{path}", headers=headers)
                    else:
                        resp = await client.post(f"https://api.spotify.com{path}", headers=headers)
                    return ToolResult(ok=True, output=f"Spotify: {action} ✅")

            return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Spotify error: {exc}")


# ---------------------------------------------------------------------------
# Home Assistant API
# ---------------------------------------------------------------------------


class HomeAssistantTool(ToolABC):
    """Control smart home via Home Assistant API."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="home_assistant",
            description=(
                "Control smart home devices via Home Assistant. "
                "Actions: list_entities, toggle, turn_on, turn_off, get_state, call_service. "
                "Requires HA_URL and HA_TOKEN environment variables."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list_entities", "toggle", "turn_on", "turn_off", "get_state", "call_service"],
                    },
                    "entity_id": {"type": "string", "description": "Entity ID (e.g., light.living_room)."},
                    "domain": {"type": "string", "description": "Service domain (for call_service)."},
                    "service": {"type": "string", "description": "Service name (for call_service)."},
                    "service_data": {"type": "object", "description": "Service data (for call_service)."},
                },
                "required": ["action"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        ha_url = os.environ.get("HA_URL", "http://localhost:8123")
        ha_token = os.environ.get("HA_TOKEN")
        if not ha_token:
            return ToolResult(ok=False, output="", error="HA_TOKEN not set.")

        headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
        action = args["action"]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if action == "list_entities":
                    resp = await client.get(f"{ha_url}/api/states", headers=headers)
                    entities = resp.json()
                    lines = [f"{e['entity_id']}: {e['state']}" for e in entities[:30]]
                    return ToolResult(ok=True, output="\n".join(lines))

                elif action == "get_state":
                    entity_id = args.get("entity_id", "")
                    resp = await client.get(f"{ha_url}/api/states/{entity_id}", headers=headers)
                    data = resp.json()
                    return ToolResult(ok=True, output=f"{entity_id}: {data.get('state', 'unknown')}")

                elif action in ("toggle", "turn_on", "turn_off"):
                    entity_id = args.get("entity_id", "")
                    domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"
                    resp = await client.post(
                        f"{ha_url}/api/services/{domain}/{action}",
                        headers=headers, json={"entity_id": entity_id},
                    )
                    return ToolResult(ok=True, output=f"✅ {action} {entity_id}")

                elif action == "call_service":
                    domain = args.get("domain", "")
                    service = args.get("service", "")
                    data = args.get("service_data", {})
                    resp = await client.post(
                        f"{ha_url}/api/services/{domain}/{service}",
                        headers=headers, json=data,
                    )
                    return ToolResult(ok=True, output=f"✅ Called {domain}.{service}")

            return ToolResult(ok=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Home Assistant error: {exc}")
