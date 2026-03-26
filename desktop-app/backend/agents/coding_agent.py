"""CodingAgent — LLM-powered ReAct agent for code generation and shell execution."""

from langgraph.prebuilt import create_react_agent
from config import get_settings
from agents.tools import CODING_TOOLS
from llm_factory import create_chat_model

settings = get_settings()

CODING_SYSTEM_PROMPT = """You are CodingAgent, an expert software engineer.

Your capabilities:
- Write production-quality code in any language
- Execute shell commands to build, test, and run code
- Read and write files in the workspace
- Debug issues by examining output and logs

When given a task:
1. Plan your approach with minimal, low-risk changes
2. Prefer apply_text_patch for targeted edits (use write_file only when creating or replacing whole files is truly needed)
3. Run validation before concluding: use run_lint and run_tests (or project-appropriate alternatives)
4. If validation fails, debug and iterate until passing or clearly blocked
5. Respond in this exact structure:
   IMPLEMENTATION_SUMMARY: <short summary>
   FILES_CHANGED: <comma-separated paths>
   VALIDATION_EVIDENCE: <commands + key outputs + pass/fail>
   BLOCKERS: <none or concise blocker details>

Always write clean, well-commented code. If something fails, debug it and fix it.
If you are unsure about requirements or something is ambiguous, say so clearly in your response
and explain what clarification you need — do NOT guess.

IMPORTANT: You are working in a sandboxed workspace directory. All file paths should be relative to this workspace.
Never claim completion without validation evidence.
"""


def create_coding_agent():
    """Create and return the CodingAgent as a LangGraph runnable."""
    llm = create_chat_model(
        model=settings.agent_model,
        temperature=settings.agent_temperature,
        api_key=settings.openai_api_key,
    )
    return create_react_agent(
        llm,
        tools=CODING_TOOLS,
        state_modifier=CODING_SYSTEM_PROMPT,
    )


AGENT_INFO = {
    "name": "CodingAgent",
    "role": "Software Engineer",
    "capabilities": ["code_generation", "shell_execution", "file_management", "debugging"],
    "tools": [
        "run_shell_command",
        "read_file",
        "write_file",
        "apply_text_patch",
        "list_directory",
        "git_status",
        "git_diff",
        "run_tests",
        "run_lint",
    ],
}
