"""LangChain tools for agent use — safer shell execution, file I/O, and validation."""

import subprocess
import os
from pathlib import Path
from langchain_core.tools import tool
from config import get_settings

settings = get_settings()

# Resolve working directory relative to backend root when needed.
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isabs(settings.shell_working_dir):
    WORKSPACE = os.path.abspath(settings.shell_working_dir)
else:
    WORKSPACE = os.path.abspath(os.path.join(BACKEND_ROOT, settings.shell_working_dir))
os.makedirs(WORKSPACE, exist_ok=True)

BLOCKED_SHELL_PATTERNS = (
    "rm -rf /",
    "rm -rf /*",
    "shutdown",
    "reboot",
    "mkfs",
    ":(){ :|:& };:",
)


def _is_within_workspace(target_path: str) -> bool:
    return os.path.abspath(target_path).startswith(WORKSPACE)


def _run_command(command: str, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        output += f"EXIT CODE: {result.returncode}"
        return output if output.strip() else "Command completed with no output."
    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def run_shell_command(command: str) -> str:
    """Execute a shell command in the workspace directory and return stdout + stderr.
    Use this for running scripts, installing packages, compiling code, running tests, etc.
    """
    lowered = command.lower().strip()
    if any(pattern in lowered for pattern in BLOCKED_SHELL_PATTERNS):
        return "ERROR: Command blocked by safety policy."
    return _run_command(command, timeout=120)


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file from the workspace directory.
    The file_path should be relative to the workspace.
    """
    try:
        full_path = os.path.join(WORKSPACE, file_path)
        if not _is_within_workspace(full_path):
            return "ERROR: Access denied — path is outside workspace."
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content if content else "(empty file)"
    except FileNotFoundError:
        return f"ERROR: File not found: {file_path}"
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file in the workspace directory.
    The file_path should be relative to the workspace. Parent directories are created automatically.
    """
    try:
        full_path = os.path.join(WORKSPACE, file_path)
        if not _is_within_workspace(full_path):
            return "ERROR: Access denied — path is outside workspace."
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def list_directory(dir_path: str = ".") -> str:
    """List files and directories in the workspace. The dir_path is relative to workspace."""
    try:
        full_path = os.path.join(WORKSPACE, dir_path)
        if not _is_within_workspace(full_path):
            return "ERROR: Access denied — path is outside workspace."
        entries = []
        for entry in sorted(os.listdir(full_path)):
            entry_path = os.path.join(full_path, entry)
            if os.path.isdir(entry_path):
                entries.append(f"  📁 {entry}/")
            else:
                size = os.path.getsize(entry_path)
                entries.append(f"  📄 {entry} ({size} bytes)")
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def apply_text_patch(file_path: str, old_text: str, new_text: str) -> str:
    """Apply a targeted text replacement in a file. Replaces exactly one occurrence."""
    try:
        full_path = os.path.join(WORKSPACE, file_path)
        if not _is_within_workspace(full_path):
            return "ERROR: Access denied — path is outside workspace."
        if not os.path.exists(full_path):
            return f"ERROR: File not found: {file_path}"
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        count = content.count(old_text)
        if count == 0:
            return "ERROR: old_text not found in file."
        if count > 1:
            return "ERROR: old_text appears multiple times. Provide more specific context."
        updated = content.replace(old_text, new_text, 1)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(updated)
        return f"Applied patch to {file_path}."
    except Exception as e:
        return f"ERROR: {str(e)}"


@tool
def git_status() -> str:
    """Return concise git status for workspace."""
    if not Path(WORKSPACE, ".git").exists():
        return "Not a git repository."
    return _run_command("git status --short --branch", timeout=30)


@tool
def git_diff() -> str:
    """Return current git diff (unstaged + staged)."""
    if not Path(WORKSPACE, ".git").exists():
        return "Not a git repository."
    return _run_command("git diff && git diff --staged", timeout=30)


@tool
def run_tests(command: str = "pytest -q") -> str:
    """Run project tests. Override command if project uses another test runner."""
    return _run_command(command, timeout=300)


@tool
def run_lint(command: str = "ruff check .") -> str:
    """Run project lint checks. Override command if project uses another linter."""
    return _run_command(command, timeout=300)


# Tool sets for different agents
CODING_TOOLS = [
    run_shell_command,
    read_file,
    write_file,
    apply_text_patch,
    list_directory,
    git_status,
    git_diff,
    run_tests,
    run_lint,
]
REVIEWER_TOOLS = [read_file, list_directory, run_shell_command, git_diff, run_tests, run_lint]
WORKFLOW_TOOLS = [list_directory, read_file]
