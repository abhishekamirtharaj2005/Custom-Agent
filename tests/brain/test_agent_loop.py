from __future__ import annotations

from hermclaw.brain.agent_loop import FallbackEntry, HermclawAgent
from hermclaw.brain.transports.base import TransportError
from hermclaw.brain.transports.fake import FakeTransport, text_response, tool_call_response
from hermclaw.config import ModelConfig
from hermclaw.tools.shell import ShellTool


async def test_simple_text_turn(wired_profile) -> None:
    transport = FakeTransport(responses=[text_response("Hello there!")])
    agent = HermclawAgent(
        profile="default", memory_store=wired_profile["memory_store"], identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"], tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=transport, model_config=ModelConfig(model_name="fake"),
    )
    session_id = wired_profile["memory_store"].create_session(channel="cli", model="fake")
    result = await agent.run_turn(session_id, "hi")
    assert result.text == "Hello there!"
    assert result.stop_reason == "end_turn"
    assert result.tool_calls_made == []


async def test_tool_calling_round_trip(wired_profile) -> None:
    wired_profile["tool_dispatcher"].register(ShellTool(backend="local"))
    transport = FakeTransport(responses=[
        tool_call_response("shell", {"command": "echo integration-test-marker"}),
        text_response("Done, it printed the marker."),
    ])
    agent = HermclawAgent(
        profile="default", memory_store=wired_profile["memory_store"], identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"], tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=transport, model_config=ModelConfig(model_name="fake"),
    )
    session_id = wired_profile["memory_store"].create_session(channel="cli", model="fake")
    result = await agent.run_turn(session_id, "run echo integration-test-marker")

    assert result.stop_reason == "end_turn"
    assert len(result.tool_calls_made) == 1
    assert "integration-test-marker" in result.tool_calls_made[0].result.output

    persisted = wired_profile["memory_store"].get_session_messages(session_id)
    assert [m.role for m in persisted] == ["user", "assistant", "tool", "assistant"]


async def test_conversation_history_is_reloaded_on_next_turn(wired_profile) -> None:
    transport = FakeTransport(responses=[text_response("first reply"), text_response("second reply")])
    agent = HermclawAgent(
        profile="default", memory_store=wired_profile["memory_store"], identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"], tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=transport, model_config=ModelConfig(model_name="fake"),
    )
    session_id = wired_profile["memory_store"].create_session(channel="cli", model="fake")
    await agent.run_turn(session_id, "first message")
    await agent.run_turn(session_id, "second message")

    second_call_messages = transport.calls[1]["messages"]
    contents = [m["content"] for m in second_call_messages]
    assert "first message" in contents
    assert "first reply" in contents
    assert "second message" in contents


async def test_fallback_transport_used_on_primary_failure(wired_profile) -> None:
    class AlwaysFailsTransport(FakeTransport):
        async def send(self, *args, **kwargs):
            raise TransportError("simulated primary outage")

    primary = AlwaysFailsTransport()
    fallback = FakeTransport(responses=[text_response("fallback handled it")])
    agent = HermclawAgent(
        profile="default", memory_store=wired_profile["memory_store"], identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"], tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=primary, model_config=ModelConfig(model_name="primary-fake"),
        fallbacks=[FallbackEntry(transport=fallback, model_config=ModelConfig(model_name="fallback-fake"))],
    )
    session_id = wired_profile["memory_store"].create_session(channel="cli", model="fake")
    result = await agent.run_turn(session_id, "hi")
    assert result.text == "fallback handled it"


async def test_system_prompt_includes_skill_listing(wired_profile, tmp_path) -> None:
    skills_dir = wired_profile["paths"].skills_dir
    skill_dir = skills_dir / "example-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: example-skill\ndescription: does example things\n---\nbody\n")
    wired_profile["skill_registry"].load()

    transport = FakeTransport(responses=[text_response("ok")])
    agent = HermclawAgent(
        profile="default", memory_store=wired_profile["memory_store"], identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"], tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=transport, model_config=ModelConfig(model_name="fake"),
    )
    session_id = wired_profile["memory_store"].create_session(channel="cli", model="fake")
    await agent.run_turn(session_id, "hi")
    assert "example-skill" in transport.calls[0]["system"]


async def test_agent_with_context_manager_lifecycle(wired_profile, tmp_path) -> None:
    from hermclaw.brain.memory.context_manager import ContextManager
    from hermclaw.tools.file_tools import FileWriteTool

    context_db_path = tmp_path / "context.db"
    cm = ContextManager(db_path=context_db_path)

    file_tool = FileWriteTool()
    wired_profile["tool_dispatcher"].register(file_tool)

    target_file = tmp_path / "created.txt"
    transport = FakeTransport(responses=[
        tool_call_response("file_write", {"path": str(target_file), "content": "Hello Context"}),
        text_response("File created successfully."),
    ])

    agent = HermclawAgent(
        profile="default",
        memory_store=wired_profile["memory_store"],
        identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"],
        tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=transport,
        model_config=ModelConfig(model_name="fake"),
        context_manager=cm,
    )

    session_id = wired_profile["memory_store"].create_session(channel="cli", model="fake")
    result = await agent.run_turn(session_id, "Please create a new file named created.txt with hello content")

    assert result.text == "File created successfully."
    assert len(result.tool_calls_made) == 1

    # Verify task state in context manager
    state = cm.get_task_state(session_id)
    assert "Please create a new file" in state.goal
    assert str(target_file) in state.files_modified

    # Verify events recorded in raw_events
    cur = cm._db.execute("SELECT event_type FROM raw_events WHERE session_id = ?", (session_id,))
    event_types = [r[0] for r in cur.fetchall()]
    assert "user_message" in event_types
    assert "file_write" in event_types
    assert "assistant_response" in event_types

    # Verify checkpoint created
    chk = cm.get_latest_checkpoint(session_id)
    assert chk is not None

    cm.close()


async def test_unlimited_tool_iterations_per_turn(wired_profile) -> None:
    from hermclaw.tools.shell import ShellTool
    wired_profile["tool_dispatcher"].register(ShellTool(backend="local"))

    # Produce 15 sequential tool calls in a single turn
    responses = [
        tool_call_response("shell", {"command": f"echo step_{i}"})
        for i in range(15)
    ]
    responses.append(text_response("All 15 steps completed successfully."))

    transport = FakeTransport(responses=responses)
    agent = HermclawAgent(
        profile="default",
        memory_store=wired_profile["memory_store"],
        identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"],
        tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=transport,
        model_config=ModelConfig(model_name="fake"),
    )

    session_id = wired_profile["memory_store"].create_session(channel="cli", model="fake")
    result = await agent.run_turn(session_id, "Run 15 steps")

    assert result.stop_reason == "end_turn"
    assert result.text == "All 15 steps completed successfully."
    assert len(result.tool_calls_made) == 15


