"""Tests for Hermclaw's External Context & Memory Manager.

Verifies all 11 core requirements:
1. Working Memory
2. Long-Term Memory
3. Task State Persistence
4. Automatic Context Compression
5. Hierarchical Memory (Levels 1-5, raw events never deleted)
6. Intelligent Retrieval
7. Memory Importance Classification & Selective Promotion
8. Automatic Checkpointing & Restoration
9. Dynamic Context Budgeting
10. Computer Vision / UI Optimization
11. Automatic Continuation across multi-step execution and context resets
"""

import asyncio
from pathlib import Path
import pytest

from hermclaw.brain.memory.context_manager import (
    BudgetAllocation,
    ContextManager,
    TaskState,
    classify_memory_importance,
    compact_ui_observation,
    normalize_messages,
)
from hermclaw.brain.memory.vector_memory import VectorMemory
from hermclaw.config import MemoryConfig, ModelConfig


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_context.db"


@pytest.fixture
def temp_vector_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_vector.db"


def test_task_state_lifecycle_and_prompt_rendering(temp_db_path: Path):
    """Req 3: Task State maintenance and prompt block generation."""
    cm = ContextManager(db_path=temp_db_path)

    session_id = "session_test_1"
    state = cm.initialize_task_from_prompt(
        session_id,
        "Build auth service\n1. Setup database schema\n2. Create JWT handler\n3. Add unit tests",
    )

    assert state.goal == "Build auth service"
    assert len(state.pending_tasks) == 3
    assert state.current_subtask == "Setup database schema"

    # State transitions
    state.mark_completed("Setup database schema")
    state.add_file_modified("src/models.py")
    state.add_decision("Selected PostgreSQL and asyncpg")
    state.add_error("Initial connection refused on port 5432")
    state.next_action = "Implement JWT token generation"
    cm.save_task_state(state)

    # Reload from DB and verify persistence
    loaded = cm.get_task_state(session_id)
    assert loaded.goal == "Build auth service"
    assert "Setup database schema" in loaded.completed_tasks
    assert "Create JWT handler" in loaded.pending_tasks
    assert loaded.current_subtask == "Create JWT handler"
    assert "src/models.py" in loaded.files_modified
    assert "Selected PostgreSQL and asyncpg" in loaded.important_decisions
    assert len(loaded.errors) == 1
    assert loaded.next_action == "Implement JWT token generation"

    # Render prompt block
    prompt_block = loaded.render_prompt_block(max_tokens=300)
    assert "[Current Task State]" in prompt_block
    assert "Goal: Build auth service" in prompt_block
    assert "Active Subtask: Create JWT handler" in prompt_block
    assert "src/models.py" in prompt_block

    cm.close()


def test_budget_allocation_scaling():
    """Req 9: Context Budget calculation and dynamic scaling."""
    # Local small model (4K context)
    small_budget = BudgetAllocation.calculate(context_window=4096, max_context_percent=0.75)
    assert small_budget.total_budget == 3072
    assert small_budget.system_tokens >= 200
    assert small_budget.task_state_tokens >= 200
    assert small_budget.recent_actions_tokens >= 300
    assert small_budget.retrieved_memory_tokens >= 300
    assert small_budget.relevant_files_tokens >= 200
    assert small_budget.current_observation_tokens >= 150

    # Cloud large model (128K context)
    large_budget = BudgetAllocation.calculate(context_window=128000, max_context_percent=0.80)
    assert large_budget.total_budget == 102400
    assert large_budget.system_tokens == 10240
    assert large_budget.task_state_tokens == 15360
    assert large_budget.recent_actions_tokens == 20480
    assert large_budget.retrieved_memory_tokens == 25600
    assert large_budget.relevant_files_tokens == 20480
    assert large_budget.current_observation_tokens == 10240


def test_memory_importance_classification():
    """Req 7: Memory Importance classification."""
    assert classify_memory_importance("event", "Here is the production api_key: sk-12345") == "critical"
    assert classify_memory_importance("event", "Constraint: never delete existing tests") == "critical"
    assert classify_memory_importance("file_write", "wrote file hermclaw/config.py") == "important"
    assert classify_memory_importance("decision", "Decided to adopt SQLite for storage") == "important"
    assert classify_memory_importance("error", "Failed: Connection refused") == "important"
    assert classify_memory_importance("event", "[debug] Heartbeat ping 200 OK") == "temporary"
    assert classify_memory_importance("event", "Listing files in directory") == "useful"


