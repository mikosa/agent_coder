import pytest
from unittest.mock import AsyncMock, patch
from backend.config import Config
from backend.agent import AgentLoop


@pytest.mark.asyncio
async def test_agent_loop_mocked_llm(tmp_path):
    ws = tmp_path / "agent_ws"
    ws.mkdir()

    cfg = Config(
        openai_base_url="http://localhost:11434/v1",
        model_name="qwen2.5-coder:32b",
        workspace_dir=str(ws),
        max_turn_steps=5
    )

    events = []

    async def mock_event_cb(evt):
        events.append(evt)

    agent = AgentLoop(config=cfg, event_callback=mock_event_cb)

    # Mock chat completion response sequence: first turn uses write_file tool, second turn gives final text
    mock_responses = [
        {
            "role": "assistant",
            "content": "I will create main.py for you.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "write_file",
                    "arguments": {"path": "main.py", "content": "print('LocalCoder Rocks!')"}
                }
            ]
        },
        {
            "role": "assistant",
            "content": "Task finished successfully!",
            "tool_calls": []
        }
    ]

    with patch.object(agent.llm_client, "chat_completion", side_effect=mock_responses):
        result = await agent.run("Create main.py file")

    assert result == "Task finished successfully!"
    assert (ws / "main.py").exists()
    assert (ws / "main.py").read_text() == "print('LocalCoder Rocks!')"

    event_types = [e["type"] for e in events]
    assert "goal_started" in event_types
    assert "tool_call_start" in event_types
    assert "tool_call_completed" in event_types
    assert "goal_completed" in event_types
