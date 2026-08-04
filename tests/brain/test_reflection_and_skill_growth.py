from __future__ import annotations

from hermclaw.brain.reflection import reflect
from hermclaw.brain.skill_growth import SkillEvolutionEngine, _token_similarity
from hermclaw.brain.transports.fake import FakeTransport, text_response, tool_call_response
from hermclaw.skills.registry import SkillRegistry


async def test_reflection_distills_facts_and_hands_off_repeated_procedure(wired_profile) -> None:
    store = wired_profile["memory_store"]
    identity = wired_profile["identity_files"]
    growth = wired_profile["skill_growth_engine"]

    for i in range(5):
        sid = store.create_session(channel="cli", model="fake", title=f"session {i}")
        store.add_message(sid, "user", f"Deploy to staging please (variant {i})")
        store.add_message(sid, "assistant", "Deploying now.")

    distillation = {
        "facts": ["The project uses blue-green deployment"],
        "user_facts": ["User wants deploys done before 5pm"],
        "repeated_procedures": [
            {"description": "Deploy the app to staging", "occurrences": 5,
             "steps": ["Run tests", "Build image", "Push to registry", "Roll deployment"]},
            {"description": "One-off task seen only twice", "occurrences": 2, "steps": ["Do a thing"]},
        ],
    }
    transport = FakeTransport(responses=[tool_call_response("submit_reflection", distillation)])

    result = await reflect("default", store, identity, growth, transport, n_sessions=20)

    assert result.sessions_reviewed == 5
    assert len(result.procedures_handed_to_skill_growth) == 1  # only the >=3-occurrence one
    assert len(result.draft_skills_created) == 1
    assert "blue-green" in identity.read_memory()
    assert "5pm" in identity.read_user()

    registry = SkillRegistry(directory=wired_profile["paths"].skills_dir)
    registry.load()
    assert len(registry.auto_generated_skills()) == 1


async def test_reflection_dedups_reworded_repeat_procedure(wired_profile) -> None:
    store = wired_profile["memory_store"]
    identity = wired_profile["identity_files"]
    growth = wired_profile["skill_growth_engine"]

    for i in range(5):
        sid = store.create_session(channel="cli", model="fake", title=f"session {i}")
        store.add_message(sid, "user", f"Deploy to staging please (variant {i})")
        store.add_message(sid, "assistant", "Deploying now.")

    first = {
        "facts": [], "user_facts": [],
        "repeated_procedures": [{
            "description": "Deploy the app to staging", "occurrences": 5,
            "steps": ["Run tests", "Build image", "Push to registry", "Roll deployment"],
        }],
    }
    result1 = await reflect("default", store, identity, growth, FakeTransport(responses=[tool_call_response("submit_reflection", first)]))
    assert len(result1.draft_skills_created) == 1

    # Same underlying procedure, meaningfully different wording (different
    # word forms, not just reordering) -- this is the "5 sessions with
    # trivial wording differences still produce exactly one skill" case.
    second = {
        "facts": [], "user_facts": [],
        "repeated_procedures": [{
            "description": "Deploying the application onto the staging environment", "occurrences": 4,
            "steps": ["Kick off tests", "Build the image", "Push image to the registry", "Update staging"],
        }],
    }
    result2 = await reflect("default", store, identity, growth, FakeTransport(responses=[tool_call_response("submit_reflection", second)]))

    assert len(result2.draft_skills_created) == 0
    registry = SkillRegistry(directory=wired_profile["paths"].skills_dir)
    registry.load()
    assert len(registry.auto_generated_skills()) == 1


def test_token_similarity_separates_same_from_different_procedures() -> None:
    same_a = "Deploy the app to staging"
    same_b = "Deploying the application onto the staging environment"
    different = "Send a weekly summary email to the team"

    same_score = _token_similarity(same_a, same_b)
    different_score = _token_similarity(same_a, different)
    assert same_score > different_score
    assert same_score >= 0.5
    assert different_score < 0.5


async def test_reflection_handles_zero_sessions_gracefully(wired_profile) -> None:
    store = wired_profile["memory_store"]
    identity = wired_profile["identity_files"]
    growth = wired_profile["skill_growth_engine"]
    result = await reflect("default", store, identity, growth, FakeTransport())
    assert result.sessions_reviewed == 0
    assert result.facts_saved == []


async def test_skill_evolution_proposes_and_applies(wired_profile) -> None:
    growth = wired_profile["skill_growth_engine"]
    growth.generate_draft_skill({"description": "Deploy to staging", "occurrences": 3, "steps": ["a", "b"]}, "default")

    registry = SkillRegistry(directory=wired_profile["paths"].skills_dir)
    registry.load()

    transport = FakeTransport(responses=[text_response("1. Run tests\n2. Build+push image\n3. Update staging")])
    evo = SkillEvolutionEngine(registry, wired_profile["memory_store"], transport)
    result = await evo.evolve_skill("deploy-to-staging")
    assert result is not None
    path = evo.apply_evolution(result)
    assert "Run tests" in path.read_text()


async def test_skill_evolution_unknown_skill_returns_none(wired_profile) -> None:
    registry = SkillRegistry(directory=wired_profile["paths"].skills_dir)
    registry.load()
    evo = SkillEvolutionEngine(registry, wired_profile["memory_store"], FakeTransport())
    assert await evo.evolve_skill("does-not-exist") is None


async def test_skill_evolution_gepa_stub_raises_not_implemented(wired_profile) -> None:
    registry = SkillRegistry(directory=wired_profile["paths"].skills_dir)
    evo = SkillEvolutionEngine(registry, wired_profile["memory_store"], FakeTransport())
    try:
        await evo.evolve_with_gepa("anything")
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass
