import json
import asyncio
from typing import List, Dict, Any, Callable, Optional, Awaitable
from .config import Config
from .llm_client import LocalLLMClient
from .prompts import get_system_prompt
from .context_manager import ContextManager
from .tools import execute_tool, create_checkpoint, list_dir


class AgentLoop:
    def __init__(
        self,
        config: Config,
        event_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        approval_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[bool]]] = None
    ):
        self.config = config
        self.llm_client = LocalLLMClient(
            base_url=config.openai_base_url,
            api_key=config.openai_api_key,
            model_name=config.model_name
        )
        self.event_callback = event_callback
        self.approval_callback = approval_callback
        self.context_manager = ContextManager(max_context_tokens=config.max_context_tokens)

        system_prompt = get_system_prompt(config.model_family)
        system_prompt += (
            f"\n\nWorkspace root: {config.get_abs_workspace()}\n"
            "All relative file paths and shell working directories start here. "
            "Discover relevant subfolders with list_dir, file_tree, and grep_search, "
            "then read the files needed to answer the user's request. "
            "Do not ask the user to paste files you can read with these tools.\n"
            "Initial top-level directory listing (may be truncated):\n"
            + list_dir(config.workspace_dir)[:6000]
        )
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

    async def emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emits structured progress events to CLI logger or WebSockets UI."""
        if self.event_callback:
            await self.event_callback({
                "type": event_type,
                "data": payload
            })

    async def run(self, user_goal: str) -> str:
        """Executes the agent loop until the goal is accomplished or max turns reached."""
        self.history.append({"role": "user", "content": user_goal})
        await self.emit_event("goal_started", {"goal": user_goal})

        # Auto-create initial git checkpoint if enabled
        if self.config.auto_checkpoint:
            try:
                await create_checkpoint(self.config.workspace_dir, f"Auto-checkpoint before: {user_goal[:40]}")
            except Exception:
                pass

        step_count = 0
        final_answer = ""

        while step_count < self.config.max_turn_steps:
            step_count += 1
            await self.emit_event("step_start", {"step": step_count, "max_steps": self.config.max_turn_steps})

            # Compact history if approaching token limits
            self.history = self.context_manager.compact_history(self.history)

            try:
                response = await self.llm_client.chat_completion(self.history)
            except Exception as e:
                err_msg = f"Error during model completion: {str(e)}"
                await self.emit_event("error", {"message": err_msg})
                return f"Agent Loop Halted: {err_msg}"

            assistant_content = response.get("content") or ""
            tool_calls = response.get("tool_calls") or []

            # Emit model thinking / message text
            if assistant_content.strip():
                await self.emit_event("assistant_message", {"content": assistant_content})

            # Append assistant message to history
            assistant_msg_entry: Dict[str, Any] = {
                "role": "assistant",
                "content": assistant_content
            }
            if tool_calls:
                assistant_msg_entry["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"])
                        }
                    }
                    for tc in tool_calls
                ]
            self.history.append(assistant_msg_entry)

            # If no tool calls, model finished its task!
            if not tool_calls:
                final_answer = assistant_content
                await self.emit_event("goal_completed", {"result": final_answer, "steps": step_count})
                return final_answer

            # Process tool calls sequentially
            for tool_call in tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]

                await self.emit_event("tool_call_start", {
                    "tool_id": tool_id,
                    "name": tool_name,
                    "args": tool_args
                })

                # Check command approval if running terminal command
                approved = True
                if tool_name == "run_command" and not self.config.auto_approve_commands:
                    if self.approval_callback:
                        approved = await self.approval_callback(tool_name, tool_args)
                    else:
                        approved = True

                if not approved:
                    tool_result = f"Command execution rejected by user for command: '{tool_args.get('command')}'"
                    await self.emit_event("tool_call_rejected", {
                        "tool_id": tool_id,
                        "name": tool_name,
                        "reason": "User rejected command execution."
                    })
                else:
                    try:
                        tool_result = await execute_tool(
                            workspace_dir=self.config.workspace_dir,
                            tool_name=tool_name,
                            args=tool_args,
                            config_ref=self.config
                        )
                    except Exception as ex:
                        tool_result = f"Error executing tool '{tool_name}': {str(ex)}"

                await self.emit_event("tool_call_completed", {
                    "tool_id": tool_id,
                    "name": tool_name,
                    "result": tool_result
                })

                # Append tool result to history in standard OpenAI format
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": tool_result
                })

        # Max steps reached safeguard
        limit_msg = f"Agent loop reached maximum turn limit ({self.config.max_turn_steps} steps)."
        await self.emit_event("limit_reached", {"message": limit_msg})
        return limit_msg
