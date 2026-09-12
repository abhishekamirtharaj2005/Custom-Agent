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

