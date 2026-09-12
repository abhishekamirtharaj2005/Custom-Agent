import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from hermclaw.dashboard.service import DashboardService, CLOUD_PROVIDERS
from hermclaw.dashboard.server import create_dashboard_app
from hermclaw.brain.model_catalog import ModelCatalog


def test_model_catalog_has_all_requested_cloud_models():
    catalog = ModelCatalog()
    # Check OpenAI
    assert catalog.resolve("gpt-4o") is not None
    assert catalog.resolve("gpt-4o-mini") is not None
    assert catalog.resolve("o1") is not None
    assert catalog.resolve("o3-mini") is not None
    
    # Check Anthropic Claude
    assert catalog.resolve("claude-3-7-sonnet-latest") is not None
    assert catalog.resolve("claude-3-5-sonnet-latest") is not None
    assert catalog.resolve("claude-3-5-haiku-20241022") is not None
    
    # Check Google Gemini
    assert catalog.resolve("gemini-2.5-pro") is not None
    assert catalog.resolve("gemini-2.5-flash") is not None
    assert catalog.resolve("gemini-2.0-flash") is not None


def test_api_keys_status_and_save(tmp_path: Path, monkeypatch):
    # Set fake hermclaw_home to tmp_path
    monkeypatch.setattr("hermclaw.dashboard.service.hermclaw_home", lambda: tmp_path)
    
    # Clear env vars
    for p in CLOUD_PROVIDERS:
        monkeypatch.delenv(p["env_var"], raising=False)
        if p.get("alt_env_var"):
            monkeypatch.delenv(p["alt_env_var"], raising=False)

    svc = DashboardService()
    status_initial = svc.get_api_keys_status()
    assert all(not p["configured"] for p in status_initial)

    # Save keys for OpenAI and Gemini
    ok, msg = svc.save_api_keys({
        "OPENAI_API_KEY": "sk-proj-test1234567890",
        "GEMINI_API_KEY": "AIzaSyTestGeminiKey123456",
    })
    assert ok is True

    # Verify status after saving
    status_after = svc.get_api_keys_status()
    openai_st = next(s for s in status_after if s["id"] == "openai")
    gemini_st = next(s for s in status_after if s["id"] == "gemini")
    claude_st = next(s for s in status_after if s["id"] == "anthropic")

    assert openai_st["configured"] is True
    assert "sk-p...7890" == openai_st["preview"]
    assert gemini_st["configured"] is True
    assert claude_st["configured"] is False

    # Check that .env file contains keys
    env_content = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" in env_content
    assert "GEMINI_API_KEY" in env_content


@pytest.mark.live
@pytest.mark.asyncio
async def test_available_models_with_local_and_cloud(tmp_path: Path, monkeypatch):

    monkeypatch.setattr("hermclaw.dashboard.service.hermclaw_home", lambda: tmp_path)
    svc = DashboardService()

    # Mock Ollama returning 2 local models
    async def mock_check_ollama():
        return True, ["gemma4:12b", "llama3.1:8b"]
    monkeypatch.setattr(svc, "check_ollama", mock_check_ollama)

    # Initially with no cloud keys
    for p in CLOUD_PROVIDERS:
        monkeypatch.delenv(p["env_var"], raising=False)
        if p.get("alt_env_var"):
            monkeypatch.delenv(p["alt_env_var"], raising=False)

    models_initial = await svc.get_available_models()
    local_models = [m for m in models_initial if m["type"] == "local"]
    cloud_models = [m for m in models_initial if m["type"] == "cloud"]

    assert len(local_models) == 2
    assert local_models[0]["display_label"] == "gemma4:12b [Local]"
    assert len(cloud_models) == 0

    # Add Anthropic Claude and OpenAI keys
    svc.save_api_keys({
        "ANTHROPIC_API_KEY": "sk-ant-test-key-123456",
        "OPENAI_API_KEY": "sk-test-openai-123456",
    })

    models_with_cloud = await svc.get_available_models()
    cloud_models_updated = [m for m in models_with_cloud if m["type"] == "cloud"]
    
    assert len(cloud_models_updated) > 0
    # Check that tags contain [Cloud - Provider]
    openai_models = [m for m in cloud_models_updated if m["provider"] == "openai"]
    claude_models = [m for m in cloud_models_updated if m["provider"] == "anthropic"]

    assert len(openai_models) > 0
    assert any("[Cloud - OpenAI]" in m["display_label"] for m in openai_models)
    assert any("[Cloud - Anthropic Claude]" in m["display_label"] for m in claude_models)


