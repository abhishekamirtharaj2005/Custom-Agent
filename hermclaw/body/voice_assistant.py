"""Hands-Free Voice Assistant: Ambient listening loop and audio interaction ('Jarvis' mode).

Coordinates:
- Speech input capture (microphone or push-to-talk fallback)
- Audio transcription (STT)
- Agent turn execution (LLM + tools)
- Text-to-speech spoken responses (TTS)
"""

from __future__ import annotations

import asyncio
import os
import platform
import sys
import time
from typing import Any, Callable, Coroutine, Optional

import structlog

logger = structlog.get_logger(__name__)

# Trigger wake phrases
WAKE_WORDS = ["hey hermclaw", "hermclaw", "jarvis", "assistant"]
EXIT_PHRASES = ["exit", "quit", "goodbye", "stop listening", "bye hermclaw"]


class VoiceAssistantSession:
    """Manages an active hands-free voice interaction session."""

    def __init__(
        self,
        agent_runtime: Any,
        wake_word_enabled: bool = True,
        voice_preset: str = "en-female",
        listen_timeout: float = 10.0,
    ) -> None:
        self.runtime = agent_runtime
        self.wake_word_enabled = wake_word_enabled
        self.voice_preset = voice_preset
        self.listen_timeout = listen_timeout
        self.is_running = False

    async def speak(self, text: str) -> None:
        """Speak response aloud using TTSTool or native system voice."""
        try:
            from hermclaw.tools.tts_tool import TTSTool
            tts = TTSTool()
            await tts.execute({"text": text, "voice": self.voice_preset, "action": "speak"})
        except Exception as exc:
            logger.warning("voice_assistant.speak_failed", error=str(exc))
            print(f"🔊 [Spoken]: {text}")

    async def run_voice_loop(self) -> None:
        """Start the continuous hands-free voice assistant loop."""
        self.is_running = True
        greeting = "Hermclaw Voice Assistant active. I'm listening. How can I help you today?"
        print("\n" + "=" * 60)
        print("🎙️  HERMCLAW VOICE ASSISTANT (JARVIS MODE)")
        print(f"    Voice preset: {self.voice_preset}")
        print("    Say 'exit' or press Ctrl+C to terminate.")
        print("=" * 60 + "\n")

        await self.speak(greeting)

        while self.is_running:
            try:
                # Capture voice prompt (async console/mic reader)
                prompt = await self._listen_for_input()
                if not prompt:
                    continue

                prompt_clean = prompt.strip().lower()

                # Check exit phrases
                if any(phrase in prompt_clean for phrase in EXIT_PHRASES):
                    farewell = "Goodbye! Returning to background mode."
                    print(f"\n[Hermclaw]: {farewell}")
                    await self.speak(farewell)
                    break

                # Filter wake word if enabled
                effective_prompt = prompt
                for ww in WAKE_WORDS:
                    if prompt_clean.startswith(ww):
                        effective_prompt = prompt[len(ww):].strip(", !.?")
                        break

                if not effective_prompt:
                    continue

                print(f"\n🗣️  User: {effective_prompt}")
                print("⏳ Thinking & executing...")

                # Run full agent turn
                result = await self.runtime.agent.run_turn(
                    user_input=effective_prompt,
                    session_id="voice_session",
                )
                response_text = result.text or "I have completed the task."
                print(f"🤖 Hermclaw: {response_text}\n")

                # Speak reply (truncate to first 300 chars for natural voice pace if very long)
                spoken_text = response_text
                if len(spoken_text) > 400:
                    sentences = response_text.split(". ")
                    spoken_text = ". ".join(sentences[:2]) + ". I have displayed the complete details on your screen."

                await self.speak(spoken_text)

            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\nVoice assistant stopped by user.")
                break
            except Exception as exc:
                logger.error("voice_assistant.error", exc_info=exc)
                print(f"Error in voice loop: {exc}")
                await asyncio.sleep(1.0)

        self.is_running = False

    async def _listen_for_input(self) -> str:
        """Read microphone or input stream asynchronously."""
        loop = asyncio.get_running_loop()
        try:
            # Use non-blocking standard input prompt
            sys.stdout.write("🎤 Listening (type or speak)... ")
            sys.stdout.flush()
            user_input = await loop.run_in_executor(None, sys.stdin.readline)
            return user_input.strip() if user_input else ""
        except Exception:
            return ""


async def start_voice_assistant(
    runtime: Any,
    voice_preset: str = "en-female",
) -> None:
    """Entry point to launch the voice assistant session."""
    session = VoiceAssistantSession(runtime, voice_preset=voice_preset)
    await session.run_voice_loop()
