from typing import Dict, Any
from .file_tools import read_file, write_file, edit_file, list_dir, delete_file, create_directory
from .terminal_tools import run_command
from .code_tools import grep_search, file_tree
from .git_tools import git_status, create_checkpoint, rollback_checkpoint, git_diff
from .patch_tools import apply_patch
from .process_tools import start_background_command, read_process_logs, stop_background_process, list_background_processes
from .ast_tools import check_syntax, inspect_symbols

OPENAI_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file in the workspace with optional start/end line bounds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                    "start_line": {"type": "integer", "description": "Optional start line number"},
                    "end_line": {"type": "integer", "description": "Optional end line number"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file with full contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to target file"},
                    "content": {"type": "string", "description": "Full file content to write"},
                    "overwrite": {"type": "boolean", "description": "Whether to overwrite existing file"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit an existing file by replacing an exact snippet with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to target file"},
                    "target_content": {"type": "string", "description": "Exact text substring to replace"},
                    "replacement_content": {"type": "string", "description": "Replacement text substring"}
                },
                "required": ["path", "target_content", "replacement_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply patch using Search/Replace blocks (<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE) or unified diff.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to target file"},
                    "patch_content": {"type": "string", "description": "Search/Replace block patch content"}
                },
                "required": ["path", "patch_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a bash / terminal command in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command string to execute"},
                    "cwd": {"type": "string", "description": "Subdirectory relative to workspace (default '.')"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and subdirectories at a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default '.')"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Grep search for text pattern or regex across workspace files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text pattern or regex"},
                    "search_path": {"type": "string", "description": "Path to search within"},
                    "is_regex": {"type": "boolean", "description": "Whether query is regex"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_tree",
            "description": "Generate a visual directory tree structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Root path for tree"},
                    "max_depth": {"type": "integer", "description": "Max depth level"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Check current git working tree status.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_checkpoint",
            "description": "Stage all workspace changes and commit a git checkpoint snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Checkpoint description message"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_checkpoint",
            "description": "Rollback workspace changes to previous checkpoint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commit_hash": {"type": "string", "description": "Optional commit hash (default HEAD~1)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Inspect uncommitted git diffs in workspace.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_background_command",
            "description": "Start a long-running shell command in the background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command string to run in background"},
                    "cwd": {"type": "string", "description": "Subdirectory path"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_process_logs",
            "description": "Read recent stdout/stderr output from a background process.",
            "parameters": {
                "type": "object",
                "properties": {
                    "process_id": {"type": "string", "description": "Background process ID"},
                    "lines": {"type": "integer", "description": "Number of log lines"}
                },
                "required": ["process_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_background_process",
            "description": "Terminate a background process.",
            "parameters": {
                "type": "object",
                "properties": {
                    "process_id": {"type": "string", "description": "Background process ID"}
                },
                "required": ["process_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_background_processes",
            "description": "List all active and recent background processes.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_syntax",
            "description": "Check Python or Bash syntax without running code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_symbols",
            "description": "Inspect Python AST classes, functions, methods, imports.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to Python file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spawn_subagent",
            "description": "Delegate a sub-task to an isolated child coding subagent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Goal prompt for subagent"},
                    "role": {"type": "string", "description": "Role label for subagent"}
                },
                "required": ["goal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": ["path"]
            }
        }
    }
]


async def execute_tool(workspace_dir: str, tool_name: str, args: Dict[str, Any], config_ref=None) -> str:
    """Dispatches tool execution to the respective Python handler."""
    if tool_name == "read_file":
        return read_file(workspace_dir, args.get("path", ""), args.get("start_line"), args.get("end_line"))
    elif tool_name == "write_file":
        return write_file(workspace_dir, args.get("path", ""), args.get("content", ""), args.get("overwrite", True))
    elif tool_name == "edit_file":
        return edit_file(workspace_dir, args.get("path", ""), args.get("target_content", ""), args.get("replacement_content", ""))
    elif tool_name == "apply_patch":
        return apply_patch(workspace_dir, args.get("path", ""), args.get("patch_content", ""))
    elif tool_name == "run_command":
        return await run_command(workspace_dir, args.get("command", ""), args.get("cwd", "."), int(args.get("timeout", 60)))
    elif tool_name == "list_dir":
        return list_dir(workspace_dir, args.get("path", "."))
    elif tool_name == "grep_search":
        return grep_search(workspace_dir, args.get("query", ""), args.get("search_path", "."), args.get("is_regex", False))
    elif tool_name == "file_tree":
        return file_tree(workspace_dir, args.get("path", "."), int(args.get("max_depth", 3)))
    elif tool_name == "git_status":
        return await git_status(workspace_dir)
    elif tool_name == "create_checkpoint":
        return await create_checkpoint(workspace_dir, args.get("message", "Checkpoint"))
    elif tool_name == "rollback_checkpoint":
        return await rollback_checkpoint(workspace_dir, args.get("commit_hash"))
    elif tool_name == "git_diff":
        return await git_diff(workspace_dir)
    elif tool_name == "start_background_command":
        return await start_background_command(workspace_dir, args.get("command", ""), args.get("cwd", "."))
    elif tool_name == "read_process_logs":
        return read_process_logs(args.get("process_id", ""), int(args.get("lines", 50)))
    elif tool_name == "stop_background_process":
        return await stop_background_process(args.get("process_id", ""))
    elif tool_name == "list_background_processes":
        return list_background_processes()
    elif tool_name == "check_syntax":
        return await check_syntax(workspace_dir, args.get("path", ""))
    elif tool_name == "inspect_symbols":
        return inspect_symbols(workspace_dir, args.get("path", ""))
    elif tool_name == "spawn_subagent":
        if config_ref:
            from ..subagent import spawn_subagent
            return await spawn_subagent(config_ref, args.get("goal", ""), args.get("role", "Coding Subagent"))
        return "Error: Subagent spawning unavailable without agent config reference."
    elif tool_name == "delete_file":
        return delete_file(workspace_dir, args.get("path", ""))
    elif tool_name == "create_directory":
        return create_directory(workspace_dir, args.get("path", ""))
    else:
        return f"Error: Unknown tool '{tool_name}'."
