"""Plugin system enhancements: hooks, install/uninstall, registry.

Implements:
- Plugin lifecycle hooks (on_load, on_unload, on_message, etc.)
- Plugin install/uninstall/update
- Plugin registry with metadata
- Plugin version tracking
"""

from __future__ import annotations

import importlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Plugin lifecycle hooks
# ---------------------------------------------------------------------------


class PluginHook:
    """A named hook point in the plugin lifecycle."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._handlers: list[Callable] = []

    def register(self, handler: Callable) -> None:
        self._handlers.append(handler)
        logger.debug("plugin_hook.registered", hook=self.name, handler=handler.__name__)

    def unregister(self, handler: Callable) -> None:
        self._handlers = [h for h in self._handlers if h is not handler]

    async def fire(self, **kwargs: Any) -> list[Any]:
        """Fire the hook, calling all registered handlers."""
        results = []
        for handler in self._handlers:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**kwargs)
                else:
                    result = handler(**kwargs)
                results.append(result)
            except Exception as exc:
                logger.error("plugin_hook.handler_error",
                           hook=self.name, handler=handler.__name__, error=str(exc)[:100])
        return results


class PluginHookManager:
    """Manages all plugin lifecycle hooks."""

    HOOK_NAMES = [
        "on_load",          # Plugin loaded
        "on_unload",        # Plugin unloaded
        "on_message",       # New message received
        "on_response",      # Agent response generated
        "on_tool_call",     # Before tool execution
        "on_tool_result",   # After tool execution
        "on_session_start", # New session started
        "on_session_end",   # Session ended
        "on_error",         # Error occurred
        "on_config_reload", # Config file reloaded
    ]

    def __init__(self) -> None:
        self._hooks: dict[str, PluginHook] = {
            name: PluginHook(name) for name in self.HOOK_NAMES
        }

    def get(self, name: str) -> PluginHook:
        if name not in self._hooks:
            self._hooks[name] = PluginHook(name)
        return self._hooks[name]

    def register(self, hook_name: str, handler: Callable) -> None:
        self.get(hook_name).register(handler)

    async def fire(self, hook_name: str, **kwargs: Any) -> list[Any]:
        return await self.get(hook_name).fire(**kwargs)


# ---------------------------------------------------------------------------
# Plugin installer
# ---------------------------------------------------------------------------


class PluginInstaller:
    """Install, uninstall, and update plugins."""

    def __init__(self, plugins_dir: Path) -> None:
        self._dir = plugins_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def install_from_dir(self, source: Path, name: Optional[str] = None) -> bool:
        """Install a plugin from a directory."""
        name = name or source.name
        target = self._dir / name

        if target.exists():
            logger.warning("plugin.already_installed", name=name)
            return False

        shutil.copytree(source, target)

        # Create metadata
        meta = {
            "name": name,
            "installed_at": time.time(),
            "source": str(source),
            "version": "1.0.0",
        }
        (target / "plugin_meta.json").write_text(json.dumps(meta, indent=2))
        logger.info("plugin.installed", name=name)
        return True

    def uninstall(self, name: str) -> bool:
        """Uninstall a plugin."""
        target = self._dir / name
        if not target.exists():
            logger.warning("plugin.not_found", name=name)
            return False

        shutil.rmtree(target)
        logger.info("plugin.uninstalled", name=name)
        return True

    def update(self, name: str, source: Path) -> bool:
        """Update a plugin by replacing it."""
        target = self._dir / name
        if target.exists():
            # Backup old version
            backup = self._dir / f".{name}.backup"
            if backup.exists():
                shutil.rmtree(backup)
            shutil.move(str(target), str(backup))

        return self.install_from_dir(source, name)

    def list_installed(self) -> list[dict[str, Any]]:
        """List all installed plugins."""
        plugins = []
        for d in self._dir.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                meta_file = d / "plugin_meta.json"
                meta = {}
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                    except Exception:
                        pass

                has_init = (d / "__init__.py").exists()
                has_json = (d / "plugin.json").exists()

                plugins.append({
                    "name": d.name,
                    "path": str(d),
                    "has_init": has_init,
                    "has_manifest": has_json,
                    **meta,
                })
        return plugins


# ---------------------------------------------------------------------------
# CLI shell completion
# ---------------------------------------------------------------------------


COMPLETION_BASH = '''
_hermclaw_complete() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="chat serve doctor status skills plugins setup config reflect session mcp-server models"

    if [ $COMP_CWORD -eq 1 ]; then
        COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
    fi
}
complete -F _hermclaw_complete hermclaw
'''

COMPLETION_ZSH = '''
#compdef hermclaw

_hermclaw() {
    local -a commands
    commands=(
        'chat:Start an interactive chat session'
        'serve:Start the gateway server'
        'doctor:Run system diagnostics'
        'status:Show system status'
        'skills:Manage skills'
        'plugins:Manage plugins'
        'setup:Interactive setup wizard'
        'config:Show configuration'
        'reflect:Reflect on agent behavior'
        'session:Session management'
        'mcp-server:Start MCP server'
        'models:List available models'
    )
    _describe 'command' commands
}

_hermclaw
'''

COMPLETION_FISH = '''
complete -c hermclaw -f
complete -c hermclaw -n "__fish_use_subcommand" -a chat -d "Start interactive chat"
complete -c hermclaw -n "__fish_use_subcommand" -a serve -d "Start gateway server"
complete -c hermclaw -n "__fish_use_subcommand" -a doctor -d "Run diagnostics"
complete -c hermclaw -n "__fish_use_subcommand" -a status -d "Show status"
complete -c hermclaw -n "__fish_use_subcommand" -a skills -d "Manage skills"
complete -c hermclaw -n "__fish_use_subcommand" -a plugins -d "Manage plugins"
complete -c hermclaw -n "__fish_use_subcommand" -a setup -d "Setup wizard"
complete -c hermclaw -n "__fish_use_subcommand" -a mcp-server -d "Start MCP server"
complete -c hermclaw -n "__fish_use_subcommand" -a models -d "List models"
'''


def install_completion(shell: str = "bash") -> str:
    """Return shell completion script for the given shell."""
    scripts = {"bash": COMPLETION_BASH, "zsh": COMPLETION_ZSH, "fish": COMPLETION_FISH}
    return scripts.get(shell, COMPLETION_BASH)
