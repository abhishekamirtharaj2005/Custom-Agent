"""Voice and speech extras: Azure Speech, Deepgram, NeuTTS, Discord voice.

Implements:
- Azure Speech Services (TTS + STT)
- Deepgram transcription
- NeuTTS synthesis (local)
- Discord voice doctor
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Azure Speech Services
# ---------------------------------------------------------------------------


class AzureSpeechTTS:
    """Text-to-Speech via Azure Cognitive Services Speech."""

    def __init__(self, key: str = "", region: str = "eastus") -> None:
        self._key = key or os.environ.get("AZURE_SPEECH_KEY", "")
        self._region = region or os.environ.get("AZURE_SPEECH_REGION", "eastus")

    async def synthesize(self, text: str, voice: str = "en-US-JennyNeural",
                         output_path: str = "") -> dict[str, Any]:
        if not self._key:
            return {"error": "AZURE_SPEECH_KEY not set"}

        if not output_path:
            out_dir = Path.home() / ".hermclaw" / "tts_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"azure_{uuid.uuid4().hex[:8]}.wav")

        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
            <voice name="{voice}">{text[:5000]}</voice>
        </speak>
        """

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1",
                    headers={
                        "Ocp-Apim-Subscription-Key": self._key,
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                    },
                    content=ssml,
                )
                resp.raise_for_status()
                Path(output_path).write_bytes(resp.content)

            return {"path": output_path, "size_bytes": len(resp.content)}
        except Exception as exc:
            return {"error": f"Azure Speech error: {exc}"}


class AzureSpeechSTT:
    """Speech-to-Text via Azure Cognitive Services Speech."""

    def __init__(self, key: str = "", region: str = "eastus") -> None:
        self._key = key or os.environ.get("AZURE_SPEECH_KEY", "")
        self._region = region or os.environ.get("AZURE_SPEECH_REGION", "eastus")

    async def transcribe(self, audio_path: str, language: str = "en-US") -> dict[str, Any]:
        if not self._key:
            return {"error": "AZURE_SPEECH_KEY not set"}

        try:
            audio_data = Path(audio_path).read_bytes()
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"https://{self._region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
                    headers={
                        "Ocp-Apim-Subscription-Key": self._key,
                        "Content-Type": "audio/wav",
                    },
                    params={"language": language},
                    content=audio_data,
                )
                resp.raise_for_status()
                data = resp.json()

            return {
                "text": data.get("DisplayText", ""),
                "confidence": data.get("NBest", [{}])[0].get("Confidence", 0),
                "status": data.get("RecognitionStatus", ""),
            }
        except Exception as exc:
            return {"error": f"Azure STT error: {exc}"}


# ---------------------------------------------------------------------------
# Deepgram transcription
# ---------------------------------------------------------------------------


class DeepgramTranscriber:
    """Real-time and file transcription via Deepgram API."""

    API_URL = "https://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str = "") -> None:
        self._key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")

    async def transcribe_file(self, audio_path: str, language: str = "en",
                               model: str = "nova-2") -> dict[str, Any]:
        if not self._key:
            return {"error": "DEEPGRAM_API_KEY not set"}

        try:
            audio_data = Path(audio_path).read_bytes()
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Token {self._key}",
                        "Content-Type": "audio/wav",
                    },
                    params={
                        "model": model,
                        "language": language,
                        "smart_format": "true",
                        "punctuate": "true",
                    },
                    content=audio_data,
                )
                resp.raise_for_status()
                data = resp.json()

            transcript = ""
            confidence = 0.0
            results = data.get("results", {}).get("channels", [{}])
            if results:
                alternatives = results[0].get("alternatives", [{}])
                if alternatives:
                    transcript = alternatives[0].get("transcript", "")
                    confidence = alternatives[0].get("confidence", 0)

            return {"text": transcript, "confidence": confidence}
        except Exception as exc:
            return {"error": f"Deepgram error: {exc}"}

    async def transcribe_url(self, audio_url: str, language: str = "en") -> dict[str, Any]:
        if not self._key:
            return {"error": "DEEPGRAM_API_KEY not set"}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Token {self._key}",
                        "Content-Type": "application/json",
                    },
                    json={"url": audio_url},
                    params={"model": "nova-2", "language": language},
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", {}).get("channels", [{}])
            if results:
                alts = results[0].get("alternatives", [{}])
                if alts:
                    return {"text": alts[0].get("transcript", ""), "confidence": alts[0].get("confidence", 0)}
            return {"text": "", "confidence": 0}
        except Exception as exc:
            return {"error": f"Deepgram error: {exc}"}


