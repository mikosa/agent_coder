import os
from pathlib import Path
import subprocess
from unittest.mock import AsyncMock, patch

import pytest
from rich.console import Console

import main as cli
from backend.config import Config


ROOT = Path(__file__).resolve().parents[1]


def test_runner_preserves_project_folder_and_runs_shell_without_model(tmp_path):
    env = {key: value for key, value in os.environ.items() if key != "WORKSPACE_DIR"}
    result = subprocess.run(
        [str(ROOT / "scripts/run.sh"), "--no-checkpoint"],
        cwd=tmp_path,
        env=env,
        input="!pwd\n/exit\n",
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert str(tmp_path) in result.stdout
    assert f"CWD: {tmp_path}" in result.stdout
    assert "Exit Code: 0" in result.stdout
    assert "Goodbye!" in result.stdout
    assert not (tmp_path / ".git").exists()


def test_invalid_workspace_reports_error(tmp_path):
    result = subprocess.run(
        [str(ROOT / "scripts/run.sh"), "--workspace", str(tmp_path / "missing")],
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert "Workspace is not a directory" in result.stderr


@pytest.mark.asyncio
async def test_cli_reads_nested_file_and_prints_answer(tmp_path):
    nested = tmp_path / "src" / "services"
    nested.mkdir(parents=True)
    (nested / "example.py").write_text("def answer():\n    return 42\n")
    config = Config(workspace_dir=str(tmp_path), auto_checkpoint=False)
    requests = []

    async def completion(client, messages, temperature=0.2):
        requests.append(messages)
        if len(requests) == 1:
            assert str(tmp_path) in messages[0]["content"]
            assert "src/" in messages[0]["content"]
            return {"content": "Reading the nested source file.", "tool_calls": [{
                "id": "read_nested", "name": "read_file",
                "arguments": {"path": "src/services/example.py"},
            }]}
        assert messages[-1]["role"] == "tool"
        assert "return 42" in messages[-1]["content"]
        return {"content": "The answer function returns 42.", "tool_calls": []}

    console = Console(record=True, width=120)
    with patch.object(cli, "console", console), patch(
        "backend.llm_client.LocalLLMClient.chat_completion", completion
    ):
        await cli.run_interactive_cli(config, "Explain the nested source file")
    output = console.export_text()
    assert "The answer function returns 42." in output
    assert "Goal Completed" in output
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_manual_shell_output_available_to_next_question(tmp_path):
    seen = []

    async def completion(client, messages, temperature=0.2):
        seen.extend(messages)
        return {"content": "Your shell command succeeded.", "tool_calls": []}

    with patch.object(cli.Prompt, "ask", side_effect=["!echo CLI_MARKER", "What happened?", "/exit"]), patch(
        "backend.llm_client.LocalLLMClient.chat_completion", completion
    ):
        await cli.run_interactive_cli(Config(workspace_dir=str(tmp_path), auto_checkpoint=False))
    assert any("CLI_MARKER" in m["content"] and "STDOUT" in m["content"] for m in seen)


@pytest.mark.asyncio
async def test_approval_eof_rejects_command():
    with patch.object(cli.Confirm, "ask", side_effect=EOFError):
        assert await cli.cli_command_approval("run_command", {"command": "echo test"}) is False
