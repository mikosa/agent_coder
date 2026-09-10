import os
from pathlib import Path
from typing import Optional, Dict, Any, List


def _resolve_path(workspace_dir: str, rel_or_abs_path: str) -> Path:
    base = Path(workspace_dir).resolve()
    target = Path(rel_or_abs_path)
    if not target.is_absolute():
        target = base / target
    target = target.resolve()
    return target


def read_file(workspace_dir: str, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Reads content from a file within the workspace."""
    try:
        file_path = _resolve_path(workspace_dir, path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist."
        if not file_path.is_file():
            return f"Error: Path '{path}' is not a regular file."

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if start_line is not None or end_line is not None:
            start = (start_line - 1) if start_line and start_line > 0 else 0
            end = end_line if end_line and end_line <= total_lines else total_lines
            lines = lines[start:end]
            header = f"--- Reading lines {start + 1}-{end} of {total_lines} from {path} ---\n"
        else:
            header = f"--- Content of {path} ({total_lines} lines) ---\n"

        # Format with line numbers for easy editing
        start_idx = (start_line if start_line and start_line > 0 else 1)
        numbered_lines = [f"{start_idx + i:4d} | {line}" for i, line in enumerate(lines)]
        return header + "".join(numbered_lines)
    except Exception as e:
        return f"Error reading file '{path}': {str(e)}"


def write_file(workspace_dir: str, path: str, content: str, overwrite: bool = True) -> str:
    """Writes content to a file. Creates parent directories automatically."""
    try:
        file_path = _resolve_path(workspace_dir, path)
        if file_path.exists() and not overwrite:
            return f"Error: File '{path}' already exists and overwrite is set to False."

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        line_count = len(content.splitlines())
        return f"Successfully wrote {line_count} lines to '{path}'."
    except Exception as e:
        return f"Error writing to file '{path}': {str(e)}"


def edit_file(workspace_dir: str, path: str, target_content: str, replacement_content: str) -> str:
    """Replaces exact target_content snippet with replacement_content in a file."""
    try:
        file_path = _resolve_path(workspace_dir, path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist."

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            full_content = f.read()

        if target_content not in full_content:
            return f"Error: Could not find target_content in '{path}'. Please ensure exact matching including whitespace."

        occurrences = full_content.count(target_content)
        if occurrences > 1:
            return f"Error: Found {occurrences} occurrences of target_content in '{path}'. Provide more context lines to ensure uniqueness."

        new_content = full_content.replace(target_content, replacement_content, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Successfully edited '{path}' (replaced 1 block)."
    except Exception as e:
        return f"Error editing file '{path}': {str(e)}"


def list_dir(workspace_dir: str, path: str = ".") -> str:
    """Lists files and directories at path."""
    try:
        dir_path = _resolve_path(workspace_dir, path)
        if not dir_path.exists():
            return f"Error: Directory '{path}' does not exist."
        if not dir_path.is_dir():
            return f"Error: Path '{path}' is not a directory."

        entries = sorted(os.listdir(dir_path))
        result = [f"Contents of directory '{path}':"]
        for entry in entries:
            full = dir_path / entry
            if full.is_dir():
                result.append(f"  [DIR]  {entry}/")
            else:
                size = full.stat().st_size
                result.append(f"  [FILE] {entry} ({size} bytes)")

        return "\n".join(result)
    except Exception as e:
        return f"Error listing directory '{path}': {str(e)}"


def delete_file(workspace_dir: str, path: str) -> str:
    """Deletes a file."""
    try:
        file_path = _resolve_path(workspace_dir, path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist."
        if file_path.is_dir():
            return f"Error: Path '{path}' is a directory. Use custom terminal command to remove non-empty directory."
        file_path.unlink()
        return f"Successfully deleted file '{path}'."
    except Exception as e:
        return f"Error deleting file '{path}': {str(e)}"


def create_directory(workspace_dir: str, path: str) -> str:
    """Creates a directory structure."""
    try:
        dir_path = _resolve_path(workspace_dir, path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return f"Successfully created directory '{path}'."
    except Exception as e:
        return f"Error creating directory '{path}': {str(e)}"