@pytest.mark.live
def test_dashboard_server_endpoints(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("hermclaw.dashboard.service.hermclaw_home", lambda: tmp_path)
    svc = DashboardService()
    app = create_dashboard_app(service=svc)
    client = TestClient(app)

    # 1. GET /api/settings/keys
    res = client.get("/api/settings/keys")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(p["id"] == "openai" for p in data)

    # 2. POST /api/settings/keys
    res_post = client.post("/api/settings/keys", json={
        "keys": {
            "GROQ_API_KEY": "gsk_testgroqkey123456"
        }
    })
    assert res_post.status_code == 200
    assert res_post.json()["success"] is True

    # Verify groq is now configured
    res_after = client.get("/api/settings/keys")
    groq_info = next(p for p in res_after.json() if p["id"] == "groq")
    assert groq_info["configured"] is True

    # 3. GET /api/models
    res_models = client.get("/api/models")
    assert res_models.status_code == 200
    models_data = res_models.json()
    assert any(m["provider"] == "groq" for m in models_data)
    groq_m = next(m for m in models_data if m["provider"] == "groq")
    assert "[Cloud - Groq]" in groq_m["display_label"]


@pytest.mark.live
@pytest.mark.asyncio
async def test_switch_model_validation(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("hermclaw.dashboard.service.hermclaw_home", lambda: tmp_path)
    svc = DashboardService()
    
    # Without API key, switching to anthropic or openai raises ValueError
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Anthropic API key is not configured"):
        await svc.switch_model("claude-3-5-sonnet-latest")

    # Local Ollama model does not require cloud API key
    res = await svc.switch_model("gemma4:12b")
    assert res["success"] is True
    assert res["model_name"] == "gemma4:12b"


@pytest.mark.live
def test_ai_engine_config_and_saved_models(tmp_path: Path, monkeypatch):
    """Test AI Engine Config card save, saved models list, and model edit/switch."""
    monkeypatch.setattr("hermclaw.dashboard.service.hermclaw_home", lambda: tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = create_dashboard_app()
    client = TestClient(app)

    # 1. Initially saved models
    res = client.get("/api/engine/saved-models")
    assert res.status_code == 200
    init_models = res.json()
    assert isinstance(init_models, list)

    # 2. Save Engine Config for OpenAI gpt-4o-mini
    res_save = client.post("/api/engine/save", json={
        "provider": "openai",
        "model_name": "gpt-4o-mini",
        "api_key": "sk-proj-testkey987654",
        "set_active": True,
    })
    assert res_save.status_code == 200
    assert res_save.json()["success"] is True

    # 3. Verify in saved models list
    res_saved = client.get("/api/engine/saved-models")
    assert res_saved.status_code == 200
    saved_list = res_saved.json()
    found = next((m for m in saved_list if m["id"] == "gpt-4o-mini"), None)
    assert found is not None
    assert found["provider"] == "openai"
    assert found["type"] == "cloud"
    assert found["is_active"] is True
    assert "sk-p" in found["key_preview"]

    # 4. Verify in /api/models
    res_models = client.get("/api/models")
    assert any(m["id"] == "gpt-4o-mini" for m in res_models.json())


@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_cloud_model_classification_and_switch(tmp_path: Path, monkeypatch):
    """Test that any Gemini model is strictly tagged as Cloud with Google Gemini provider, not Local."""
    monkeypatch.setattr("hermclaw.dashboard.service.hermclaw_home", lambda: tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy_fake_test_gemini_key_12345")

    svc = DashboardService()
    # Save a custom gemini model (e.g. gemini-3.8-flash)
    ok, msg = svc.save_engine_config(
        provider="gemini",
        model_name="gemini-3.8-flash",
        api_key="AIzaSy_fake_test_gemini_key_12345",
        set_active=True,
    )
    assert ok is True

    # 1. Available models check
    models = await svc.get_available_models()
    gemini_m = next((m for m in models if m["id"] == "gemini-3.8-flash"), None)
    assert gemini_m is not None
    assert gemini_m["type"] == "cloud"
    assert gemini_m["provider"] == "gemini"
    assert gemini_m["tag"] == "[Cloud - Google Gemini]"
    assert "[Cloud - Google Gemini]" in gemini_m["display_label"]
    assert "[Local]" not in gemini_m["display_label"]

    # 2. Saved models list check
    saved = await svc.get_saved_models_list()
    saved_gemini = next((m for m in saved if m["id"] == "gemini-3.8-flash"), None)
    assert saved_gemini is not None
    assert saved_gemini["type"] == "cloud"
    assert saved_gemini["provider"] == "gemini"
    assert saved_gemini["provider_name"] == "Google Gemini"
    assert saved_gemini["tag"] == "[Cloud - Google Gemini]"

    # 3. Model switch check
    res_switch = await svc.switch_model("gemini-3.8-flash")
    assert res_switch["success"] is True
    assert res_switch["model_name"] == "gemini-3.8-flash"
    assert res_switch["provider"] == "gemini"
    assert svc._current_provider == "gemini"
    assert svc._current_model == "gemini-3.8-flash"

    # Runtime transport should be GeminiTransport
    runtime = await svc.get_runtime()
    from hermclaw.brain.transports.gemini import GeminiTransport
    assert isinstance(runtime.agent.transport, GeminiTransport)


@pytest.mark.live
@pytest.mark.asyncio
async def test_send_message_transport_error_surfaced(tmp_path: Path, monkeypatch):
    """Test that transport errors return informative error messages instead of empty responses."""
    monkeypatch.setattr("hermclaw.dashboard.service.hermclaw_home", lambda: tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")

    svc = DashboardService()
    await svc.switch_model("gemini-3.8-flash", provider="gemini")
    sid = await svc.create_session("Test Error Session")

    runtime = await svc.get_runtime()

    # Mock agent.run_turn to raise TransportError
    from hermclaw.brain.transports.base import TransportError
    async def mock_run_turn(*args, **kwargs):
        raise TransportError("HTTP 404 from Gemini: models/gemini-3.8-flash not found")

    monkeypatch.setattr(runtime.agent, "run_turn", mock_run_turn)

    # Call send_message
    res = await svc.send_message(sid, "hello")
    assert "text" in res
    assert "⚠️ **Agent Error:**" in res["text"]
    assert "models/gemini-3.8-flash not found" in res["text"]
    assert "Tip:" in res["text"]
    assert res["text"] != "(empty response)"


def test_gemini_thought_signature_preservation_and_fallback():
    """Test that GeminiTransport parses thoughtSignature and serializes it back to contents,
    and falls back cleanly to descriptive text if thoughtSignature is missing."""
    from hermclaw.brain.transports.gemini import GeminiTransport
    from hermclaw.brain.agent_loop import tool_use_block, rows_to_canonical_messages
    from hermclaw.brain.transports.base import ToolCallRequest
    from hermclaw.brain.memory.store import MessageRow
    from datetime import datetime, timezone

    # 1. Parsing response with thoughtSignature
    transport = GeminiTransport(api_key="dummy_key", model_name="gemini-3.8-flash")
    raw_response = {
        "candidates": [{
            "content": {
                "parts": [{
                    "functionCall": {
                        "name": "app_launcher",
                        "args": {"app_name": "notepad"},
                    },
                    "thoughtSignature": "test_cryptographic_signature_abc123"
                }],
                "role": "model"
            },
            "finishReason": "STOP"
        }]
    }
    parsed = transport._parse_response(raw_response)
    assert len(parsed.tool_calls) == 1
    tc = parsed.tool_calls[0]
    assert tc.name == "app_launcher"
    assert tc.thought_signature == "test_cryptographic_signature_abc123"

    # 2. tool_use_block preserves thought_signature
    tu = tool_use_block(tc)
    assert tu["type"] == "tool_use"
    assert tu["thought_signature"] == "test_cryptographic_signature_abc123"

    # 3. Serializing back to Gemini contents format with thoughtSignature
    messages_with_sig = [
        {"role": "user", "content": "open notepad"},
        {"role": "assistant", "content": [tu]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "app_launcher", "content": "Notepad opened"}]}
    ]
    contents, _ = transport._to_gemini_contents(messages_with_sig, "")
    assert len(contents) == 3
    model_turn = contents[1]
    assert model_turn["role"] == "model"
    assert "thoughtSignature" in model_turn["parts"][0]
    assert model_turn["parts"][0]["thoughtSignature"] == "test_cryptographic_signature_abc123"
    assert model_turn["parts"][0]["functionCall"]["name"] == "app_launcher"
    
    user_tool_resp = contents[2]
    assert user_tool_resp["role"] == "user"
    assert "functionResponse" in user_tool_resp["parts"][0]
    assert user_tool_resp["parts"][0]["functionResponse"]["name"] == "app_launcher"

    # 4. Fallback for older/unsigned tool calls: downgrade to text to avoid Gemini API 400
    tc_unsigned = ToolCallRequest(id="app_launcher", name="app_launcher", arguments={"app_name": "notepad"})
    tu_unsigned = tool_use_block(tc_unsigned)
    assert "thought_signature" not in tu_unsigned

    messages_unsigned = [
        {"role": "user", "content": "open notepad"},
        {"role": "assistant", "content": [tu_unsigned]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "app_launcher", "content": "Notepad opened"}]}
    ]
    contents_unsigned, _ = transport._to_gemini_contents(messages_unsigned, "")
    assert len(contents_unsigned) == 3
    # Model turn should be text, not functionCall without thoughtSignature
    assert "text" in contents_unsigned[1]["parts"][0]
    assert "app_launcher" in contents_unsigned[1]["parts"][0]["text"]
    # User turn should be text, not unmatched functionResponse
    assert "text" in contents_unsigned[2]["parts"][0]
    assert "Notepad opened" in contents_unsigned[2]["parts"][0]["text"]



