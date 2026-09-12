"""Dashboard Service: Data and execution bridge for the Hermclaw Web Dashboard.

Provides high-level access to:
- Overview stats (agent, model, profiles, system)
- Interactive agent chat execution & session management
- Skills registry & validation
- Self-learning reflection triggering & history
- Concept Learning Graph querying & modification
- Identity & Memory editors (MEMORY.md, USER.md, SOUL.md, Vector Memory)
- Kanban boards, tasks, and Todo items
- Long-term autonomous Goals & OKRs
- Virtual Pet companion (Clawbert) & Achievements
- Tools directory & execution playground
- System health, doctor diagnostics, and config management
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import os
import platform
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import psutil
import structlog

from hermclaw.brain.model_catalog import ModelCatalog, ModelInfo
from hermclaw.brain.profiles import ProfileManager
from hermclaw.brain.reflection import reflect as run_reflection
from hermclaw.brain.transports import MissingCredentialsError, build_transport
from hermclaw.config import (
    HermclawConfig,
    ModelConfig,
    default_config_path,
    hermclaw_home,
    load_config,
    save_config_text,
)
from hermclaw.runtime import AgentRuntime, build_agent_runtime, gateway_token
from hermclaw.security.secrets import redact, resolve_env_ref
from hermclaw.skills.registry import SkillRegistry
from hermclaw.tools.achievements import BUILTIN_ACHIEVEMENTS
from hermclaw.tools.goals_tool import GoalsDB
from hermclaw.tools.task_tools import _KanbanDB
from hermclaw.tools.virtual_pet import MOOD_EMOTES, PET_ART, VirtualPet

logger = structlog.get_logger(__name__)

CLOUD_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "openai",
        "name": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "placeholder": "sk-proj-...",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o (Omni Flagship)", "context": "128k"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Fast & Cheap)", "context": "128k"},
            {"id": "o1", "name": "o1 (Deep Reasoning)", "context": "200k"},
            {"id": "o3-mini", "name": "o3-mini (STEM & Code)", "context": "200k"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context": "128k"},
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "env_var": "ANTHROPIC_API_KEY",
        "placeholder": "sk-ant-api03-...",
        "models": [
            {"id": "claude-3-7-sonnet-latest", "name": "Claude 3.7 Sonnet (Hybrid Reasoning)", "context": "200k"},
            {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet", "context": "200k"},
            {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku (Ultra-Fast)", "context": "200k"},
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "context": "200k"},
        ],
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "env_var": "GEMINI_API_KEY",
        "alt_env_var": "GOOGLE_API_KEY",
        "placeholder": "AIzaSy...",
        "models": [
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (1M Context)", "context": "1M"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "context": "1M"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context": "1M"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context": "2M"},
        ],
    },
    {
        "id": "groq",
        "name": "Groq",
        "env_var": "GROQ_API_KEY",
        "placeholder": "gsk_...",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Groq Llama 3.3 70B (High Speed)", "context": "128k"},
        ],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "placeholder": "sk-...",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek V3 (Chat & Coding)", "context": "64k"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1 (Reasoner)", "context": "64k"},
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "env_var": "OPENROUTER_API_KEY",
        "placeholder": "sk-or-v1-...",
        "models": [
            {"id": "openrouter/auto", "name": "OpenRouter Auto-Routing", "context": "128k"},
        ],
    },
]


class DashboardService:
    """Unified service for the Hermclaw Web Dashboard."""

    def __init__(self, config_path: Optional[Path] = None, profile: str = "default") -> None:
        self.config_path = config_path or default_config_path()
        self.profile = profile
        self.pm = ProfileManager()
        self._runtime: Optional[AgentRuntime] = None
        self._runtime_lock = asyncio.Lock()
        self._started_at = time.time()

    # ------------------------------------------------------------------
    # Runtime & Agent Management
    # ------------------------------------------------------------------

    async def get_runtime(self) -> AgentRuntime:
        """Get or lazily initialize the shared AgentRuntime for the active profile."""
        async with self._runtime_lock:
            if self._runtime is None:
                config_result = load_config(self.config_path)
                if not config_result.valid or config_result.config is None:
                    raise RuntimeError(f"Config is invalid: {config_result.errors}")
                self._runtime = await build_agent_runtime(self.profile, config_result.config, self.pm)
            return self._runtime

    async def reload_runtime(self) -> None:
        """Reload the agent runtime (e.g. after config changes)."""
        async with self._runtime_lock:
            if self._runtime is not None:
                try:
                    await self._runtime.aclose()
                except Exception as exc:
                    logger.warning("runtime.close_error", error=str(exc))
                self._runtime = None
        await self.get_runtime()

    def get_config(self) -> dict[str, Any]:
        """Return the current redacted configuration dict."""
        res = load_config(self.config_path)
        if not res.config:
            return {}
        return redact(res.config.model_dump(by_alias=True))

    def get_raw_config_text(self) -> str:
        """Return the raw hermclaw.yaml text."""
        if self.config_path.exists():
            return self.config_path.read_text(encoding="utf-8")
        return ""

    def save_raw_config_text(self, raw_text: str) -> tuple[bool, list[str]]:
        """Validate and save raw YAML text to hermclaw.yaml."""
        from hermclaw.config import _validate_dict, _yaml

        try:
            parsed = dict(_yaml.load(raw_text) or {})
        except Exception as exc:
            return False, [f"YAML parse error: {exc}"]

        new_config, errors = _validate_dict(parsed)
        if new_config is None:
            return False, errors

        try:
            save_config_text(raw_text, self.config_path)
            return True, []
        except Exception as exc:
            return False, [str(exc)]

    # ------------------------------------------------------------------
    # Cloud LLM API Keys & Model Management
    # ------------------------------------------------------------------

    def get_api_keys_status(self) -> list[dict[str, Any]]:
        """Return the configuration status of all supported Cloud LLM providers."""
        env_file = hermclaw_home() / ".env"
        env_vars = dict(os.environ)

        # Also parse .env file in case some vars weren't yet in os.environ
        if env_file.exists():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in env_vars:
                            env_vars[k] = v
            except Exception:
                pass

        result = []
        for p in CLOUD_PROVIDERS:
            val = env_vars.get(p["env_var"]) or (env_vars.get(p.get("alt_env_var")) if p.get("alt_env_var") else None)
            is_set = bool(val and val.strip())
            masked = ""
            if is_set:
                v_clean = val.strip()
                if len(v_clean) > 8:
                    masked = f"{v_clean[:4]}...{v_clean[-4:]}"
                else:
                    masked = "****"

            result.append({
                "id": p["id"],
                "name": p["name"],
                "env_var": p["env_var"],
                "configured": is_set,
                "preview": masked,
                "placeholder": p["placeholder"],
                "models_count": len(p["models"]),
            })
        return result

    def save_api_keys(self, keys: dict[str, str]) -> tuple[bool, str]:
        """Save API keys to ~/.hermclaw/.env and update os.environ in-memory."""
        env_file = hermclaw_home() / ".env"
        env_file.parent.mkdir(parents=True, exist_ok=True)

        existing_lines = []
        existing_keys = set()
        if env_file.exists():
            try:
                existing_lines = env_file.read_text(encoding="utf-8").splitlines()
            except Exception:
                existing_lines = []

        new_lines = []
        updated_keys = set()

        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, _ = stripped.partition("=")
                k = k.strip()
                existing_keys.add(k)
                if k in keys and keys[k] is not None:
                    v = str(keys[k]).strip()
                    new_lines.append(f'{k}="{v}"')
                    updated_keys.add(k)
                    os.environ[k] = v
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Append any new keys not already in the file
        for k, v in keys.items():
            if k not in updated_keys and v is not None and str(v).strip():
                v_clean = str(v).strip()
                new_lines.append(f'{k}="{v_clean}"')
                os.environ[k] = v_clean
                if k == "GEMINI_API_KEY":
                    os.environ["GOOGLE_API_KEY"] = v_clean
                elif k == "GOOGLE_API_KEY":
                    os.environ["GEMINI_API_KEY"] = v_clean

        # Mirror GEMINI_API_KEY to GOOGLE_API_KEY
        if "GEMINI_API_KEY" in keys and keys["GEMINI_API_KEY"]:
            os.environ["GOOGLE_API_KEY"] = str(keys["GEMINI_API_KEY"]).strip()

        try:
            env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return True, "API keys saved successfully"
        except Exception as exc:
            return False, f"Failed to save .env file: {exc}"

    def _get_saved_models_file(self) -> Path:
        p = hermclaw_home() / "saved_models.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _read_saved_custom_models(self) -> list[dict[str, Any]]:
        f = self._get_saved_models_file()
        if not f.exists():
            return []
        try:
            import json
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_saved_custom_models(self, models: list[dict[str, Any]]) -> None:
        f = self._get_saved_models_file()
        try:
            import json
            f.write_text(json.dumps(models, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("failed_to_write_saved_models", error=str(exc))

    def save_engine_config(
        self,
        provider: str,
        model_name: str,
        api_key: Optional[str] = None,
        set_active: bool = False,
    ) -> tuple[bool, str]:
        """Save AI engine configuration for a provider and model, optionally saving the API key."""
        provider_norm = provider.strip().lower()
        model_name_clean = model_name.strip()
        if not model_name_clean:
            return False, "Model name cannot be empty."

        provider_env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }

        # 1. Save API key if provided
        if api_key and api_key.strip():
            env_var = provider_env_map.get(provider_norm)
            if env_var:
                ok, msg = self.save_api_keys({env_var: api_key.strip()})
                if not ok:
                    return False, f"Failed to save API key: {msg}"

        # 2. Record custom model in saved_models.json
        saved = self._read_saved_custom_models()
        existing = next((m for m in saved if m.get("id") == model_name_clean and m.get("provider") == provider_norm), None)
        if not existing:
            saved.append({
                "id": model_name_clean,
                "name": model_name_clean,
                "provider": provider_norm,
                "type": "local" if provider_norm == "ollama" else "cloud",
                "custom": True,
                "updated_at": time.time(),
            })
            self._write_saved_custom_models(saved)

        # 3. If set_active, switch active model
        if set_active:
            self._current_model = model_name_clean
            self._current_provider = provider_norm
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.switch_model(model_name_clean))
            except Exception:
                pass

        return True, f"Configured {model_name_clean} ({provider_norm}) successfully!"

    def clear_provider_key(self, provider: str) -> tuple[bool, str]:
        """Clear a provider's API key from ~/.hermclaw/.env and os.environ."""
        provider_env_map = {
            "openai": ["OPENAI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "groq": ["GROQ_API_KEY"],
            "deepseek": ["DEEPSEEK_API_KEY"],
            "openrouter": ["OPENROUTER_API_KEY"],
        }
        keys_to_clear = provider_env_map.get(provider.strip().lower(), [])
        if not keys_to_clear:
            return False, f"Unknown provider '{provider}'"

        env_file = hermclaw_home() / ".env"
        if env_file.exists():
            try:
                lines = env_file.read_text(encoding="utf-8").splitlines()
                kept = []
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        k, _, _ = stripped.partition("=")
                        if k.strip() in keys_to_clear:
                            continue
                    kept.append(line)
                env_file.write_text("\n".join(kept) + "\n", encoding="utf-8")
            except Exception as exc:
                return False, f"Failed to modify .env: {exc}"

        for k in keys_to_clear:
            os.environ.pop(k, None)

        return True, f"Cleared API key for {provider}"

    def delete_saved_model(self, provider: str, model_name: str) -> tuple[bool, str]:
        """Remove a custom saved model from ~/.hermclaw/saved_models.json."""
        saved = self._read_saved_custom_models()
        filtered = [m for m in saved if not (m.get("id") == model_name and m.get("provider") == provider.lower())]
        self._write_saved_custom_models(filtered)
        return True, f"Removed model {model_name}"

    async def get_saved_models_list(self) -> list[dict[str, Any]]:
        """Return full list of saved/available models with active status, key preview, and edit metadata."""
        all_models = await self.get_available_models()
        config_res = load_config(self.config_path)
        active_model = getattr(self, "_current_model", None) or (config_res.config.brain.model.model_name if config_res.config else "gemma4:12b")

        status_list = self.get_api_keys_status()
        status_map = {s["id"]: s for s in status_list}
        custom_saved = self._read_saved_custom_models()
        custom_keys = {(m.get("provider"), m.get("id")) for m in custom_saved}

        result = []
        for m in all_models:
            mid = m["id"]
            prov = m.get("provider", "other")
            is_cloud = m.get("type") == "cloud"
            prov_status = status_map.get(prov, {})

            key_preview = "Local (Ollama)" if not is_cloud else (
                prov_status.get("preview") or "Host Environment Variable"
            )

            result.append({
                "id": mid,
                "name": m.get("name", mid),
                "provider": prov,
                "provider_name": prov_status.get("name", prov.title()),
                "type": "cloud" if is_cloud else "local",
                "tag": m.get("tag", "[Cloud]" if is_cloud else "[Local]"),
                "display_label": m.get("display_label", f"{mid} [{prov}]"),
                "configured": True,
                "key_preview": key_preview,
                "is_active": (mid == active_model),
                "context": m.get("context", "128k"),
                "can_delete": (prov, mid) in custom_keys,
            })
        return result

    async def get_available_models(self) -> list[dict[str, Any]]:
        """Return a unified list of available local and cloud models with local/cloud tagging."""
        models: list[dict[str, Any]] = []

        # 1. Local Ollama models
        ollama_online, ollama_models = await self.check_ollama()
        for m in ollama_models:
            models.append({
                "id": m,
                "name": m,
                "type": "local",
                "provider": "ollama",
                "tag": "[Local]",
                "display_label": f"{m} [Local]",
                "available": True,
            })

        # Fallback local model if Ollama returned empty but active config is local
        config_res = load_config(self.config_path)
        active_model = getattr(self, "_current_model", None) or (config_res.config.brain.model.model_name if config_res.config else "gemma4:12b")
        active_provider = getattr(self, "_current_provider", None) or (config_res.config.brain.model.provider if config_res.config else "openai_compat")
        is_cloud_active = (
            any(cm["id"] == active_model for cp in CLOUD_PROVIDERS for cm in cp["models"])
            or getattr(self, "_current_provider", None) in [cp["id"] for cp in CLOUD_PROVIDERS]
        )
        if not is_cloud_active and not any(m["id"] == active_model for m in models) and active_provider in ("openai_compat", "ollama"):
            models.insert(0, {
                "id": active_model,
                "name": active_model,
                "type": "local",
                "provider": "ollama",
                "tag": "[Local]",
                "display_label": f"{active_model} [Local]",
                "available": ollama_online,
            })

        # 2. Cloud models for configured providers
        status_list = self.get_api_keys_status()
        status_map = {item["id"]: item["configured"] for item in status_list}

        for cp in CLOUD_PROVIDERS:
            is_configured = status_map.get(cp["id"], False)
            if is_configured:
                for cm in cp["models"]:
                    models.append({
                        "id": cm["id"],
                        "name": cm["name"],
                        "type": "cloud",
                        "provider": cp["id"],
                        "tag": f"[Cloud - {cp['name']}]",
                        "display_label": f"{cm['id']} [Cloud - {cp['name']}]",
                        "available": True,
                        "context": cm.get("context", "128k"),
                    })

        # 3. Custom models saved by user
        custom_saved = self._read_saved_custom_models()
        for cm in custom_saved:
            cid = cm.get("id")
            cprov = cm.get("provider", "other")
            if not any(m["id"] == cid for m in models):
                cp_meta = next((cp for cp in CLOUD_PROVIDERS if cp["id"] == cprov), None)
                pname = cp_meta["name"] if cp_meta else cprov.title()
                is_cloud = cm.get("type") == "cloud" or cprov != "ollama"
                models.append({
                    "id": cid,
                    "name": cm.get("name", cid),
                    "type": "cloud" if is_cloud else "local",
                    "provider": cprov,
                    "tag": f"[Cloud - {pname}]" if is_cloud else "[Local]",
                    "display_label": f"{cid} [Cloud - {pname}]" if is_cloud else f"{cid} [Local]",
                    "available": True,
                    "context": cm.get("context", "128k"),
                })

        return models

    async def switch_model(self, model_name: str) -> dict[str, Any]:
        """Switch the active LLM model and reconfigure runtime transport."""
        runtime = await self.get_runtime()
        catalog = ModelCatalog()
        info = catalog.resolve(model_name)

        if not info:
            info = ModelInfo(
                name=model_name,
                provider="openai_compat",
                context_window=128_000,
                max_output_tokens=8192,
                description=f"{model_name} (local via Ollama)",
                api_base="http://localhost:11434/v1",
            )

        api_base_env = None
        if info.provider == "anthropic":
            api_key_env = "ANTHROPIC_API_KEY"
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ValueError("Anthropic API key is not configured. Please save it in Settings.")
        elif info.provider == "gemini":
            api_key_env = "GEMINI_API_KEY" if os.environ.get("GEMINI_API_KEY") else "GOOGLE_API_KEY"
            if not os.environ.get(api_key_env):
                raise ValueError("Google Gemini API key is not configured. Please save it in Settings.")
        else:  # openai_compat
            if "localhost" in (info.api_base or "") or "127.0.0.1" in (info.api_base or "") or not info.api_base:
                api_base_env = "OLLAMA_API_BASE"
                api_key_env = "OLLAMA_API_KEY"
                os.environ["OLLAMA_API_BASE"] = info.api_base or "http://localhost:11434/v1"
            elif "openai.com" in info.api_base:
                api_base_env = "OPENAI_API_BASE"
                api_key_env = "OPENAI_API_KEY"
                if not os.environ.get("OPENAI_API_KEY"):
                    raise ValueError("OpenAI API key is not configured. Please save it in Settings.")
                os.environ["OPENAI_API_BASE"] = info.api_base
            elif "groq.com" in info.api_base:
                api_base_env = "GROQ_API_BASE"
                api_key_env = "GROQ_API_KEY"
                if not os.environ.get("GROQ_API_KEY"):
                    raise ValueError("Groq API key is not configured. Please save it in Settings.")
                os.environ["GROQ_API_BASE"] = info.api_base
            elif "deepseek.com" in info.api_base:
                api_base_env = "DEEPSEEK_API_BASE"
                api_key_env = "DEEPSEEK_API_KEY"
                if not os.environ.get("DEEPSEEK_API_KEY"):
                    raise ValueError("DeepSeek API key is not configured. Please save it in Settings.")
                os.environ["DEEPSEEK_API_BASE"] = info.api_base
            elif "openrouter.ai" in info.api_base:
                api_base_env = "OPENROUTER_API_BASE"
                api_key_env = "OPENROUTER_API_KEY"
                if not os.environ.get("OPENROUTER_API_KEY"):
                    raise ValueError("OpenRouter API key is not configured. Please save it in Settings.")
                os.environ["OPENROUTER_API_BASE"] = info.api_base
            else:
                api_base_env = f"HERMCLAW_API_BASE_{info.provider.upper()}"
                api_key_env = "OPENAI_API_KEY"
                os.environ[api_base_env] = info.api_base

        new_cfg = ModelConfig(
            provider=info.provider,
            model_name=info.name,
            api_base_env=api_base_env,
            api_key_env=api_key_env,
            context_window=info.context_window,
        )

        transport = build_transport(new_cfg)
        runtime.agent.transport = transport
        runtime.agent.model_config = new_cfg
        self._current_model = info.name
        self._current_provider = info.provider

        logger.info("dashboard.model_switched", model=info.name, provider=info.provider)
        return {
            "success": True,
            "model_name": info.name,
            "provider": info.provider,
            "description": info.description,
            "context_window": info.context_window,
        }

    # ------------------------------------------------------------------
    # Overview & Telemetry
    # ------------------------------------------------------------------

    async def get_overview(self) -> dict[str, Any]:
        """Aggregate stats for the Command Center dashboard view."""
        config_res = load_config(self.config_path)
        config = config_res.config

        base_model_name = config.brain.model.model_name if config else "unknown"
        base_provider = config.brain.model.provider if config else "unknown"

        active_model = getattr(self, "_current_model", None) or base_model_name
        active_provider = getattr(self, "_current_provider", None) or base_provider

        # Check Ollama connection
        ollama_online, _ = await self.check_ollama()
        all_models = await self.get_available_models()

        # Session count
        session_count = 0
        try:
            runtime = await self.get_runtime()
            recent_sessions = await runtime.memory_store.a_get_recent_sessions(n=500)
            session_count = len(recent_sessions)
        except Exception:
            pass

        # Skills count
        skills_info = self.get_skills()
        auto_skills = [s for s in skills_info if s.get("auto_generated")]

        # Learning graph count
        graph_stats = self.get_learning_graph_stats()

        # Tasks & Goals
        kanban_data = self.get_kanban_summary()
        goals_data = self.get_goals_summary()

        # Virtual Pet
        pet_data = self.get_pet()

        # System resources
        system_stats = self.get_system_metrics()

        return {
            "profile": self.profile,
            "profiles_available": self.pm.list_profiles(),
            "model": {
                "name": active_model,
                "provider": active_provider,
                "ollama_online": ollama_online,
                "available_models": all_models,
            },

            "stats": {
                "total_sessions": session_count,
                "total_skills": len(skills_info),
                "auto_skills": len(auto_skills),
                "total_concepts": graph_stats.get("total_concepts", 0),
                "total_relationships": graph_stats.get("total_relationships", 0),
                "active_goals": goals_data.get("active", 0),
                "completed_goals": goals_data.get("completed", 0),
                "total_tasks": kanban_data.get("total_tasks", 0),
                "todo_count": kanban_data.get("todos_pending", 0),
                "pet_level": pet_data.get("level", 1),
                "pet_mood": pet_data.get("mood", "happy"),
                "pet_stage": pet_data.get("stage", "egg"),
            },
            "system": system_stats,
            "uptime_seconds": round(time.time() - self._started_at, 1),
        }

    async def check_ollama(self) -> tuple[bool, list[str]]:
        """Check if local Ollama daemon is reachable and list models."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get("http://localhost:11434/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    return True, models
        except Exception:
            pass
        return False, []

    def get_system_metrics(self) -> dict[str, Any]:
        """Live CPU, RAM, Disk, and host details."""
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home()))

        return {
            "cpu_percent": cpu_percent,
            "ram_percent": mem.percent,
            "ram_used_mb": round(mem.used / (1024 * 1024), 1),
            "ram_total_mb": round(mem.total / (1024 * 1024), 1),
            "disk_percent": disk.percent,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(logical=True),
        }

    # ------------------------------------------------------------------
    # Chat & Session Management
    # ------------------------------------------------------------------

    async def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent chat sessions."""
        runtime = await self.get_runtime()
        sessions = await runtime.memory_store.a_get_recent_sessions(n=limit)
        results = []
        for s in sessions:
            results.append({
                "id": s.id,
                "title": s.title or f"Session {s.id[:8]}",
                "channel": getattr(s, "channel", "web-dashboard"),
                "started_at": str(s.started_at)[:19] if s.started_at else "",
                "total_tokens": getattr(s, "total_tokens", 0) or 0,
            })
        return results

    async def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a specific session."""
        runtime = await self.get_runtime()
        messages = await runtime.memory_store.a_get_session_messages(session_id, include_compressed_away=True)
        results = []
        for m in messages:
            tool_calls = []
            if m.tool_calls:
                for tc in m.tool_calls:
                    tool_calls.append({
                        "name": tc.name if hasattr(tc, "name") else tc.get("name", ""),
                        "arguments": tc.arguments if hasattr(tc, "arguments") else tc.get("arguments", {}),
                    })
            results.append({
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": str(m.created_at)[:19] if m.created_at else "",
                "tool_calls": tool_calls,
                "tokens": getattr(m, "tokens", 0) or 0,
            })
        return results

    async def create_session(self, title: Optional[str] = None) -> str:
        """Create a new session and return its ID."""
        runtime = await self.get_runtime()
        config_res = load_config(self.config_path)
        model_name = config_res.config.brain.model.model_name if config_res.config else "default"
        sid = await runtime.memory_store.a_create_session(channel="web-dashboard", model=model_name)
        if title:
            paths = self.pm.ensure_profile(self.profile)
            conn = sqlite3.connect(str(paths.state_db))
            try:
                conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, sid))
                conn.commit()
            finally:
                conn.close()
        return sid

    async def send_message(self, session_id: str, message: str, model: Optional[str] = None) -> dict[str, Any]:
        """Run an agent turn on a session and capture response and tool calls."""
        if model and model.strip():
            await self.switch_model(model.strip())
        runtime = await self.get_runtime()

        start_time = time.time()
        turn_result = await runtime.agent.run_turn(session_id, message)
        elapsed = round(time.time() - start_time, 2)

        # Extract tool calls performed in this turn
        tools_executed = []
        for step in getattr(turn_result, "steps", []):
            if hasattr(step, "tool_call"):
                tc = step.tool_call
                tools_executed.append({
                    "name": tc.name if hasattr(tc, "name") else getattr(tc, "tool_name", "tool"),
                    "arguments": tc.arguments if hasattr(tc, "arguments") else {},
                    "output": str(getattr(step, "tool_result", ""))[:1000],
                })

        return {
            "text": turn_result.text,
            "session_id": session_id,
            "elapsed_seconds": elapsed,
            "input_tokens": turn_result.usage.input_tokens if turn_result.usage else 0,
            "output_tokens": turn_result.usage.output_tokens if turn_result.usage else 0,
            "tools_executed": tools_executed,
        }

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from state.db."""
        paths = self.pm.ensure_profile(self.profile)
        conn = sqlite3.connect(str(paths.state_db))
        try:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return True
        except Exception as exc:
            logger.error("session.delete_error", error=str(exc))
            return False
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Skills & Reflection
    # ------------------------------------------------------------------

    def get_skills(self) -> list[dict[str, Any]]:
        """List all skills available to this profile."""
        paths = self.pm.ensure_profile(self.profile)
        config_res = load_config(self.config_path)
        extra = config_res.config.skills.extra_directories if config_res.config else []
        registry = SkillRegistry(directory=paths.skills_dir, extra_directories=extra)
        registry.load()

        skills = []
        for name in registry.names():
            skill = registry.get(name)
            if not skill:
                continue
            skills.append({
                "name": skill.name,
                "description": skill.description,
                "auto_generated": getattr(skill, "auto_generated", False),
                "path": str(skill.path),
                "body": skill.body,
            })
        return skills

    def validate_skills(self) -> list[dict[str, Any]]:
        """Run validation against all skills for the profile."""
        paths = self.pm.ensure_profile(self.profile)
        config_res = load_config(self.config_path)
        extra = config_res.config.skills.extra_directories if config_res.config else []
        registry = SkillRegistry(directory=paths.skills_dir, extra_directories=extra)
        validations = registry.discover()
        return [
            {
                "name": v.skill_path.name,
                "path": str(v.skill_path),
                "passed": v.passed,
                "errors": v.errors,
            }
            for v in validations
        ]

    async def trigger_reflection(self) -> dict[str, Any]:
        """Trigger reflection across recent sessions to distill facts & auto-skills."""
        config_res = load_config(self.config_path)
        if not config_res.config:
            raise RuntimeError("Config not loaded.")

        runtime = await self.get_runtime()
        reflection_result = await run_reflection(
            self.profile,
            runtime.memory_store,
            runtime.identity_files,
            runtime.skill_growth_engine,
            runtime.agent.transport,
        )

        return {
            "sessions_reviewed": reflection_result.sessions_reviewed,
            "facts_saved": reflection_result.facts_saved,
            "user_facts_saved": reflection_result.user_facts_saved,
            "draft_skills_created": reflection_result.draft_skills_created,
            "timestamp": datetime.datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Learning Graph
    # ------------------------------------------------------------------

    def _get_learning_graph_db(self) -> sqlite3.Connection:
        db_path = hermclaw_home() / "learning_graph.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_learning_graph_data(self) -> dict[str, Any]:
        """Return full nodes and edges for network graph visualization."""
        conn = self._get_learning_graph_db()
        try:
            concepts = conn.execute(
                "SELECT id, name, category, description, confidence, usage_count, created_at FROM concepts ORDER BY usage_count DESC"
            ).fetchall()

            relationships = conn.execute(
                """
                SELECT r.id, r.source_id, r.target_id, r.relation_type, r.strength,
                       c1.name as source_name, c2.name as target_name
                FROM relationships r
                JOIN concepts c1 ON r.source_id = c1.id
                JOIN concepts c2 ON r.target_id = c2.id
                """
            ).fetchall()

            nodes = [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "category": c["category"] or "general",
                    "description": c["description"] or "",
                    "confidence": c["confidence"],
                    "usage_count": c["usage_count"],
                }
                for c in concepts
            ]

            edges = [
                {
                    "id": r["id"],
                    "source": r["source_id"],
                    "target": r["target_id"],
                    "source_name": r["source_name"],
                    "target_name": r["target_name"],
                    "relation_type": r["relation_type"],
                    "strength": r["strength"],
                }
                for r in relationships
            ]

            categories: dict[str, int] = {}
            for n in nodes:
                cat = n["category"]
                categories[cat] = categories.get(cat, 0) + 1

            return {
                "nodes": nodes,
                "edges": edges,
                "categories": categories,
                "total_concepts": len(nodes),
                "total_relationships": len(edges),
            }
        except sqlite3.OperationalError:
            return {"nodes": [], "edges": [], "categories": {}, "total_concepts": 0, "total_relationships": 0}
        finally:
            conn.close()

    def get_learning_graph_stats(self) -> dict[str, Any]:
        """Quick summary of learning graph."""
        data = self.get_learning_graph_data()
        return {
            "total_concepts": data["total_concepts"],
            "total_relationships": data["total_relationships"],
            "categories": data["categories"],
        }

    def add_learning_concept(self, name: str, category: str = "general", description: str = "", confidence: float = 0.5) -> str:
        """Add a concept to the learning graph."""
        from hermclaw.brain.learning_graph import LearningGraph
        graph = LearningGraph()
        try:
            return graph.add_concept(name, category, description, confidence)
        finally:
            graph.close()

    def add_learning_relationship(self, source_name: str, target_name: str, relation_type: str = "related_to", strength: float = 0.5) -> str:
        """Add a relation between two concepts."""
        from hermclaw.brain.learning_graph import LearningGraph
        graph = LearningGraph()
        try:
            return graph.add_relationship(source_name, target_name, relation_type, strength)
        finally:
            graph.close()

    # ------------------------------------------------------------------
    # Memory & Identity Vault
    # ------------------------------------------------------------------

    def get_identity_file(self, file_type: str) -> str:
        """Read MEMORY.md, USER.md, or SOUL.md."""
        paths = self.pm.ensure_profile(self.profile)
        mapping = {
            "memory": paths.memory_md,
            "user": paths.user_md,
            "soul": paths.soul_md,
        }
        target = mapping.get(file_type.lower())
        if not target or not target.exists():
            return ""
        return target.read_text(encoding="utf-8")

    def save_identity_file(self, file_type: str, content: str) -> bool:
        """Save MEMORY.md, USER.md, or SOUL.md with automatic timestamped backup."""
        paths = self.pm.ensure_profile(self.profile)
        mapping = {
            "memory": paths.memory_md,
            "user": paths.user_md,
            "soul": paths.soul_md,
        }
        target = mapping.get(file_type.lower())
        if not target:
            return False

        # Make backup
        if target.exists():
            backup_path = target.with_suffix(f".bak.{int(time.time())}")
            try:
                backup_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass

        target.write_text(content, encoding="utf-8")
        return True

    async def search_vector_memory(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search vector memory for semantic matches."""
        try:
            runtime = await self.get_runtime()
            if runtime.vector_memory is not None:
                results = await runtime.vector_memory.a_search(query, limit=limit)
                return [
                    {
                        "content": r.content if hasattr(r, "content") else str(r),
                        "score": getattr(r, "score", 0.0),
                        "metadata": getattr(r, "metadata", {}),
                    }
                    for r in results
                ]
        except Exception as exc:
            logger.debug("vector_memory.search_error", error=str(exc))
        return []

    # ------------------------------------------------------------------
    # Tasks (Kanban & Todos)
    # ------------------------------------------------------------------

    def _get_kanban_db(self) -> _KanbanDB:
        db_path = hermclaw_home() / "kanban.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return _KanbanDB(db_path)

    def get_kanban_summary(self) -> dict[str, int]:
        db = self._get_kanban_db()
        try:
            boards = db.list_boards()
            total_tasks = 0
            if boards:
                board_data = db.get_board(boards[0]["id"])
                if board_data:
                    for col in board_data.get("columns", []):
                        total_tasks += len(col.get("tasks", []))
            todos = db.list_todos(show_done=False)
            return {"total_tasks": total_tasks, "todos_pending": len(todos)}
        finally:
            db.close()

    def get_kanban_board(self, board_id: Optional[str] = None) -> dict[str, Any]:
        """Fetch Kanban board with columns and tasks."""
        db = self._get_kanban_db()
        try:
            boards = db.list_boards()
            if not boards:
                # Initialize default project board
                bid = db.create_board("Default Project")
                boards = db.list_boards()

            target_id = board_id or boards[0]["id"]
            board = db.get_board(target_id)
            return {
                "boards": boards,
                "current_board": board or {"columns": []},
            }
        finally:
            db.close()

    def add_kanban_task(self, board_id: str, column_name: str, title: str, description: str = "", priority: str = "medium") -> str:
        db = self._get_kanban_db()
        try:
            return db.add_task(board_id=board_id, title=title, description=description, priority=priority, column_name=column_name)
        finally:
            db.close()

    def move_kanban_task(self, task_id: str, column_name: str) -> bool:
        db = self._get_kanban_db()
        try:
            return db.move_task(task_id, column_name)
        finally:
            db.close()

    def delete_kanban_task(self, task_id: str) -> bool:
        db_path = hermclaw_home() / "kanban.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DELETE FROM kb_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_todos(self, show_done: bool = True) -> list[dict[str, Any]]:
        db = self._get_kanban_db()
        try:
            return db.list_todos(show_done=show_done)
        finally:
            db.close()

    def add_todo(self, text: str, priority: str = "medium") -> str:
        db = self._get_kanban_db()
        try:
            return db.add_todo(text, priority)
        finally:
            db.close()

    def toggle_todo(self, todo_id: str, done: bool) -> bool:
        db_path = hermclaw_home() / "kanban.db"
        conn = sqlite3.connect(str(db_path))
        try:
            now = time.time() if done else None
            conn.execute("UPDATE todos SET done = ?, completed_at = ? WHERE id = ?", (1 if done else 0, now, todo_id))
            conn.commit()
            return True
        finally:
            conn.close()

    def delete_todo(self, todo_id: str) -> bool:
        db_path = hermclaw_home() / "kanban.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Autonomous Goals (OKRs)
    # ------------------------------------------------------------------

    def _get_goals_db(self) -> GoalsDB:
        db_path = hermclaw_home() / "goals.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return GoalsDB(db_path)

    def get_goals_summary(self) -> dict[str, int]:
        db = self._get_goals_db()
        try:
            active = len(db.list_active())
            all_goals = db.list_all()
            completed = len([g for g in all_goals if g.get("status") == "completed"])
            return {"active": active, "completed": completed}
        finally:
            db.close()

    def list_goals(self, status: str = "all") -> list[dict[str, Any]]:
        db = self._get_goals_db()
        try:
            if status == "active":
                return db.list_active()
            all_goals = db.list_all()
            if status == "all":
                return all_goals
            return [g for g in all_goals if g.get("status") == status]
        finally:
            db.close()

    def create_goal(self, title: str, description: str = "", priority: str = "medium") -> str:
        db = self._get_goals_db()
        try:
            return db.create(title, description, priority)
        finally:
            db.close()

    def update_goal_progress(self, goal_id: str, progress: int, entry: str = "") -> bool:
        db = self._get_goals_db()
        try:
            ok = db.update_progress(goal_id, progress, entry)
            if progress >= 100:
                db.complete(goal_id)
            return ok
        finally:
            db.close()

    def delete_goal(self, goal_id: str) -> bool:
        db_path = hermclaw_home() / "goals.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DELETE FROM goal_logs WHERE goal_id = ?", (goal_id,))
            conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Virtual Pet (Clawbert) & Achievements
    # ------------------------------------------------------------------

    def get_pet(self) -> dict[str, Any]:
        pet = VirtualPet()
        try:
            status = pet.status()
            if "error" in status:
                pet.adopt("Clawbert", "hermit_crab")
                status = pet.status()
            stage = status.get("stage", "egg")
            mood = status.get("mood", "curious")
            art = PET_ART.get(stage, PET_ART["egg"])
            emote = MOOD_EMOTES.get(mood, "(^_^)")
            status["art"] = art
            status["emote"] = emote
            return status
        finally:
            pet.close()

    def pet_action(self, action: str) -> dict[str, Any]:
        """Perform feed, play, or rest action on Clawbert."""
        pet = VirtualPet()
        try:
            status = pet.status()
            if "error" in status:
                pet.adopt("Clawbert", "hermit_crab")

            if action == "feed":
                result = pet.feed()
            elif action == "play":
                result = pet.play()
            elif action == "rest":
                result = pet.rest()
            else:
                result = {"error": f"Unknown action {action}"}
            new_status = pet.status()
            stage = new_status.get("stage", "egg")
            new_status["art"] = PET_ART.get(stage, PET_ART["egg"])
            new_status["emote"] = MOOD_EMOTES.get(new_status.get("mood", "happy"), "(^_^)")
            new_status["action_result"] = result
            return new_status
        finally:
            pet.close()

    def get_achievements(self) -> list[dict[str, Any]]:
        """Fetch all achievements and unlock status."""
        db_path = hermclaw_home() / "achievements.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            # Check if table exists
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='achievements'"
            ).fetchone()
            if not exists:
                from hermclaw.tools.achievements import AchievementsTool
                tool = AchievementsTool()
                return tool.get_all()

            rows = conn.execute("SELECT * FROM achievements ORDER BY unlocked DESC, id ASC").fetchall()
            if not rows:
                from hermclaw.tools.achievements import AchievementsTool
                tool = AchievementsTool()
                return tool.get_all()

            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Tools Directory & Playground
    # ------------------------------------------------------------------

    async def get_tools_catalog(self) -> list[dict[str, Any]]:
        """List all 40+ tools registered in the runtime tool dispatcher."""
        runtime = await self.get_runtime()
        tools_list = []
        for tool in runtime.tool_dispatcher._tools.values():
            spec = tool.spec()
            tools_list.append({
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
                "read_only": getattr(spec, "read_only", False),
            })
        tools_list.sort(key=lambda t: t["name"])
        return tools_list

    async def execute_tool_playground(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool directly via the ToolDispatcher playground."""
        runtime = await self.get_runtime()
        tool = runtime.tool_dispatcher._tools.get(tool_name)
        if not tool:
            return {"ok": False, "output": "", "error": f"Tool '{tool_name}' not found."}

        start = time.time()
        try:
            res = await runtime.tool_dispatcher.dispatch(tool_name, arguments)
            return {
                "ok": res.ok,
                "output": res.output,
                "error": res.error,
                "elapsed_seconds": round(time.time() - start, 3),
            }
        except Exception as exc:
            return {
                "ok": False,
                "output": "",
                "error": str(exc),
                "elapsed_seconds": round(time.time() - start, 3),
            }

    # ------------------------------------------------------------------
    # Diagnostics & Doctor
    # ------------------------------------------------------------------

    async def run_diagnostics(self) -> dict[str, Any]:
        """Run full health check suite equivalent to `hermclaw doctor`."""
        checks: list[dict[str, Any]] = []

        # Config validity
        res = load_config(self.config_path)
        checks.append({
            "name": "Config Validity",
            "passed": res.valid,
            "detail": f"Loaded from {self.config_path}" if res.valid else "; ".join(res.errors),
        })

        # Profile state.db
        paths = self.pm.ensure_profile(self.profile)
        db_exists = paths.state_db.exists()
        checks.append({
            "name": f"Profile '{self.profile}' SQLite State DB",
            "passed": db_exists,
            "detail": str(paths.state_db) if db_exists else "Missing (auto-created on first use)",
        })

        # Identity files
        mem_ok = paths.memory_md.exists()
        user_ok = paths.user_md.exists()
        soul_ok = paths.soul_md.exists()
        checks.append({
            "name": "Identity Files (MEMORY.md, USER.md, SOUL.md)",
            "passed": mem_ok and user_ok and soul_ok,
            "detail": f"Memory: {'OK' if mem_ok else 'No'}, User: {'OK' if user_ok else 'No'}, Soul: {'OK' if soul_ok else 'No'}",
        })

        # Gateway auth token
        if res.config:
            token = gateway_token(res.config)
            checks.append({
                "name": "Gateway Auth Token",
                "passed": bool(token),
                "detail": "Configured" if token else "Not set (gateway running in open/local mode)",
            })

        # Ollama connection
        ollama_ok, models = await self.check_ollama()
        checks.append({
            "name": "Ollama Local Service (11434)",
            "passed": ollama_ok,
            "detail": f"Online with {len(models)} model(s): {', '.join(models[:4])}" if ollama_ok else "Offline or unreachable at http://localhost:11434",
        })

        # Skills validation
        skill_validations = self.validate_skills()
        all_skills_passed = all(v["passed"] for v in skill_validations) if skill_validations else True
        checks.append({
            "name": f"Skill Validations ({len(skill_validations)} skills)",
            "passed": all_skills_passed,
            "detail": "All skills passed schema check" if all_skills_passed else f"{sum(1 for v in skill_validations if not v['passed'])} skills have errors",
        })

        return {
            "all_passed": all(c["passed"] for c in checks),
            "checks": checks,
            "config_path": str(self.config_path),
            "timestamp": datetime.datetime.now().isoformat(),
        }
