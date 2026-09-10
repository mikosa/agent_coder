"""Your LLM integration: edit this file to connect LocalCoder to your API.

The CLI and tool parser live in backend/. Keep API-specific changes here:
defaults, URL, headers, payload, and response extraction. Use --model to select
another model through this same adapter and parser.
"""

import json
from typing import Any

import httpx


# CUSTOMIZE: defaults. Environment variables and CLI flags can override these.
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_API_KEY = "not-needed"
DEFAULT_MODEL = "qwen2.5-coder:32b"
REQUEST_TIMEOUT = 120.0

# Set False if your API expects tool requests as JSON in the model's text.
USE_NATIVE_TOOLS = True


class LLMAdapter:
    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    def build_url(self) -> str:
        """CUSTOMIZE: return your complete inference URL."""
        return f"{self.base_url}/chat/completions"

    def build_headers(self) -> dict[str, str]:
        """CUSTOMIZE: authentication and any API-specific headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def build_payload(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        """CUSTOMIZE: conversation and generation options for your API.

        `messages` includes requests, previous answers, and tool results.
        Preserve that context when mapping to your API's format.
        """
        if not USE_NATIVE_TOOLS:
            messages = self.text_messages(messages)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if USE_NATIVE_TOOLS:
            payload.update(tools=tools, tool_choice="auto")
        return payload

    def extract_response(self, response: httpx.Response) -> dict[str, Any] | str:
        """CUSTOMIZE: extract the model's answer from the HTTP response.

        Return model text, e.g. response.json()["answer"] or response.text,
        or {"content": "...", "tool_calls": [...]} for native function calls.
        Do not parse tool JSON here: backend/tool_parser.py handles that.
        The default expects an OpenAI-compatible JSON response envelope.
        """
        data = response.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Model response was truncated; increase the API output token limit.")
        return choice["message"]

    async def request(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
        temperature: float = 0.2,
    ) -> dict[str, Any] | str:
        """Make one non-streaming HTTP request; the caller parses tool calls."""
        response = await self.client.post(
            self.build_url(),
            headers=self.build_headers(),
            json=self.build_payload(messages, tools, temperature),
        )
        response.raise_for_status()
        return self.extract_response(response)

    async def close(self):
        await self.client.aclose()

    @staticmethod
    def text_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Represent tool calls/results as text for APIs without native tools."""
        converted = []
        for message in messages:
            role = message["role"]
            content = message.get("content") or ""
            if role == "tool":
                role = "user"
                content = (
                    f"Tool result for {message.get('name', 'tool')} "
                    f"({message.get('tool_call_id', '')}):\n{content}"
                )
            elif message.get("tool_calls"):
                # Serialize once: content may already contain text tool syntax.
                content = "\n".join(
                    "<tool_call>" + json.dumps({
                        "name": call["function"]["name"],
                        "arguments": json.loads(call["function"]["arguments"]),
                    }) + "</tool_call>"
                    for call in message["tool_calls"]
                )
            converted.append({"role": role, "content": content})
        return converted