@pytest.mark.asyncio
async def test_importance_selective_promotion(temp_db_path: Path, temp_vector_db_path: Path):
    """Req 7 & Req 2: Selective promotion of important/critical events to VectorMemory."""
    vm = VectorMemory(db_path=temp_vector_db_path)
    cm = ContextManager(db_path=temp_db_path, vector_memory=vm)

    # 1. Temporary event -> not promoted
    await cm.record_event("s1", "heartbeat", "[debug] heartbeat ping")
    # 2. Useful event -> not promoted
    await cm.record_event("s1", "read", "read file README.md")
    # 3. Important event -> promoted to vector memory
    await cm.record_event("s1", "file_write", "wrote file /src/server.py", metadata={"path": "/src/server.py"})
    # 4. Critical event -> promoted to vector memory
    await cm.record_event("s1", "decision", "CRITICAL constraint: never delete the root database table")

    # Search in vector memory
    results = await vm.search("server.py", limit=5)
    assert any("server.py" in r["content"] for r in results)

    crit_results = await vm.search("database table", limit=5)
    assert any("never delete" in r["content"] for r in crit_results)

    # Verify task state tracked the modified file
    state = cm.get_task_state("s1")
    assert "/src/server.py" in state.files_modified

    vm.close()
    cm.close()


def test_checkpoints_and_restoration(temp_db_path: Path):
    """Req 8: Checkpoint saving, retrieval, and full state recovery."""
    cm = ContextManager(db_path=temp_db_path)
    session_id = "recovery_session"

    state = cm.get_task_state(session_id)
    state.goal = "Refactor payment processing"
    state.completed_tasks = ["Analyze Stripe API", "Draft migration plan"]
    state.pending_tasks = ["Implement webhook receiver", "Write idempotency tests"]
    state.current_subtask = "Implement webhook receiver"
    state.files_modified = ["payments/webhook.py"]
    state.add_decision("Use HMAC SHA256 validation for Stripe signatures")
    cm.save_task_state(state)

    working_memory = [
        {"role": "user", "content": "Let's work on webhook validation"},
        {"role": "assistant", "content": "I'll implement the signature verification function."},
    ]

    cid = cm.save_checkpoint(session_id, milestone="webhook_started", working_memory=working_memory)
    assert cid.startswith("chk_")

    # Simulate fresh startup / recovery
    cm_restored = ContextManager(db_path=temp_db_path)
    res = cm_restored.restore_from_checkpoint(session_id)
    assert res is not None
    restored_state, restored_working_memory = res

    assert restored_state.goal == "Refactor payment processing"
    assert restored_state.current_subtask == "Implement webhook receiver"
    assert "payments/webhook.py" in restored_state.files_modified
    assert "Use HMAC SHA256 validation for Stripe signatures" in restored_state.important_decisions
    assert len(restored_working_memory) == 2

    cm.close()
    cm_restored.close()


