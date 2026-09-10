import asyncio
from typing import Dict, Any, Optional
from .config import Config


async def spawn_subagent(config: Config, goal: str, role: str = "Coding Subagent") -> str:
    """Spawns an isolated child AgentLoop to work on a sub-task."""
    from .agent import AgentLoop

    subagent_id = f"subagent_{role.lower().replace(' ', '_')}"

    # Create subagent with a smaller max step cap to prevent infinite loops
    sub_config = Config(
        openai_base_url=config.openai_base_url,
        openai_api_key=config.openai_api_key,
        model_name=config.model_name,
        max_turn_steps=12,
        auto_approve_commands=config.auto_approve_commands,
        workspace_dir=config.workspace_dir
    )

    sub_agent = AgentLoop(config=sub_config)

    try:
        res = await sub_agent.run(f"[Subagent Task - Role: {role}]\nGoal: {goal}")
        return f"=== Subagent [{role}] Completed Task ===\nResult:\n{res}"
    except Exception as e:
        return f"Subagent [{role}] failed with error: {str(e)}"
    finally:
        await sub_agent.llm_client.close()
