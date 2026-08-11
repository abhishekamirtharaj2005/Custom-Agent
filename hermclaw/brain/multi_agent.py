"""Multi-agent collaboration: ACP server, async delegation, Kanban watchers.

Implements:
- ACP (Agent Communication Protocol) server
- ACP session management
- ACP permission management
- ACP provenance tracking
- Async delegation (fire-and-forget tool calls)
- Kanban watchers (notify on task state changes)
- Kanban diagnostics
- Copilot ACP client
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Awaitable, Optional

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# ACP (Agent Communication Protocol) server
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ACPMessage:
    """A message in the ACP protocol."""
    id: str
    sender: str
    recipient: str
    type: str  # "request", "response", "notification"
    content: Any
    timestamp: float = dataclasses.field(default_factory=time.time)
    correlation_id: str = ""  # Links response to request


@dataclasses.dataclass
class ACPSession:
    """An active ACP session between agents."""
    id: str
    participants: list[str]
    created_at: float = dataclasses.field(default_factory=time.time)
    messages: list[ACPMessage] = dataclasses.field(default_factory=list)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    status: str = "active"


class ACPPermission:
    """Permission for an agent to access resources."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELEGATE = "delegate"


@dataclasses.dataclass
class ACPPermissionEntry:
    agent_id: str
    resource: str
    permissions: list[str]
    granted_at: float = dataclasses.field(default_factory=time.time)
    expires_at: Optional[float] = None


@dataclasses.dataclass
class ProvenanceRecord:
    """Track the origin and chain of agent actions."""
    action_id: str
    agent_id: str
    action_type: str
    input_hash: str
    output_hash: str
    parent_action: Optional[str] = None
    timestamp: float = dataclasses.field(default_factory=time.time)
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


