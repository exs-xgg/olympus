"""FastAPI router — all REST endpoints for Olympus."""

import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent

from models.database import get_db, TaskModel, TaskStatus, ActionLogModel, MCPServerModel, AgentProfileModel, ChatMessageModel
from models.schemas import (
    TaskCreate, TaskResponse, TaskResumeRequest, TaskRejectRequest,
    AgentStatus, ActionLogResponse, MCPServerCreate, MCPServerResponse,
    InterventionAuditResponse, AgentProfileCreate, AgentProfileResponse,
    AgentChatRequest, AgentChatResponse, AgentChatMessageResponse,
)
from orchestrator.graph import compile_graph, AGENT_REGISTRY
from orchestrator.websocket import ws_manager
from agents.coding_agent import create_coding_agent
from agents.reviewer_agent import create_reviewer_agent
from agents.workflow_agent import create_workflow_agent
from agents.tools import (
    run_shell_command,
    read_file,
    write_file,
    list_directory,
    apply_text_patch,
    git_status,
    git_diff,
    run_tests,
    run_lint,
)
from llm_factory import create_chat_model
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
_service_started_at = datetime.now(timezone.utc)
settings = get_settings()

# Compiled graph (singleton, initialized on first use)
_graph = None
_chat_tool_registry = {
    "run_shell_command": run_shell_command,
    "read_file": read_file,
    "write_file": write_file,
    "apply_text_patch": apply_text_patch,
    "list_directory": list_directory,
    "git_status": git_status,
    "git_diff": git_diff,
    "run_tests": run_tests,
    "run_lint": run_lint,
}


def get_graph():
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph


def _build_chat_agent(agent_name: str, profile: AgentProfileModel | None = None):
    if agent_name == "CodingAgent":
        return create_coding_agent()
    if agent_name == "ReviewerAgent":
        return create_reviewer_agent()
    if agent_name == "WorkflowAgent":
        return create_workflow_agent()
    if profile is None:
        return None

    llm = create_chat_model(
        model=profile.model or settings.agent_model,
        temperature=float(profile.temperature or settings.agent_temperature),
        api_key=settings.openai_api_key,
    )
    tools = [_chat_tool_registry[name] for name in (profile.tools_json or []) if name in _chat_tool_registry]
    return create_react_agent(
        llm,
        tools=tools,
        state_modifier=profile.system_prompt,
    )


def _looks_like_review_request(text: str) -> bool:
    keywords = (
        "review", "audit", "security", "vulnerability", "lint", "test",
        "qa", "quality", "bug hunt", "code smell",
    )
    return any(token in text for token in keywords)


def _looks_like_coding_request(text: str) -> bool:
    keywords = (
        "implement", "build", "create", "write", "fix", "refactor",
        "debug", "code", "function", "endpoint", "component", "script",
    )
    return any(token in text for token in keywords)


def _looks_like_planning_request(text: str) -> bool:
    keywords = (
        "plan", "strategy", "design", "architecture", "break down",
        "steps", "approach", "roadmap", "decompose",
    )
    return any(token in text for token in keywords)


def _matches_custom_agent(text: str, profile: AgentProfileModel) -> bool:
    name_tokens = [token for token in profile.name.lower().replace("-", " ").replace("_", " ").split() if len(token) > 2]
    role_tokens = [token for token in profile.role.lower().replace("-", " ").replace("/", " ").split() if len(token) > 4]
    candidate_tokens = list(dict.fromkeys(name_tokens + role_tokens[:8]))
    return any(token in text for token in candidate_tokens)


async def _resolve_chat_target(
    requested_agent: str,
    message: str,
    db: AsyncSession,
) -> tuple[str, AgentProfileModel | None]:
    normalized_agent = (requested_agent or "").strip()
    if normalized_agent and normalized_agent.lower() != "auto":
        if normalized_agent in AGENT_REGISTRY:
            return normalized_agent, None
        row = await db.execute(select(AgentProfileModel).where(AgentProfileModel.name == normalized_agent))
        profile = row.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail=f"Agent '{normalized_agent}' not found")
        return normalized_agent, profile

    text = (message or "").lower()
    profile_rows = (await db.execute(
        select(AgentProfileModel).order_by(AgentProfileModel.created_at.desc())
    )).scalars().all()
    for row in profile_rows:
        if _matches_custom_agent(text, row):
            return row.name, row

    if _looks_like_review_request(text):
        return "ReviewerAgent", None
    if _looks_like_planning_request(text):
        return "WorkflowAgent", None
    if _looks_like_coding_request(text):
        return "CodingAgent", None
    return "WorkflowAgent", None


