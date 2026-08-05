#!/usr/bin/env python3
"""
Hermclaw One-Command Installer & Setup Wizard
==============================================

Usage:
    pip install hermclaw && hermclaw setup

Or run directly from the repo:
    python install.py

This script:
  1. Asks interactive configuration questions
  2. Installs hermclaw + selected extras
  3. Generates ~/.hermclaw/hermclaw.yaml
  4. Pulls Ollama model if needed
  5. Verifies the installation
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

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
  {C.DIM}Unified, Self-Improving Personal AI Agent{C.RESET}
  {C.DIM}28 tools • persistent memory • self-learning • no guardrails{C.RESET}
""")


def ask(prompt: str, default: str = "", options: list[str] | None = None) -> str:
    """Ask a question with optional default and options."""
    if options:
        print(f"\n  {C.CYAN}{prompt}{C.RESET}")
        for i, opt in enumerate(options, 1):
            marker = f"{C.GREEN}→{C.RESET}" if (default and opt == default) else " "
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
                # Allow typing the option name directly
                for opt in options:
                    if choice.lower() in opt.lower():
                        return opt
            print(f"    {C.RED}Invalid choice. Try again.{C.RESET}")
    else:
        suffix = f" {C.DIM}(default: {default}){C.RESET}" if default else ""
        val = input(f"\n  {C.CYAN}{prompt}{suffix}: {C.RESET}").strip()
        return val or default


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask a yes/no question."""
    hint = "Y/n" if default else "y/N"
    val = input(f"\n  {C.CYAN}{prompt} [{hint}]: {C.RESET}").strip().lower()
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def ask_secret(prompt: str, env_var: str) -> tuple[str, str]:
    """Ask for a secret (API key), returns (env_var_name, value)."""
    existing = os.environ.get(env_var, "")
    if existing:
        masked = existing[:8] + "..." + existing[-4:] if len(existing) > 12 else "***"
        print(f"\n  {C.GREEN}✓{C.RESET} {env_var} already set: {C.DIM}{masked}{C.RESET}")
        return env_var, existing
    val = input(f"\n  {C.CYAN}{prompt}\n  {C.DIM}(env var: {env_var}, leave empty to skip): {C.RESET}").strip()
    return env_var, val


def run_cmd(cmd: list[str], desc: str, check: bool = True, capture: bool = False) -> Optional[str]:
    """Run a command with status display."""
    print(f"  {C.DIM}→ {desc}...{C.RESET}", end="", flush=True)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=300, check=check,
        )
        print(f" {C.GREEN}✓{C.RESET}")
        if capture:
            return result.stdout.strip()
        return None
    except subprocess.CalledProcessError as e:
        print(f" {C.RED}✗{C.RESET}")
        if e.stderr:
            print(f"    {C.RED}{e.stderr.strip()[:200]}{C.RESET}")
        if check:
            raise
        return None
    except FileNotFoundError:
        print(f" {C.RED}✗ (command not found){C.RESET}")
        return None
    except subprocess.TimeoutExpired:
        print(f" {C.YELLOW}⏰ (timed out){C.RESET}")
        return None


def check_python():
    """Verify Python version."""
    v = sys.version_info
    if v < (3, 11):
        print(f"\n  {C.RED}✗ Python 3.11+ required, found {v.major}.{v.minor}.{v.micro}{C.RESET}")
        print(f"  {C.DIM}Install from https://python.org/downloads{C.RESET}")
        sys.exit(1)
    print(f"  {C.GREEN}✓{C.RESET} Python {v.major}.{v.minor}.{v.micro}")


def check_ollama() -> bool:
    """Check if Ollama is installed and running."""
    if not shutil.which("ollama"):
        return False
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_ollama_models() -> list[str]:
    """Get list of pulled Ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            models = []
            for line in lines[1:]:  # skip header
                parts = line.split()
                if parts:
                    models.append(parts[0])
            return models
    except Exception:
        pass
    return []


# ─── Model Provider Configs ──────────────────────────────────────────────────

