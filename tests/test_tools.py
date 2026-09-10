import pytest
from pathlib import Path
from backend.tools import execute_tool
from backend.tools.file_tools import read_file, write_file, edit_file, list_dir, delete_file
from backend.tools.code_tools import grep_search, file_tree


@pytest.fixture
def temp_workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    return str(ws)


def test_file_write_and_read(temp_workspace):
    res_write = write_file(temp_workspace, "hello.py", "print('hello world')\n")
    assert "Successfully wrote" in res_write

    res_read = read_file(temp_workspace, "hello.py")
    assert "hello world" in res_read


def test_file_edit(temp_workspace):
    write_file(temp_workspace, "script.py", "def foo():\n    return 42\n")
    res_edit = edit_file(temp_workspace, "script.py", "return 42", "return 100")
    assert "Successfully edited" in res_edit

    res_read = read_file(temp_workspace, "script.py")
    assert "return 100" in res_read


def test_list_dir_and_tree(temp_workspace):
    write_file(temp_workspace, "dir1/file1.txt", "content")
    write_file(temp_workspace, "dir1/file2.txt", "content")

    res_dir = list_dir(temp_workspace, "dir1")
    assert "file1.txt" in res_dir
    assert "file2.txt" in res_dir

    res_tree = file_tree(temp_workspace)
    assert "dir1/" in res_tree


def test_grep_search(temp_workspace):
    write_file(temp_workspace, "app.py", "def calculate_total(items):\n    return sum(items)\n")
    res_grep = grep_search(temp_workspace, "calculate_total")
    assert "app.py:1: def calculate_total" in res_grep


@pytest.mark.asyncio
async def test_execute_run_command(temp_workspace):
    res = await execute_tool(
        workspace_dir=temp_workspace,
        tool_name="run_command",
        args={"command": "echo 'Hello from bash'"}
    )
    assert "Hello from bash" in res
    assert "Exit Code: 0" in res
