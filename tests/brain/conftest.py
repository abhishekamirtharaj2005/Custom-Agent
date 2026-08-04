from __future__ import annotations

from pathlib import Path

import pytest

from hermclaw.brain.memory.store import MemoryStore
from hermclaw.brain.profiles import IdentityFiles, ProfileManager
from hermclaw.brain.skill_growth import SkillGrowthEngine
from hermclaw.skills.registry import SkillRegistry
from hermclaw.tools.approvals import build_approval_gate
from hermclaw.tools.base import ToolDispatcher


@pytest.fixture
def wired_profile(profile_manager: ProfileManager):
    """A fully-constructed set of profile-scoped objects (memory store,
    identity files, skill registry/growth, tool dispatcher) for the
    'default' profile, with no transport attached -- tests supply their
    own FakeTransport."""
    paths = profile_manager.ensure_profile("default")
    store = MemoryStore(paths.state_db)
    identity = IdentityFiles(paths)
    registry = SkillRegistry(directory=paths.skills_dir)
    registry.load()
    growth = SkillGrowthEngine(profile_manager)
    dispatcher = ToolDispatcher(build_approval_gate(mode="off"))
    return {
        "paths": paths, "memory_store": store, "identity_files": identity,
        "skill_registry": registry, "skill_growth_engine": growth, "tool_dispatcher": dispatcher,
    }