# ---------------------------------------------------------------------------
# NeuTTS synthesis (local)
# ---------------------------------------------------------------------------


class NeuTTS:
    """Local neural TTS using NeuTTS models with sample voices.

    Falls back to pyttsx3 or edge-tts if NeuTTS is not available.
    """

    def __init__(self, model_dir: Optional[str] = None) -> None:
        self._model_dir = model_dir or str(Path.home() / ".hermclaw" / "models" / "tts")

    async def synthesize(self, text: str, voice: str = "default",
                         output_path: str = "") -> dict[str, Any]:
        if not output_path:
            out_dir = Path.home() / ".hermclaw" / "tts_output"
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(out_dir / f"neutts_{uuid.uuid4().hex[:8]}.wav")

        # Try piper TTS (fast local TTS)
        try:
            import subprocess
            piper_model = Path(self._model_dir) / f"{voice}.onnx"
            if piper_model.exists():
                proc = subprocess.run(
                    ["piper", "--model", str(piper_model), "--output_file", output_path],
                    input=text.encode(), capture_output=True, timeout=30,
                )
                if proc.returncode == 0:
                    return {"path": output_path, "engine": "piper"}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback to pyttsx3
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file(text[:2000], output_path)
            engine.runAndWait()
            return {"path": output_path, "engine": "pyttsx3"}
        except ImportError:
            pass

        # Fallback to edge-tts
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text[:2000], "en-US-JennyNeural")
            await communicate.save(output_path)
            return {"path": output_path, "engine": "edge-tts"}
        except ImportError:
            return {"error": "No TTS engine available (install piper, pyttsx3, or edge-tts)"}


# ---------------------------------------------------------------------------
# Discord voice doctor
# ---------------------------------------------------------------------------


class DiscordVoiceDoctor:
    """Diagnose Discord voice connection issues."""

    def diagnose(self) -> list[dict[str, str]]:
        """Run all Discord voice diagnostics."""
        results = []

        # Check for discord.py[voice]
        results.append(self._check_discord_voice())
        results.append(self._check_ffmpeg())
        results.append(self._check_opus())
        results.append(self._check_nacl())
        results.append(self._check_network())

        return results

    def _check_discord_voice(self) -> dict[str, str]:
        try:
            import discord
            if hasattr(discord, 'VoiceClient'):
                return {"check": "discord.py[voice]", "status": "✅", "detail": f"Version {discord.__version__}"}
            return {"check": "discord.py[voice]", "status": "⚠️", "detail": "Voice not installed (pip install discord.py[voice])"}
        except ImportError:
            return {"check": "discord.py[voice]", "status": "❌", "detail": "Not installed"}

    def _check_ffmpeg(self) -> dict[str, str]:
        import subprocess
        try:
            proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            version = proc.stdout.split("\n")[0] if proc.stdout else "unknown"
            return {"check": "FFmpeg", "status": "✅", "detail": version[:80]}
        except FileNotFoundError:
            return {"check": "FFmpeg", "status": "❌", "detail": "Not found (required for voice)"}
        except Exception:
            return {"check": "FFmpeg", "status": "⚠️", "detail": "Error checking"}

    def _check_opus(self) -> dict[str, str]:
        try:
            import ctypes.util
            opus = ctypes.util.find_library("opus")
            if opus:
                return {"check": "Opus codec", "status": "✅", "detail": f"Found: {opus}"}
            return {"check": "Opus codec", "status": "⚠️", "detail": "Not found (may use bundled)"}
        except Exception:
            return {"check": "Opus codec", "status": "⚠️", "detail": "Cannot check"}

    def _check_nacl(self) -> dict[str, str]:
        try:
            import nacl
            return {"check": "PyNaCl", "status": "✅", "detail": f"Version {nacl.__version__}"}
        except ImportError:
            return {"check": "PyNaCl", "status": "❌", "detail": "Not installed (pip install PyNaCl)"}

    def _check_network(self) -> dict[str, str]:
        import socket
        try:
            socket.create_connection(("discord.com", 443), timeout=5)
            return {"check": "Discord connectivity", "status": "✅", "detail": "Connected"}
        except Exception:
            return {"check": "Discord connectivity", "status": "❌", "detail": "Cannot reach Discord"}
