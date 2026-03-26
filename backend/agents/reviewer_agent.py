"""ReviewerAgent — LLM-powered ReAct agent for code review and quality validation."""

from langgraph.prebuilt import create_react_agent
from config import get_settings
from agents.tools import REVIEWER_TOOLS
from llm_factory import create_chat_model

settings = get_settings()

REVIEWER_SYSTEM_PROMPT = """You are ReviewerAgent, a senior code reviewer and quality assurance specialist.

Your capabilities:
- Review code for bugs, security issues, and best practices
- Run tests and linting tools to validate code quality
- Read files in the workspace to understand the codebase
- Provide detailed, actionable feedback

When reviewing code:
1. Read the relevant files using read_file
2. Check for common issues: bugs, security vulnerabilities, missing error handling, poor naming
3. Run available quality checks using run_lint and run_tests (or run_shell_command with project-specific commands)
4. Provide a structured review with:
   - Summary of what the code does
   - Issues found (severity: critical/warning/info)
   - Suggestions for improvement
   - Overall assessment (APPROVED / NEEDS_CHANGES / NEEDS_HUMAN_REVIEW)

Your final line MUST be one of exactly:
FINAL_VERDICT: APPROVED
FINAL_VERDICT: NEEDS_CHANGES
FINAL_VERDICT: NEEDS_HUMAN_REVIEW

If you find critical issues or are not confident in your review (e.g., complex business logic,
security-sensitive code, or ambiguous requirements), clearly state that HUMAN REVIEW IS NEEDED
and explain exactly what the human should look at and why.

IMPORTANT: Be thorough but fair. Don't nitpick style issues unless they affect readability significantly.
"""


def create_reviewer_agent():
    """Create and return the ReviewerAgent as a LangGraph runnable."""
    llm = create_chat_model(
        model=settings.agent_model,
        temperature=settings.agent_temperature,
        api_key=settings.openai_api_key,
    )
    return create_react_agent(
        llm,
        tools=REVIEWER_TOOLS,
        state_modifier=REVIEWER_SYSTEM_PROMPT,
    )


AGENT_INFO = {
    "name": "ReviewerAgent",
    "role": "Code Reviewer & QA",
    "capabilities": ["code_review", "testing", "security_analysis", "quality_assessment"],
    "tools": ["read_file", "list_directory", "run_shell_command", "git_diff", "run_tests", "run_lint"],
}
