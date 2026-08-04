from __future__ import annotations

import asyncio
import io
from pathlib import Path

import pytest

from hermclaw.brain.profiles import IdentityFiles, ProfileManager


def test_ensure_profile_creates_expected_layout(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    paths = pm.ensure_profile("alice")
    assert paths.root.is_dir()
    assert paths.soul_md.exists()
    assert paths.memory_md.exists()
    assert paths.user_md.exists()
    assert paths.skills_dir.is_dir()
    assert paths.workspace_dir.is_dir()


def test_two_profiles_get_distinct_roots(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    a = pm.ensure_profile("alice")
    b = pm.ensure_profile("work_bot")
    assert a.root != b.root


def test_path_traversal_rejected(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    with pytest.raises(ValueError):
        pm.paths("../../etc")
    with pytest.raises(ValueError):
        pm.paths("some/nested/path")


def test_list_profiles(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    pm.ensure_profile("alice")
    pm.ensure_profile("bob")
    assert set(pm.list_profiles()) == {"alice", "bob"}


def test_soul_md_never_auto_written(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    paths = pm.ensure_profile("alice")
    identity = IdentityFiles(paths)
    original_soul = identity.read_soul()
    identity.append_memory_facts(["some fact"])
    identity.append_user_facts(["some user fact"])
    assert identity.read_soul() == original_soul


def test_memory_facts_appended_and_trimmed_to_limit(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    paths = pm.ensure_profile("alice")
    identity = IdentityFiles(paths, memory_char_limit=150)
    identity.append_memory_facts(["short fact one"])
    assert "short fact one" in identity.read_memory()

    identity.append_memory_facts([f"filler fact number {i} taking up meaningful space" for i in range(20)])
    assert len(identity.read_memory()) <= 150 + 60  # small slop for a final partial line boundary


def test_assemble_system_prompt_includes_all_sections(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    paths = pm.ensure_profile("alice")
    identity = IdentityFiles(paths)
    identity.paths.soul_md.write_text("# SOUL.md\n\nBe concise.\n")
    identity.append_memory_facts(["The user's project uses Postgres"])
    identity.append_user_facts(["The user prefers terse answers"])

    prompt = identity.assemble_system_prompt(
        recent_summary="Last session covered deployment setup.",
        skills_compact=[{"name": "deploy-helper", "description": "Helps deploy things"}],
    )
    assert "Be concise" in prompt
    assert "Postgres" in prompt
    assert "terse answers" in prompt
    assert "deployment setup" in prompt
    assert "deploy-helper" in prompt


@pytest.mark.asyncio
async def test_concurrent_profiles_never_cross_contaminate(tmp_path: Path) -> None:
    pm = ProfileManager(home=tmp_path)
    paths_a = pm.ensure_profile("alice")
    paths_b = pm.ensure_profile("work_bot")

    opened_paths: list[str] = []
    orig_open = io.open

    def tracking_open(path, *args, **kwargs):
        opened_paths.append(str(path))
        return orig_open(path, *args, **kwargs)

    async def touch_profile(name: str, paths, delay: float) -> None:
        identity = IdentityFiles(paths)
        for i in range(5):
            identity.append_user_facts([f"{name} fact {i}"])
            await asyncio.sleep(delay)
            content = identity.read_user()
            assert name in content
            other = "alice" if name == "work_bot" else "work_bot"
            assert other not in content, f"cross-profile leak: {other} found in {name}'s USER.md"

    io.open = tracking_open
    try:
        await asyncio.gather(
            touch_profile("alice", paths_a, 0.01),
            touch_profile("work_bot", paths_b, 0.007),
        )
    finally:
        io.open = orig_open

    alice_touched = [p for p in opened_paths if "/alice/" in p]
    workbot_touched = [p for p in opened_paths if "/work_bot/" in p]
    assert alice_touched and workbot_touched
    assert not (set(alice_touched) & set(workbot_touched))
