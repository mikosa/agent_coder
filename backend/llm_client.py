"""Shared model client. Customize the HTTP API in the root agent.py file."""

from typing import Any

import httpx

from agent import LLMAdapter
from .tool_parser import parse_response, parse_text_tool_calls
from .tools import OPENAI_TOOL_SCHEMAS


class LocalLLMClient:
    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.base_url = base_url
        self.model_name = model_name
        self.adapter = LLMAdapter(base_url, api_key, model_name)

    async def chat_completion(
        self, messages: list[dict[str, Any]], temperature: float = 0.2,
    ) -> dict[str, Any]:
        try:
            response = await self.adapter.request(messages, OPENAI_TOOL_SCHEMAS, temperature)
        except httpx.TimeoutException as error:
            raise ConnectionError("Model request timed out. Check the server or REQUEST_TIMEOUT in agent.py.") from error
        except httpx.RequestError as error:
            raise ConnectionError(
                f"Could not connect to the model endpoint at '{self.base_url}'. "
                "Configure agent.py or pass --url and --model."
            ) from error
        except httpx.HTTPStatusError as error:
            raise RuntimeError(
                f"Model API returned HTTP {error.response.status_code}. "
                "Check the URL, headers, and payload in agent.py."
            ) from error
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError(
                "Could not extract the model response. Check extract_response() "
                "in agent.py and the API's response format/output limit."
            ) from error
        return parse_response(response)

    async def close(self):
        await self.adapter.close()

    def _parse_tool_calls_from_text(self, text: str) -> list[dict[str, Any]]:
        return parse_text_tool_calls(text)
