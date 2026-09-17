"""Autonomous Multi-Agent Swarm: role-specialized subagent orchestration.

Provides:
- Specialist Personas:
  - researcher: Web search, docs, paper analysis, literature synthesis.
  - coder: Code execution sandbox, file editing, git control, test execution.
  - desktop_operator: GUI navigation, live screen vision, mouse/keyboard actions.
  - reviewer: Quality audit, security review, syntax validation, synthesis.
- SwarmOrchestrator: Coordinates multi-specialist pipelines to solve complex tasks.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Any, Callable, Coroutine, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class SpecialistPersona:
    role: str
    title: str
    description: str
    system_prompt: str
    preferred_tools: list[str]


SPECIALIST_PERSONAS: dict[str, SpecialistPersona] = {
    "researcher": SpecialistPersona(
        role="researcher",
        title="Senior Research & Intelligence Analyst",
        description="Deep search, web crawling, documentation discovery, and data synthesis.",
        system_prompt=(
            "You are the RESEARCHER in an autonomous multi-agent swarm. "
            "Your objective: Thoroughly investigate the user's objective, search documentation, "
            "gather technical facts, analyze source materials, and produce structured findings."
        ),
        preferred_tools=["web_search", "url_read", "pdf_read", "session_search", "knowledge_vault"],
    ),
    "coder": SpecialistPersona(
        role="coder",
        title="Principal Software Engineer",
        description="Software development, code sandbox execution, file manipulation, and debugging.",
        system_prompt=(
            "You are the CODER in an autonomous multi-agent swarm. "
            "Your objective: Implement robust, production-grade code, edit files accurately, "
            "run sandbox tests, debug errors, and ensure functional correctness."
        ),
        preferred_tools=["code_exec", "file_read", "file_write", "file_edit", "shell", "git", "patch"],
    ),
    "desktop_operator": SpecialistPersona(
        role="desktop_operator",
        title="Desktop Automation & GUI Specialist",
        description="Live screen inspection, window navigation, app launching, mouse and keyboard control.",
        system_prompt=(
            "You are the DESKTOP OPERATOR in an autonomous multi-agent swarm. "
            "Your objective: Control the desktop environment, inspect visible windows, click UI controls, "
            "launch desktop applications, and type or paste inputs reliably."
        ),
        preferred_tools=["computer", "screen_vision", "app_launcher", "clipboard"],
    ),
    "reviewer": SpecialistPersona(
        role="reviewer",
        title="Staff Quality & Security Auditor",
        description="Code review, verification, safety validation, and final executive synthesis.",
        system_prompt=(
            "You are the REVIEWER in an autonomous multi-agent swarm. "
            "Your objective: Audit all outputs for safety, accuracy, edge cases, and completeness. "
            "Synthesize the swarm's collective findings into a crisp, authoritative delivery."
        ),
        preferred_tools=["file_read", "code_exec", "system_info"],
    ),
}


class SwarmOrchestrator:
    """Orchestrates sequential or parallel specialist subagent pipelines."""

    def __init__(
        self,
        agent_executor: Optional[Callable[[str, list[str]], Coroutine[Any, Any, str]]] = None,
    ) -> None:
        """agent_executor: async function(prompt, preferred_tools) -> response_text"""
        self._executor = agent_executor

    def list_roles(self) -> list[dict[str, Any]]:
        """Return all available specialist personas."""
        return [
            {
                "role": p.role,
                "title": p.title,
                "description": p.description,
                "preferred_tools": p.preferred_tools,
            }
            for p in SPECIALIST_PERSONAS.values()
        ]

    async def execute_swarm_pipeline(
        self,
        task: str,
        roles: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Execute a coordinated swarm pipeline across assigned roles."""
        assigned_roles = roles or ["researcher", "coder", "reviewer"]
        pipeline_log: list[dict[str, Any]] = []
        cumulative_context = f"Original Overall Goal: {task}\n"

        logger.info("swarm.pipeline_started", task=task[:60], roles=assigned_roles)
        start_time = time.time()

        for role_key in assigned_roles:
            persona = SPECIALIST_PERSONAS.get(role_key.lower())
            if not persona:
                continue

            role_prompt = (
                f"{persona.system_prompt}\n\n"
                f"=== Swarm Context So Far ===\n{cumulative_context}\n\n"
                f"Your specific duty as {persona.title}: Advance the goal with your specialized toolset. "
                f"Provide concise, actionable results."
            )

            step_start = time.time()
            if self._executor:
                try:
                    result_text = await self._executor(role_prompt, persona.preferred_tools)
                except Exception as exc:
                    result_text = f"Specialist {role_key} encountered an execution error: {exc}"
            else:
                # Simulated coordination when executor is stubbed
                result_text = (
                    f"[{persona.title}] analyzed task '{task[:40]}...'. "
                    f"Prepared operational plan using tools: {', '.join(persona.preferred_tools)}."
                )

            step_duration = round(time.time() - step_start, 2)
            pipeline_log.append({
                "role": persona.role,
                "title": persona.title,
                "output": result_text,
                "duration_seconds": step_duration,
            })
            cumulative_context += f"\n--- [{persona.title} Output] ---\n{result_text}\n"

        total_duration = round(time.time() - start_time, 2)
        return {
            "task": task,
            "roles_executed": assigned_roles,
            "total_duration_seconds": total_duration,
            "steps": pipeline_log,
            "final_synthesis": pipeline_log[-1]["output"] if pipeline_log else "No output.",
        }
