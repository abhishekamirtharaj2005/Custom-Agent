#!/usr/bin/env python3
"""
Hermclaw One-Command Installer & Interactive Setup Wizard
=========================================================

Usage:
    pip install hermclaw && hermclaw setup

Or run directly from repo:
    python install.py

This interactive wizard asks everything needed to configure Hermclaw:
  1. Agent & User Personalization (names, timezone, personality)
  2. Primary AI Model Provider & API credentials (Ollama, OpenAI, Claude, Gemini, Groq, DeepSeek, etc.)
  3. Optional Secondary / Fallback Model (auto-failover)
  4. Messaging Channel Connections (Telegram, Discord, WhatsApp, Slack, Teams, Signal, Matrix, Google Chat, Feishu, Mattermost, Twilio SMS, Webhooks)
  5. Web Search & Deep Research APIs (Brave, Tavily, Exa, Firecrawl)
  6. Voice, Music & Media APIs (ElevenLabs, Suno/Udio, fal.ai)
  7. Smart Home Integrations (Home Assistant, Philips Hue, Spotify)
  8. System Permissions & Security (Shell, Computer Use, Approvals)
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ─── ANSI Colors ──────────────────────────────────────────────────────────────

class C:
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE    = "\033[94m"
    WHITE   = "\033[97m"
    RESET   = "\033[0m"


def banner():
    print(f"""
{C.CYAN}{C.BOLD}
  ██╗  ██╗███████╗██████╗ ███╗   ███╗ ██████╗██╗      █████╗ ██╗    ██╗
  ██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██║     ██╔══██╗██║    ██║
  ███████║█████╗  ██████╔╝██╔████╔██║██║     ██║     ███████║██║ █╗ ██║
  ██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██║     ██║     ██╔══██║██║███╗██║
  ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║╚██████╗███████╗██║  ██║╚███╔███╔╝
  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
{C.RESET}
  {C.BOLD}HermClaw Unified AI Assistant — Complete Setup & Configuration Wizard{C.RESET}
  {C.DIM}Models • Channels • Web Search • Voice & Music • Smart Home • Security{C.RESET}
