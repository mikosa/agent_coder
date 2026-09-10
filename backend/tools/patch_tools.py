import re
from pathlib import Path


def _resolve_path(workspace_dir: str, rel_or_abs_path: str) -> Path:
    base = Path(workspace_dir).resolve()
    target = Path(rel_or_abs_path)
    if not target.is_absolute():
        target = base / target
    return target.resolve()


def apply_search_replace_blocks(full_content: str, patch_content: str) -> str:
    """Applies search/replace blocks in format <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE"""
    pattern = re.compile(
        r"<<<<<<< SEARCH\n([\s\S]*?)\n=======\n([\s\S]*?)\n>>>>>>> REPLACE",
        re.MULTILINE
    )
    blocks = pattern.findall(patch_content)
    if not blocks:
        raise ValueError("No valid Search/Replace blocks found in patch_content.")

    new_content = full_content
    applied_count = 0

    for search_block, replace_block in blocks:
        if search_block in new_content:
            new_content = new_content.replace(search_block, replace_block, 1)
            applied_count += 1
        else:
            # Strip trailing space matching fallback
            search_stripped = "\n".join([line.rstrip() for line in search_block.splitlines()])
            content_stripped = "\n".join([line.rstrip() for line in new_content.splitlines()])
            if search_stripped in content_stripped:
                new_content = content_stripped.replace(search_stripped, replace_block, 1)
                applied_count += 1
            else:
                raise ValueError(f"Could not find SEARCH block in target file:\n{search_block[:200]}...")

    return new_content, applied_count


def apply_patch(workspace_dir: str, path: str, patch_content: str) -> str:
    """Applies a patch (Search/Replace blocks or unified diff) to a file."""
    try:
        file_path = _resolve_path(workspace_dir, path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist for patch application."

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            full_content = f.read()

        # Try Search/Replace blocks first
        if "<<<<<<< SEARCH" in patch_content:
            new_content, count = apply_search_replace_blocks(full_content, patch_content)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Successfully applied {count} Search/Replace block patch(es) to '{path}'."

        # Fallback to direct substring search replace if format simple
        if "=======" in patch_content and ">>>>>>>" not in patch_content:
            parts = patch_content.split("=======")
            if len(parts) == 2:
                search_part, replace_part = parts[0].strip(), parts[1].strip()
                if search_part in full_content:
                    new_content = full_content.replace(search_part, replace_part, 1)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    return f"Successfully applied simple patch block to '{path}'."

        return f"Error: Unrecognized patch format for '{path}'. Use Search/Replace blocks with <<<<<<< SEARCH, =======, >>>>>>> REPLACE."

    except Exception as e:
        return f"Error applying patch to '{path}': {str(e)}"
