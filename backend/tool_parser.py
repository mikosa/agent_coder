"""Convert model replies into validated tool requests; never execute here."""

import json
import re
from typing import Any
from uuid import uuid4

from .tools import OPENAI_TOOL_SCHEMAS


class ToolCallParseError(ValueError):
    """A tool request cannot be safely interpreted; do not report completion."""


SCHEMAS = {tool["function"]["name"]: tool["function"]["parameters"] for tool in OPENAI_TOOL_SCHEMAS}
BLOCKS = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>|```(?:json)?\s*\n?(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def normalize_call(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ToolCallParseError("Each tool call must be a JSON object.")
    function = raw.get("function", raw)
    if isinstance(function, str):
        function = {**raw, "name": function}
    if not isinstance(function, dict):
        raise ToolCallParseError("Tool function must contain a name and arguments.")
    name = function.get("name") or function.get("tool")
    if not isinstance(name, str) or name not in SCHEMAS:
        raise ToolCallParseError(f"Unknown tool name: {name!r}.")
    arguments = next((function[key] for key in ("arguments", "args", "parameters") if key in function), {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise ToolCallParseError(f"Invalid JSON arguments for '{name}'.") from error
    if not isinstance(arguments, dict):
        raise ToolCallParseError(f"Arguments for '{name}' must be a JSON object.")

    schema = SCHEMAS[name]
    missing = set(schema.get("required", [])) - arguments.keys()
    if missing:
        raise ToolCallParseError(f"Missing arguments for '{name}': {', '.join(sorted(missing))}.")
    types = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list}
    for key, value in arguments.items():
        spec = schema.get("properties", {}).get(key)
        if spec is None:
            raise ToolCallParseError(f"Unknown argument '{key}' for '{name}'.")
        expected = types.get(spec.get("type"))
        if expected and type(value) is not expected:
            raise ToolCallParseError(f"Argument '{key}' for '{name}' must be {spec['type']}.")
    call_id = raw.get("id") or f"call_{uuid4().hex}"
    if not isinstance(call_id, str):
        raise ToolCallParseError("Tool call id must be a string.")
    return {"id": call_id, "name": name, "arguments": arguments}


def looks_like_call(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value) and any(looks_like_call(item) for item in value)
    return isinstance(value, dict) and (
        "tool" in value or "function" in value or "tool_calls" in value
        or ("name" in value and any(key in value for key in ("arguments", "args", "parameters")))
    )


def normalize_calls(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and "tool_calls" in value:
        value = value["tool_calls"]
    if not isinstance(value, list):
        value = [value]
    if not value:
        raise ToolCallParseError("A tool request must contain at least one call.")
    calls = [normalize_call(item) for item in value]
    ids = [call["id"] for call in calls]
    if len(set(ids)) != len(ids):
        raise ToolCallParseError("Duplicate tool call ids in model response.")
    return calls


def parse_text_tool_calls(text: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None
    if looks_like_call(value):
        return normalize_calls(value)

    calls = []
    for match in BLOCKS.finditer(text):
        explicit = match.group(1) is not None
        block = match.group(1) if explicit else match.group(2)
        try:
            value = json.loads(block)
        except json.JSONDecodeError as error:
            if explicit or re.search(r'"(?:tool|tool_calls|arguments|args)"\s*:', block):
                raise ToolCallParseError("Malformed JSON in model tool request.") from error
            continue
        if explicit or looks_like_call(value):
            calls.extend(normalize_calls(value))

    remainder = BLOCKS.sub("", text)
    if re.search(r"</?tool_call\b", remainder, re.IGNORECASE):
        raise ToolCallParseError("Incomplete <tool_call> block in model response.")
    if re.search(r'"(?:tool|tool_calls|arguments|args)"\s*:', remainder) and (
        stripped.startswith(("{", "[")) or "```" in remainder
    ):
        raise ToolCallParseError("Incomplete JSON tool request in model response.")
    ids = [call["id"] for call in calls]
    if len(set(ids)) != len(ids):
        raise ToolCallParseError("Duplicate tool call ids in model response.")
    return calls


def parse_response(response: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(response, str):
        content, calls = response, parse_text_tool_calls(response)
    elif isinstance(response, dict):
        content = response.get("content") or ""
        if not isinstance(content, str):
            raise ToolCallParseError("extract_response() must return text content as a string.")
        native = response.get("tool_calls")
        if native is not None and not isinstance(native, list):
            raise ToolCallParseError("Native tool_calls must be a list.")
        # Native calls take precedence so echoed text calls never execute twice.
        calls = normalize_calls(native) if native else parse_text_tool_calls(content)
    else:
        raise ToolCallParseError("extract_response() must return model text or a message object.")
    if not calls and not content.strip():
        raise ToolCallParseError("Model returned no answer or tool calls.")
    return {"role": "assistant", "content": content, "tool_calls": calls}