@pytest.mark.asyncio
async def test_hierarchical_memory_never_deletes_raw_events(temp_db_path: Path):
    """Req 5: Raw events -> Episode summaries -> Task summaries -> Phase summaries -> Global summary."""
    cm = ContextManager(db_path=temp_db_path)
    session_id = "hierarchical_session"

    # Level 1: Raw events
    for i in range(10):
        await cm.record_event(session_id, "tool_action", f"Ran action step {i}", role="assistant")

    # Verify 10 raw events exist
    cur = cm._db.execute("SELECT COUNT(*) FROM raw_events WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 10

    # Level 2: Episode summary
    cm.create_episode_summary(session_id, "Completed initial environment setup and package installation")

    # Level 3: Task summary
    cm.create_task_summary(session_id, "db_migration", "Applied schema migrations 001 through 004")

    # Level 4: Phase summary
    cm.create_phase_summary(session_id, "phase_1_infrastructure", "Infrastructure deployment verified healthy")

    # Level 5: Global summary
    cm.create_global_summary(session_id, "Hermclaw project initial platform rollout successful")

    # Verify raw events are NEVER deleted
    cur = cm._db.execute("SELECT COUNT(*) FROM raw_events WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 10

    # Verify hierarchical summaries retrievable
    summaries = cm.get_latest_summaries(session_id, limit=10)
    levels = [s["level"] for s in summaries]
    assert 5 in levels
    assert 4 in levels
    assert 3 in levels
    assert 2 in levels

    cm.close()


def test_computer_vision_optimization():
    """Req 10: Convert large screenshots/UI into compact structured state."""
    # Huge base64 image
    fake_b64 = "data:image/png;base64," + "A" * 20000 + "=="
    compact = compact_ui_observation(fake_b64)
    assert "data:image" not in compact
    assert "Screenshot data stored externally" in compact

    # UI structured dictionary
    ui_dict = {
        "title": "Hermclaw Dashboard",
        "elements": [{"id": 1, "type": "button", "label": "Save"}, {"id": 2, "type": "input"}],
    }
    compact_dict = compact_ui_observation(ui_dict)
    assert "[UI State: Window='Hermclaw Dashboard', Elements=2 interactive controls]" in compact_dict

    # List with image url
    image_list = [{"type": "image_url", "image_url": fake_b64}, {"type": "text", "text": "Click the submit button"}]
    compact_list = compact_ui_observation(image_list)
    assert "[Screenshot captured: Full resolution stored externally]" in compact_list
    assert "Click the submit button" in compact_list


def test_normalize_messages():
    """Verify normalize_messages enforces role alternation and starts with user."""
    # Consecutive assistants and starting with assistant
    raw_msgs = [
        {"role": "assistant", "content": "I am ready."},
        {"role": "assistant", "content": "Let me help you."},
        {"role": "user", "content": "Please run the tests."},
        {"role": "user", "content": "And format the report."},
    ]
    normalized = normalize_messages(raw_msgs)
    assert len(normalized) == 3
    assert normalized[0]["role"] == "user"
    assert normalized[1]["role"] == "assistant"
    assert normalized[2]["role"] == "user"
    assert "Please run the tests." in normalized[2]["content"]
    assert "And format the report." in normalized[2]["content"]


@pytest.mark.asyncio
async def test_budgeted_context_construction(temp_db_path: Path, temp_vector_db_path: Path):
    """Req 1, 6, 9: Budgeted context keeps only relevant working tail, injected task state, and retrieved memories."""
    vm = VectorMemory(db_path=temp_vector_db_path)
    cfg = MemoryConfig(recent_interactions_count=2, max_context_percent=0.75)
    cm = ContextManager(db_path=temp_db_path, config=cfg, vector_memory=vm)

    session_id = "budget_session"
    state = cm.get_task_state(session_id)
    state.goal = "Optimize database queries"
    state.current_subtask = "Add composite indexes"
    state.pending_tasks = ["Add composite indexes", "Verify query plan"]
    cm.save_task_state(state)

    # Seed vector memory with relevant past decision
    await vm.store("Composite index on (user_id, created_at) reduced latency by 80%", category="decision")

    # Simulate conversation history with 10 exchanges
    all_msgs = []
    for i in range(10):
        all_msgs.append({"role": "user", "content": f"User question {i}"})
        all_msgs.append({"role": "assistant", "content": f"Assistant response {i}"})

    model_config = ModelConfig(provider="anthropic", model_name="claude-3-7-sonnet", context_window=8192)

    budgeted = await cm.build_budgeted_context(
        session_id=session_id,
        user_message="How should we index the table?",
        system_prompt="You are Hermclaw.",
        all_messages=all_msgs,
        model_config=model_config,
    )

    # Context should not dump all 20 messages; working tail kept to recent exchanges + injected task context
    assert len(budgeted) < 12
    # Ensure task state & relevant memory present
    rendered_text = " ".join(str(m["content"]) for m in budgeted)
    assert "Goal: Optimize database queries" in rendered_text
    assert "Composite index" in rendered_text
    assert "Assistant response 9" in rendered_text

    vm.close()
    cm.close()


@pytest.mark.asyncio
async def test_auto_compression_and_continuation(temp_db_path: Path):
    """Req 4 & 11: Automatic compression when context limit approached, continuing with clean context."""
    cfg = MemoryConfig(max_context_percent=0.50)
    cm = ContextManager(db_path=temp_db_path, config=cfg)
    session_id = "comp_session"

    state = cm.get_task_state(session_id)
    state.goal = "Migrate auth service"
    state.current_subtask = "Write unit tests"
    state.completed_tasks = ["Setup schema", "Implement routes"]
    state.files_modified = ["src/auth.py", "src/models.py"]
    cm.save_task_state(state)

    # Create large message payload to simulate context saturation
    large_msgs = [
        {"role": "user", "content": "Here is the code " + ("X" * 3000)},
        {"role": "assistant", "content": "Understood. " + ("Y" * 3000)},
    ]
    model_cfg = ModelConfig(provider="openai_compat", model_name="qwen3.8", context_window=4096)

    # Should trigger compression since 6000 chars // 4 = 1500 tokens > (4096 * 0.50 = 2048)
    # Let's add more to guarantee crossing 2048:
    large_msgs.append({"role": "user", "content": "More data " + ("Z" * 4000)})

    assert cm.should_compress_context(large_msgs, system_prompt="Sys prompt", model_config=model_cfg) is True

    summary, continuation = await cm.compress_and_create_continuation(session_id, working_messages=large_msgs)

    assert "Completed subtasks" in summary or "Execution progressed" in summary
    assert len(continuation) >= 2
    assert "[Context Auto-Compressed]" in str(continuation[0]["content"])
    assert "Migrate auth service" in str(continuation[0]["content"])

    # Checkpoint was saved automatically
    chk = cm.get_latest_checkpoint(session_id)
    assert chk is not None
    assert chk["milestone"] == "auto_compression"

    cm.close()


@pytest.mark.asyncio
async def test_multi_step_task_across_multiple_context_resets(temp_db_path: Path, temp_vector_db_path: Path):
    """Req 11: Agent works through multi-subtask workload across multiple automatic context resets

    Verifies the entire lifecycle:
    User gives one large task
    -> Agent plans it
    -> Executes subtasks
    -> Saves state and memories
    -> Compresses context when necessary
    -> Starts a fresh context internally
    -> Retrieves relevant previous information
    -> Continues automatically
    -> Repeats until the entire task is completed.
    """
    vm = VectorMemory(db_path=temp_vector_db_path)
    cfg = MemoryConfig(max_context_percent=0.60, recent_interactions_count=2)
    cm = ContextManager(db_path=temp_db_path, config=cfg, vector_memory=vm)

    session_id = "long_running_session"
    initial_prompt = (
        "Create full microservice:\n"
        "1. Create database schema\n"
        "2. Implement business logic\n"
        "3. Add integration tests\n"
        "4. Deploy container"
    )

    # 1. Agent plans it
    state = cm.initialize_task_from_prompt(session_id, initial_prompt)
    assert len(state.pending_tasks) == 4
    assert state.current_subtask == "Create database schema"

    # 2. Subtask 1: Create database schema
    await cm.record_event(session_id, "file_write", "wrote schema.sql", metadata={"path": "schema.sql"})
    state.mark_completed("Create database schema")
    state.add_file_modified("schema.sql")
    state.add_decision("Used UUIDv4 for primary keys")
    cm.save_task_state(state)

    # 3. Simulate context nearing limit -> Reset 1
    working_msgs = [
        {"role": "user", "content": "Database schema created. Proceed with business logic."},
        {"role": "assistant", "content": "Starting business logic implementation."},
    ]
    summary1, cont1 = await cm.compress_and_create_continuation(session_id, working_msgs)
    assert "schema.sql" in summary1 or "Create database schema" in summary1
    assert "Active Subtask: Implement business logic" in str(cont1[0]["content"])

    # 4. Subtask 2: Implement business logic
    await cm.record_event(session_id, "file_write", "wrote app/service.py", metadata={"path": "app/service.py"})
    state.mark_completed("Implement business logic")
    state.add_file_modified("app/service.py")
    state.add_decision("Added redis caching layer for get_user endpoint")
    cm.save_task_state(state)

    # 5. Simulate context nearing limit -> Reset 2
    working_msgs2 = [
        {"role": "user", "content": "Business logic complete. Now add tests."},
        {"role": "assistant", "content": "Writing integration test suite."},
    ]
    summary2, cont2 = await cm.compress_and_create_continuation(session_id, working_msgs2)
    assert "Active Subtask: Add integration tests" in str(cont2[0]["content"])

    # 6. Subtask 3 & 4
    await cm.record_event(session_id, "file_write", "wrote tests/test_service.py", metadata={"path": "tests/test_service.py"})
    state = cm.get_task_state(session_id)
    state.mark_completed("Add integration tests")
    state.mark_completed("Deploy container")
    state.status = "completed"
    cm.save_task_state(state)
    cm.save_checkpoint(session_id, milestone="task_complete", working_memory=cont2)

    # Verify final persistent state across multiple resets
    final_state = cm.get_task_state(session_id)
    assert len(final_state.completed_tasks) == 4
    assert "Create database schema" in final_state.completed_tasks
    assert "Implement business logic" in final_state.completed_tasks
    assert "Add integration tests" in final_state.completed_tasks
    assert "Deploy container" in final_state.completed_tasks
    assert "schema.sql" in final_state.files_modified
    assert "app/service.py" in final_state.files_modified
    assert "tests/test_service.py" in final_state.files_modified
    assert "Used UUIDv4 for primary keys" in final_state.important_decisions
    assert "Added redis caching layer for get_user endpoint" in final_state.important_decisions
    assert final_state.status == "completed"

    # Verify all raw events were preserved intact
    cur = cm._db.execute("SELECT COUNT(*) FROM raw_events WHERE session_id = ?", (session_id,))
    assert cur.fetchone()[0] == 3

    # Verify hierarchical summaries preserved both resets
    summaries = cm.get_latest_summaries(session_id, limit=5)
    assert len(summaries) >= 2

    # Verify retrieval can bring back knowledge across the resets
    recalled = await cm.retrieve_relevant_memories("UUIDv4 primary keys", session_id=session_id)
    assert any("UUIDv4" in r or "schema" in r for r in recalled)

    vm.close()
    cm.close()
