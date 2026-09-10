import asyncio
import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.text import Text

from backend.config import Config
from backend.agent import AgentLoop
from backend.tools.terminal_tools import run_command

console = Console()


def print_banner():
    banner_text = """
 [bold cyan]LocalCoder[/bold cyan] - Autonomous Local Coding Agent Loop
 [dim]Ask about your project, request code changes, or run a shell command with !command.[/dim]
    """
    console.print(Panel(banner_text, border_style="cyan", title="🤖 local_coder", title_align="left"))


async def cli_event_handler(event: dict):
    event_type = event.get("type")
    data = event.get("data", {})

    if event_type == "goal_started":
        console.print(f"\n[bold yellow]🎯 Goal Started:[/bold yellow] [bold white]{data.get('goal')}[/bold white]")

    elif event_type == "step_start":
        step = data.get("step")
        max_s = data.get("max_steps")
        console.print(f"\n[dim]── Turn Step {step}/{max_s} ──────────────────────────────────────[/dim]")

    elif event_type == "assistant_message":
        content = data.get("content", "")
        if content.strip():
            console.print(Markdown(content))

    elif event_type == "tool_call_start":
        tool_name = data.get("name")
        args = data.get("args", {})
        console.print(f"[bold cyan]🛠  Invoking Tool:[/bold cyan] [bold green]{tool_name}[/bold green]")
        arg_str = "\n".join([f"  • {k}: {repr(v)}" for k, v in args.items()])
        console.print(Panel(arg_str, title=f"Arguments: {tool_name}", border_style="blue", expand=False))

    elif event_type == "tool_call_completed":
        result = data.get("result", "")
        display_res = result[:1500] + "\n... [truncated]" if len(result) > 1500 else result
        console.print(Panel(display_res, title="Tool Output", border_style="dim white", expand=False))

    elif event_type == "tool_call_rejected":
        console.print(f"[bold red]⛔ Tool Execution Rejected:[/bold red] {data.get('reason')}")

    elif event_type == "error":
        console.print(f"[bold red]❌ Error:[/bold red] {data.get('message')}")

    elif event_type == "goal_completed":
        console.print(f"\n[bold green]✅ Goal Completed in {data.get('steps')} steps![/bold green]")

    elif event_type == "limit_reached":
        console.print(data.get("message", "Turn limit reached."), style="yellow", markup=False)


async def cli_command_approval(tool_name: str, args: dict) -> bool:
    cmd = args.get("command", "")
    console.print(f"\n[bold magenta]⚠️  Command Approval Required:[/bold magenta]")
    console.print(Panel(Syntax(cmd, "bash", theme="monokai"), title="Pending Shell Command", border_style="magenta"))
    try:
        return Confirm.ask("Execute this command in terminal?", default=False)
    except (EOFError, KeyboardInterrupt):
        return False


def print_cli_help():
    console.print(
        "Type a question or coding task and press Enter.\n"
        "The agent reads this workspace and its subfolders as needed.\n"
        "!command    Run a shell command in the workspace (for example, !pwd or !ls)\n"
        "/help       Show this help\n"
        "/clear      Clear the screen\n"
        "/exit       Exit the agent\n"
        "Shell commands run separately; !cd does not change the session workspace.",
        markup=False,
    )


async def run_interactive_cli(config: Config, initial_prompt: str = None):
    print_banner()
    console.print(f"[dim]Endpoint:[/dim]       [cyan]{config.openai_base_url}[/cyan]")
    console.print(f"[dim]Model:[/dim]          [green]{config.model_name}[/green]")
    console.print(f"[dim]Prompt Preset:[/dim]  [yellow]{config.model_family}[/yellow]")
    console.print(f"[dim]Workspace:[/dim]      [white]{Path(config.workspace_dir).resolve()}[/white]\n")

    agent = AgentLoop(
        config=config,
        event_callback=cli_event_handler,
        approval_callback=cli_command_approval
    )

    try:
        if initial_prompt:
            await agent.run(initial_prompt)
            return

        print_cli_help()
        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]local_coder >[/bold cyan]").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q", "/exit", "/quit"):
                    console.print("[dim]Goodbye![/dim]")
                    break
                if user_input.lower() in ("help", "/help"):
                    print_cli_help()
                    continue
                if user_input.lower() in ("clear", "/clear"):
                    console.clear()
                    print_banner()
                    continue
                if user_input.startswith("!"):
                    command = user_input[1:].strip()
                    if command:
                        result = await run_command(config.workspace_dir, command)
                        console.print(Panel(Text(result), title="Shell output"))
                        agent.history.append({
                            "role": "user",
                            "content": f"I ran this shell command: {command}\nOutput:\n{result}",
                        })
                    continue

                await agent.run(user_input)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Session ended.[/dim]")
                break
    finally:
        await agent.llm_client.close()


def main():
    parser = argparse.ArgumentParser(description="LocalCoder - Autonomous Coding Agent for Local LLMs")
    parser.add_argument("--url", "-u", type=str, help="LLM API base URL (mapped to the request URL in agent.py)")
    parser.add_argument("--model", "-m", type=str, help="LLM model name")
    parser.add_argument("--family", "-f", type=str, help="Model family preset (qwen, deepseek, codestral, generic)")
    parser.add_argument("--api-key", "-k", type=str, help="API Key")
    parser.add_argument("--auto-approve", "-y", action="store_true", help="Auto approve shell commands")
    parser.add_argument("--no-checkpoint", action="store_true", help="Disable automatic git checkpoints")
    parser.add_argument("--workspace", "-w", type=str, help="Workspace directory (defaults to the current folder or WORKSPACE_DIR)")
    parser.add_argument("--prompt", "-p", type=str, help="Run a single prompt and exit")
    parser.add_argument("--web", action="store_true", help="Launch FastAPI Web UI server")
    parser.add_argument("--port", type=int, help="Web UI port")

    args = parser.parse_args()

    config = Config()
    if args.url:
        config.openai_base_url = args.url
    if args.model:
        config.model_name = args.model
    if args.family:
        config.model_family = args.family
    if args.api_key:
        config.openai_api_key = args.api_key
    if args.auto_approve:
        config.auto_approve_commands = True
    if args.no_checkpoint:
        config.auto_checkpoint = False
    if args.workspace:
        config.workspace_dir = args.workspace
    if args.port:
        config.server_port = args.port

    workspace = Path(config.workspace_dir).expanduser().resolve()
    if not workspace.is_dir():
        parser.error(f"Workspace is not a directory: {workspace}")
    config.workspace_dir = str(workspace)

    if args.web:
        from backend.server import start_server
        start_server(config)
    else:
        asyncio.run(run_interactive_cli(config, args.prompt))


if __name__ == "__main__":
    main()
