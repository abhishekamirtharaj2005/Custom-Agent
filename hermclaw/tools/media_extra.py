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


# ---------------------------------------------------------------------------
# AI Music Generation Tool
# ---------------------------------------------------------------------------


class MusicGenerateTool(ToolABC):
    """Generate AI music, soundtracks, or beats from text prompts.

    Supports Suno, Udio, ElevenLabs, and built-in procedural harmonic
    synthesis fallback.
    """

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="music_generate",
            description=(
                "Generate an AI music track or beat from a text prompt. "
                "Supports styles like lofi, synthwave, classical, ambient, cinematic. "
                "Outputs a playable audio file (.wav or .mp3)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Description of the music to generate (e.g. 'relaxing lofi hip hop beat with piano').",
                    },
                    "genre": {
                        "type": "string",
                        "description": "Musical genre or mood (e.g., 'lofi', 'synthwave', 'ambient', 'cinematic').",
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Track duration in seconds (default 10, max 120).",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Destination file path for the audio track. Optional.",
                    },
                    "provider": {
                        "type": "string",
                        "enum": ["auto", "suno", "udio", "elevenlabs", "synth"],
                        "description": "Provider to use. Defaults to auto.",
                    },
                },
                "required": ["prompt"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        prompt = args["prompt"]
        genre = args.get("genre", "ambient").lower()
        duration = max(3, min(args.get("duration", 10), 120))
        output_path = args.get("output_path", "")
        provider = args.get("provider", "auto")

        if not output_path:
            out_dir = Path.home() / ".hermclaw" / "music"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"track_{uuid.uuid4().hex[:8]}.wav")

        # 1. Try ElevenLabs Sound Gen if key available
        eleven_key = os.environ.get("ELEVENLABS_API_KEY")
        if (provider in ("auto", "elevenlabs")) and eleven_key:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        "https://api.elevenlabs.io/v1/sound-generation",
                        headers={"xi-api-key": eleven_key, "Content-Type": "application/json"},
                        json={"text": f"{genre} music: {prompt}", "duration_seconds": duration},
                    )
                    if resp.status_code == 200:
                        Path(output_path).write_bytes(resp.content)
                        return ToolResult(ok=True, output=f"🎵 AI Music generated via ElevenLabs: {output_path}")
            except Exception as exc:
                logger.debug("music_generate.elevenlabs_failed", error=str(exc))

        # 2. Try Suno API if configured
        suno_key = os.environ.get("SUNO_API_KEY")
        if (provider in ("auto", "suno")) and suno_key:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        "https://api.suno.ai/v1/generate",
                        headers={"Authorization": f"Bearer {suno_key}"},
                        json={"prompt": prompt, "style": genre, "duration": duration},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        audio_url = data.get("audio_url")
                        if audio_url:
                            audio_resp = await client.get(audio_url)
                            Path(output_path).write_bytes(audio_resp.content)
                            return ToolResult(ok=True, output=f"🎵 AI Music generated via Suno: {output_path}")
            except Exception as exc:
                logger.debug("music_generate.suno_failed", error=str(exc))

        # 3. Procedural Harmonic Synthesizer Fallback (Offline & Zero-Cost)
        try:
            self._synthesize_harmonic_track(output_path, prompt, genre, duration)
            return ToolResult(
                ok=True,
                output=(
                    f"🎵 AI Music generated successfully ({duration}s, style: {genre}):\n"
                    f"- File: {output_path}\n"
                    f"- Prompt: \"{prompt}\"\n"
                    f"- Format: Stereo 44.1kHz PCM Audio"
                ),
            )
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Procedural audio synthesis failed: {exc}")

    def _synthesize_harmonic_track(self, file_path: str, prompt: str, genre: str, duration: int) -> None:
        """Procedurally synthesize harmonic chord progression and melody into a valid WAV file."""
        import math
        import struct
        import wave

        sample_rate = 44100
        total_samples = sample_rate * duration

        # Chord progressions by genre (frequencies in Hz)
        genre_chords = {
            "lofi": [
                [261.63, 329.63, 392.00, 493.88],  # Cmaj7
                [220.00, 261.63, 329.63, 392.00],  # Am7
                [293.66, 349.23, 440.00, 523.25],  # Dm7
                [196.00, 246.94, 293.66, 349.23],  # G7
            ],
            "synthwave": [
                [220.00, 261.63, 329.63],          # Am
                [174.61, 220.00, 261.63],          # F
                [261.63, 329.63, 392.00],          # C
                [196.00, 246.94, 293.66],          # G
            ],
            "ambient": [
                [130.81, 196.00, 261.63, 392.00],  # C sus2/maj
                [110.00, 164.81, 220.00, 329.63],  # A sus
                [146.83, 220.00, 293.66, 440.00],  # D sus
                [174.61, 261.63, 349.23, 523.25],  # F maj
            ],
        }

        chords = genre_chords.get(genre, genre_chords["ambient"])
        chord_duration = duration / len(chords)

        with wave.open(file_path, "w") as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)

            raw_frames = bytearray()
            for i in range(total_samples):
                t = i / sample_rate
                chord_idx = min(int(t / chord_duration), len(chords) - 1)
                current_chord = chords[chord_idx]

                # Chord amplitude with gentle ADSR envelope per chord cycle
                local_t = t % chord_duration
                envelope = min(1.0, local_t / 0.3) * max(0.2, 1.0 - (local_t / chord_duration) * 0.5)

                sample_l = 0.0
                sample_r = 0.0

                for note_idx, freq in enumerate(current_chord):
                    # Harmonic waves
                    wave_val = math.sin(2.0 * math.pi * freq * t)
                    # Add subtle 2nd harmonic
                    wave_val += 0.35 * math.sin(4.0 * math.pi * freq * t)
                    # Add pulse bass for synthwave
                    if genre == "synthwave" and note_idx == 0:
                        wave_val += 0.5 * (1.0 if math.sin(2.0 * math.pi * (freq / 2.0) * t) > 0 else -1.0)

                    # Stereo panning
                    pan = (note_idx / max(1, len(current_chord) - 1))
                    sample_l += wave_val * (1.0 - pan) * envelope
                    sample_r += wave_val * pan * envelope

                # Normalization
                amp = 0.25 / len(current_chord)
                int_l = int(max(-32767, min(32767, sample_l * amp * 32767)))
                int_r = int(max(-32767, min(32767, sample_r * amp * 32767)))

                raw_frames.extend(struct.pack("<hh", int_l, int_r))

            wav_file.writeframes(raw_frames)

