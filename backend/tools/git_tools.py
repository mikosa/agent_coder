import asyncio
import os
from pathlib import Path


async def _run_git(workspace_dir: str, args: list) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=workspace_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return (
        process.returncode,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace")
    )


async def ensure_git_repo(workspace_dir: str):
    """Initializes git repo if workspace is not already a git repository."""
    code, stdout, _ = await _run_git(workspace_dir, ["rev-parse", "--is-inside-work-tree"])
    if code != 0:
        await _run_git(workspace_dir, ["init"])
        # Configure local git user if not set
        await _run_git(workspace_dir, ["config", "user.name", "LocalCoder Agent"])
        await _run_git(workspace_dir, ["config", "user.email", "agent@localcoder.local"])


async def git_status(workspace_dir: str) -> str:
    """Returns current git repository status."""
    await ensure_git_repo(workspace_dir)
    code, stdout, stderr = await _run_git(workspace_dir, ["status", "--short"])
    if code != 0:
        return f"Git status error: {stderr}"
    if not stdout.strip():
        return "Git working directory is clean. No changes detected."
    return f"Git Status:\n{stdout}"


async def create_checkpoint(workspace_dir: str, message: str = "Agent Checkpoint") -> str:
    """Stages all changes and creates a git checkpoint commit."""
    await ensure_git_repo(workspace_dir)
    await _run_git(workspace_dir, ["add", "-A"])
    code, stdout, stderr = await _run_git(workspace_dir, ["commit", "-m", f"checkpoint: {message}"])
    if code != 0:
        if "nothing to commit" in stdout or "nothing to commit" in stderr:
            return "Checkpoint skipped: No uncommitted changes in workspace."
        return f"Error creating checkpoint: {stderr or stdout}"

    # Get commit hash
    _, commit_hash, _ = await _run_git(workspace_dir, ["rev-parse", "--short", "HEAD"])
    return f"Successfully created git checkpoint [{commit_hash.strip()}]: '{message}'"


async def rollback_checkpoint(workspace_dir: str, commit_hash: str = None) -> str:
    """Rolls back workspace to the previous checkpoint commit or specified commit hash."""
    await ensure_git_repo(workspace_dir)
    target = commit_hash if commit_hash else "HEAD~1"

    code, stdout, stderr = await _run_git(workspace_dir, ["reset", "--hard", target])
    if code != 0:
        return f"Error during git rollback to '{target}': {stderr or stdout}"

    await _run_git(workspace_dir, ["clean", "-fd"])
    _, current_hash, _ = await _run_git(workspace_dir, ["rev-parse", "--short", "HEAD"])
    return f"Successfully rolled back workspace to checkpoint [{current_hash.strip()}]."


async def git_diff(workspace_dir: str) -> str:
    """Returns working directory git diff."""
    await ensure_git_repo(workspace_dir)
    code, stdout, stderr = await _run_git(workspace_dir, ["diff", "HEAD"])
    if code != 0:
        return f"Error getting git diff: {stderr}"
    if not stdout.strip():
        return "No uncommitted changes in git diff."
    return f"Git Diff:\n{stdout}"
