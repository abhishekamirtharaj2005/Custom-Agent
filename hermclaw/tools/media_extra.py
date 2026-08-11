"""Video generation, additional search providers, and ElevenLabs TTS.

New tools:
- VideoGenerateTool: Video generation via AI APIs
- ElevenLabsTTS: High-quality TTS via ElevenLabs
- ExaSearchTool: Exa neural search
- TavilySearchTool: Tavily search API
- ImageRoutingTool: Auto-select best image provider
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Video generation
# ---------------------------------------------------------------------------


class VideoGenerateTool(ToolABC):
    """Generate videos using AI APIs (supports xAI/Grok video)."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="video_generate",
            description=(
                "Generate a video from a text description. "
                "Requires OPENAI_API_KEY or XAI_API_KEY for API access. "
                "Returns path to the generated video file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Description of the video to generate."},
                    "duration": {"type": "integer", "description": "Duration in seconds (default 5, max 30)."},
                    "output_path": {"type": "string", "description": "Path to save the video. Optional."},
                },
                "required": ["prompt"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        prompt = args["prompt"]
        duration = min(args.get("duration", 5), 30)
        output_path = args.get("output_path", "")

        if not output_path:
            out_dir = Path.home() / ".hermclaw" / "videos"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"video_{uuid.uuid4().hex[:8]}.mp4")

        # Try xAI/Grok API first
        xai_key = os.environ.get("XAI_API_KEY")
        if xai_key:
            return await self._xai_generate(prompt, duration, output_path, xai_key)

        # Try OpenAI (future video endpoint)
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            return await self._openai_generate(prompt, duration, output_path, openai_key)

        return ToolResult(ok=False, output="", error=(
            "No video generation API key found. Set XAI_API_KEY or OPENAI_API_KEY."
        ))

    async def _xai_generate(self, prompt: str, duration: int, output_path: str, api_key: str) -> ToolResult:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    "https://api.x.ai/v1/video/generations",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"prompt": prompt, "duration": duration},
                )
                resp.raise_for_status()
                data = resp.json()

                video_url = data.get("url", "")
                if video_url:
                    video_resp = await client.get(video_url)
                    Path(output_path).write_bytes(video_resp.content)
                    return ToolResult(ok=True, output=f"Video generated: {output_path}")

            return ToolResult(ok=False, output="", error="No video URL in response")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Video generation failed: {exc}")

    async def _openai_generate(self, prompt: str, duration: int, output_path: str, api_key: str) -> ToolResult:
        return ToolResult(ok=False, output="", error="OpenAI video generation not yet available via API")


# ---------------------------------------------------------------------------
# ElevenLabs TTS
# ---------------------------------------------------------------------------


class ElevenLabsTTS(ToolABC):
    """High-quality TTS using ElevenLabs API."""

    VOICES = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",
        "adam": "pNInz6obpgDQGcFmaJgB",
        "sam": "yoZ06aMxZJJ28mfd3POQ",
        "emily": "LcfcDJNUP1GQjkzn1xUU",
        "josh": "TxGEqnHWrfWFTfGW9XjX",
    }

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="elevenlabs_tts",
            description=(
                "Generate high-quality speech using ElevenLabs. "
                "Voices: rachel, adam, sam, emily, josh. "
                "Requires ELEVENLABS_API_KEY environment variable."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to speak."},
                    "voice": {"type": "string", "description": "Voice name (rachel, adam, etc.)."},
                    "output_path": {"type": "string", "description": "Path to save audio. Optional."},
                },
                "required": ["text"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return ToolResult(ok=False, output="", error="ELEVENLABS_API_KEY not set.")

        text = args["text"]
        voice_name = args.get("voice", "rachel")
        voice_id = self.VOICES.get(voice_name, voice_name)
        output_path = args.get("output_path", "")

        if not output_path:
            out_dir = Path.home() / ".hermclaw" / "tts_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"eleven_{uuid.uuid4().hex[:8]}.mp3")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                    json={"text": text[:5000], "model_id": "eleven_multilingual_v2"},
                )
                resp.raise_for_status()
                Path(output_path).write_bytes(resp.content)

            return ToolResult(ok=True, output=f"Audio saved: {output_path}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"ElevenLabs error: {exc}")


# ---------------------------------------------------------------------------
# Exa Search
# ---------------------------------------------------------------------------


class ExaSearchTool(ToolABC):
    """Neural search using Exa API."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="exa_search",
            description=(
                "Neural/semantic search using Exa. Finds relevant content "
                "based on meaning, not just keywords. Requires EXA_API_KEY."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "num_results": {"type": "integer", "description": "Number of results (default 5)."},
                    "use_autoprompt": {"type": "boolean", "description": "Let Exa optimize the query."},
                },
                "required": ["query"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("EXA_API_KEY")
        if not api_key:
            return ToolResult(ok=False, output="", error="EXA_API_KEY not set.")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={"x-api-key": api_key, "Content-Type": "application/json"},
                    json={
                        "query": args["query"],
                        "numResults": min(args.get("num_results", 5), 10),
                        "useAutoprompt": args.get("use_autoprompt", True),
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for i, r in enumerate(data.get("results", []), 1):
                results.append(f"{i}. **{r.get('title', '')}**\n   URL: {r.get('url', '')}\n   {r.get('text', '')[:200]}")

            return ToolResult(ok=True, output="\n\n".join(results) or "No results.")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Exa search error: {exc}")


# ---------------------------------------------------------------------------
# Tavily Search
# ---------------------------------------------------------------------------


class TavilySearchTool(ToolABC):
    """AI-powered search using Tavily API."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="tavily_search",
            description=(
                "AI-powered search using Tavily. Returns comprehensive "
                "answers with sources. Requires TAVILY_API_KEY."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "search_depth": {"type": "string", "enum": ["basic", "advanced"], "description": "Search depth."},
                },
                "required": ["query"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return ToolResult(ok=False, output="", error="TAVILY_API_KEY not set.")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": api_key,
                        "query": args["query"],
                        "search_depth": args.get("search_depth", "basic"),
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            answer = data.get("answer", "")
            results = []
            for i, r in enumerate(data.get("results", [])[:5], 1):
                results.append(f"{i}. **{r.get('title', '')}**\n   URL: {r.get('url', '')}\n   {r.get('content', '')[:200]}")

            output = ""
            if answer:
                output = f"**Answer:** {answer}\n\n"
            output += "\n\n".join(results)

            return ToolResult(ok=True, output=output or "No results.")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Tavily search error: {exc}")


# ---------------------------------------------------------------------------
# Image routing (auto-select provider)
# ---------------------------------------------------------------------------


class ImageRouter:
    """Auto-select the best image generation provider based on availability."""

    PROVIDERS = ["dall-e", "fal.ai", "stable-diffusion"]

    @staticmethod
    def select_provider() -> str:
        """Select the best available provider."""
        if os.environ.get("OPENAI_API_KEY"):
            return "dall-e"
        if os.environ.get("FAL_KEY"):
            return "fal.ai"
        return "none"

    @staticmethod
    def is_available(provider: str) -> bool:
        if provider == "dall-e":
            return bool(os.environ.get("OPENAI_API_KEY"))
        if provider == "fal.ai":
            return bool(os.environ.get("FAL_KEY"))
        return False
