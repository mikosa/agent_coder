import asyncio
import os
import time
from pathlib import Path
from typing import Dict, Any, List


class BackgroundProcess:
    def __init__(self, process_id: str, command: str, cwd: str, process: asyncio.subprocess.Process):
        self.process_id = process_id
        self.command = command
        self.cwd = cwd
        self.process = process
        self.start_time = time.time()
        self.logs: List[str] = []
        self._read_task = None

    async def start_log_reader(self):
        async def _read_stream(stream, prefix):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                self.logs.append(f"[{prefix}] {decoded}")
                if len(self.logs) > 1000:
                    self.logs.pop(0)

        t1 = asyncio.create_task(_read_stream(self.process.stdout, "STDOUT"))
        t2 = asyncio.create_task(_read_stream(self.process.stderr, "STDERR"))
        self._read_task = asyncio.gather(t1, t2)

    def is_running(self) -> bool:
        return self.process.returncode is None


active_processes: Dict[str, BackgroundProcess] = {}


async def start_background_command(workspace_dir: str, command: str, cwd: str = ".") -> str:
    """Launches a shell command asynchronously in the background."""
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

        pid_str = f"proc_{os.urandom(3).hex()}"
        bg_proc = BackgroundProcess(pid_str, command, str(work_dir), process)
        await bg_proc.start_log_reader()
        active_processes[pid_str] = bg_proc

        return f"Successfully started background process [{pid_str}] (PID: {process.pid}) for command: '{command}'"
    except Exception as e:
        return f"Error starting background process: {str(e)}"


def read_process_logs(process_id: str, lines: int = 50) -> str:
    """Reads recent log output lines from a running or completed background process."""
    if process_id not in active_processes:
        return f"Error: Background process '{process_id}' not found."

    bg_proc = active_processes[process_id]
    status = "RUNNING" if bg_proc.is_running() else f"EXITED (code: {bg_proc.process.returncode})"

    recent_logs = bg_proc.logs[-lines:] if bg_proc.logs else ["[No logs generated yet]"]

    header = f"=== Background Process [{process_id}] Status: {status} ==="
    cmd_info = f"Command: {bg_proc.command}"
    log_text = "\n".join(recent_logs)
    return f"{header}\n{cmd_info}\n--- Recent Logs ({len(recent_logs)} lines) ---\n{log_text}"


async def stop_background_process(process_id: str) -> str:
    """Stops/kills a background process."""
    if process_id not in active_processes:
        return f"Error: Background process '{process_id}' not found."

    bg_proc = active_processes[process_id]
    if not bg_proc.is_running():
        return f"Process [{process_id}] is already stopped (Exit code: {bg_proc.process.returncode})."

    try:
        bg_proc.process.kill()
        await bg_proc.process.wait()
        return f"Successfully killed background process [{process_id}]."
    except Exception as e:
        return f"Error killing background process [{process_id}]: {str(e)}"


def list_background_processes() -> str:
    """Lists all active and recent background processes."""
    if not active_processes:
        return "No background processes currently registered."

    output = ["=== Registered Background Processes ==="]
    for pid, proc in active_processes.items():
        status = "RUNNING" if proc.is_running() else f"EXITED ({proc.process.returncode})"
        uptime = int(time.time() - proc.start_time)
        output.append(f"• [{pid}] Status: {status} | Uptime: {uptime}s | Cmd: '{proc.command}'")

    return "\n".join(output)
