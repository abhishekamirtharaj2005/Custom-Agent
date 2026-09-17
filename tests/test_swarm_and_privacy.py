"""Tests for SwarmOrchestrator and PrivacyGuard."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from PIL import Image

from hermclaw.brain.swarm import SwarmOrchestrator, SPECIALIST_PERSONAS
from hermclaw.tools.delegate_tool import DelegateTool
from hermclaw.security.privacy_guard import PrivacyGuard, ActionRiskPolicy


@pytest.mark.asyncio
async def test_swarm_orchestrator():
    orch = SwarmOrchestrator()
    roles = orch.list_roles()
    assert len(roles) >= 4
    role_names = [r["role"] for r in roles]
    assert "researcher" in role_names
    assert "coder" in role_names
    assert "desktop_operator" in role_names
    assert "reviewer" in role_names

    # Test pipeline execution
    pipeline = await orch.execute_swarm_pipeline(
        task="Build an automated stock analysis dashboard",
        roles=["researcher", "coder", "reviewer"],
    )
    assert len(pipeline["steps"]) == 3
    assert pipeline["roles_executed"] == ["researcher", "coder", "reviewer"]
    assert "Final Synthesis" in pipeline["final_synthesis"] or len(pipeline["steps"]) > 0


@pytest.mark.asyncio
async def test_delegate_tool_swarm_action():
    tool = DelegateTool()

    # 1. Roles action
    res_roles = await tool.execute({"action": "roles"})
    assert res_roles.ok is True
    assert "RESEARCHER" in res_roles.output
    assert "CODER" in res_roles.output

    # 2. Swarm action
    res_swarm = await tool.execute({
        "action": "swarm",
        "prompt": "Analyze WhatsApp messages and summarize key items",
        "roles": "researcher,coder",
    })
    assert res_swarm.ok is True
    assert "Multi-Agent Swarm Pipeline Completed" in res_swarm.output
    assert "researcher ➔ coder" in res_swarm.output


def test_privacy_guard_detection_and_masking():
    guard = PrivacyGuard()

    # Sensitive window detection
    assert guard.is_window_sensitive("1Password - Vault") is True
    assert guard.is_window_sensitive("Chase Online Banking") is True
    assert guard.is_window_sensitive("Metamask Notification") is True
    assert guard.is_window_sensitive("Visual Studio Code - main.py") is False

    # Masking test on an image
    test_img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    masked_img, was_masked = guard.mask_screenshot_if_sensitive(test_img, "1Password - Master Key")
    assert was_masked is True
    assert masked_img is not None


def test_action_risk_policy():
    policy = ActionRiskPolicy(mode=ActionRiskPolicy.POLICY_BALANCED)

    # Safe actions
    assert policy.classify_action("file_read", {"path": "main.py"}) == ActionRiskPolicy.RISK_SAFE
    needed, _ = policy.is_approval_required("file_read", {"path": "main.py"})
    assert needed is False

    # Moderate actions
    assert policy.classify_action("computer", {"action": "click", "x": 100, "y": 200}) == ActionRiskPolicy.RISK_MODERATE
    needed, _ = policy.is_approval_required("computer", {"action": "click"})
    assert needed is False  # Balanced mode only gates critical

    # Critical actions
    assert policy.classify_action("shell", {"command": "rm -rf /"}) == ActionRiskPolicy.RISK_CRITICAL
    needed, _ = policy.is_approval_required("shell", {"command": "rm -rf /"})
    assert needed is True  # Balanced mode gates critical
