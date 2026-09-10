import json

import httpx
import pytest

import agent as integration
from backend.agent import AgentLoop
from backend.config import Config
from backend.llm_client import LocalLLMClient
from backend.tool_parser import ToolCallParseError, parse_response


def native_call(name="read_file", arguments=None, call_id="call_1"):
    return {
        "id": call_id, "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments or {"path": "src/main.py"})},
    }


@pytest.mark.parametrize("text", [
    '{"tool":"read_file","args":{"path":"src/main.py"}}',
    '```json\n{"name":"read_file","arguments":{"path":"src/main.py"}}\n```',
    '<tool_call>{"name":"read_file","arguments":{"path":"src/main.py"}}</tool_call>',
    '{"tool_calls":[{"function":"read_file","parameters":{"path":"src/main.py"}}]}',
    '[{"name":"read_file","arguments":"{\\"path\\":\\"src/main.py\\"}"}]',
])
def test_text_formats(text):
    response = parse_response(text)
    assert len(response["tool_calls"]) == 1
    call = response["tool_calls"][0]
    assert call["name"] == "read_file"
    assert call["arguments"] == {"path": "src/main.py"}
    assert call["id"]


def test_native_calls_take_precedence_over_echoed_text():
    response = parse_response({
        "content": '<tool_call>{"name":"read_file","arguments":{"path":"src/main.py"}}</tool_call>',
        "tool_calls": [native_call()],
    })
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["id"] == "call_1"


def test_multiple_calls_keep_order_and_unique_ids():
    text = (
        '<tool_call>{"name":"list_dir","arguments":{}}</tool_call>\n'
        '```json\n{"tool":"read_file","args":{"path":"nested/file.txt"}}\n```'
    )
    first = parse_response(text)["tool_calls"]
    second = parse_response(text)["tool_calls"]
    assert [call["name"] for call in first] == ["list_dir", "read_file"]
    assert len({call["id"] for call in first + second}) == 4


@pytest.mark.parametrize("response", [
    "The function returns 42.",
    '```json\n{"name":"example","value":42}\n```',
    '```python\nprint("hello")\n```',
])
def test_ordinary_answers_are_not_tools(response):
    assert parse_response(response)["tool_calls"] == []


@pytest.mark.parametrize("response", [
    '<tool_call>{invalid}</tool_call>',
    '<tool_call>{"name":"read_file","arguments":{}}',
    '```json\n{"tool": "read_file", "args":',
    '{"tool":"read_file","args":',
    '<tool_call>{"name":"invented_tool","arguments":{}}</tool_call>',
    '<tool_call>{"name":"read_file","arguments":{}}</tool_call>',
    '<tool_call>{"name":"read_file","arguments":[]}</tool_call>',
    '<tool_call>{"name":"read_file","arguments":{"path":42}}</tool_call>',
    '<tool_call>{"name":"read_file","arguments":{"path":"x","start_line":true}}</tool_call>',
    '<tool_call>{"name":"read_file","arguments":{"path":"x","invented":true}}</tool_call>',
    '<tool_call>[]</tool_call>',
    {"content": None, "tool_calls": [native_call(), native_call()]},
    {"content": "done", "tool_calls": {"name": "read_file"}},
    {"content": "", "tool_calls": []},
    {"content": ["unsupported content parts"]},
])
def test_invalid_calls_fail_explicitly(response):
    with pytest.raises(ToolCallParseError):
        parse_response(response)


