"""Core LangGraph Supervisor Graph — orchestrates all agent execution.

This is the brain of the control plane. It uses:
- Supervisor pattern: a central LLM routes tasks to sub-agents
- interrupt(): pauses for human-in-the-loop when agents need clarification
- PostgresSaver: persists all state to PostgreSQL for durability
"""

import logging
import operator
import os
import re
import subprocess
import uuid
import json
from typing import Annotated, TypedDict, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import interrupt, Command

from config import get_settings
from agents.coding_agent import create_coding_agent, AGENT_INFO as CODING_INFO
from agents.reviewer_agent import create_reviewer_agent, AGENT_INFO as REVIEWER_INFO
from agents.workflow_agent import create_workflow_agent, AGENT_INFO as WORKFLOW_INFO
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
from models.database import sync_session_factory, AgentProfileModel
from llm_factory import create_chat_model

logger = logging.getLogger(__name__)
settings = get_settings()
_checkpointer_cm = None
_custom_agents: dict[str, dict] = {}
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isabs(settings.shell_working_dir):
    WORKSPACE = os.path.abspath(settings.shell_working_dir)
else:
    WORKSPACE = os.path.abspath(os.path.join(BACKEND_ROOT, settings.shell_working_dir))

_TOOL_REGISTRY = {
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

# --- State Definition ---

class AgentState(TypedDict):
    """Shared state flowing through the supervisor graph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    task_id: str
    task_description: str
    current_agent: str
    status: str
    plan: str
    results: Annotated[list[str], operator.add]
    needs_human: bool
    human_question: str
    iteration_count: int
    reviewer_approved: bool
    pending_action: dict
    approval_status: str
    github_repo_created: bool


# --- Node Functions ---

def _refresh_custom_agents():
    """Load custom agent profiles from DB for runtime routing/execution."""
    global _custom_agents
    with sync_session_factory() as session:
        rows = session.query(AgentProfileModel).all()
    _custom_agents = {
        row.name: {
            "name": row.name,
            "role": row.role,
            "system_prompt": row.system_prompt,
            "model": row.model or settings.agent_model,
            "temperature": float(row.temperature or settings.agent_temperature),
            "tools": row.tools_json or [],
        }
        for row in rows
    }


def _resolve_decision(raw_decision: str) -> str:
    text = (raw_decision or "").strip()
    upper = text.upper()
    if "FINISH" in upper:
        return "FINISH"
    if "HUMAN" in upper:
        return "HUMAN"
    if "WORKFLOWAGENT" in upper:
        return "WorkflowAgent"
    if "CODINGAGENT" in upper:
        return "CodingAgent"
    if "REVIEWERAGENT" in upper:
        return "ReviewerAgent"
    for custom_name in _custom_agents.keys():
        if custom_name.upper() in upper:
            return custom_name
    return "WorkflowAgent"


def _build_custom_agent(name: str):
    profile = _custom_agents.get(name)
    if not profile:
        return None
    llm = create_chat_model(
        model=profile.get("model", settings.agent_model),
        temperature=profile.get("temperature", settings.agent_temperature),
        api_key=settings.openai_api_key,
    )
    tool_names = profile.get("tools") or []
    tools = [_TOOL_REGISTRY[t] for t in tool_names if t in _TOOL_REGISTRY]
    return create_react_agent(
        llm,
        tools=tools,
        state_modifier=profile.get("system_prompt", ""),
    )


def _next_planned_custom_agent(state: AgentState) -> str | None:
    """Pick a custom agent explicitly referenced in plan but not yet executed."""
    plan = state.get("plan", "") or ""
    if not plan:
        return None
    results = state.get("results", []) or []
    for name in _custom_agents.keys():
        if f"[{name}]" in plan and not any(r.startswith(f"{name}:") for r in results):
            return name
    return None


def _parse_repo_name(task_description: str) -> str:
    match = re.search(r"(?:repo(?:sitory)?\s+(?:named|called)\s+)([a-zA-Z0-9._-]+)", task_description, re.IGNORECASE)
    if match:
        return match.group(1)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", task_description.lower()).strip("-")
    return (slug[:40] or f"olympus-task-{uuid.uuid4().hex[:8]}")


def _extract_pending_github_action(state: AgentState) -> dict | None:
    task_description = state.get("task_description", "")
    lowered = task_description.lower()
    if "github" not in lowered or ("repo" not in lowered and "repository" not in lowered):
        return None
    return {
        "action_id": f"create-github-repo-{state['task_id']}",
        "type": "create_github_repo",
        "requires_approval": True,
        "proposed_params": {
            "name": _parse_repo_name(task_description),
            "visibility": "private",
            "owner": "",
            "description": task_description[:200],
        },
    }


def _parse_human_response_payload(human_response) -> dict:
    if isinstance(human_response, dict):
        return human_response
    if isinstance(human_response, str):
        raw = human_response.strip()
        if not raw:
            return {"human_input": ""}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"human_input": raw}
    return {"human_input": str(human_response)}


def supervisor_node(state: AgentState) -> Command:
    """Supervisor decides which agent to invoke next or whether to finish."""
    _refresh_custom_agents()
    llm = create_chat_model(
        model=settings.agent_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )

    iteration = state.get("iteration_count", 0)
    pending_action = state.get("pending_action") or {}
    approval_status = state.get("approval_status", "not_required")

    if state.get("needs_human", False):
        return Command(
            goto="human_review",
            update={
                "current_agent": "supervisor",
                "status": "waiting_for_human",
                "iteration_count": iteration + 1,
            },
        )

    if not pending_action:
        discovered = _extract_pending_github_action(state)
        if discovered:
            question = (
                "Approval required before creating GitHub repository.\n"
                f"Proposed repo name: {discovered['proposed_params']['name']}\n"
                f"Visibility: {discovered['proposed_params']['visibility']}\n"
                "Approve, edit, or reject this action."
            )
            return Command(
                goto="human_review",
                update={
                    "pending_action": discovered,
                    "approval_status": "pending",
                    "needs_human": True,
                    "human_question": question,
                    "status": "waiting_for_human",
                    "current_agent": "supervisor",
                    "iteration_count": iteration + 1,
                },
            )

    if (
        pending_action
        and pending_action.get("type") == "create_github_repo"
        and approval_status == "approved"
        and not state.get("github_repo_created", False)
    ):
        return Command(
            goto="github_repo_action",
            update={
                "current_agent": "GitHubRepoAction",
                "status": "running",
                "iteration_count": iteration + 1,
            },
        )

    # Safety: max 10 iterations
    if iteration >= 10:
        logger.warning(f"Task {state['task_id']} hit max iterations, completing")
        return Command(
            goto="finalize",
            update={
                "current_agent": "supervisor",
                "status": "completing",
                "iteration_count": iteration + 1,
            },
        )

    planned_custom = _next_planned_custom_agent(state)
    if planned_custom:
        logger.info(f"Routing planned custom agent {planned_custom} for task {state['task_id']}")
        return Command(
            goto="custom_agent",
            update={
                "current_agent": planned_custom,
                "status": "running",
                "iteration_count": iteration + 1,
            },
        )

    custom_agents_block = "\n".join(
        [f"- {name}: {info.get('role', 'Custom agent')}" for name, info in _custom_agents.items()]
    ) or "- (none configured)"

    system_msg = SystemMessage(content=f"""You are the Supervisor orchestrating AI agents to complete a task.

TASK: {state['task_description']}

AVAILABLE AGENTS:
- WorkflowAgent: Breaks down tasks into plans. Use FIRST for complex tasks.
- CodingAgent: Writes code, runs shell commands, creates files. Use for implementation.
- ReviewerAgent: Reviews code quality, runs tests. Use AFTER coding is done.
CUSTOM AGENTS:
{custom_agents_block}

CURRENT STATE:
- Plan: {state.get('plan', 'No plan yet')}
- Results so far: {len(state.get('results', []))} steps completed
- Iteration: {iteration}/10

RULES:
1. For new tasks, ALWAYS start with WorkflowAgent to create a plan
2. Route based on task type and plan, not a fixed sequence:
   - Coding tasks -> CodingAgent
   - Review/QA tasks -> ReviewerAgent
   - Custom-domain tasks -> matching custom agent
3. Use CodingAgent ONLY when code/workspace implementation is required
4. Use ReviewerAgent after coding/changes when validation is needed
5. NEVER route to FINISH until reviewer_approved is true
6. If a needed capability is missing or anything is unclear -> route to "HUMAN" for human input

Respond with EXACTLY one of: WorkflowAgent, CodingAgent, ReviewerAgent, FINISH, HUMAN, or a custom agent name from CUSTOM AGENTS.
If HUMAN, also explain what question to ask the human.
""")

    response = llm.invoke(state["messages"] + [system_msg])
    decision = _resolve_decision(response.content.strip())

    logger.info(f"Supervisor decision for task {state['task_id']}: {decision}")

    if "FINISH" in decision.upper():
        if not state.get("reviewer_approved", False):
            logger.info(
                f"Supervisor blocked FINISH for task {state['task_id']} - reviewer approval missing, routing ReviewerAgent"
            )
            return Command(
                goto="reviewer_agent",
                update={
                    "current_agent": "ReviewerAgent",
                    "status": "running",
                    "iteration_count": iteration + 1,
                },
            )
        return Command(
            goto="finalize",
            update={
                "current_agent": "supervisor",
                "status": "completing",
                "iteration_count": iteration + 1,
            },
        )
    elif decision == "HUMAN":
        # Extract the question from the decision
        question = decision.replace("HUMAN", "").replace(":", "").strip()
        if not question:
            question = "The supervisor needs clarification on this task. Please provide additional details."
        return Command(
            goto="human_review",
            update={
                "current_agent": "supervisor",
                "needs_human": True,
                "human_question": question,
                "status": "waiting_for_human",
                "iteration_count": iteration + 1,
            },
        )
    elif decision == "WorkflowAgent":
        return Command(
            goto="workflow_agent",
            update={
                "current_agent": "WorkflowAgent",
                "status": "running",
                "iteration_count": iteration + 1,
            },
        )
    elif decision == "CodingAgent":
        return Command(
            goto="coding_agent",
            update={
                "current_agent": "CodingAgent",
                "status": "running",
                "iteration_count": iteration + 1,
            },
        )
    elif decision == "ReviewerAgent":
        return Command(
            goto="reviewer_agent",
            update={
                "current_agent": "ReviewerAgent",
                "status": "running",
                "iteration_count": iteration + 1,
            },
        )
    elif decision in _custom_agents:
        return Command(
            goto="custom_agent",
            update={
                "current_agent": decision,
                "status": "running",
                "iteration_count": iteration + 1,
            },
        )
    else:
        # Default to workflow for unknown decisions
        return Command(
            goto="workflow_agent",
            update={
                "current_agent": "WorkflowAgent",
                "status": "running",
                "iteration_count": iteration + 1,
            },
        )


def workflow_agent_node(state: AgentState) -> dict:
    """Run the WorkflowAgent to decompose the task."""
    logger.info(f"WorkflowAgent executing for task {state['task_id']}")
    agent = create_workflow_agent()

    task_msg = HumanMessage(content=f"""Please analyze and create an execution plan for this task:

TASK: {state['task_description']}

Create a clear, numbered plan with agent assignments.""")

    result = agent.invoke({"messages": [task_msg]})
    last_msg = result["messages"][-1]

    return {
        "messages": [AIMessage(content=f"[WorkflowAgent] {last_msg.content}")],
        "plan": last_msg.content,
        "results": [f"WorkflowAgent: Created execution plan"],
        "current_agent": "supervisor",
    }


def coding_agent_node(state: AgentState) -> dict:
    """Run the CodingAgent for coding/workspace implementation tasks."""
    logger.info(f"CodingAgent executing for task {state['task_id']}")
    agent = create_coding_agent()

    context = f"""TASK: {state['task_description']}

PLAN:
{state.get('plan', 'No plan provided — use your best judgment.')}

Previous results:
{chr(10).join(state.get('results', ['None']))}

Execute the next coding or workspace implementation step from the plan.
Only perform code/file/shell implementation tasks that match your role.
Do not create GitHub repositories directly; that is handled by privileged workflow after human approval."""

    task_msg = HumanMessage(content=context)
    result = agent.invoke({"messages": [task_msg]})
    last_msg = result["messages"][-1]

    return {
        "messages": [AIMessage(content=f"[CodingAgent] {last_msg.content}")],
        "results": [f"CodingAgent: Implementation step completed"],
        "current_agent": "supervisor",
        "reviewer_approved": False,
    }


def reviewer_agent_node(state: AgentState) -> dict:
    """Run the ReviewerAgent to validate code."""
    logger.info(f"ReviewerAgent executing for task {state['task_id']}")
    agent = create_reviewer_agent()

    context = f"""Please review the code that was just written for this task:

TASK: {state['task_description']}

PLAN:
{state.get('plan', 'No plan provided.')}

Previous agent outputs:
{chr(10).join(state.get('results', ['None']))}

Review the workspace for the implemented code. Check for bugs, security issues, and quality."""

    task_msg = HumanMessage(content=context)
    result = agent.invoke({"messages": [task_msg]})
    last_msg = result["messages"][-1]

    # Parse review outcome for supervisor enforcement.
    needs_human = "NEEDS_HUMAN_REVIEW" in last_msg.content.upper() or "HUMAN REVIEW" in last_msg.content.upper()
    verdict_approved = "FINAL_VERDICT: APPROVED" in last_msg.content.upper()

    update = {
        "messages": [AIMessage(content=f"[ReviewerAgent] {last_msg.content}")],
        "results": [f"ReviewerAgent: Code review completed"],
        "current_agent": "supervisor",
        "reviewer_approved": verdict_approved and not needs_human,
    }

    if needs_human:
        update["needs_human"] = True
        update["human_question"] = f"ReviewerAgent flagged issues for human review:\n\n{last_msg.content}"

    return update


def custom_agent_node(state: AgentState) -> dict:
    """Run a custom agent configured via UI."""
    agent_name = state.get("current_agent", "")
    logger.info(f"Custom agent {agent_name} executing for task {state['task_id']}")
    _refresh_custom_agents()
    agent = _build_custom_agent(agent_name)
    if agent is None:
        return {
            "messages": [AIMessage(content=f"[{agent_name}] Agent is not configured.")],
            "results": [f"{agent_name}: Missing configuration"],
            "current_agent": "supervisor",
        }

    context = f"""TASK: {state['task_description']}

PLAN:
{state.get('plan', 'No plan provided.')}

Previous results:
{chr(10).join(state.get('results', ['None']))}

Execute your part of the task according to your role and tools."""
    task_msg = HumanMessage(content=context)
    result = agent.invoke({"messages": [task_msg]})
    last_msg = result["messages"][-1]
    return {
        "messages": [AIMessage(content=f"[{agent_name}] {last_msg.content}")],
        "results": [f"{agent_name}: Step completed"],
        "current_agent": "supervisor",
    }


def human_review_node(state: AgentState) -> dict:
    """Pause execution and wait for human input via LangGraph interrupt()."""
    question = state.get("human_question", "Human input needed. Please provide guidance.")
    logger.info(f"HITL triggered for task {state['task_id']}: {question}")

    # This pauses the graph and saves state to PostgreSQL via checkpointer
    human_response = interrupt({
        "task_id": state["task_id"],
        "question": question,
        "type": "hitl_request",
        "pending_action": state.get("pending_action") or {},
    })

    payload = _parse_human_response_payload(human_response)
    approval = payload.get("approval") if isinstance(payload, dict) else None
    pending = state.get("pending_action") or {}
    action_id = pending.get("action_id")

    update: dict = {
        "messages": [HumanMessage(content=f"[Human Input] {payload}")],
        "status": "running",
        "current_agent": "supervisor",
    }

    if action_id:
        if isinstance(approval, dict) and approval.get("action_id") == action_id:
            decision = (approval.get("decision") or "").lower()
            if decision in {"approve", "edit"}:
                merged_params = dict(pending.get("proposed_params") or {})
                merged_params.update(approval.get("params") or {})
                pending["approved_params"] = merged_params
                pending["approved_by"] = approval.get("approved_by") or "human_operator"
                update.update({
                    "pending_action": pending,
                    "approval_status": "approved",
                    "needs_human": False,
                    "human_question": "",
                })
            else:
                update.update({
                    "approval_status": "rejected",
                    "needs_human": True,
                    "human_question": "GitHub repo creation was rejected. Edit and approve to continue.",
                    "status": "waiting_for_human",
                })
        else:
            update.update({
                "approval_status": "pending",
                "needs_human": True,
                "human_question": "Missing or invalid approval payload for pending privileged action.",
                "status": "waiting_for_human",
            })
    else:
        update.update({
            "needs_human": False,
            "human_question": "",
        })
    return update


def github_repo_action_node(state: AgentState) -> dict:
    """Execute approved GitHub repository creation action."""
    pending = state.get("pending_action") or {}
    params = pending.get("approved_params") or pending.get("proposed_params") or {}
    repo_name = (params.get("name") or "").strip()
    visibility = (params.get("visibility") or "private").strip().lower()
    owner = (params.get("owner") or "").strip()
    description = (params.get("description") or "").strip()

    if not repo_name:
        return {
            "messages": [AIMessage(content="[GitHubRepoAction] Missing repository name in approved parameters.")],
            "results": ["GitHubRepoAction: Failed - missing repository name"],
            "needs_human": True,
            "human_question": "Approved action is missing repository name. Please edit and approve again.",
            "status": "waiting_for_human",
            "current_agent": "supervisor",
        }

    vis_flag = "--public" if visibility == "public" else "--private"
    owner_prefix = f"{owner}/" if owner else ""
    escaped_description = description.replace('"', '\\"')
    command = f'gh repo create {owner_prefix}{repo_name} {vis_flag} --description "{escaped_description}" --confirm'
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            return {
                "messages": [AIMessage(content=f"[GitHubRepoAction] Failed to create repository.\n{output.strip()}")],
                "results": ["GitHubRepoAction: Failed to create repository"],
                "needs_human": True,
                "human_question": (
                    "GitHub repo creation failed. Confirm gh auth, permissions, and parameters, then approve again.\n"
                    f"Error:\n{output.strip()[:1200]}"
                ),
                "status": "waiting_for_human",
                "current_agent": "supervisor",
            }
        return {
            "messages": [AIMessage(content=f"[GitHubRepoAction] Repository created successfully.\n{output.strip()}")],
            "results": [f"GitHubRepoAction: Created repository {owner_prefix}{repo_name} ({visibility})"],
            "github_repo_created": True,
            "current_agent": "supervisor",
            "status": "running",
        }
    except Exception as exc:
        return {
            "messages": [AIMessage(content=f"[GitHubRepoAction] Exception: {str(exc)}")],
            "results": [f"GitHubRepoAction: Exception during creation - {str(exc)}"],
            "needs_human": True,
            "human_question": "GitHub repo creation raised an exception. Please review and approve retry.",
            "status": "waiting_for_human",
            "current_agent": "supervisor",
        }


def finalize_node(state: AgentState) -> dict:
    """Compile final results."""
    logger.info(f"Finalizing task {state['task_id']}")

    summary = f"""Task completed: {state['task_description']}

Steps executed: {len(state.get('results', []))}
Results:
""" + "\n".join(f"  - {r}" for r in state.get("results", []))

    return {
        "messages": [AIMessage(content=f"[Finalized] {summary}")],
        "status": "completed",
        "current_agent": "none",
    }


# --- Graph Construction ---

def build_supervisor_graph():
    """Build the LangGraph supervisor graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("workflow_agent", workflow_agent_node)
    graph.add_node("coding_agent", coding_agent_node)
    graph.add_node("reviewer_agent", reviewer_agent_node)
    graph.add_node("custom_agent", custom_agent_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("github_repo_action", github_repo_action_node)
    graph.add_node("finalize", finalize_node)

    # Entry point
    graph.add_edge(START, "supervisor")

    # After each agent, go back to supervisor for routing
    graph.add_edge("workflow_agent", "supervisor")
    graph.add_edge("coding_agent", "supervisor")
    graph.add_edge("reviewer_agent", "supervisor")
    graph.add_edge("custom_agent", "supervisor")
    graph.add_edge("human_review", "supervisor")
    graph.add_edge("github_repo_action", "supervisor")

    # Finalize ends the graph
    graph.add_edge("finalize", END)

    return graph


def get_checkpointer():
    """Create PostgresSaver checkpointer."""
    return PostgresSaver.from_conn_string(settings.database_url_sync)


def compile_graph():
    """Compile the graph with checkpointer for production use."""
    global _checkpointer_cm
    graph = build_supervisor_graph()
    _checkpointer_cm = get_checkpointer()
    checkpointer = _checkpointer_cm.__enter__()
    checkpointer.setup()  # Create checkpoint tables
    return graph.compile(checkpointer=checkpointer)


# Agent registry for status endpoint
AGENT_REGISTRY = {
    "WorkflowAgent": WORKFLOW_INFO,
    "CodingAgent": CODING_INFO,
    "ReviewerAgent": REVIEWER_INFO,
}
