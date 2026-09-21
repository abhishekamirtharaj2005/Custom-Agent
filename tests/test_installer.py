"""Tests for HermClaw installer, setup wizard and config generator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from install import PROVIDERS, generate_config, install
from hermclaw.config import load_config


def test_generate_config_ollama_basic(tmp_path: Path):
    settings = {
        "agent_name": "hermclaw",
        "user_name": "Alice",
        "timezone": "UTC",
        "persona": "Jarvis",
        "provider_config": PROVIDERS["Ollama (local, free, 100% private — recommended)"],
        "model_name": "gemma4:12b",
        "channels": {
            "telegram": {"enabled": True},
            "discord": {"enabled": True},
        },
        "fallbacks": [],
        "shell_enabled": True,
        "approval_mode": "off",
        "env_vars": {"OLLAMA_API_KEY": "ollama", "TELEGRAM_BOT_TOKEN": "123:ABC"},
    }

    yaml_text = generate_config(settings)
    config_file = tmp_path / "hermclaw.yaml"
    config_file.write_text(yaml_text, encoding="utf-8")

    res = load_config(config_file)
    assert res.valid, f"Generated config failed validation: {res.errors}"
    assert res.config.agent.name == "hermclaw"
    assert res.config.brain.model.model_name == "gemma4:12b"
    assert res.config.body.channels.telegram.enabled is True
    assert res.config.body.channels.discord.enabled is True
    assert res.config.body.channels.slack.enabled is False
    assert res.config.tools.shell_enabled is True


def test_generate_config_with_all_channels_and_fallbacks(tmp_path: Path):
    settings = {
        "agent_name": "jarvis",
        "user_name": "Bob",
        "timezone": "America/New_York",
        "persona": "Autonomous Engineer",
        "provider_config": PROVIDERS["OpenAI (GPT-4o, GPT-4o-mini, o1, o3)"],
        "model_name": "gpt-4o",
        "channels": {
            "telegram": {"enabled": True},
            "discord": {"enabled": True},
            "slack": {"enabled": True},
            "whatsapp": {"enabled": True},
            "teams": {"enabled": True},
            "signal": {"enabled": True},
            "matrix": {"enabled": True},
            "google_chat": {"enabled": True},
            "feishu": {"enabled": True},
            "mattermost": {"enabled": True},
            "twilio": {"enabled": True},
            "webhook": {"enabled": True},
        },
        "fallbacks": [
            {
                "provider": "anthropic",
                "model_name": "claude-3-7-sonnet-20250219",
                "api_key_env": "ANTHROPIC_API_KEY",
                "api_base_env": None,
                "context_window": 200000,
            }
        ],
        "shell_enabled": True,
        "approval_mode": "smart",
        "env_vars": {
            "OPENAI_API_KEY": "sk-test",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "TELEGRAM_BOT_TOKEN": "123:ABC",
            "DISCORD_BOT_TOKEN": "dc_tok",
        },
    }

    yaml_text = generate_config(settings)
    config_file = tmp_path / "hermclaw.yaml"
    config_file.write_text(yaml_text, encoding="utf-8")

    res = load_config(config_file)
    assert res.valid, f"Generated config failed validation: {res.errors}"
    assert res.config.agent.name == "jarvis"
    assert res.config.brain.model.provider == "openai_compat"
    assert res.config.brain.model.model_name == "gpt-4o"
    assert len(res.config.brain.model.fallbacks) == 1
    assert res.config.brain.model.fallbacks[0].provider == "anthropic"

    # All channels enabled
    chs = res.config.body.channels
    assert chs.telegram.enabled is True
    assert chs.discord.enabled is True
    assert chs.slack.enabled is True
    assert chs.whatsapp.enabled is True
    assert chs.teams.enabled is True
    assert chs.signal.enabled is True
    assert chs.matrix.enabled is True
    assert chs.google_chat.enabled is True
    assert chs.feishu.enabled is True
    assert chs.mattermost.enabled is True
    assert chs.twilio.enabled is True
    assert chs.webhook.enabled is True


def test_install_execution(tmp_path: Path):
    hermclaw_home = tmp_path / ".hermclaw"

    settings = {
        "agent_name": "hermclaw",
        "user_name": "Abhishek",
        "timezone": "Asia/Kolkata",
        "persona": "Jarvis (Proactive, efficient, concise, executive secretary)",
        "provider_config": PROVIDERS["Google Gemini (Gemini 2.5 Flash, Gemini 1.5 Pro)"],
        "model_name": "gemini-2.5-flash",
        "channels": {"telegram": {"enabled": True}},
        "fallbacks": [],
        "shell_enabled": True,
        "approval_mode": "off",
        "env_vars": {
            "GEMINI_API_KEY": "test_gemini_key",
            "TELEGRAM_BOT_TOKEN": "test_tg_token",
            "BRAVE_API_KEY": "test_brave_key",
        },
    }

    with patch("pathlib.Path.home", return_value=tmp_path):
        install(settings)

    # Verify directories
    assert (hermclaw_home / "profiles" / "default" / "skills").exists()
    assert (hermclaw_home / "profiles" / "default" / "vault").exists()

    # Verify USER.md & IDENTITY.md
    user_md = hermclaw_home / "profiles" / "default" / "USER.md"
    assert user_md.exists()
    assert "Abhishek" in user_md.read_text(encoding="utf-8")
    assert "Asia/Kolkata" in user_md.read_text(encoding="utf-8")

    ident_md = hermclaw_home / "profiles" / "default" / "IDENTITY.md"
    assert ident_md.exists()
    assert "hermclaw" in ident_md.read_text(encoding="utf-8")

    # Verify config
    cfg_file = hermclaw_home / "hermclaw.yaml"
    assert cfg_file.exists()
    res = load_config(cfg_file)
    assert res.valid

    # Verify .env
    env_file = hermclaw_home / ".env"
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert 'GEMINI_API_KEY="test_gemini_key"' in content
    assert 'TELEGRAM_BOT_TOKEN="test_tg_token"' in content
    assert 'BRAVE_API_KEY="test_brave_key"' in content
