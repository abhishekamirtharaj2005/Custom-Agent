"""Builds a fully-wired HermclawAgent for one profile from a validated
HermclawConfig. Used by both body/gateway.py (channels + scheduler) and
cli.py (`hermclaw chat` / `hermclaw reflect`), so the two entry points
can never wire a profile up differently by accident.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import structlog

from hermclaw.body.mcp_client import McpClientManager
from hermclaw.brain.agent_loop import FallbackEntry, HermclawAgent
from hermclaw.brain.memory.compressor import ContextCompressor
from hermclaw.brain.memory.store import MemoryStore
from hermclaw.brain.memory.vector_memory import MemoryManageTool, VectorMemory
from hermclaw.brain.profiles import IdentityFiles, ProfileManager, ProfilePaths
from hermclaw.brain.skill_growth import SkillGrowthEngine
from hermclaw.brain.transports import MissingCredentialsError, build_transport
from hermclaw.config import HermclawConfig
from hermclaw.security.secrets import resolve_env_ref
from hermclaw.skills.registry import SkillRegistry
from hermclaw.tools.approvals import build_approval_gate
from hermclaw.tools.base import ToolDispatcher
from hermclaw.tools.browser_tool import BrowserTool
from hermclaw.tools.code_exec import CodeExecTool
from hermclaw.tools.delegate_tool import DelegateTool
from hermclaw.tools.file_tools import (
    FileEditTool,
    FileReadTool,
    FileWriteTool,
    GrepSearchTool,
    ListDirTool,
)
from hermclaw.tools.achievements import AchievementsTool
from hermclaw.tools.app_launcher import AppLauncherTool
from hermclaw.tools.clipboard_tool import ClipboardTool
from hermclaw.tools.git_tool import GitTool
from hermclaw.tools.goals_tool import GoalsTool
from hermclaw.tools.media_tools import ImageGenerateTool, VisionTool
from hermclaw.tools.memory_search import SessionSearchTool
from hermclaw.tools.notify_tool import NotifyTool
from hermclaw.tools.pdf_tool import PDFTool
from hermclaw.tools.scheduler_tool import SchedulerTool
from hermclaw.tools.shell import ShellTool
from hermclaw.tools.system_info import SystemInfoTool
from hermclaw.tools.task_tools import KanbanTool, TodoTool
from hermclaw.tools.tts_tool import TTSTool
from hermclaw.tools.virtual_pet import VirtualPetTool
from hermclaw.tools.web_tools import UrlReadTool, WebSearchTool

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class AgentRuntime:
    profile: str
    paths: ProfilePaths
    memory_store: MemoryStore
    identity_files: IdentityFiles
    skill_registry: SkillRegistry
    skill_growth_engine: SkillGrowthEngine
    tool_dispatcher: ToolDispatcher
    agent: HermclawAgent
    mcp_manager: Optional[McpClientManager] = None
    vector_memory: Optional[VectorMemory] = None

    async def aclose(self) -> None:
        if self.mcp_manager is not None:
            await self.mcp_manager.close()
        if self.vector_memory is not None:
            self.vector_memory.close()
        self.memory_store.close()


async def build_agent_runtime(
    profile: str,
    config: HermclawConfig,
    profile_manager: Optional[ProfileManager] = None,
) -> AgentRuntime:
    pm = profile_manager or ProfileManager()
    paths = pm.ensure_profile(profile)

    memory_store = MemoryStore(paths.state_db)
    identity_files = IdentityFiles(
        paths, memory_char_limit=config.brain.memory.memory_char_limit, user_char_limit=config.brain.memory.user_char_limit,
    )
    skill_registry = SkillRegistry(
        directory=paths.skills_dir, extra_directories=[d for d in config.skills.extra_directories],
    )
    skill_registry.load()
    skill_growth_engine = SkillGrowthEngine(pm)

    gate = build_approval_gate(mode=config.tools.approvals.mode)
    dispatcher = ToolDispatcher(gate)

    workspace = str(paths.workspace_dir)

    if config.tools.shell_enabled:
        dispatcher.register(
            ShellTool(
                backend=config.tools.backend,
                docker_image=config.tools.docker_image,
                docker_network=config.tools.docker_network,
                ssh_host=config.tools.ssh_host,
                ssh_user=config.tools.ssh_user,
                ssh_identity_file=config.tools.ssh_identity_file,
                filesystem_scope=workspace,
            )
        )

    # File tools -- structured file manipulation
    dispatcher.register(FileReadTool())
    dispatcher.register(FileWriteTool())
    dispatcher.register(FileEditTool())
    dispatcher.register(ListDirTool())
    dispatcher.register(GrepSearchTool())

    # Web tools -- search and URL reading
    dispatcher.register(WebSearchTool())
    dispatcher.register(UrlReadTool())

    # Browser automation (Playwright -- lazy-loads, no hard dep)
    dispatcher.register(BrowserTool())

    # Code execution tool
    dispatcher.register(CodeExecTool())

    # Media tools -- image generation and vision
    dispatcher.register(ImageGenerateTool())
    dispatcher.register(VisionTool())

    # Task management -- kanban and todos
    dispatcher.register(KanbanTool())
    dispatcher.register(TodoTool())

    # Multi-agent delegation
    dispatcher.register(DelegateTool())

    # Vector memory -- semantic search
    vector_db_path = paths.state_db.parent / "vector_memory.db"
    vector_memory = VectorMemory(vector_db_path, chat_model_name=config.brain.model.model_name)
    dispatcher.register(MemoryManageTool(vector_memory))

    # Goals system
    dispatcher.register(GoalsTool())

    # System tools
    dispatcher.register(AppLauncherTool())
    dispatcher.register(ClipboardTool())
    dispatcher.register(NotifyTool())
    dispatcher.register(SystemInfoTool())

    # Scheduler -- recurring tasks and cron
    dispatcher.register(SchedulerTool())

    # Voice -- TTS
    dispatcher.register(TTSTool())

    # Git checkpoint management
    dispatcher.register(GitTool())

    # PDF extraction
    dispatcher.register(PDFTool())

    # Learning graph
    from hermclaw.brain.learning_graph import LearningGraphTool
    dispatcher.register(LearningGraphTool())

    # Fun / gamification
    dispatcher.register(VirtualPetTool())
    dispatcher.register(AchievementsTool())

    # Session search -- the agent's episodic recall tool.
    dispatcher.register(SessionSearchTool(memory_store))

    # Load plugins and register their tools
    try:
        from hermclaw.plugins import PluginManager
        plugin_mgr = PluginManager()
        for plugin_instance in plugin_mgr.load_all():
            for tool in plugin_instance.tools:
                dispatcher.register(tool)
                logger.info("runtime.plugin_tool_registered", plugin=plugin_instance.manifest.name, tool=tool.spec().name)
    except Exception as exc:
        logger.warning("runtime.plugin_load_error", error=str(exc))

    mcp_manager: Optional[McpClientManager] = None
    if config.skills.mcp_servers:
        mcp_manager = McpClientManager(config.skills.mcp_servers)
        for tool in await mcp_manager.connect_all():
            dispatcher.register(tool)

    try:
        transport = build_transport(config.brain.model)
    except MissingCredentialsError:
        raise

    fallbacks = []
    for fb in config.brain.model.fallbacks:
        try:
            fallbacks.append(FallbackEntry(transport=build_transport(fb), model_config=fb))
        except MissingCredentialsError as exc:
            logger.warning("runtime.fallback_unavailable", provider=fb.provider, error=str(exc))

    compressor = ContextCompressor(
        memory_store, identity_files,
        compression_threshold=config.brain.memory.compression_threshold,
        keep_recent_exchanges=config.brain.memory.keep_recent_exchanges,
    )

    agent = HermclawAgent(
        profile=profile, memory_store=memory_store, identity_files=identity_files,
        skill_registry=skill_registry, tool_dispatcher=dispatcher, transport=transport,
        model_config=config.brain.model, fallbacks=fallbacks, compressor=compressor,
        vector_memory=vector_memory,
    )

    return AgentRuntime(
        profile=profile, paths=paths, memory_store=memory_store, identity_files=identity_files,
        skill_registry=skill_registry, skill_growth_engine=skill_growth_engine,
        tool_dispatcher=dispatcher, agent=agent, mcp_manager=mcp_manager,
        vector_memory=vector_memory,
    )


def gateway_token(config: HermclawConfig) -> Optional[str]:
    return resolve_env_ref(config.body.gateway.auth.token_env)