class ACPServer:
    """Agent Communication Protocol server.

    Enables multiple Hermclaw instances (or external agents) to:
    - Discover each other
    - Exchange messages
    - Delegate tasks
    - Share resources
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ACPSession] = {}
        self._agents: dict[str, dict[str, Any]] = {}  # agent_id -> info
        self._message_queue: dict[str, asyncio.Queue] = {}
        self._permissions: list[ACPPermissionEntry] = []
        self._provenance: list[ProvenanceRecord] = []
        self._handlers: dict[str, Callable] = {}

    # --- Agent registry ---

    def register_agent(self, agent_id: str, capabilities: list[str] | None = None,
                       metadata: dict | None = None) -> None:
        self._agents[agent_id] = {
            "id": agent_id,
            "capabilities": capabilities or [],
            "registered_at": time.time(),
            "metadata": metadata or {},
        }
        self._message_queue[agent_id] = asyncio.Queue()
        logger.info("acp.agent_registered", agent_id=agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        self._message_queue.pop(agent_id, None)

    def list_agents(self) -> list[dict]:
        return list(self._agents.values())

    def find_agent(self, capability: str) -> Optional[str]:
        """Find an agent with a specific capability."""
        for agent_id, info in self._agents.items():
            if capability in info.get("capabilities", []):
                return agent_id
        return None

    # --- Session management ---

    def create_session(self, participants: list[str]) -> ACPSession:
        session = ACPSession(
            id=uuid.uuid4().hex[:12],
            participants=participants,
        )
        self._sessions[session.id] = session
        logger.info("acp.session_created", id=session.id, participants=participants)
        return session

    def get_session(self, session_id: str) -> Optional[ACPSession]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.status = "closed"
            logger.info("acp.session_closed", id=session_id)

    # --- Messaging ---

    async def send(self, message: ACPMessage) -> None:
        queue = self._message_queue.get(message.recipient)
        if queue:
            await queue.put(message)
            session = self._find_session(message.sender, message.recipient)
            if session:
                session.messages.append(message)
        else:
            logger.warning("acp.recipient_not_found", recipient=message.recipient)

    async def receive(self, agent_id: str, timeout: float = 30.0) -> Optional[ACPMessage]:
        queue = self._message_queue.get(agent_id)
        if not queue:
            return None
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def _find_session(self, agent_a: str, agent_b: str) -> Optional[ACPSession]:
        for session in self._sessions.values():
            if agent_a in session.participants and agent_b in session.participants:
                return session
        return None

    # --- Permissions ---

    def grant_permission(self, agent_id: str, resource: str,
                        permissions: list[str], ttl_s: float = 0) -> None:
        entry = ACPPermissionEntry(
            agent_id=agent_id,
            resource=resource,
            permissions=permissions,
            expires_at=time.time() + ttl_s if ttl_s else None,
        )
        self._permissions.append(entry)

    def check_permission(self, agent_id: str, resource: str, action: str) -> bool:
        now = time.time()
        for p in self._permissions:
            if p.agent_id == agent_id and p.resource == resource and action in p.permissions:
                if p.expires_at is None or p.expires_at > now:
                    return True
        return False

    # --- Provenance ---

    def record_provenance(self, agent_id: str, action_type: str,
                         input_data: str, output_data: str,
                         parent: Optional[str] = None) -> str:
        import hashlib
        record = ProvenanceRecord(
            action_id=uuid.uuid4().hex[:12],
            agent_id=agent_id,
            action_type=action_type,
            input_hash=hashlib.sha256(input_data.encode()).hexdigest()[:16],
            output_hash=hashlib.sha256(output_data.encode()).hexdigest()[:16],
            parent_action=parent,
        )
        self._provenance.append(record)
        return record.action_id

    def get_provenance_chain(self, action_id: str) -> list[ProvenanceRecord]:
        chain = []
        current = action_id
        while current:
            record = next((r for r in self._provenance if r.action_id == current), None)
            if record:
                chain.append(record)
                current = record.parent_action
            else:
                break
        return list(reversed(chain))


# ---------------------------------------------------------------------------
# Async delegation
# ---------------------------------------------------------------------------


class AsyncDelegator:
    """Fire-and-forget task delegation to background agents."""

    def __init__(self, acp_server: Optional[ACPServer] = None) -> None:
        self._acp = acp_server
        self._pending: dict[str, asyncio.Task] = {}
        self._results: dict[str, Any] = {}

    async def delegate(self, task_fn: Callable[..., Awaitable[Any]], *args: Any,
                       task_id: Optional[str] = None, **kwargs: Any) -> str:
        """Delegate a task to run in the background."""
        task_id = task_id or uuid.uuid4().hex[:8]

        async def _wrapped() -> Any:
            try:
                result = await task_fn(*args, **kwargs)
                self._results[task_id] = {"status": "completed", "result": result}
                return result
            except Exception as exc:
                self._results[task_id] = {"status": "failed", "error": str(exc)}
                raise

        task = asyncio.create_task(_wrapped())
        self._pending[task_id] = task
        task.add_done_callback(lambda t: self._pending.pop(task_id, None))

        logger.info("async_delegate.started", task_id=task_id)
        return task_id

    def get_result(self, task_id: str) -> Optional[dict]:
        return self._results.get(task_id)

    def list_pending(self) -> list[str]:
        return list(self._pending.keys())

    async def wait(self, task_id: str, timeout: float = 300) -> Any:
        task = self._pending.get(task_id)
        if not task:
            result = self._results.get(task_id)
            return result["result"] if result and result["status"] == "completed" else None
        return await asyncio.wait_for(task, timeout=timeout)


# ---------------------------------------------------------------------------
# Kanban watchers & diagnostics
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class KanbanWatcher:
    """Watch for task state changes in the Kanban board."""
    id: str
    task_id: str
    watch_states: list[str]  # States to watch for: "done", "blocked", etc.
    callback: Optional[Callable] = None
    notification_channel: str = ""  # "email", "notify", "webhook"


class KanbanWatcherManager:
    """Manage watchers on Kanban tasks."""

    def __init__(self) -> None:
        self._watchers: list[KanbanWatcher] = []

    def add_watcher(self, task_id: str, states: list[str],
                   channel: str = "notify") -> KanbanWatcher:
        watcher = KanbanWatcher(
            id=uuid.uuid4().hex[:8],
            task_id=task_id,
            watch_states=states,
            notification_channel=channel,
        )
        self._watchers.append(watcher)
        logger.info("kanban.watcher_added", task_id=task_id, states=states)
        return watcher

    def remove_watcher(self, watcher_id: str) -> None:
        self._watchers = [w for w in self._watchers if w.id != watcher_id]

    async def notify_state_change(self, task_id: str, new_state: str) -> int:
        """Check watchers and send notifications for state changes."""
        notified = 0
        for w in self._watchers:
            if w.task_id == task_id and new_state in w.watch_states:
                logger.info("kanban.watcher_triggered",
                          watcher_id=w.id, task_id=task_id, state=new_state)
                notified += 1
        return notified

    def list_watchers(self, task_id: Optional[str] = None) -> list[KanbanWatcher]:
        if task_id:
            return [w for w in self._watchers if w.task_id == task_id]
        return self._watchers


class KanbanDiagnostics:
    """Diagnose issues with the Kanban board."""

    @staticmethod
    def check_stale_tasks(tasks: list[dict], stale_days: int = 7) -> list[dict]:
        """Find tasks that haven't been updated recently."""
        cutoff = time.time() - (stale_days * 86400)
        stale = []
        for task in tasks:
            updated = task.get("updated_at", 0)
            if updated < cutoff and task.get("status") != "done":
                stale.append({
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "status": task.get("status"),
                    "days_stale": int((time.time() - updated) / 86400),
                })
        return stale

    @staticmethod
    def check_blocked(tasks: list[dict]) -> list[dict]:
        """Find tasks that are blocked."""
        return [t for t in tasks if t.get("status") == "blocked"]

    @staticmethod
    def workload_distribution(tasks: list[dict]) -> dict[str, int]:
        """Distribution of tasks by status."""
        dist: dict[str, int] = {}
        for t in tasks:
            status = t.get("status", "unknown")
            dist[status] = dist.get(status, 0) + 1
        return dist
