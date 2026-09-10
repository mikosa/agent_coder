import os
import re
from pathlib import Path


def grep_search(workspace_dir: str, query: str, search_path: str = ".", is_regex: bool = False) -> str:
    """Searches for pattern/string within files in search_path."""
    try:
        base_dir = Path(workspace_dir).resolve()
        target_dir = (base_dir / search_path).resolve() if not Path(search_path).is_absolute() else Path(search_path).resolve()

        if not target_dir.exists():
            return f"Error: Search path '{search_path}' does not exist."

        results = []
        pattern = re.compile(query if is_regex else re.escape(query), re.IGNORECASE)

        # Ignore patterns
        ignored_dirs = {".git", ".venv", "__pycache__", "node_modules", ".idea", ".vscode", "dist", "build"}

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                file_path = Path(root) / file
                # Skip binary or huge files
                if file_path.stat().st_size > 1_000_000:
                    continue
                try:
                    rel_path = file_path.relative_to(base_dir)
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append(f"{rel_path}:{line_num}: {line.strip()}")
                                if len(results) >= 100:
                                    results.append("... [Reached max 100 results match cap]")
                                    break
                except Exception:
                    continue
                if len(results) >= 100:
                    break

        if not results:
            return f"No matches found for query: '{query}' in '{search_path}'."

        return f"Found {len(results)} matches for '{query}':\n" + "\n".join(results)
    except Exception as e:
        return f"Error during grep search: {str(e)}"


def file_tree(workspace_dir: str, path: str = ".", max_depth: int = 3) -> str:
    """Generates visual text representation of project file tree."""
    try:
        base_dir = Path(workspace_dir).resolve()
        target_dir = (base_dir / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()

        if not target_dir.exists():
            return f"Error: Path '{path}' does not exist."

        ignored = {".git", ".venv", "__pycache__", "node_modules", ".idea", ".vscode", "dist", "build"}
        tree_str = [f"{target_dir.name}/"]

        def _build_tree(dir_path: Path, prefix: str = "", current_depth: int = 1):
            if current_depth > max_depth:
                tree_str.append(f"{prefix}└── ... (max depth reached)")
                return

            entries = [e for e in sorted(dir_path.iterdir()) if e.name not in ignored]
            count = len(entries)

            for i, entry in enumerate(entries):
                is_last = (i == count - 1)
                connector = "└── " if is_last else "├── "
                next_prefix = prefix + ("    " if is_last else "│   ")

                if entry.is_dir():
                    tree_str.append(f"{prefix}{connector}{entry.name}/")
                    _build_tree(entry, next_prefix, current_depth + 1)
                else:
                    tree_str.append(f"{prefix}{connector}{entry.name}")

        _build_tree(target_dir)
        return "\n".join(tree_str)
    except Exception as e:
        return f"Error building file tree: {str(e)}"
