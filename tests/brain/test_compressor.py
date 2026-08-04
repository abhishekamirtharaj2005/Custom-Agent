from __future__ import annotations

from hermclaw.brain.agent_loop import HermclawAgent
from hermclaw.brain.memory.compressor import ContextCompressor
from hermclaw.brain.transports.fake import FakeTransport, text_response, tool_call_response
from hermclaw.config import ModelConfig


def _make_agent(wired_profile, transport, compressor, context_window=2000):
    return HermclawAgent(
        profile="default", memory_store=wired_profile["memory_store"], identity_files=wired_profile["identity_files"],
        skill_registry=wired_profile["skill_registry"], tool_dispatcher=wired_profile["tool_dispatcher"],
        transport=transport, model_config=ModelConfig(model_name="fake", context_window=context_window),
        compressor=compressor,
    )


async def test_compression_triggers_past_threshold_and_links_lineage(wired_profile) -> None:
    store = wired_profile["memory_store"]
    identity = wired_profile["identity_files"]
    compressor = ContextCompressor(store, identity, compression_threshold=0.5, keep_recent_exchanges=1)

    def responder(messages, tools, system):
        tool_names = [t.name for t in tools]
        if "save_memory" in tool_names:
            return tool_call_response("save_memory", {"fact": "Deploying via Docker Compose", "about_user": True}, call_id="m1")
        if not tools:
            return text_response("Summary: discussed a multi-step deployment.")
        return text_response("continuing")

    transport = FakeTransport(responder=responder)
    agent = _make_agent(wired_profile, transport, compressor)

    session_id = store.create_session(channel="cli", model="fake")
    for i in range(30):
        store.add_message(session_id, "user" if i % 2 == 0 else "assistant", "x" * 200 + f" turn {i}")

    result = await agent.run_turn(session_id, "one more message to push past threshold")

    assert result.compressed is True
    assert result.session_id != session_id
    new_session = store.get_session(result.session_id)
    assert new_session.parent_session_id == session_id
    assert "Docker Compose" in identity.read_user()


async def test_old_messages_flagged_not_deleted(wired_profile) -> None:
    store = wired_profile["memory_store"]
    identity = wired_profile["identity_files"]
    compressor = ContextCompressor(store, identity, compression_threshold=0.5, keep_recent_exchanges=1)

    transport = FakeTransport(responder=lambda m, t, s: text_response("ok") if not t else tool_call_response("save_memory", {"fact": "noted"}))
    agent = _make_agent(wired_profile, transport, compressor)

    session_id = store.create_session(channel="cli", model="fake")
    for i in range(30):
        store.add_message(session_id, "user" if i % 2 == 0 else "assistant", "y" * 200 + f" turn {i}")

    await agent.run_turn(session_id, "trigger compression")

    all_msgs = store.get_session_messages(session_id, include_compressed_away=True)
    active_msgs = store.get_session_messages(session_id, include_compressed_away=False)
    assert len(active_msgs) < len(all_msgs)


async def test_below_threshold_does_not_compress(wired_profile) -> None:
    store = wired_profile["memory_store"]
    identity = wired_profile["identity_files"]
    compressor = ContextCompressor(store, identity, compression_threshold=0.99, keep_recent_exchanges=2)
    transport = FakeTransport(responses=[text_response("short reply")])
    agent = _make_agent(wired_profile, transport, compressor, context_window=1_000_000)

    session_id = store.create_session(channel="cli", model="fake")
    result = await agent.run_turn(session_id, "a short message")
    assert result.compressed is False
    assert result.session_id == session_id
