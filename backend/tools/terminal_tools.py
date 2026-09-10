import asyncio
import os
from pathlib import Path


async def run_command(workspace_dir: str, command: str, cwd: str = ".", timeout: int = 60) -> str:
    """Executes a bash/shell command asynchronously in the terminal with timeout and output capture."""
    try:
        base_dir = Path(workspace_dir).resolve()
        work_dir = (base_dir / cwd).resolve() if not Path(cwd).is_absolute() else Path(cwd).resolve()

        if not work_dir.exists():
            return f"Error: Working directory '{cwd}' does not exist."

        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy()
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            return f"Error: Command timed out after {timeout} seconds: '{command}'"

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = process.returncode

        output_lines = [
            f"=== Command Output (Exit Code: {exit_code}) ===",
            f"Command: {command}",
            f"CWD: {work_dir}"
        ]

        if stdout.strip():
            output_lines.append("\n--- STDOUT ---")
            output_lines.append(stdout.rstrip())

        if stderr.strip():
            output_lines.append("\n--- STDERR ---")
            output_lines.append(stderr.rstrip())

        if not stdout.strip() and not stderr.strip():
            output_lines.append("\n[Command completed with no output]")

        res = "\n".join(output_lines)

        # Truncate extremely large outputs (e.g. over 8000 characters)
        if len(res) > 8000:
            truncated_len = len(res) - 8000
            res = res[:8000] + f"\n... [Output truncated by {truncated_len} characters]"

        return res

    except Exception as e:
        return f"Execution Error for command '{command}': {str(e)}"
