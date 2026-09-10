import ast
import asyncio
from pathlib import Path


def _resolve_path(workspace_dir: str, rel_or_abs_path: str) -> Path:
    base = Path(workspace_dir).resolve()
    target = Path(rel_or_abs_path)
    if not target.is_absolute():
        target = base / target
    return target.resolve()


async def check_syntax(workspace_dir: str, path: str) -> str:
    """Validates Python or Bash syntax without executing the code."""
    try:
        file_path = _resolve_path(workspace_dir, path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist for syntax checking."

        suffix = file_path.suffix.lower()

        # Python syntax check using ast
        if suffix in (".py", ".pyw"):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code_content = f.read()

            try:
                ast.parse(code_content, filename=str(file_path))
                return f"✅ Python Syntax Check Passed: '{path}' is valid code."
            except SyntaxError as syn_err:
                return (
                    f"❌ Python Syntax Error in '{path}':\n"
                    f"  Line {syn_err.lineno}, Col {syn_err.offset}: {syn_err.msg}\n"
                    f"  Code: {syn_err.text.strip() if syn_err.text else ''}"
                )

        # Bash / Shell script syntax check using bash -n
        elif suffix in (".sh", ".bash"):
            process = await asyncio.create_subprocess_exec(
                "bash", "-n", str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr_bytes = await process.communicate()
            if process.returncode == 0:
                return f"✅ Bash Syntax Check Passed: '{path}' is valid script."
            else:
                stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
                return f"❌ Bash Syntax Error in '{path}':\n{stderr}"

        else:
            return f"Syntax checker supports .py, .sh, .bash files. Skipping syntax check for '{suffix}' file."

    except Exception as e:
        return f"Error checking syntax for '{path}': {str(e)}"


def inspect_symbols(workspace_dir: str, path: str) -> str:
    """Parses Python AST to list all classes, functions, methods, signatures, and docstrings."""
    try:
        file_path = _resolve_path(workspace_dir, path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist."
        if file_path.suffix.lower() not in (".py", ".pyw"):
            return f"Error: Symbol inspection only supported for Python files (.py)."

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            code_content = f.read()

        tree = ast.parse(code_content, filename=str(file_path))

        symbols = [f"=== AST Symbol Inspection for '{path}' ==="]

        # Imports
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        if imports:
            symbols.append(f"Imports ({len(imports)}): " + ", ".join(imports[:15]))

        # Top-level classes and functions
        class SymbolVisitor(ast.NodeVisitor):
            def __init__(self):
                self.items = []

            def visit_ClassDef(self, node):
                bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                base_str = f"({', '.join(bases)})" if bases else ""
                doc = ast.get_docstring(node)
                doc_first = f" - '{doc.splitlines()[0]}'" if doc else ""
                self.items.append(f"• [CLASS] {node.name}{base_str} (Lines {node.lineno}-{node.end_lineno}){doc_first}")

                # Visit methods inside class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in item.args.args]
                        m_doc = ast.get_docstring(item)
                        m_doc_first = f" - '{m_doc.splitlines()[0]}'" if m_doc else ""
                        self.items.append(f"    └─ [METHOD] {item.name}({', '.join(args)}) (Lines {item.lineno}-{item.end_lineno}){m_doc_first}")

            def visit_FunctionDef(self, node):
                # Top level functions only
                if isinstance(node.parent if hasattr(node, 'parent') else None, ast.Module) or True:
                    args = [a.arg for a in node.args.args]
                    doc = ast.get_docstring(node)
                    doc_first = f" - '{doc.splitlines()[0]}'" if doc else ""
                    self.items.append(f"• [FUNC] {node.name}({', '.join(args)}) (Lines {node.lineno}-{node.end_lineno}){doc_first}")

        visitor = SymbolVisitor()
        # Set parent reference for node
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                visitor.visit_ClassDef(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visitor.visit_FunctionDef(node)

        symbols.extend(visitor.items)

        if len(symbols) == 1:
            symbols.append("No top-level functions or classes found.")

        return "\n".join(symbols)

    except Exception as e:
        return f"Error inspecting symbols in '{path}': {str(e)}"