PROVIDERS = {
    "Ollama (local, free — recommended)": {
        "provider": "openai_compat",
        "api_key_env": "OLLAMA_API_KEY",
        "api_base_env": "OLLAMA_API_BASE",
        "context_window": 131072,
        "needs_key": False,
        "default_model": "gemma4:12b",
        "models": ["gemma4:12b", "gemma4:27b", "llama3.3:70b", "qwen3:14b", "deepseek-r1:14b", "mistral:7b"],
    },
    "OpenAI": {
        "provider": "openai_compat",
        "api_key_env": "OPENAI_API_KEY",
        "api_base_env": None,
        "context_window": 128000,
        "needs_key": True,
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "Anthropic (Claude)": {
        "provider": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_base_env": None,
        "context_window": 200000,
        "needs_key": True,
        "default_model": "claude-sonnet-4-20250514",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
    },
    "Groq (fast, free tier)": {
        "provider": "openai_compat",
        "api_key_env": "GROQ_API_KEY",
        "api_base_env": "GROQ_API_BASE",
        "context_window": 131072,
        "needs_key": True,
        "default_model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "gemma2-9b-it", "mixtral-8x7b-32768"],
        "api_base_value": "https://api.groq.com/openai/v1",
    },
    "OpenRouter (100+ models)": {
        "provider": "openai_compat",
        "api_key_env": "OPENROUTER_API_KEY",
        "api_base_env": "OPENROUTER_API_BASE",
        "context_window": 128000,
        "needs_key": True,
        "default_model": "google/gemma-3-27b-it",
        "models": ["google/gemma-3-27b-it", "meta-llama/llama-3.3-70b-instruct", "anthropic/claude-sonnet-4"],
        "api_base_value": "https://openrouter.ai/api/v1",
    },
    "Custom OpenAI-compatible": {
        "provider": "openai_compat",
        "api_key_env": "CUSTOM_API_KEY",
        "api_base_env": "CUSTOM_API_BASE",
        "context_window": 128000,
        "needs_key": True,
        "default_model": "",
        "models": [],
    },
}


# ─── Config Generator ────────────────────────────────────────────────────────

def generate_config(settings: dict) -> str:
    """Generate hermclaw.yaml from collected settings."""
    provider_cfg = settings["provider_config"]
    model_name = settings["model_name"]
    channels = settings.get("channels", {})
    api_base_line = ""
    if provider_cfg.get("api_base_env"):
        api_base_line = f'    api_base_env: "{provider_cfg["api_base_env"]}"'
    else:
        api_base_line = "    api_base_env: null"

    channel_sections = []
    for ch_name, ch_cfg in [
        ("telegram", channels.get("telegram", {})),
        ("discord", channels.get("discord", {})),
        ("slack", channels.get("slack", {})),
    ]:
        enabled = ch_cfg.get("enabled", False)
        if ch_name == "telegram":
            channel_sections.append(f"""    telegram:
      enabled: {str(enabled).lower()}
      bot_token_env: "TELEGRAM_BOT_TOKEN"
      mode: "polling" """)
        elif ch_name == "discord":
            channel_sections.append(f"""    discord:
      enabled: {str(enabled).lower()}
      bot_token_env: "DISCORD_BOT_TOKEN" """)
        elif ch_name == "slack":
            channel_sections.append(f"""    slack:
      enabled: {str(enabled).lower()}
      bot_token_env: "SLACK_BOT_TOKEN"
      app_token_env: "SLACK_APP_TOKEN"
      socket_mode: true""")

    channels_yaml = "\n".join(channel_sections)
    api_key_line = f'    api_key_env: "{provider_cfg["api_key_env"]}"'

    shell_enabled = str(settings.get("shell_enabled", True)).lower()
    approval_mode = settings.get("approval_mode", "off")

    return f"""# Hermclaw configuration
# Generated by hermclaw setup wizard

agent:
  name: "hermclaw"
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
    cli:
      enabled: true
    web:
      enabled: false
    whatsapp:
      enabled: false

  scheduler:
    heartbeat:
      enabled: true
      every: "30m"
      show_ok: false
      show_alerts: true
    jobs: []

brain:
  model:
    provider: "{provider_cfg['provider']}"
    model_name: "{model_name}"
{api_key_line}
{api_base_line}
    context_window: {provider_cfg['context_window']}
    fallbacks: []
  memory:
    compression_threshold: 0.5
    keep_recent_exchanges: 2
    memory_char_limit: 2200
    user_char_limit: 1375
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


# ─── Setup Wizard ─────────────────────────────────────────────────────────────

def setup_wizard() -> dict:
    """Interactive setup wizard. Returns settings dict."""
    settings = {}

    # ── Step 1: Model Provider ───────────────────────────────────────────
    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 1: Model Provider{C.RESET}")
    print(f"{C.BOLD}{'─' * 60}{C.RESET}")

    provider_names = list(PROVIDERS.keys())
    has_ollama = check_ollama()

    if has_ollama:
        print(f"\n  {C.GREEN}✓{C.RESET} Ollama detected and running")
        existing_models = get_ollama_models()
        if existing_models:
            print(f"  {C.DIM}Available models: {', '.join(existing_models[:5])}{C.RESET}")
    else:
        print(f"\n  {C.YELLOW}⚠{C.RESET} Ollama not detected. You can still use cloud providers.")
        print(f"  {C.DIM}Install Ollama: https://ollama.com/download{C.RESET}")

    default_provider = provider_names[0] if has_ollama else provider_names[1]
    chosen_provider = ask("Choose your model provider:", default=default_provider, options=provider_names)
    provider_cfg = PROVIDERS[chosen_provider]
    settings["provider_config"] = provider_cfg

    # ── Model selection ──────────────────────────────────────────────────
    if provider_cfg["models"]:
        model = ask("Choose a model:", default=provider_cfg["default_model"], options=provider_cfg["models"])
    else:
        model = ask("Enter the model name:", default=provider_cfg["default_model"])
    settings["model_name"] = model

    # ── API key ──────────────────────────────────────────────────────────
    env_vars = {}
    if provider_cfg["needs_key"]:
        key_env, key_val = ask_secret(
            f"Enter your API key for {chosen_provider}:",
            provider_cfg["api_key_env"],
        )
        if key_val:
            env_vars[key_env] = key_val

    if provider_cfg.get("api_base_value"):
        env_vars[provider_cfg["api_base_env"]] = provider_cfg["api_base_value"]
    elif provider_cfg.get("api_base_env") and "Custom" in chosen_provider:
        base_url = ask("Enter the API base URL:", default="http://localhost:11434/v1")
        if base_url:
            env_vars[provider_cfg["api_base_env"]] = base_url

    settings["env_vars"] = env_vars

    # ── Step 2: Chat Platforms ───────────────────────────────────────────
    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 2: Chat Platforms{C.RESET}")
    print(f"{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"\n  {C.DIM}CLI chat is always enabled. Choose additional platforms:{C.RESET}")

    channels = {}

    # Telegram
    if ask_yes_no("Enable Telegram bot?"):
        channels["telegram"] = {"enabled": True}
        _, tg_token = ask_secret("Telegram bot token:", "TELEGRAM_BOT_TOKEN")
        if tg_token:
            env_vars["TELEGRAM_BOT_TOKEN"] = tg_token

    # Discord
    if ask_yes_no("Enable Discord bot?"):
        channels["discord"] = {"enabled": True}
        _, dc_token = ask_secret("Discord bot token:", "DISCORD_BOT_TOKEN")
        if dc_token:
            env_vars["DISCORD_BOT_TOKEN"] = dc_token

    # Slack
    if ask_yes_no("Enable Slack bot?"):
        channels["slack"] = {"enabled": True}
        _, sk_bot = ask_secret("Slack bot token:", "SLACK_BOT_TOKEN")
        if sk_bot:
            env_vars["SLACK_BOT_TOKEN"] = sk_bot
        _, sk_app = ask_secret("Slack app token:", "SLACK_APP_TOKEN")
        if sk_app:
            env_vars["SLACK_APP_TOKEN"] = sk_app

    settings["channels"] = channels

    # ── Step 3: Security ─────────────────────────────────────────────────
    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}STEP 3: Security & Permissions{C.RESET}")
    print(f"{C.BOLD}{'─' * 60}{C.RESET}")

    settings["shell_enabled"] = ask_yes_no("Enable shell access (run terminal commands)?", default=True)

    approval_mode = ask(
        "Tool approval mode:",
        default="off",
        options=["off (run everything directly)", "auto (auto-approve safe commands)", "always (ask before every command)"],
    )
    settings["approval_mode"] = approval_mode.split(" ")[0]

    return settings


# ─── Installer ────────────────────────────────────────────────────────────────

def install(settings: dict):
    """Execute installation based on collected settings."""
    hermclaw_dir = Path.home() / ".hermclaw"
    config_path = hermclaw_dir / "hermclaw.yaml"
    env_path = hermclaw_dir / ".env"

    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}INSTALLING HERMCLAW{C.RESET}")
    print(f"{C.BOLD}{'─' * 60}{C.RESET}\n")

    # 1. Create directories
    print(f"  {C.DIM}→ Creating directories...{C.RESET}", end="", flush=True)
    hermclaw_dir.mkdir(parents=True, exist_ok=True)
    (hermclaw_dir / "profiles" / "default" / "skills").mkdir(parents=True, exist_ok=True)
    print(f" {C.GREEN}✓{C.RESET}")

    # 2. Install hermclaw package
    install_cmd = [sys.executable, "-m", "pip", "install", "-e", "."]

    # Add extras based on channels
    extras = []
    channels = settings.get("channels", {})
    if channels.get("telegram", {}).get("enabled"):
        extras.append("telegram")
    if channels.get("discord", {}).get("enabled"):
        extras.append("discord")
    if channels.get("slack", {}).get("enabled"):
        extras.append("slack")

    provider_cfg = settings["provider_config"]
    if provider_cfg["provider"] == "anthropic":
        extras.append("anthropic")

    if extras:
        install_cmd = [sys.executable, "-m", "pip", "install", "-e", f".[{','.join(extras)}]"]

    run_cmd(install_cmd, "Installing hermclaw package")

    # 3. Write config
    print(f"  {C.DIM}→ Writing config to {config_path}...{C.RESET}", end="", flush=True)
    if config_path.exists():
        backup = config_path.with_suffix(".yaml.backup")
        config_path.rename(backup)
        print(f"\n    {C.YELLOW}⚠ Existing config backed up to {backup.name}{C.RESET}", end="")
    config_yaml = generate_config(settings)
    config_path.write_text(config_yaml, encoding="utf-8")
    print(f" {C.GREEN}✓{C.RESET}")

    # 4. Write .env file with secrets
    env_vars = settings.get("env_vars", {})
    if env_vars:
        print(f"  {C.DIM}→ Writing secrets to {env_path}...{C.RESET}", end="", flush=True)
        env_lines = []
        if env_path.exists():
            # Preserve existing entries
            for line in env_path.read_text().splitlines():
                key = line.split("=")[0].strip() if "=" in line else ""
                if key and key not in env_vars:
                    env_lines.append(line)
        for key, val in env_vars.items():
            env_lines.append(f'{key}="{val}"')
        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        # Restrict permissions on .env
        if platform.system() != "Windows":
            os.chmod(str(env_path), 0o600)
        print(f" {C.GREEN}✓{C.RESET}")

    # 5. Pull Ollama model if using Ollama
    if "Ollama" in str(settings.get("provider_config", {}).get("api_key_env", "")):
        model_name = settings["model_name"]
        existing = get_ollama_models()
        if model_name not in existing:
            print(f"\n  {C.CYAN}Pulling Ollama model: {model_name}{C.RESET}")
            print(f"  {C.DIM}(this may take a few minutes on first run){C.RESET}\n")
            try:
                subprocess.run(
                    ["ollama", "pull", model_name],
                    check=True, timeout=600,
                )
                print(f"\n  {C.GREEN}✓ Model {model_name} pulled successfully{C.RESET}")
            except subprocess.TimeoutExpired:
                print(f"\n  {C.YELLOW}⏰ Model pull timed out. Run manually: ollama pull {model_name}{C.RESET}")
            except Exception as e:
                print(f"\n  {C.YELLOW}⚠ Could not pull model. Run manually: ollama pull {model_name}{C.RESET}")
        else:
            print(f"  {C.GREEN}✓{C.RESET} Model {model_name} already available")

    # 6. Verify installation
    print()
    run_cmd(
        [sys.executable, "-c", "from hermclaw.cli import app; print('hermclaw package OK')"],
        "Verifying installation",
    )

    # ── Done ─────────────────────────────────────────────────────────────
    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.GREEN}✅ HERMCLAW INSTALLED SUCCESSFULLY!{C.RESET}")
    print(f"{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"""
  {C.BOLD}Config:{C.RESET}  {config_path}
  {C.BOLD}Secrets:{C.RESET} {env_path if env_vars else 'none (Ollama, no key needed)'}
  {C.BOLD}Model:{C.RESET}   {settings['model_name']}

  {C.BOLD}{C.CYAN}Quick start:{C.RESET}
    hermclaw chat          {C.DIM}# start chatting{C.RESET}
    hermclaw doctor        {C.DIM}# check system health{C.RESET}
    hermclaw serve         {C.DIM}# start API server + channels{C.RESET}

  {C.BOLD}{C.CYAN}Need help?{C.RESET}
    hermclaw --help        {C.DIM}# all commands{C.RESET}
    hermclaw setup         {C.DIM}# re-run this wizard{C.RESET}
""")


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    banner()

    print(f"  {C.BOLD}Pre-flight checks:{C.RESET}")
    check_python()

    has_ollama = check_ollama()
    if has_ollama:
        print(f"  {C.GREEN}✓{C.RESET} Ollama is running")
    else:
        print(f"  {C.YELLOW}!{C.RESET} Ollama not detected (cloud providers still work)")

    settings = setup_wizard()

    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  {C.BOLD}{C.MAGENTA}REVIEW{C.RESET}")
    print(f"{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  Provider:  {C.CYAN}{settings['provider_config']['provider']}{C.RESET}")
    print(f"  Model:     {C.CYAN}{settings['model_name']}{C.RESET}")
    channels = settings.get("channels", {})
    enabled_chs = [k for k, v in channels.items() if v.get("enabled")]
    print(f"  Channels:  {C.CYAN}cli{', ' + ', '.join(enabled_chs) if enabled_chs else ''}{C.RESET}")
    print(f"  Shell:     {C.CYAN}{'enabled' if settings.get('shell_enabled') else 'disabled'}{C.RESET}")
    print(f"  Approvals: {C.CYAN}{settings.get('approval_mode', 'off')}{C.RESET}")

    if not ask_yes_no("\n  Proceed with installation?", default=True):
        print(f"\n  {C.YELLOW}Installation cancelled.{C.RESET}\n")
        sys.exit(0)

    install(settings)


if __name__ == "__main__":
    main()
