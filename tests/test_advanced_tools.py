import pytest
import asyncio
from pathlib import Path
from backend.tools.patch_tools import apply_patch
from backend.tools.git_tools import ensure_git_repo, git_status, create_checkpoint, rollback_checkpoint, git_diff
from backend.tools.process_tools import start_background_command, read_process_logs, stop_background_process, list_background_processes
from backend.tools.ast_tools import check_syntax, inspect_symbols
from backend.context_manager import ContextManager


@pytest.fixture
def temp_workspace(tmp_path):
    ws = tmp_path / "adv_workspace"
    ws.mkdir()
    return str(ws)


def test_apply_patch_search_replace(temp_workspace):
    file_path = Path(temp_workspace) / "math_utils.py"
    file_path.write_text("def add(a, b):\n    return a - b\n")

    patch = """
<<<<<<< SEARCH
def add(a, b):
    return a - b
=======
def add(a, b):
    return a + b
>>>>>>> REPLACE
"""
    res = apply_patch(temp_workspace, "math_utils.py", patch)
    assert "Successfully applied" in res
    assert "return a + b" in file_path.read_text()


@pytest.mark.asyncio
async def test_git_checkpoint_and_rollback(temp_workspace):
    await ensure_git_repo(temp_workspace)
    (Path(temp_workspace) / "file1.txt").write_text("v1")
    await create_checkpoint(temp_workspace, "Initial commit")

    (Path(temp_workspace) / "file1.txt").write_text("v2")
    res_cp = await create_checkpoint(temp_workspace, "Version 2")
    assert "Successfully created git checkpoint" in res_cp

    res_rb = await rollback_checkpoint(temp_workspace)
    assert "Successfully rolled back" in res_rb
    assert (Path(temp_workspace) / "file1.txt").read_text() == "v1"


@pytest.mark.asyncio
async def test_background_process_management(temp_workspace):
    res_start = await start_background_command(temp_workspace, "python3 -c 'import time; print(\"BG START\"); time.sleep(5); print(\"BG END\")'")
    assert "Successfully started background process" in res_start

    proc_id = res_start.split("[")[1].split("]")[0]

    await asyncio.sleep(0.5)
    logs = read_process_logs(proc_id)
    assert "BG START" in logs

    res_stop = await stop_background_process(proc_id)
    assert "Successfully killed" in res_stop or "already stopped" in res_stop


@pytest.mark.asyncio
async def test_ast_syntax_and_symbols(temp_workspace):
    code = """
import os

class Calculator:
    '''Calculates numbers.'''
    def multiply(self, x, y):
        return x * y

def main():
    c = Calculator()
    print(c.multiply(2, 3))
"""
    (Path(temp_workspace) / "calc.py").write_text(code)

    res_syn = await check_syntax(temp_workspace, "calc.py")
    assert "Python Syntax Check Passed" in res_syn

    res_sym = inspect_symbols(temp_workspace, "calc.py")
    assert "Calculator" in res_sym
    assert "multiply" in res_sym
    assert "main" in res_sym


def test_context_manager_compaction():
    cm = ContextManager(max_context_tokens=100)

    multiline_tool_output = "Line of log output data...\n" * 100

    history = [
        {"role": "system", "content": "System Prompt"},
        {"role": "user", "content": "User Goal"},
        {"role": "assistant", "content": "Executing tools"},
        {"role": "tool", "content": multiline_tool_output},
        {"role": "tool", "content": multiline_tool_output},
        {"role": "assistant", "content": "Thinking step"},
        {"role": "user", "content": "Follow up step"},
        {"role": "assistant", "content": "Final step"}
    ]

    compacted = cm.compact_history(history)
    assert cm.estimate_history_tokens(compacted) < cm.estimate_history_tokens(history)