def _row_to_langchain_message(row: ChatMessageModel):
    content = row.content or ""
    if row.role == "user":
        return HumanMessage(content=content)
    if row.role == "agent":
        # Keep source agent visible for better multi-agent context in auto mode.
        if row.agent_name:
            return AIMessage(content=f"[{row.agent_name}] {content}")
        return AIMessage(content=content)
    return AIMessage(content=f"[System] {content}")


# Track active agents
_agent_tasks: dict[str, str] = {}  # agent_name -> task_id


def _message_to_text(message) -> str:
    """Normalize LangChain message content for logging."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


async def _log_action(db: AsyncSession, task_id: str, action: str, agent_name: str = None, detail: str = None):
    """Log an action to the database and broadcast via WebSocket."""
    log = ActionLogModel(
        id=str(uuid.uuid4()),
        task_id=task_id,
        agent_name=agent_name,
        action=action,
        detail=detail,
    )
    db.add(log)
    await db.commit()
    await ws_manager.broadcast_log({
        "task_id": task_id,
        "agent_name": agent_name,
        "action": action,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _run_task_in_background(task_id: str, description: str):
    """Execute a task through the LangGraph supervisor in a background thread."""
    from models.database import async_session_factory

    graph = get_graph()
    thread_id = f"task-{task_id}"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 100,
    }

    initial_state = {
        "messages": [HumanMessage(content=f"Execute this task: {description}")],
        "task_id": task_id,
        "task_description": description,
        "current_agent": "supervisor",
        "status": "running",
        "plan": "",
        "results": [],
        "needs_human": False,
        "human_question": "",
        "iteration_count": 0,
        "reviewer_approved": False,
        "pending_action": {},
        "approval_status": "not_required",
        "github_repo_created": False,
    }

    async with async_session_factory() as db:
        # Update task to running
        await db.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(status=TaskStatus.RUNNING, thread_id=thread_id)
        )
        await db.commit()
        await _log_action(db, task_id, "task_started", detail="Task execution started")
        await ws_manager.broadcast_task_update({
            "id": task_id, "status": "running", "assigned_agent": "supervisor"
        })

        try:
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            def _stream_graph_updates():
                latest_state_local = {}
                try:
                    for chunk in graph.stream(initial_state, config, stream_mode="updates"):
                        if isinstance(chunk, dict):
                            for update_data in chunk.values():
                                if isinstance(update_data, dict):
                                    latest_state_local.update(update_data)
                        loop.call_soon_threadsafe(queue.put_nowait, {"kind": "chunk", "payload": chunk})
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"kind": "result", "payload": latest_state_local},
                    )
                except Exception as exc:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"kind": "error", "payload": str(exc)},
                    )
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, {"kind": "done"})

            worker = asyncio.create_task(asyncio.to_thread(_stream_graph_updates))
            latest_state = {}
            while True:
                item = await queue.get()
                kind = item.get("kind")
                if kind == "done":
                    break
                if kind == "error":
                    raise RuntimeError(item.get("payload", "Unknown graph stream error"))
                if kind == "result":
                    latest_state = item.get("payload") or {}
                    continue
                if kind != "chunk":
                    continue
                chunk = item.get("payload")
                if not isinstance(chunk, dict):
                    continue
                for node_name, update_data in chunk.items():
                    if not isinstance(update_data, dict):
                        continue
                    current_agent = update_data.get("current_agent") or node_name
                    await _log_action(
                        db,
                        task_id,
                        "progress_step",
                        agent_name=current_agent,
                        detail=f"{node_name} completed a graph step",
                    )
                    await db.execute(
                        update(TaskModel)
                        .where(TaskModel.id == task_id)
                        .values(assigned_agent=current_agent)
                    )
                    await db.commit()
                    await ws_manager.broadcast_task_update({
                        "id": task_id,
                        "assigned_agent": current_agent,
                        "status": "running",
                    })

                    messages = update_data.get("messages") or []
                    if messages:
                        latest_message = messages[-1]
                        message_text = _message_to_text(latest_message)
                        if message_text:
                            await _log_action(
                                db,
                                task_id,
                                "agent_output",
                                agent_name=current_agent,
                                detail=message_text[:8000],
                            )
            await worker

            result = latest_state or graph.get_state(config).values
            final_status = result.get("status", "completed")

            if final_status == "waiting_for_human":
                # Graph hit an interrupt — task is paused
                question = result.get("human_question", "Human input required")
                pending_action = result.get("pending_action") or {}
                approval_status = result.get("approval_status", "pending")
                await db.execute(
                    update(TaskModel)
                    .where(TaskModel.id == task_id)
                    .values(
                        status=TaskStatus.WAITING_FOR_HUMAN,
                        assigned_agent=result.get("current_agent", "supervisor"),
                        human_input_request=question,
                        metadata_json={
                            "pending_action": pending_action,
                            "approval_status": approval_status,
                        },
                    )
                )
                await db.commit()
                await _log_action(db, task_id, "hitl_triggered", detail=question)
                await ws_manager.broadcast_task_update({
                    "id": task_id, "status": "waiting_for_human",
                    "human_input_request": question,
                })
                await ws_manager.broadcast_hitl_request({
                    "task_id": task_id,
                    "question": question,
                    "pending_action": pending_action,
                    "approval_status": approval_status,
                })
            else:
                # Check if graph was interrupted (for HITL)
                # LangGraph returns partial state when interrupted
                snapshot = graph.get_state(config)
                if snapshot.next:
                    # Graph is paused at an interrupt point
                    state_values = snapshot.values
                    question = state_values.get("human_question", "Human input required")
                    pending_action = state_values.get("pending_action") or {}
                    approval_status = state_values.get("approval_status", "pending")
                    await db.execute(
                        update(TaskModel)
                        .where(TaskModel.id == task_id)
                        .values(
                            status=TaskStatus.WAITING_FOR_HUMAN,
                            assigned_agent=state_values.get("current_agent", "supervisor"),
                            human_input_request=question,
                            metadata_json={
                                "pending_action": pending_action,
                                "approval_status": approval_status,
                            },
                        )
                    )
                    await db.commit()
                    await _log_action(db, task_id, "hitl_triggered", detail=question)
                    await ws_manager.broadcast_task_update({
                        "id": task_id, "status": "waiting_for_human",
                        "human_input_request": question,
                    })
                    await ws_manager.broadcast_hitl_request({
                        "task_id": task_id,
                        "question": question,
                        "pending_action": pending_action,
                        "approval_status": approval_status,
                    })
                else:
                    # Task completed
                    final_messages = result.get("messages", [])
                    final_result = final_messages[-1].content if final_messages else "Task completed"
                    await db.execute(
                        update(TaskModel)
                        .where(TaskModel.id == task_id)
                        .values(status=TaskStatus.COMPLETED, result=final_result)
                    )
                    await db.commit()
                    await _log_action(db, task_id, "task_completed", detail="Task finished successfully")
                    await ws_manager.broadcast_task_update({
                        "id": task_id, "status": "completed", "result": final_result,
                    })

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await db.execute(
                update(TaskModel)
                .where(TaskModel.id == task_id)
                .values(status=TaskStatus.FAILED, error=str(e))
            )
            await db.commit()
            await _log_action(db, task_id, "task_failed", detail=str(e))
            await ws_manager.broadcast_task_update({
                "id": task_id, "status": "failed", "error": str(e),
            })


# --- Endpoints ---

@router.post("/tasks", response_model=TaskResponse)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Create a new task and start execution."""
    task = TaskModel(
        id=str(uuid.uuid4()),
        title=body.title,
        description=body.description,
        status=TaskStatus.QUEUED,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    await _log_action(db, task.id, "task_created", detail=f"Task created: {body.title}")
    await ws_manager.broadcast_task_update({
        "id": task.id, "status": "queued", "title": body.title,
    })

    # Start execution in background
    asyncio.create_task(_run_task_in_background(task.id, body.description))

    return task


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all tasks, optionally filtered by status."""
    query = select(TaskModel).order_by(TaskModel.created_at.desc())
    if status:
        query = query.where(TaskModel.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single task by ID."""
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/resume", response_model=TaskResponse)
async def resume_task(
    task_id: str,
    body: TaskResumeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resume a task that's waiting for human input."""
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.WAITING_FOR_HUMAN:
        raise HTTPException(status_code=400, detail=f"Task is not waiting for human input (status: {task.status})")

    resume_payload = {
        "human_input": body.human_input,
        "approval": body.approval.model_dump() if body.approval else None,
    }

    # Store the human response
    task.human_input_response = body.human_input or ""
    task.status = TaskStatus.RUNNING
    await db.commit()

    await _log_action(db, task_id, "human_input_received", detail=str(resume_payload)[:4000])
    await ws_manager.broadcast_task_update({
        "id": task_id, "status": "running",
    })

    # Resume the graph in background
    asyncio.create_task(_resume_task_in_background(task_id, resume_payload, task.thread_id))

    await db.refresh(task)
    return task


async def _resume_task_in_background(task_id: str, human_input, thread_id: str):
    """Resume a paused LangGraph execution with human input."""
    from models.database import async_session_factory

    graph = get_graph()
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 100,
    }

    async with async_session_factory() as db:
        try:
            # Resume graph with human input via Command
            result = await asyncio.to_thread(
                graph.invoke,
                Command(resume=human_input),
                config,
            )

            # Check final state
            snapshot = graph.get_state(config)
            if snapshot.next:
                # Paused again at another interrupt
                state_values = snapshot.values
                question = state_values.get("human_question", "Human input required again")
                pending_action = state_values.get("pending_action") or {}
                approval_status = state_values.get("approval_status", "pending")
                await db.execute(
                    update(TaskModel)
                    .where(TaskModel.id == task_id)
                    .values(
                        status=TaskStatus.WAITING_FOR_HUMAN,
                        human_input_request=question,
                        metadata_json={
                            "pending_action": pending_action,
                            "approval_status": approval_status,
                        },
                    )
                )
                await db.commit()
                await ws_manager.broadcast_task_update({
                    "id": task_id, "status": "waiting_for_human",
                    "human_input_request": question,
                })
                await ws_manager.broadcast_hitl_request({
                    "task_id": task_id,
                    "question": question,
                    "pending_action": pending_action,
                    "approval_status": approval_status,
                })
            else:
                # Completed
                final_messages = result.get("messages", [])
                final_result = final_messages[-1].content if final_messages else "Task completed"
                await db.execute(
                    update(TaskModel)
                    .where(TaskModel.id == task_id)
                    .values(status=TaskStatus.COMPLETED, result=final_result)
                )
                await db.commit()
                await _log_action(db, task_id, "task_completed", detail="Task finished after resume")
                await ws_manager.broadcast_task_update({
                    "id": task_id, "status": "completed", "result": final_result,
                })

        except Exception as e:
            logger.error(f"Task {task_id} failed on resume: {e}", exc_info=True)
            await db.execute(
                update(TaskModel)
                .where(TaskModel.id == task_id)
                .values(status=TaskStatus.FAILED, error=str(e))
            )
            await db.commit()
            await ws_manager.broadcast_task_update({
                "id": task_id, "status": "failed", "error": str(e),
            })


@router.post("/tasks/{task_id}/reject", response_model=TaskResponse)
async def reject_task(
    task_id: str,
    body: TaskRejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reject a task currently waiting for human input."""
    result = await db.execute(select(TaskModel).where(TaskModel.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.WAITING_FOR_HUMAN:
        raise HTTPException(status_code=400, detail=f"Task is not waiting for human input (status: {task.status})")

    task.status = TaskStatus.FAILED
    task.error = f"Rejected by operator: {body.reason}"
    await db.commit()
    await _log_action(db, task_id, "human_input_rejected", detail=body.reason)
    await ws_manager.broadcast_task_update({
        "id": task_id,
        "status": "failed",
        "error": task.error,
    })
    await db.refresh(task)
    return task


@router.get("/tasks/{task_id}/logs", response_model=list[ActionLogResponse])
async def get_task_logs(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get all action logs for a task."""
    result = await db.execute(
        select(ActionLogModel)
        .where(ActionLogModel.task_id == task_id)
        .order_by(ActionLogModel.timestamp.asc())
    )
    return result.scalars().all()


@router.get("/agents/status", response_model=list[AgentStatus])
async def get_agents_status(db: AsyncSession = Depends(get_db)):
    """Get status of all registered agents."""
    action_rows = (await db.execute(select(ActionLogModel))).scalars().all()
    token_estimate = max(1, len(action_rows)) * 120
    uptime_seconds = int((datetime.now(timezone.utc) - _service_started_at).total_seconds())

    agents = []
    for name, info in AGENT_REGISTRY.items():
        agent_logs = [row for row in action_rows if row.agent_name == info["name"]]
        error_count = len([row for row in agent_logs if "failed" in row.action or "error" in row.action])
        tasks_done = len([row for row in agent_logs if row.action == "task_completed"])

        agents.append(AgentStatus(
            name=info["name"],
            role=info["role"],
            status="idle",  # Could be enhanced with real tracking
            capabilities=info["capabilities"],
            tools=info["tools"],
            current_task_id=_agent_tasks.get(name),
            model="gpt-5-mini",
            uptime_seconds=uptime_seconds,
            tokens_used=token_estimate,
            error_count=error_count,
            tasks_done=tasks_done,
        ))

    profile_rows = (await db.execute(
        select(AgentProfileModel).order_by(AgentProfileModel.created_at.desc())
    )).scalars().all()
    for row in profile_rows:
        profile_logs = [log for log in action_rows if log.agent_name == row.name]
        error_count = len([log for log in profile_logs if "failed" in log.action or "error" in log.action])
        tasks_done = len([log for log in profile_logs if log.action == "task_completed"])
        agents.append(AgentStatus(
            name=row.name,
            role=row.role,
            status="idle",
            capabilities=["custom_agent"],
            tools=row.tools_json or [],
            current_task_id=_agent_tasks.get(row.name),
            model=row.model,
            uptime_seconds=uptime_seconds,
            tokens_used=token_estimate,
            error_count=error_count,
            tasks_done=tasks_done,
            temperature=float(row.temperature or 0.2),
            max_tokens=4096,
        ))
    return agents


@router.get("/agents", response_model=list[AgentProfileResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    """List configured custom agents created by operators."""
    rows = (await db.execute(
        select(AgentProfileModel).order_by(AgentProfileModel.created_at.desc())
    )).scalars().all()
    return [
        AgentProfileResponse(
            id=row.id,
            name=row.name,
            role=row.role,
            system_prompt=row.system_prompt,
            model=row.model,
            temperature=float(row.temperature or 0.2),
            tools=row.tools_json or [],
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.post("/agents", response_model=AgentProfileResponse)
async def create_agent(body: AgentProfileCreate, db: AsyncSession = Depends(get_db)):
    """Create and persist a custom agent profile from the UI."""
    existing = await db.execute(select(AgentProfileModel).where(AgentProfileModel.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent with this name already exists")

    row = AgentProfileModel(
        id=str(uuid.uuid4()),
        name=body.name,
        role=body.role,
        system_prompt=body.system_prompt,
        model=body.model,
        temperature=str(body.temperature),
        tools_json=body.tools,
        status="configured",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return AgentProfileResponse(
        id=row.id,
        name=row.name,
        role=row.role,
        system_prompt=row.system_prompt,
        model=row.model,
        temperature=float(row.temperature or 0.2),
        tools=row.tools_json or [],
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/agents/chat", response_model=AgentChatResponse)
async def chat_with_agent(body: AgentChatRequest, db: AsyncSession = Depends(get_db)):
    """Chat directly with a selected agent, preserving per-thread context in Postgres."""
    agent_name, profile = await _resolve_chat_target(body.agent_name, body.message, db)
    thread_id = (body.thread_id or "").strip() or str(uuid.uuid4())

    agent = _build_chat_agent(agent_name, profile)
    if agent is None:
        raise HTTPException(status_code=400, detail=f"Agent '{agent_name}' is not chat-capable")

    history_rows = (await db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.thread_id == thread_id)
        .order_by(ChatMessageModel.created_at.asc())
    )).scalars().all()
    history = [_row_to_langchain_message(row) for row in history_rows]
    history.append(HumanMessage(content=body.message))

    try:
        result = await asyncio.to_thread(agent.invoke, {"messages": history})
    except Exception as exc:
        logger.error(f"Chat with {agent_name} failed for thread {thread_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Agent chat failed")

    messages = result.get("messages", [])
    if not messages:
        raise HTTPException(status_code=500, detail="Agent returned no message")

    reply = _message_to_text(messages[-1])
    if not reply.strip():
        reply = "I do not have a response yet."

    # Persist user + agent messages so threads survive backend restarts.
    db.add(ChatMessageModel(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        role="user",
        content=body.message,
        agent_name=None,
    ))
    db.add(ChatMessageModel(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        role="agent",
        content=reply,
        agent_name=agent_name,
    ))
    await db.commit()

    return AgentChatResponse(
        thread_id=thread_id,
        agent_name=agent_name,
        response=reply,
    )


@router.get("/agents/chat/{thread_id}/messages", response_model=list[AgentChatMessageResponse])
async def get_agent_chat_messages(thread_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch persisted chat messages for a thread."""
    rows = (await db.execute(
        select(ChatMessageModel)
        .where(ChatMessageModel.thread_id == thread_id)
        .order_by(ChatMessageModel.created_at.asc())
    )).scalars().all()
    return [
        AgentChatMessageResponse(
            thread_id=row.thread_id,
            role=row.role,
            content=row.content,
            agent_name=row.agent_name,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/mcp/servers", response_model=list[MCPServerResponse])
async def list_mcp_servers(db: AsyncSession = Depends(get_db)):
    """List configured MCP servers."""
    rows = (await db.execute(select(MCPServerModel).order_by(MCPServerModel.created_at.desc()))).scalars().all()
    return [
        MCPServerResponse(
            id=row.id,
            name=row.name,
            transport=row.transport,
            command=row.command,
            args=row.args,
            env_keys=[item.get("key", "") for item in (row.env_json or []) if item.get("key")],
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.post("/mcp/servers", response_model=MCPServerResponse)
async def create_mcp_server(body: MCPServerCreate, db: AsyncSession = Depends(get_db)):
    """Create and persist MCP server config."""
    existing = await db.execute(select(MCPServerModel).where(MCPServerModel.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="MCP server with this name already exists")

    row = MCPServerModel(
        id=str(uuid.uuid4()),
        name=body.name,
        transport=body.transport,
        command=body.command,
        args=body.args,
        env_json=[item.model_dump() for item in body.env],
        status="configured",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return MCPServerResponse(
        id=row.id,
        name=row.name,
        transport=row.transport,
        command=row.command,
        args=row.args,
        env_keys=[item.get("key", "") for item in (row.env_json or []) if item.get("key")],
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/audit/interventions", response_model=list[InterventionAuditResponse])
async def list_intervention_audit(db: AsyncSession = Depends(get_db)):
    """List intervention-related audit events."""
    intervention_actions = {
        "hitl_triggered",
        "human_input_received",
        "human_input_rejected",
    }
    rows = (await db.execute(
        select(ActionLogModel).order_by(ActionLogModel.timestamp.desc())
    )).scalars().all()
    filtered = [row for row in rows if row.action in intervention_actions]
    return [
        InterventionAuditResponse(
            id=row.id,
            task_id=row.task_id,
            action=row.action,
            detail=row.detail,
            timestamp=row.timestamp,
            agent_name=row.agent_name,
        )
        for row in filtered
    ]
