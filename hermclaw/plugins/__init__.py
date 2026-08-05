"""Plugin system for Hermclaw.

Discovers, loads, and manages plugins from:
- Built-in plugins directory
- User plugins directory (~/.hermclaw/plugins/)
- Git-installed plugins

Each plugin is a directory with a plugin.json manifest and optional
Python modules that register tools, hooks, or skills.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class PluginManifest:
    """Parsed plugin.json manifest."""

    def __init__(self, data: dict[str, Any], plugin_dir: Path) -> None:
        self.name: str = data.get("name", plugin_dir.name)
        self.version: str = data.get("version", "0.0.0")
        self.description: str = data.get("description", "")
        self.author: str = data.get("author", "")
        self.entry_point: str = data.get("entry_point", "main.py")
        self.dependencies: list[str] = data.get("dependencies", [])
        self.hooks: list[str] = data.get("hooks", [])
        self.enabled: bool = data.get("enabled", True)
        self.plugin_dir = plugin_dir

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled,
            "directory": str(self.plugin_dir),
        }


class PluginInstance:
    """A loaded plugin instance."""

    def __init__(self, manifest: PluginManifest, module: Any = None) -> None:
        self.manifest = manifest
        self.module = module
        self.tools: list[Any] = []
        self.hooks: dict[str, list[Any]] = {}


class PluginManager:
    """Discovers and manages Hermclaw plugins."""

    def __init__(self, plugin_dirs: Optional[list[Path]] = None) -> None:
        home = Path.home() / ".hermclaw"
        default_dirs = [
            home / "plugins",
        ]
        self._dirs = plugin_dirs or default_dirs
        self._plugins: dict[str, PluginInstance] = {}

    def discover(self) -> list[PluginManifest]:
        """Discover all plugins in configured directories."""
        manifests = []
        for plugin_dir in self._dirs:
            if not plugin_dir.exists():
                plugin_dir.mkdir(parents=True, exist_ok=True)
                continue
            for item in sorted(plugin_dir.iterdir()):
                if not item.is_dir():
                    continue
                manifest_path = item / "plugin.json"
                if not manifest_path.exists():
                    continue
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest = PluginManifest(data, item)
                    manifests.append(manifest)
                except (json.JSONDecodeError, Exception) as exc:
                    logger.warning("plugin.invalid_manifest", path=str(manifest_path), error=str(exc))
        return manifests

    def load_all(self) -> list[PluginInstance]:
        """Load all discovered and enabled plugins."""
        manifests = self.discover()
        loaded = []
        for manifest in manifests:
            if not manifest.enabled:
                logger.info("plugin.skipped_disabled", name=manifest.name)
                continue
            try:
                instance = self._load_plugin(manifest)
                self._plugins[manifest.name] = instance
                loaded.append(instance)
                logger.info("plugin.loaded", name=manifest.name, version=manifest.version)
            except Exception as exc:
                logger.error("plugin.load_failed", name=manifest.name, error=str(exc))
        return loaded

    def _load_plugin(self, manifest: PluginManifest) -> PluginInstance:
        """Load a single plugin's entry point module."""
        entry = manifest.plugin_dir / manifest.entry_point
        module = None
        if entry.exists() and entry.suffix == ".py":
            spec = importlib.util.spec_from_file_location(
                f"hermclaw_plugin_{manifest.name}", str(entry)
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

        instance = PluginInstance(manifest, module)

        # If the module has a register() function, call it to get tools
        if module and hasattr(module, "register"):
            result = module.register()
            if isinstance(result, dict):
                instance.tools = result.get("tools", [])
                instance.hooks = result.get("hooks", {})
            elif isinstance(result, list):
                instance.tools = result

        return instance

    def get(self, name: str) -> Optional[PluginInstance]:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all discovered plugins with status."""
        manifests = self.discover()
        result = []
        for m in manifests:
            info = m.to_dict()
            info["loaded"] = m.name in self._plugins
            result.append(info)
        return result

    def install_from_git(self, repo_url: str) -> str:
        """Install a plugin from a git repository."""
        plugin_dir = self._dirs[0]
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Extract repo name from URL
        name = repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]

        target = plugin_dir / name
        if target.exists():
            # Update existing
            subprocess.run(
                ["git", "-C", str(target), "pull"],
                capture_output=True, timeout=30,
            )
            return f"Updated plugin '{name}' from {repo_url}"
        else:
            subprocess.run(
                ["git", "clone", repo_url, str(target)],
                capture_output=True, timeout=60,
            )
            return f"Installed plugin '{name}' from {repo_url}"

    def uninstall(self, name: str) -> bool:
        """Remove a plugin directory."""
        import shutil
        for d in self._dirs:
            target = d / name
            if target.exists():
                shutil.rmtree(target)
                self._plugins.pop(name, None)
                return True
        return False

    def create_template(self, name: str) -> Path:
        """Create a plugin template directory."""
        plugin_dir = self._dirs[0] / name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "name": name,
            "version": "0.1.0",
            "description": f"A Hermclaw plugin: {name}",
            "author": "",
            "entry_point": "main.py",
            "dependencies": [],
            "hooks": ["on_message", "on_tool_call"],
            "enabled": True,
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        main_py = '''"""Plugin: {name}

Register tools, hooks, or skills for Hermclaw.
"""

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


# Example custom tool
class MyTool(ToolABC):
    def spec(self):
        return ToolSpec(
            name="{name}_example",
            description="Example tool from {name} plugin.",
            parameters={{"type": "object", "properties": {{}}, "required": []}},
        )

    async def execute(self, args):
        return ToolResult(ok=True, output="Hello from {name} plugin!")


def register():
    """Called by PluginManager when loading. Return tools and hooks."""
    return {{
        "tools": [MyTool()],
        "hooks": {{}},
    }}
'''.format(name=name)
        (plugin_dir / "main.py").write_text(main_py, encoding="utf-8")

        return plugin_dir
