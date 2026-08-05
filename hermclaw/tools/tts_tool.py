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
