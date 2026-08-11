"""Text-to-Speech (TTS) tool.

Uses edge-tts (free, no API key) for high-quality voice synthesis.
Falls back to platform-native TTS when edge-tts is not installed.
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

# Available edge-tts voices (subset)
VOICES = {
    "en-male": "en-US-GuyNeural",
    "en-female": "en-US-JennyNeural",
    "en-uk-male": "en-GB-RyanNeural",
    "en-uk-female": "en-GB-SoniaNeural",
    "en-au-female": "en-AU-NatashaNeural",
    "en-in-male": "en-IN-PrabhatNeural",
    "en-in-female": "en-IN-NeerjaNeural",
    "es-female": "es-ES-ElviraNeural",
    "fr-female": "fr-FR-DeniseNeural",
    "de-male": "de-DE-ConradNeural",
    "ja-female": "ja-JP-NanamiNeural",
    "zh-female": "zh-CN-XiaoxiaoNeural",
    "ko-female": "ko-KR-SunHiNeural",
    "hi-female": "hi-IN-SwaraNeural",
    "hi-male": "hi-IN-MadhurNeural",
    "ta-male": "ta-IN-ValluvarNeural",
}


class TTSTool(ToolABC):
    """Convert text to speech audio."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="tts",
            description=(
                "Convert text to speech. Generates an audio file from text. "
                "Voices: en-male, en-female, en-uk-male, en-uk-female, en-in-male, "
                "en-in-female, hi-male, hi-female, etc. Use action=speak to play "
                "immediately, or action=save to save to a file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to convert to speech."},
                    "voice": {"type": "string", "description": "Voice preset name (e.g., en-female, en-in-male)."},
                    "action": {
                        "type": "string",
                        "enum": ["speak", "save"],
                        "description": "speak: play immediately. save: save to file. Default: speak.",
                    },
                    "output_path": {"type": "string", "description": "Output file path (for save action)."},
                    "rate": {"type": "string", "description": "Speech rate (e.g., +20%, -10%). Default: +0%."},
                },
                "required": ["text"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        text = args.get("text", "")
        if not text:
            return ToolResult(ok=False, output="", error="'text' is required.")

        voice_key = args.get("voice", "en-female")
        voice = VOICES.get(voice_key, voice_key)
        action = args.get("action", "speak")
        rate = args.get("rate", "+0%")
        output_path = args.get("output_path", "")

        if not output_path:
            out_dir = Path.home() / ".hermclaw" / "tts_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"{uuid.uuid4().hex[:8]}.mp3")

        try:
            # Try edge-tts first
            return await self._edge_tts(text, voice, rate, output_path, action)
        except ImportError:
            # Fallback to platform TTS
            return self._platform_tts(text, action)
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"TTS failed: {exc}")

    async def _edge_tts(self, text: str, voice: str, rate: str, output_path: str, action: str) -> ToolResult:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)

        if action == "speak":
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "", output_path], shell=False)
            elif system == "Darwin":
                subprocess.Popen(["open", output_path])
            else:
                subprocess.Popen(["xdg-open", output_path])
            return ToolResult(ok=True, output=f"Speaking text ({len(text)} chars) with voice {voice}")
        else:
            return ToolResult(ok=True, output=f"Audio saved to: {output_path}")

    def _platform_tts(self, text: str, action: str) -> ToolResult:
        """Fallback: use platform-native TTS."""
        system = platform.system()
        if system == "Windows":
            ps_cmd = f'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak("{text[:500]}")'
            subprocess.Popen(["powershell", "-Command", ps_cmd])
            return ToolResult(ok=True, output=f"Speaking via Windows Speech (edge-tts not installed)")
        elif system == "Darwin":
            subprocess.Popen(["say", text[:500]])
            return ToolResult(ok=True, output=f"Speaking via macOS say")
        else:
            subprocess.Popen(["espeak", text[:500]])
            return ToolResult(ok=True, output=f"Speaking via espeak (install edge-tts for better quality)")


class TranscriptionTool(ToolABC):
    """Speech-to-text transcription using OpenAI Whisper API.

    Supports:
    - OpenAI API (requires OPENAI_API_KEY)
    - Local Whisper via Ollama or compatible endpoint
    """

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="transcribe",
            description=(
                "Transcribe audio to text using speech-to-text. "
                "Supports mp3, wav, m4a, webm, and mp4 audio files. "
                "Uses OpenAI Whisper API or local alternative."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the audio file to transcribe."},
                    "language": {"type": "string", "description": "Language code (e.g., 'en', 'hi', 'ta'). Optional."},
                },
                "required": ["path"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        audio_path = Path(os.path.expanduser(args["path"])).resolve()
        language = args.get("language")

        if not audio_path.exists():
            return ToolResult(ok=False, output="", error=f"Audio file not found: {audio_path}")

        supported = {".mp3", ".wav", ".m4a", ".webm", ".mp4", ".ogg", ".flac"}
        if audio_path.suffix.lower() not in supported:
            return ToolResult(ok=False, output="", error=f"Unsupported format: {audio_path.suffix}. Use: {', '.join(supported)}")

        # Try OpenAI Whisper API
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            return await self._openai_whisper(audio_path, api_key, language)

        # Try local whisper via command line
        return await self._local_whisper(audio_path, language)

    async def _openai_whisper(self, path: Path, api_key: str, language: str | None) -> ToolResult:
        """Transcribe via OpenAI Whisper API."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                files = {"file": (path.name, path.read_bytes(), "audio/mpeg")}
                data: dict[str, str] = {"model": "whisper-1"}
                if language:
                    data["language"] = language

                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files=files,
                    data=data,
                )
                resp.raise_for_status()
                result = resp.json()

            text = result.get("text", "")
            return ToolResult(ok=True, output=f"Transcription ({path.name}):\n\n{text}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Whisper API error: {exc}")

    async def _local_whisper(self, path: Path, language: str | None) -> ToolResult:
        """Fallback: try local whisper CLI if installed."""
        try:
            cmd = ["whisper", str(path), "--output_format", "txt"]
            if language:
                cmd.extend(["--language", language])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            if proc.returncode != 0:
                return ToolResult(ok=False, output="", error=(
                    f"Local whisper failed. Install OpenAI Whisper: pip install openai-whisper\n"
                    f"Or set OPENAI_API_KEY for cloud transcription.\n{stderr.decode()[:300]}"
                ))

            # Read the output .txt file
            txt_path = path.with_suffix(".txt")
            if txt_path.exists():
                text = txt_path.read_text(encoding="utf-8")
                return ToolResult(ok=True, output=f"Transcription ({path.name}):\n\n{text}")
            return ToolResult(ok=True, output=stdout.decode()[:4000])
        except FileNotFoundError:
            return ToolResult(ok=False, output="", error=(
                "No transcription backend available. Options:\n"
                "1. Set OPENAI_API_KEY for cloud Whisper\n"
                "2. Install local whisper: pip install openai-whisper"
            ))
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Transcription error: {exc}")

