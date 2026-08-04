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
