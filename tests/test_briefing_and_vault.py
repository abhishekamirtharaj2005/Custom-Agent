"""Tests for BriefingTool and KnowledgeVaultTool."""

from __future__ import annotations

from pathlib import Path
import pytest

from hermclaw.tools.briefing_tool import BriefingTool
from hermclaw.tools.vault_tool import KnowledgeVaultTool


@pytest.mark.asyncio
async def test_briefing_tool():
    tool = BriefingTool()
    spec = tool.spec()
    assert spec.name == "briefing"

    # 1. Morning briefing
    res_m = await tool.execute({"action": "morning_briefing"})
    assert res_m.ok is True
    assert "Executive Briefing" in res_m.output
    assert "System & Workstation Status" in res_m.output

    # 2. Nightly debrief
    res_n = await tool.execute({"action": "nightly_debrief"})
    assert res_n.ok is True
    assert "Nightly Debrief" in res_n.output

    # 3. Ergonomics check
    res_e = await tool.execute({"action": "ergonomics_check"})
    assert res_e.ok is True
    assert "minutes" in res_e.output

    # 4. Focus mode toggle
    res_f = await tool.execute({"action": "focus_mode", "toggle": "on", "duration_minutes": 30})
    assert res_f.ok is True
    assert "Focus Mode enabled" in res_f.output


@pytest.mark.asyncio
async def test_knowledge_vault_tool(tmp_path: Path):
    vault_dir = tmp_path / "MyObsidianVault"
    tool = KnowledgeVaultTool(default_vault_dir=vault_dir)

    # 1. Create a note
    res_create = await tool.execute({
        "action": "create_note",
        "title": "Quantum Computing Basics",
        "content": "Quantum superposition enables qubits to represent 0 and 1 simultaneously.",
        "tags": "quantum, physics, science",
        "links": "Linear Algebra, Quantum Gates",
    })
    assert res_create.ok is True
    assert "Created note" in res_create.output

    # Check file exists on disk
    note_file = vault_dir / "Quantum Computing Basics.md"
    assert note_file.exists()
    content = note_file.read_text(encoding="utf-8")
    assert "[[Linear Algebra]]" in content
    assert "[[Quantum Gates]]" in content
    assert "tags: [" in content

    # 2. Query vault
    res_query = await tool.execute({
        "action": "query_vault",
        "query": "superposition",
    })
    assert res_query.ok is True
    assert "Quantum Computing Basics" in res_query.output

    # 3. List notes
    res_list = await tool.execute({"action": "list_notes"})
    assert res_list.ok is True
    assert "Quantum Computing Basics" in res_list.output

    # 4. Sync vault
    res_sync = await tool.execute({"action": "sync_vault"})
    assert res_sync.ok is True
    index_file = vault_dir / "000_Index.md"
    assert index_file.exists()
    index_text = index_file.read_text(encoding="utf-8")
    assert "Hermclaw Second Brain" in index_text