""")


def ask(prompt: str, default: str = "", options: Optional[List[str]] = None) -> str:
    """Ask a question with optional default and options."""
    if options:
        print(f"\n  {C.CYAN}{C.BOLD}{prompt}{C.RESET}")
        for i, opt in enumerate(options, 1):
            is_def = default and (opt == default or opt.startswith(default))
            marker = f"{C.GREEN}→{C.RESET}" if is_def else " "
            print(f"    {marker} {C.BOLD}{i}{C.RESET}) {opt}")
        while True:
            choice = input(f"\n  {C.DIM}Choose [1-{len(options)}]{f' (default: {default})' if default else ''}: {C.RESET}").strip()
            if not choice and default:
                return default
            try:
                idx = int(choice)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            except ValueError:
                for opt in options:
                    if choice.lower() in opt.lower():
                        return opt
            print(f"    {C.RED}Invalid choice. Try again.{C.RESET}")
    else:
        suffix = f" {C.DIM}(default: {default}){C.RESET}" if default else ""
        val = input(f"\n  {C.CYAN}{C.BOLD}{prompt}{suffix}: {C.RESET}").strip()
        return val or default


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question."""
    hint = "Y/n" if default else "y/N"
    val = input(f"\n  {C.CYAN}{C.BOLD}{prompt}{C.RESET} [{hint}]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def ask_secret(prompt: str, env_var: str, description: str = "") -> Tuple[str, str]:
    """Ask for a secret (API key or bot token), returns (env_var_name, value)."""
    existing = os.environ.get(env_var, "")
    if existing:
        masked = existing[:6] + "..." + existing[-4:] if len(existing) > 10 else "***"
        print(f"\n  {C.GREEN}✓{C.RESET} {env_var} already set: {C.DIM}{masked}{C.RESET}")
        reuse = ask_yes_no(f"Keep existing {env_var}?", default=True)
        if reuse:
            return env_var, existing

    desc_line = f"  {C.DIM}{description}{C.RESET}\n" if description else ""
    val = input(f"\n  {C.CYAN}{C.BOLD}{prompt}{C.RESET}\n{desc_line}  {C.DIM}(env: {env_var}, press Enter to skip): {C.RESET}").strip()
    return env_var, val


def run_cmd(cmd: List[str], desc: str, check: bool = True, capture: bool = False) -> Optional[str]:
    """Run a command with clean status display."""
    print(f"  {C.DIM}→ {desc}...{C.RESET}", end="", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=check)
        print(f" {C.GREEN}✓{C.RESET}")
        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError as e:
        print(f" {C.RED}✗{C.RESET}")
        if e.stderr:
            print(f"    {C.RED}{e.stderr.strip()[:200]}{C.RESET}")
        return None
    except FileNotFoundError:
        print(f" {C.RED}✗ (command not found){C.RESET}")
        return None
    except subprocess.TimeoutExpired:
        print(f" {C.YELLOW}⏰ (timed out){C.RESET}")
        return None


def check_python():
    """Verify Python version 3.11+."""
    v = sys.version_info
    if v < (3, 11):
        print(f"\n  {C.RED}✗ Python 3.11+ required, found {v.major}.{v.minor}.{v.micro}{C.RESET}")
        print(f"  {C.DIM}Install Python 3.11+ from https://python.org/downloads{C.RESET}")
        sys.exit(1)
    print(f"  {C.GREEN}✓{C.RESET} Python {v.major}.{v.minor}.{v.micro}", flush=True)


def check_ollama() -> bool:
    """Check if Ollama is installed and actively listening via HTTP."""
    for host in ("127.0.0.1", "localhost"):
        try:
            req = urllib.request.Request(
                f"http://{host}:11434/api/tags",
                headers={"User-Agent": "hermclaw-installer"},
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            continue
    return False


def get_ollama_models() -> List[str]:
    """Get list of locally pulled Ollama models via HTTP REST API."""
    for host in ("127.0.0.1", "localhost"):
        try:
            req = urllib.request.Request(
                f"http://{host}:11434/api/tags",
                headers={"User-Agent": "hermclaw-installer"},
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                    return [m["name"] for m in data.get("models", []) if "name" in m]
        except Exception:
            continue
    return []


# ─── Model Provider Taxonomy ──────────────────────────────────────────────────

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "Ollama (local, free, 100% private — recommended)": {
        "provider": "openai_compat",
        "api_key_env": "OLLAMA_API_KEY",
        "api_base_env": "OLLAMA_API_BASE",
        "context_window": 131072,
        "needs_key": False,
        "default_model": "gemma4:12b",
        "models": ["gemma4:12b", "deepseek-r1:14b", "llama3.3:70b", "qwen2.5-coder:14b", "mistral:7b"],
        "api_base_value": "http://localhost:11434/v1",
        "api_key_value": "ollama",
    },
    "OpenAI (GPT-4o, GPT-4o-mini, o1, o3)": {
        "provider": "openai_compat",
        "api_key_env": "OPENAI_API_KEY",
        "api_base_env": "OPENAI_API_BASE",
        "context_window": 128000,
        "needs_key": True,
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini", "gpt-4-turbo"],
        "api_base_value": "https://api.openai.com/v1",
    },
    "Anthropic Claude (Claude 3.7 Sonnet, Claude 3.5 Haiku, Opus)": {
        "provider": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_base_env": None,
        "context_window": 200000,
        "needs_key": True,
        "default_model": "claude-3-7-sonnet-20250219",
        "models": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
    },
    "Google Gemini (Gemini 2.5 Flash, Gemini 1.5 Pro)": {
        "provider": "gemini",
        "api_key_env": "GEMINI_API_KEY",
        "api_base_env": None,
        "context_window": 1000000,
        "needs_key": True,
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"],
    },
    "Groq (ultra-fast inference: Llama 3.3 70B, DeepSeek)": {
        "provider": "openai_compat",
        "api_key_env": "GROQ_API_KEY",
        "api_base_env": "GROQ_API_BASE",
        "context_window": 131072,
        "needs_key": True,
        "default_model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b", "gemma2-9b-it", "mixtral-8x7b-32768"],
        "api_base_value": "https://api.groq.com/openai/v1",
    },
    "DeepSeek (native API: DeepSeek-V3, DeepSeek-R1)": {
        "provider": "openai_compat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_base_env": "DEEPSEEK_API_BASE",
        "context_window": 64000,
        "needs_key": True,
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "api_base_value": "https://api.deepseek.com/v1",
    },
    "OpenRouter (unified aggregator for 100+ models)": {
        "provider": "openai_compat",
        "api_key_env": "OPENROUTER_API_KEY",
        "api_base_env": "OPENROUTER_API_BASE",
        "context_window": 128000,
        "needs_key": True,
        "default_model": "google/gemini-2.5-flash",
        "models": ["google/gemini-2.5-flash", "anthropic/claude-3.7-sonnet", "meta-llama/llama-3.3-70b-instruct", "deepseek/deepseek-r1"],
        "api_base_value": "https://openrouter.ai/api/v1",
    },
    "Mistral AI (Mistral Large, Codestral)": {
        "provider": "openai_compat",
        "api_key_env": "MISTRAL_API_KEY",
        "api_base_env": "MISTRAL_API_BASE",
        "context_window": 128000,
        "needs_key": True,
        "default_model": "mistral-large-latest",
        "models": ["mistral-large-latest", "codestral-latest", "mistral-small-latest"],
        "api_base_value": "https://api.mistral.ai/v1",
    },
    "Together AI (Llama 3.3, DeepSeek-R1)": {
        "provider": "openai_compat",
        "api_key_env": "TOGETHER_API_KEY",
        "api_base_env": "TOGETHER_API_BASE",
        "context_window": 131072,
        "needs_key": True,
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-R1"],
        "api_base_value": "https://api.together.xyz/v1",
    },
    "Custom OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp)": {
        "provider": "openai_compat",
        "api_key_env": "CUSTOM_API_KEY",
        "api_base_env": "CUSTOM_API_BASE",
        "context_window": 128000,
        "needs_key": False,
        "default_model": "custom-model",
        "models": [],
        "api_base_value": "http://localhost:8000/v1",
        "api_key_value": "none",
    },
}


# ─── Setup Wizard ─────────────────────────────────────────────────────────────

def setup_wizard() -> dict:
    """Complete interactive setup wizard. Collects all configuration settings."""
    settings: Dict[str, Any] = {}
    env_vars: Dict[str, str] = {}
    channels: Dict[str, Any] = {}

    # ── STEP 1: Agent & User Personalization ──────────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 1: Agent & User Identity{C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")

    settings["agent_name"] = ask("Agent Name", default="hermclaw")
    default_user = getpass.getuser()
    settings["user_name"] = ask("Your Name / Nickname", default=default_user)
    settings["timezone"] = ask("Your Timezone / Location (for morning briefings & reminders)", default="Asia/Kolkata")

    persona = ask(
        "Agent Personality Style:",
        default="Jarvis (Proactive, efficient, concise, executive secretary)",
        options=[
            "Jarvis (Proactive, efficient, concise, executive secretary)",
            "Autonomous Engineer (Direct, analytical, coding-first)",
            "Friendly Companion (Supportive, conversational, enthusiastic)",
            "Unrestricted Hacker (No fluff, direct, powerful)",
        ],
    )
    settings["persona"] = persona

    # ── STEP 2: Primary AI Model Provider ─────────────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 2: Primary AI Model & API Key{C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")

    has_ollama = check_ollama()
    provider_names = list(PROVIDERS.keys())
    if has_ollama:
        print(f"\n  {C.GREEN}✓{C.RESET} Ollama is installed and running on your system.")
        models_found = get_ollama_models()
        if models_found:
            print(f"  {C.DIM}Locally available models: {', '.join(models_found[:5])}{C.RESET}")
    else:
        print(f"\n  {C.YELLOW}!{C.RESET} Ollama not detected locally. You can use any cloud provider.")

    chosen_p = ask("Select your primary AI model provider:", default=provider_names[0] if has_ollama else provider_names[1], options=provider_names)
    p_cfg = PROVIDERS[chosen_p]
    settings["provider_config"] = p_cfg

    # Model selection
    if p_cfg["models"]:
        model_name = ask("Select model:", default=p_cfg["default_model"], options=p_cfg["models"])
    else:
        model_name = ask("Enter model identifier:", default=p_cfg["default_model"])
    settings["model_name"] = model_name

    # API key & Base URL
    if p_cfg.get("api_base_value") and p_cfg.get("api_base_env"):
        env_vars[p_cfg["api_base_env"]] = p_cfg["api_base_value"]

    if p_cfg.get("api_key_value"):
        env_vars[p_cfg["api_key_env"]] = p_cfg["api_key_value"]

    if p_cfg["needs_key"]:
        _, key_val = ask_secret(f"Enter API Key for {chosen_p}:", p_cfg["api_key_env"])
        if key_val:
            env_vars[p_cfg["api_key_env"]] = key_val

    if "Custom" in chosen_p:
        custom_base = ask("Enter API Base URL:", default=p_cfg.get("api_base_value", "http://localhost:8000/v1"))
        env_vars[p_cfg["api_base_env"]] = custom_base
        _, custom_key = ask_secret("Enter Custom API Key (optional):", p_cfg["api_key_env"])
        if custom_key:
            env_vars[p_cfg["api_key_env"]] = custom_key

    # ── STEP 3: Fallback Model (Optional) ─────────────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 3: Backup / Fallback Model (Optional){C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.DIM}HermClaw supports automatic failover if your primary provider is down or rate-limited.{C.RESET}")

    settings["fallbacks"] = []
    if ask_yes_no("Configure an auto-failover backup model?"):
        fb_provider_names = [p for p in provider_names if p != chosen_p]
        fb_p_name = ask("Select fallback provider:", options=fb_provider_names)
        fb_cfg = PROVIDERS[fb_p_name]
        fb_model = ask("Select fallback model:", default=fb_cfg["default_model"], options=fb_cfg["models"] if fb_cfg["models"] else None)

        if fb_cfg["needs_key"]:
            _, fb_key = ask_secret(f"Enter API Key for fallback ({fb_p_name}):", fb_cfg["api_key_env"])
            if fb_key:
                env_vars[fb_cfg["api_key_env"]] = fb_key

        if fb_cfg.get("api_base_value") and fb_cfg.get("api_base_env"):
            env_vars[fb_cfg["api_base_env"]] = fb_cfg["api_base_value"]

        settings["fallbacks"].append({
            "provider": fb_cfg["provider"],
            "model_name": fb_model,
            "api_key_env": fb_cfg["api_key_env"],
            "api_base_env": fb_cfg.get("api_base_env"),
            "context_window": fb_cfg.get("context_window", 128000),
        })

    # ── STEP 4: Messaging Channels & Bot Connections ──────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 4: Messaging Platforms & Bot Connections{C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.DIM}CLI chat is always enabled. Connect HermClaw to your messaging surfaces:{C.RESET}")

    # 1. Telegram
    if ask_yes_no("Enable Telegram Bot? (Chat from your phone via Telegram)"):
        channels["telegram"] = {"enabled": True, "mode": "polling"}
        _, tg_token = ask_secret("Telegram Bot Token (from @BotFather):", "TELEGRAM_BOT_TOKEN")
        if tg_token:
            env_vars["TELEGRAM_BOT_TOKEN"] = tg_token

    # 2. Discord
    if ask_yes_no("Enable Discord Bot? (Chat in Discord servers or DMs)"):
        channels["discord"] = {"enabled": True}
        _, dc_token = ask_secret("Discord Bot Token (from Discord Developer Portal):", "DISCORD_BOT_TOKEN")
        if dc_token:
            env_vars["DISCORD_BOT_TOKEN"] = dc_token

    # 3. WhatsApp
    if ask_yes_no("Enable WhatsApp Integration?"):
        channels["whatsapp"] = {"enabled": True}
        print(f"  {C.DIM}WhatsApp supports Cloud API or Node.js Baileys sidecar bridge.{C.RESET}")
        _, wa_token = ask_secret("WhatsApp Cloud API Token (or leave empty for sidecar):", "WHATSAPP_TOKEN")
        if wa_token:
            env_vars["WHATSAPP_TOKEN"] = wa_token
            _, wa_phone = ask_secret("WhatsApp Phone Number ID:", "WHATSAPP_PHONE_ID")
            if wa_phone:
                env_vars["WHATSAPP_PHONE_ID"] = wa_phone

    # 4. Slack
    if ask_yes_no("Enable Slack Bot? (Socket mode workspace bot)"):
        channels["slack"] = {"enabled": True}
        _, sk_bot = ask_secret("Slack Bot Token (xoxb-...):", "SLACK_BOT_TOKEN")
        if sk_bot:
            env_vars["SLACK_BOT_TOKEN"] = sk_bot
        _, sk_app = ask_secret("Slack App-Level Token (xapp-...):", "SLACK_APP_TOKEN")
        if sk_app:
            env_vars["SLACK_APP_TOKEN"] = sk_app

    # 5. Microsoft Teams
    if ask_yes_no("Enable Microsoft Teams? (Incoming webhook)"):
        channels["teams"] = {"enabled": True}
        _, teams_url = ask_secret("Microsoft Teams Webhook URL:", "TEAMS_WEBHOOK_URL")
        if teams_url:
            env_vars["TEAMS_WEBHOOK_URL"] = teams_url

    # 6. Matrix
    if ask_yes_no("Enable Matrix Protocol? (Encrypted decentralized chat)"):
        channels["matrix"] = {"enabled": True}
        h_server = ask("Matrix Homeserver URL:", default="https://matrix.org")
        env_vars["MATRIX_HOMESERVER"] = h_server
        _, m_tok = ask_secret("Matrix Access Token:", "MATRIX_ACCESS_TOKEN")
        if m_tok:
            env_vars["MATRIX_ACCESS_TOKEN"] = m_tok
        m_room = ask("Default Matrix Room ID (optional):", default="")
        if m_room:
            env_vars["MATRIX_ROOM_ID"] = m_room

    # 7. Google Chat
    if ask_yes_no("Enable Google Chat? (Spaces incoming webhook)"):
        channels["google_chat"] = {"enabled": True}
        _, gc_url = ask_secret("Google Chat Webhook URL:", "GOOGLE_CHAT_WEBHOOK")
        if gc_url:
            env_vars["GOOGLE_CHAT_WEBHOOK"] = gc_url

    # 8. Feishu / Lark
    if ask_yes_no("Enable Feishu / Lark Bot?"):
        channels["feishu"] = {"enabled": True}
        _, feishu_url = ask_secret("Feishu / Lark Webhook URL:", "FEISHU_WEBHOOK")
        if feishu_url:
            env_vars["FEISHU_WEBHOOK"] = feishu_url

    # 9. Mattermost
    if ask_yes_no("Enable Mattermost?"):
        channels["mattermost"] = {"enabled": True}
        mm_url = ask("Mattermost Server URL:", default="http://localhost:8065")
        env_vars["MATTERMOST_URL"] = mm_url
        _, mm_tok = ask_secret("Mattermost Bot Token:", "MATTERMOST_TOKEN")
        if mm_tok:
            env_vars["MATTERMOST_TOKEN"] = mm_tok

    # 10. Twilio SMS / WhatsApp
    if ask_yes_no("Enable Twilio SMS / WhatsApp?"):
        channels["twilio"] = {"enabled": True}
        _, tw_sid = ask_secret("Twilio Account SID:", "TWILIO_ACCOUNT_SID")
        if tw_sid:
            env_vars["TWILIO_ACCOUNT_SID"] = tw_sid
        _, tw_auth = ask_secret("Twilio Auth Token:", "TWILIO_AUTH_TOKEN")
        if tw_auth:
            env_vars["TWILIO_AUTH_TOKEN"] = tw_auth
        tw_from = ask("Twilio Sender Phone Number (e.g. +1234567890):")
        if tw_from:
            env_vars["TWILIO_FROM_NUMBER"] = tw_from

    # 11. Generic Webhook
    if ask_yes_no("Enable Universal Generic Webhook?"):
        channels["webhook"] = {"enabled": True}
        _, wh_url = ask_secret("Webhook URL:", "WEBHOOK_URL")
        if wh_url:
            env_vars["WEBHOOK_URL"] = wh_url
        _, wh_sec = ask_secret("Webhook HMAC Secret (optional):", "WEBHOOK_SECRET")
        if wh_sec:
            env_vars["WEBHOOK_SECRET"] = wh_sec

    settings["channels"] = channels

    # ── STEP 5: Search & Web Intelligence Keys ────────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 5: Web Search & Intelligence APIs (Optional){C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.DIM}Note: Free web search & local scraping work out-of-the-box without keys.{C.RESET}")
    print(f"  {C.DIM}Configure optional research APIs if you have them (press Enter to skip):{C.RESET}")

    _, brave_key = ask_secret("Brave Search API Key (for privacy search):", "BRAVE_API_KEY")
    if brave_key:
        env_vars["BRAVE_API_KEY"] = brave_key

    _, tavily_key = ask_secret("Tavily Search API Key (for research agents):", "TAVILY_API_KEY")
    if tavily_key:
        env_vars["TAVILY_API_KEY"] = tavily_key

    _, exa_key = ask_secret("Exa Neural Search Key (for semantic web search):", "EXA_API_KEY")
    if exa_key:
        env_vars["EXA_API_KEY"] = exa_key

    _, fc_key = ask_secret("Firecrawl API Key (for deep site crawls & sitemaps):", "FIRECRAWL_API_KEY")
    if fc_key:
        env_vars["FIRECRAWL_API_KEY"] = fc_key

    # ── STEP 6: Media, Voice & Music Generation ───────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 6: Voice, Music & Media Generation APIs (Optional){C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.DIM}Note: Built-in local TTS and procedural harmonic audio synthesis work without keys.{C.RESET}")

    _, eleven_key = ask_secret("ElevenLabs API Key (for hyper-realistic voice & audio):", "ELEVENLABS_API_KEY")
    if eleven_key:
        env_vars["ELEVENLABS_API_KEY"] = eleven_key

    _, suno_key = ask_secret("Suno AI API Key (for AI song & beat generation):", "SUNO_API_KEY")
    if suno_key:
        env_vars["SUNO_API_KEY"] = suno_key

    _, fal_key = ask_secret("fal.ai API Key (for FLUX / SD fast image generation):", "FAL_KEY")
    if fal_key:
        env_vars["FAL_KEY"] = fal_key

    # ── STEP 7: Smart Home & Hardware Integrations ────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 7: Smart Home & Hardware Control (Optional){C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")

    if ask_yes_no("Configure Home Assistant smart home bridge?"):
        ha_url = ask("Home Assistant URL:", default="http://localhost:8123")
        env_vars["HA_URL"] = ha_url
        _, ha_tok = ask_secret("Home Assistant Long-Lived Access Token:", "HA_TOKEN")
        if ha_tok:
            env_vars["HA_TOKEN"] = ha_tok

    if ask_yes_no("Configure Philips Hue lighting bridge?"):
        hue_ip = ask("Philips Hue Bridge IP on local LAN:")
        if hue_ip:
            env_vars["HUE_BRIDGE_IP"] = hue_ip
        _, hue_key = ask_secret("Philips Hue Bridge Username/API Key:", "HUE_API_KEY")
        if hue_key:
            env_vars["HUE_API_KEY"] = hue_key

    if ask_yes_no("Configure Spotify integration?"):
        _, sp_id = ask_secret("Spotify Client ID:", "SPOTIFY_CLIENT_ID")
        if sp_id:
            env_vars["SPOTIFY_CLIENT_ID"] = sp_id
        _, sp_sec = ask_secret("Spotify Client Secret:", "SPOTIFY_CLIENT_SECRET")
        if sp_sec:
            env_vars["SPOTIFY_CLIENT_SECRET"] = sp_sec

    # ── STEP 8: Security & System Permissions ─────────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 8: System Permissions & Security Sandbox{C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")

    settings["shell_enabled"] = ask_yes_no("Enable Terminal & Shell Command Execution?", default=True)
    settings["computer_use"] = ask_yes_no("Enable Live Screen Awareness & Mouse/Keyboard Control?", default=True)

    approval_choice = ask(
        "Tool Approval Mode:",
        default="off",
        options=[
            "off (fully autonomous execution without interruption)",
            "smart (auto-approve safe commands, ask only on critical risks)",
            "manual (ask before executing every tool or command)",
        ],
    )
    mode = approval_choice.split(" ")[0].lower()
    if mode not in ("off", "smart", "manual"):
        mode = "off"
    settings["approval_mode"] = mode
    settings["env_vars"] = env_vars

    return settings


# ─── Config Generator ────────────────────────────────────────────────────────

def generate_config(settings: dict) -> str:
    """Generate complete hermclaw.yaml from collected settings."""
    p_cfg = settings["provider_config"]
    model_name = settings["model_name"]
    agent_name = settings.get("agent_name", "hermclaw")
    channels = settings.get("channels", {})

    api_base_line = f'    api_base_env: "{p_cfg["api_base_env"]}"' if p_cfg.get("api_base_env") else "    api_base_env: null"
    api_key_line = f'    api_key_env: "{p_cfg["api_key_env"]}"'

    # Build channels section
    ch_lines = [
        f"    cli:\n      enabled: true",
        f"    web:\n      enabled: false",
        f"    telegram:\n      enabled: {str(channels.get('telegram', {}).get('enabled', False)).lower()}\n      bot_token_env: \"TELEGRAM_BOT_TOKEN\"\n      mode: \"polling\"",
        f"    discord:\n      enabled: {str(channels.get('discord', {}).get('enabled', False)).lower()}\n      bot_token_env: \"DISCORD_BOT_TOKEN\"",
        f"    slack:\n      enabled: {str(channels.get('slack', {}).get('enabled', False)).lower()}\n      bot_token_env: \"SLACK_BOT_TOKEN\"\n      app_token_env: \"SLACK_APP_TOKEN\"\n      socket_mode: true",
        f"    whatsapp:\n      enabled: {str(channels.get('whatsapp', {}).get('enabled', False)).lower()}",
        f"    teams:\n      enabled: {str(channels.get('teams', {}).get('enabled', False)).lower()}\n      webhook_url_env: \"TEAMS_WEBHOOK_URL\"",
        f"    signal:\n      enabled: {str(channels.get('signal', {}).get('enabled', False)).lower()}\n      api_url_env: \"SIGNAL_API_URL\"\n      number_env: \"SIGNAL_NUMBER\"",
        f"    matrix:\n      enabled: {str(channels.get('matrix', {}).get('enabled', False)).lower()}\n      homeserver_env: \"MATRIX_HOMESERVER\"\n      access_token_env: \"MATRIX_ACCESS_TOKEN\"\n      room_id_env: \"MATRIX_ROOM_ID\"",
        f"    google_chat:\n      enabled: {str(channels.get('google_chat', {}).get('enabled', False)).lower()}\n      webhook_url_env: \"GOOGLE_CHAT_WEBHOOK\"",
        f"    feishu:\n      enabled: {str(channels.get('feishu', {}).get('enabled', False)).lower()}\n      webhook_url_env: \"FEISHU_WEBHOOK\"",
        f"    mattermost:\n      enabled: {str(channels.get('mattermost', {}).get('enabled', False)).lower()}\n      server_url_env: \"MATTERMOST_URL\"\n      token_env: \"MATTERMOST_TOKEN\"",
        f"    twilio:\n      enabled: {str(channels.get('twilio', {}).get('enabled', False)).lower()}\n      account_sid_env: \"TWILIO_ACCOUNT_SID\"\n      auth_token_env: \"TWILIO_AUTH_TOKEN\"\n      from_number_env: \"TWILIO_FROM_NUMBER\"",
        f"    webhook:\n      enabled: {str(channels.get('webhook', {}).get('enabled', False)).lower()}\n      webhook_url_env: \"WEBHOOK_URL\"\n      secret_env: \"WEBHOOK_SECRET\"",
    ]
    channels_yaml = "\n".join(ch_lines)

    # Build fallbacks section
    fb_lines = []
    for fb in settings.get("fallbacks", []):
        fb_base = f'      api_base_env: "{fb["api_base_env"]}"' if fb.get("api_base_env") else "      api_base_env: null"
        fb_lines.append(f"""    - provider: "{fb['provider']}"
      model_name: "{fb['model_name']}"
      api_key_env: "{fb['api_key_env']}"
{fb_base}
      context_window: {fb.get('context_window', 128000)}""")

    fallbacks_yaml = "\n".join(fb_lines) if fb_lines else "    fallbacks: []"
    if fb_lines:
        fallbacks_yaml = "    fallbacks:\n" + fallbacks_yaml

    shell_enabled = str(settings.get("shell_enabled", True)).lower()
    approval_mode = settings.get("approval_mode", "off")

    return f"""# Hermclaw Configuration
# Generated interactively by HermClaw Setup Wizard on {time.strftime('%Y-%m-%d %H:%M:%S')}

agent:
  name: "{agent_name}"
  default_profile: "default"
  list: []

body:
  gateway:
    bind: "loopback"
    host: "127.0.0.1"
    port: 18789
    auth:
      mode: "token"
      token_env: "HERMCLAW_GATEWAY_TOKEN"

  channels:
{channels_yaml}

  scheduler:
    heartbeat:
      enabled: true
      every: "30m"
      show_ok: false
      show_alerts: true
    jobs: []

brain:
  model:
    provider: "{p_cfg['provider']}"
    model_name: "{model_name}"
{api_key_line}
{api_base_line}
    context_window: {p_cfg.get('context_window', 131072)}
{fallbacks_yaml}
  memory:
    compression_threshold: 0.3
    keep_recent_exchanges: 2
    memory_char_limit: 100000
    user_char_limit: 100000
  reflection:
    enabled: true
    trigger_every_n_turns: 10

skills:
  directory: "~/.hermclaw/profiles/default/skills"
  extra_directories: []
  evolution_enabled: true
  mcp_servers: []

tools:
  shell_enabled: {shell_enabled}
  approvals:
    mode: "{approval_mode}"
  backend: "local"
  docker_image: "python:3.11-slim"
  docker_network: "none"
  ssh_host: null
  ssh_user: null
  ssh_identity_file: null
  network_enabled: true
  filesystem_scope: "~"

profiles: {{}}
"""


# ─── Installer ────────────────────────────────────────────────────────────────

def install(settings: dict):
    """Execute installation and persist configuration and credentials."""
    hermclaw_dir = Path.home() / ".hermclaw"
    profile_dir = hermclaw_dir / "profiles" / "default"
    config_path = hermclaw_dir / "hermclaw.yaml"
    env_path = hermclaw_dir / ".env"

    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}INSTALLING & INITIALIZING HERMCLAW{C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}\n")

    # 1. Create directory structure
    print(f"  {C.DIM}→ Creating profile directories...{C.RESET}", end="", flush=True)
    hermclaw_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "skills").mkdir(parents=True, exist_ok=True)
    (profile_dir / "vault").mkdir(parents=True, exist_ok=True)
    (profile_dir / "workspace").mkdir(parents=True, exist_ok=True)
    print(f" {C.GREEN}✓{C.RESET}")

    # 2. Write User Profile & Identity
    user_md = profile_dir / "USER.md"
    identity_md = profile_dir / "IDENTITY.md"

    user_content = (
        f"# User Profile\n\n"
        f"- Name: {settings.get('user_name', 'User')}\n"
        f"- Timezone / Location: {settings.get('timezone', 'UTC')}\n"
        f"- Preferred Persona: {settings.get('persona', 'Jarvis')}\n"
    )
    user_md.write_text(user_content, encoding="utf-8")

    identity_content = (
        f"# Agent Identity\n\n"
        f"- Name: {settings.get('agent_name', 'hermclaw')}\n"
        f"- Personality: {settings.get('persona', 'Jarvis')}\n"
        f"- Role: Personal Autonomous Assistant\n"
    )
    identity_md.write_text(identity_content, encoding="utf-8")

    # 3. Write config
    print(f"  {C.DIM}→ Writing configuration to {config_path}...{C.RESET}", end="", flush=True)
    if config_path.exists():
        backup = config_path.with_suffix(".yaml.backup")
        try:
            config_path.rename(backup)
            print(f"\n    {C.YELLOW}⚠ Existing config backed up to {backup.name}{C.RESET}", end="")
        except Exception:
            pass
    config_yaml = generate_config(settings)
    config_path.write_text(config_yaml, encoding="utf-8")
    print(f" {C.GREEN}✓{C.RESET}")

    # 4. Write secrets to .env
    env_vars = settings.get("env_vars", {})
    if env_vars:
        print(f"  {C.DIM}→ Saving credentials to {env_path}...{C.RESET}", end="", flush=True)
        existing_lines = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    existing_lines[k.strip()] = v.strip().strip('"')
        existing_lines.update(env_vars)

        lines = [f'{k}="{v}"' for k, v in existing_lines.items()]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if platform.system() != "Windows":
            os.chmod(str(env_path), 0o600)
        print(f" {C.GREEN}✓{C.RESET}")

    # 5. Pull Ollama model if needed
    if "Ollama" in str(settings.get("provider_config", {}).get("api_key_env", "")):
        model_name = settings["model_name"]
        existing = get_ollama_models()
        if model_name not in existing:
            print(f"\n  {C.CYAN}Pulling Ollama model: {model_name}{C.RESET}")
            print(f"  {C.DIM}(Downloading model weights via Ollama...){C.RESET}")
            try:
                subprocess.run(["ollama", "pull", model_name], check=True, timeout=600)
                print(f"  {C.GREEN}✓ Model {model_name} pulled successfully{C.RESET}")
            except Exception as e:
                print(f"  {C.YELLOW}⚠ Could not pull model automatically: {e}{C.RESET}")
                print(f"  {C.DIM}Run manually when convenient: ollama pull {model_name}{C.RESET}")
        else:
            print(f"  {C.GREEN}✓{C.RESET} Local model {model_name} is ready")

    # 6. Verify config and import
    print()
    try:
        from hermclaw.config import load_config
        res = load_config(config_path)
        if res.valid:
            print(f"  {C.GREEN}✓{C.RESET} Config verification: VALID")
        else:
            print(f"  {C.YELLOW}⚠ Config verification warnings: {res.errors}{C.RESET}")
    except Exception as exc:
        print(f"  {C.YELLOW}⚠ Verification notice: {exc}{C.RESET}")

    # ── Summary & Success ────────────────────────────────────────────────
    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}✅ HERMCLAW CONFIGURED & READY!{C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")

    enabled_channels = [k for k, v in settings.get("channels", {}).items() if v.get("enabled")]
    channel_summary = ", ".join(["cli"] + enabled_channels)

    print(f"""
  {C.BOLD}User:{C.RESET}       {settings.get('user_name', 'User')} ({settings.get('timezone', 'Local')})
  {C.BOLD}Agent:{C.RESET}      {settings.get('agent_name', 'hermclaw')} ({settings.get('persona', 'Jarvis')})
  {C.BOLD}Model:{C.RESET}      {settings['model_name']} ({settings['provider_config']['provider']})
  {C.BOLD}Channels:{C.RESET}   {channel_summary}
  {C.BOLD}Shell Exec:{C.RESET} {'Enabled' if settings.get('shell_enabled') else 'Disabled'}
  {C.BOLD}Computer:{C.RESET}   {'Enabled (Mouse & Keyboard)' if settings.get('computer_use') else 'Disabled'}
  {C.BOLD}Config:{C.RESET}     {config_path}
  {C.BOLD}Secrets:{C.RESET}    {env_path}

  {C.BOLD}{C.CYAN}Commands to get started:{C.RESET}
    {C.BOLD}hermclaw chat{C.RESET}          {C.DIM}# Launch interactive terminal chat{C.RESET}
    {C.BOLD}hermclaw doctor{C.RESET}        {C.DIM}# Run system & credentials health check{C.RESET}
    {C.BOLD}hermclaw serve{C.RESET}         {C.DIM}# Start gateway with connected channels{C.RESET}
    {C.BOLD}hermclaw dashboard{C.RESET}     {C.DIM}# Launch unified web dashboard{C.RESET}
    {C.BOLD}hermclaw voice{C.RESET}         {C.DIM}# Hands-free conversational voice assistant{C.RESET}
    {C.BOLD}hermclaw setup{C.RESET}         {C.DIM}# Re-run this setup wizard anytime{C.RESET}
""")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    banner()
    print(f"  {C.BOLD}Pre-flight diagnostic:{C.RESET}", flush=True)
    check_python()

    if check_ollama():
        print(f"  {C.GREEN}✓{C.RESET} Ollama service active", flush=True)
    else:
        print(f"  {C.YELLOW}!{C.RESET} Ollama not active (cloud providers ready)", flush=True)

    settings = setup_wizard()

    print(f"\n{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}SETUP CONFIGURATION REVIEW{C.RESET}")
    print(f"{C.BOLD}{'─' * 65}{C.RESET}")
    print(f"  Agent Name:  {C.CYAN}{settings.get('agent_name')}{C.RESET}")
    print(f"  User Name:   {C.CYAN}{settings.get('user_name')}{C.RESET}")
    print(f"  Provider:    {C.CYAN}{settings['provider_config']['provider']}{C.RESET}")
    print(f"  Model:       {C.CYAN}{settings['model_name']}{C.RESET}")
    chs = [k for k, v in settings.get("channels", {}).items() if v.get("enabled")]
    print(f"  Channels:    {C.CYAN}{', '.join(['cli'] + chs)}{C.RESET}")
    print(f"  Shell Access:{C.CYAN}{'Enabled' if settings.get('shell_enabled') else 'Disabled'}{C.RESET}")
    print(f"  Approvals:   {C.CYAN}{settings.get('approval_mode', 'off')}{C.RESET}")

    if not ask_yes_no("\n  Save configuration and complete setup?", default=True):
        print(f"\n  {C.YELLOW}Setup cancelled. No files were modified.{C.RESET}\n")
        sys.exit(0)

    install(settings)


if __name__ == "__main__":
    main()
