import json
from typing import List, Dict, Any


def estimate_tokens(text: str) -> int:
    """Fast approximation of token count (~4 characters per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class ContextManager:
    def __init__(self, max_context_tokens: int = 16000):
        self.max_context_tokens = max_context_tokens

    def estimate_history_tokens(self, history: List[Dict[str, Any]]) -> int:
        total = 0
        for msg in history:
            content = msg.get("content") or ""
            total += estimate_tokens(content)
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += estimate_tokens(json.dumps(tool_calls))
        return total

    def compact_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compacts conversation history if total tokens exceed max_context_tokens."""
        if not history or len(history) <= 3:
            return history

        current_tokens = self.estimate_history_tokens(history)
        if current_tokens <= self.max_context_tokens:
            return history

        compacted = []
        # Keep System Prompt (index 0)
        system_msg = history[0] if history[0].get("role") == "system" else None
        start_idx = 1 if system_msg else 0

        if system_msg:
            compacted.append(system_msg)

        # Keep last 3 messages as strictly recent
        recent_threshold = max(start_idx, len(history) - 3)
        middle_history = history[start_idx:recent_threshold]
        recent_history = history[recent_threshold:]

        compacted_middle = []
        for msg in middle_history:
            msg_copy = dict(msg)
            if msg_copy.get("role") == "tool":
                content = str(msg_copy.get("content", ""))
                if len(content) > 200:
                    lines = content.splitlines()
                    summary_content = (
                        f"--- Historical Tool Output Truncated ({len(lines)} lines, {len(content)} chars) ---\n"
                        + "\n".join(lines[:5])
                        + f"\n... [{max(0, len(lines) - 10)} lines summarized for context compaction] ...\n"
                        + "\n".join(lines[-5:])
                    )
                    msg_copy["content"] = summary_content
            compacted_middle.append(msg_copy)

        compacted.extend(compacted_middle)
        compacted.extend(recent_history)

        # If still over token limit, condense middle items into a single summary block
        if self.estimate_history_tokens(compacted) > self.max_context_tokens and len(compacted_middle) > 1:
            summary_text = (
                f"--- [Context Memory Summary: {len(compacted_middle)} previous turn steps compacted to save token budget] ---"
            )
            final_history = []
            if system_msg:
                final_history.append(system_msg)
            final_history.append({
                "role": "user",
                "content": summary_text
            })
            final_history.extend(recent_history)
            return final_history

        return compacted