async def mock_http(client, handler):
    await client.adapter.client.aclose()
    client.adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_default_http_request_and_model_override():
    def handler(request):
        assert str(request.url) == "http://test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "another-model"
        assert body["messages"][-1]["content"] == "Read main.py"
        assert body["stream"] is False
        assert any(tool["function"]["name"] == "read_file" for tool in body["tools"])
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [native_call()]}}]})

    client = LocalLLMClient("http://test/v1", "test-key", "another-model")
    await mock_http(client, handler)
    try:
        response = await client.chat_completion([{"role": "user", "content": "Read main.py"}])
        assert response["tool_calls"][0]["name"] == "read_file"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_custom_api_through_real_agent_loop(tmp_path, monkeypatch):
    folder = tmp_path / "nested"
    folder.mkdir()
    (folder / "note.txt").write_text("The project marker is 42.")
    requests = []
    monkeypatch.setattr(integration.LLMAdapter, "build_url", lambda self: "http://custom/generate")
    monkeypatch.setattr(integration.LLMAdapter, "build_headers", lambda self: {"X-Custom-Key": "secret"})
    monkeypatch.setattr(integration.LLMAdapter, "build_payload", lambda self, messages, tools, temperature: {
        "engine": self.model_name, "conversation": self.text_messages(messages),
    })
    monkeypatch.setattr(integration.LLMAdapter, "extract_response", lambda self, response: response.json()["answer"])

    def handler(request):
        assert str(request.url) == "http://custom/generate"
        assert request.headers["X-Custom-Key"] == "secret"
        body = json.loads(request.content)
        assert body["engine"] == "custom-model"
        requests.append(body)
        if len(requests) == 1:
            answer = '<tool_call>{"name":"read_file","arguments":{"path":"nested/note.txt"}}</tool_call>'
        else:
            assert "The project marker is 42." in body["conversation"][-1]["content"]
            assert all(message["role"] != "tool" for message in body["conversation"])
            answer = "The project marker is 42."
        return httpx.Response(200, json={"answer": answer})

    agent = AgentLoop(Config(workspace_dir=str(tmp_path), auto_checkpoint=False, model_name="custom-model"))
    await mock_http(agent.llm_client, handler)
    try:
        assert await agent.run("Read the nested note") == "The project marker is 42."
        assert len(requests) == 2
    finally:
        await agent.llm_client.close()


def test_text_mode_preserves_tool_context_without_native_fields(monkeypatch):
    monkeypatch.setattr(integration, "USE_NATIVE_TOOLS", False)
    # No client needed to inspect the payload builder.
    adapter = integration.LLMAdapter.__new__(integration.LLMAdapter)
    adapter.model_name = "text-model"
    history = [
        {"role": "system", "content": "tool instructions"},
        {"role": "assistant", "content": "", "tool_calls": [native_call()]},
        {"role": "tool", "name": "read_file", "tool_call_id": "call_1", "content": "file content"},
    ]
    payload = adapter.build_payload(history, [], 0.2)
    assert "tools" not in payload and "tool_choice" not in payload
    assert payload["messages"][1]["content"].count("<tool_call>") == 1
    assert "file content" in payload["messages"][2]["content"]
    assert history[2]["role"] == "tool"  # Don't mutate the loop's history.


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 422, 500])
async def test_http_errors_are_actionable_and_do_not_leak_body(status):
    client = LocalLLMClient("http://test", "secret", "model")
    await mock_http(client, lambda request: httpx.Response(status, text="sensitive response body"))
    try:
        with pytest.raises(RuntimeError, match=f"HTTP {status}") as caught:
            await client.chat_completion([])
        assert "sensitive" not in str(caught.value)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_bad_model_call_does_not_report_goal_completed(tmp_path):
    events = []
    async def event_callback(event):
        events.append(event["type"])
    agent = AgentLoop(Config(workspace_dir=str(tmp_path), auto_checkpoint=False), event_callback=event_callback)
    call = native_call()
    call["function"]["arguments"] = "{bad json"
    await mock_http(agent.llm_client, lambda request: httpx.Response(200, json={
        "choices": [{"message": {"content": None, "tool_calls": [call]}}],
    }))
    try:
        result = await agent.run("Read a file")
        assert "Invalid JSON arguments" in result
        assert "error" in events
        assert "goal_completed" not in events and "tool_call_start" not in events
    finally:
        await agent.llm_client.close()
