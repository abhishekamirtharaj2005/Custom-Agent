"""FastAPI Dashboard Application for Hermclaw.

Exposes the REST API and serves the Single-Page Application (SPA) frontend.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from hermclaw.dashboard.service import DashboardService


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model: Optional[str] = None


class SwitchModelRequest(BaseModel):
    model: str


class ApiKeysSaveRequest(BaseModel):
    keys: dict[str, str]


class EngineConfigSaveRequest(BaseModel):
    provider: str
    model_name: str
    api_key: Optional[str] = None
    set_active: bool = False


class DeleteModelRequest(BaseModel):
    provider: str
    model_name: str


class ClearKeyRequest(BaseModel):
    provider: str


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class ConfigSaveRequest(BaseModel):
    yaml_content: str


class AddConceptRequest(BaseModel):
    name: str
    category: str = "general"
    description: str = ""
    confidence: float = 0.5


class AddRelationshipRequest(BaseModel):
    source_name: str
    target_name: str
    relation_type: str = "related_to"
    strength: float = 0.5


class MemorySaveRequest(BaseModel):
    content: str


class AddKanbanTaskRequest(BaseModel):
    board_id: str
    column_name: str = "Backlog"
    title: str
    description: str = ""
    priority: str = "medium"


class MoveKanbanTaskRequest(BaseModel):
    task_id: str
    column_name: str


class AddTodoRequest(BaseModel):
    text: str
    priority: str = "medium"


class ToggleTodoRequest(BaseModel):
    done: bool


class CreateGoalRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"


class UpdateGoalProgressRequest(BaseModel):
    progress: int
    log_entry: str = ""


class PetActionRequest(BaseModel):
    action: str  # feed, play, rest


class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}


def create_dashboard_app(
    config_path: Optional[Path] = None,
    profile: str = "default",
    service: Optional[DashboardService] = None,
) -> FastAPI:
    """Create and configure the FastAPI dashboard application."""
    app = FastAPI(title="Hermclaw Web Dashboard", version="1.0.0")
    svc = service or DashboardService(config_path=config_path, profile=profile)

    # Enable CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_no_cache_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    static_dir = Path(__file__).parent / "static"

    # ------------------------------------------------------------------
    # Overview & Diagnostics API
    # ------------------------------------------------------------------

    @app.get("/api/overview")
    async def get_overview() -> dict[str, Any]:
        return await svc.get_overview()

    @app.get("/api/system")
    async def get_system() -> dict[str, Any]:
        return svc.get_system_metrics()

    @app.get("/api/doctor")
    async def get_doctor() -> dict[str, Any]:
        return await svc.run_diagnostics()

    @app.get("/api/config")
    async def get_config() -> dict[str, Any]:
        return {
            "redacted": svc.get_config(),
            "raw_yaml": svc.get_raw_config_text(),
        }

    @app.post("/api/config")
    async def post_config(req: ConfigSaveRequest) -> dict[str, Any]:
        ok, errors = svc.save_raw_config_text(req.yaml_content)
        if not ok:
            return {"accepted": False, "errors": errors}
        # Reload runtime
        await svc.reload_runtime()
        return {"accepted": True, "errors": []}

    # ------------------------------------------------------------------
    # Cloud LLM API Keys & Provider Settings
    # ------------------------------------------------------------------

    @app.get("/api/settings/keys")
    async def get_settings_keys() -> list[dict[str, Any]]:
        return svc.get_api_keys_status()

    @app.post("/api/settings/keys")
    async def save_settings_keys(req: ApiKeysSaveRequest) -> dict[str, Any]:
        ok, msg = svc.save_api_keys(req.keys)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}

    @app.get("/api/models")
    async def get_models() -> list[dict[str, Any]]:
        return await svc.get_available_models()

    @app.post("/api/chat/switch-model")
    async def switch_model(req: SwitchModelRequest) -> dict[str, Any]:
        try:
            return await svc.switch_model(req.model)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/engine/save")
    async def save_engine_config(req: EngineConfigSaveRequest) -> dict[str, Any]:
        ok, msg = svc.save_engine_config(
            provider=req.provider,
            model_name=req.model_name,
            api_key=req.api_key,
            set_active=req.set_active,
        )
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}

    @app.get("/api/engine/saved-models")
    async def get_engine_saved_models() -> list[dict[str, Any]]:
        return await svc.get_saved_models_list()

    @app.post("/api/engine/clear-key")
    async def clear_engine_key(req: ClearKeyRequest) -> dict[str, Any]:
        ok, msg = svc.clear_provider_key(req.provider)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}

    @app.post("/api/engine/delete-model")
    async def delete_engine_model(req: DeleteModelRequest) -> dict[str, Any]:
        ok, msg = svc.delete_saved_model(req.provider, req.model_name)
        if not ok:
            raise HTTPException(status_code=400, detail=msg)
        return {"success": True, "message": msg}

    # ------------------------------------------------------------------
    # Chat & Sessions API
    # ------------------------------------------------------------------

    @app.get("/api/sessions")
    async def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
        return await svc.list_sessions(limit=limit)

    @app.post("/api/sessions")
    async def create_session(req: CreateSessionRequest) -> dict[str, str]:
        sid = await svc.create_session(title=req.title)
        return {"session_id": sid}

    @app.get("/api/sessions/{session_id}")
    async def get_session_messages(session_id: str) -> list[dict[str, Any]]:
        return await svc.get_session_messages(session_id)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, bool]:
        ok = await svc.delete_session(session_id)
        return {"deleted": ok}

    @app.post("/api/chat")
    async def post_chat(req: ChatRequest) -> dict[str, Any]:
        try:
            return await svc.send_message(req.session_id, req.message, model=req.model)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))


    # ------------------------------------------------------------------
    # Skills & Reflection API
    # ------------------------------------------------------------------

    @app.get("/api/skills")
    async def list_skills() -> list[dict[str, Any]]:
        return svc.get_skills()

    @app.post("/api/skills/validate")
    async def validate_skills() -> list[dict[str, Any]]:
        return svc.validate_skills()

    @app.post("/api/reflect")
    async def trigger_reflection() -> dict[str, Any]:
        return await svc.trigger_reflection()

    # ------------------------------------------------------------------
    # Learning Graph API
    # ------------------------------------------------------------------

    @app.get("/api/learning-graph")
    async def get_learning_graph() -> dict[str, Any]:
        return svc.get_learning_graph_data()

    @app.post("/api/learning-graph/concept")
    async def add_concept(req: AddConceptRequest) -> dict[str, Any]:
        cid = svc.add_learning_concept(req.name, req.category, req.description, req.confidence)
        return {"id": cid, "name": req.name}

    @app.post("/api/learning-graph/relationship")
    async def add_relationship(req: AddRelationshipRequest) -> dict[str, Any]:
        rid = svc.add_learning_relationship(req.source_name, req.target_name, req.relation_type, req.strength)
        return {"id": rid}

    # ------------------------------------------------------------------
    # Memory & Identity API
    # ------------------------------------------------------------------

    @app.get("/api/memory/{file_type}")
    async def get_memory_file(file_type: str) -> dict[str, str]:
        content = svc.get_identity_file(file_type)
        return {"file_type": file_type, "content": content}

    @app.post("/api/memory/{file_type}")
    async def save_memory_file(file_type: str, req: MemorySaveRequest) -> dict[str, bool]:
        ok = svc.save_identity_file(file_type, req.content)
        return {"saved": ok}

    @app.get("/api/vector-memory/search")
    async def search_vector_memory(q: str = "", limit: int = 10) -> list[dict[str, Any]]:
        if not q:
            return []
        return await svc.search_vector_memory(q, limit=limit)

    # ------------------------------------------------------------------
    # Tasks & Goals API
    # ------------------------------------------------------------------

    @app.get("/api/kanban")
    async def get_kanban(board_id: Optional[str] = None) -> dict[str, Any]:
        return svc.get_kanban_board(board_id)

    @app.post("/api/kanban/tasks")
    async def add_kanban_task(req: AddKanbanTaskRequest) -> dict[str, str]:
        tid = svc.add_kanban_task(req.board_id, req.column_name, req.title, req.description, req.priority)
        return {"task_id": tid}

    @app.post("/api/kanban/move")
    async def move_kanban_task(req: MoveKanbanTaskRequest) -> dict[str, bool]:
        ok = svc.move_kanban_task(req.task_id, req.column_name)
        return {"moved": ok}

    @app.delete("/api/kanban/tasks/{task_id}")
    async def delete_kanban_task(task_id: str) -> dict[str, bool]:
        ok = svc.delete_kanban_task(task_id)
        return {"deleted": ok}

    @app.get("/api/todos")
    async def get_todos(show_done: bool = True) -> list[dict[str, Any]]:
        return svc.get_todos(show_done=show_done)

    @app.post("/api/todos")
    async def add_todo(req: AddTodoRequest) -> dict[str, str]:
        tid = svc.add_todo(req.text, req.priority)
        return {"todo_id": tid}

    @app.post("/api/todos/{todo_id}/toggle")
    async def toggle_todo(todo_id: str, req: ToggleTodoRequest) -> dict[str, bool]:
        ok = svc.toggle_todo(todo_id, req.done)
        return {"updated": ok}

    @app.delete("/api/todos/{todo_id}")
    async def delete_todo(todo_id: str) -> dict[str, bool]:
        ok = svc.delete_todo(todo_id)
        return {"deleted": ok}

    @app.get("/api/goals")
    async def list_goals(status: str = "all") -> list[dict[str, Any]]:
        return svc.list_goals(status=status)

    @app.post("/api/goals")
    async def create_goal(req: CreateGoalRequest) -> dict[str, str]:
        gid = svc.create_goal(req.title, req.description, req.priority)
        return {"goal_id": gid}

    @app.post("/api/goals/{goal_id}/progress")
    async def update_goal_progress(goal_id: str, req: UpdateGoalProgressRequest) -> dict[str, bool]:
        ok = svc.update_goal_progress(goal_id, req.progress, req.log_entry)
        return {"updated": ok}

    @app.delete("/api/goals/{goal_id}")
    async def delete_goal(goal_id: str) -> dict[str, bool]:
        ok = svc.delete_goal(goal_id)
        return {"deleted": ok}

    # ------------------------------------------------------------------
    # Pet & Achievements API
    # ------------------------------------------------------------------

    @app.get("/api/pet")
    async def get_pet() -> dict[str, Any]:
        return svc.get_pet()

    @app.post("/api/pet/action")
    async def pet_action(req: PetActionRequest) -> dict[str, Any]:
        return svc.pet_action(req.action)

    @app.get("/api/achievements")
    async def get_achievements() -> list[dict[str, Any]]:
        return svc.get_achievements()

    # ------------------------------------------------------------------
    # Tools Catalog & Playground API
    # ------------------------------------------------------------------

    @app.get("/api/tools")
    async def get_tools() -> list[dict[str, Any]]:
        return await svc.get_tools_catalog()

    @app.post("/api/tools/execute")
    async def execute_tool(req: ToolExecuteRequest) -> dict[str, Any]:
        return await svc.execute_tool_playground(req.tool_name, req.arguments)

    # ------------------------------------------------------------------
    # Frontend SPA Serving
    # ------------------------------------------------------------------

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        index_file = static_dir / "index.html"
        if not index_file.exists():
            return HTMLResponse("<h1>Hermclaw Dashboard: index.html not found</h1>", status_code=404)
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    return app
