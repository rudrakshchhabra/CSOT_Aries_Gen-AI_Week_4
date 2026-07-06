import ast 
import os
import re

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
MAX_GREP_RESULTS = 50
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

def resolve_path(path: str) -> str | None:
    abs_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, path))
    if not abs_path.startswith(os.path.abspath(WORKSPACE_ROOT)):
        return None
    return abs_path

def grep(
        pattern: str,
        path: str = ".",
        case_sensitive: bool = False,
        max_results: int = MAX_GREP_RESULTS
) -> dict:
    target_dir = resolve_path(path)
    if not target_dir:
        return {"error": "blocked: path escapes the workspace"}
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {str(e)}"}
    
    matches = []
    total_matches = 0

    if os.path.isfile(target_dir):
        files_to_search = [target_dir]
    elif os.path.isdir(target_dir):
        files_to_search = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                files_to_search.append(os.path.join(root, f))
    else:
        return {"error": f"path not found: {path}"}
    
    for filepath in files_to_search:
        try:
            with open(filepath, 'r', encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        total_matches += 1
                        if len(matches) < max_results:
                            rel_path = os.path.relpath(filepath, WORKSPACE_ROOT).replace("\\", "/")
                            matches.append({
                                "file": rel_path,
                                "line": line_num,
                                "text": line.strip()
                            })
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
            
    return {
        "matches": matches,
        "truncated": total_matches > max_results,
        "total_matches": total_matches
    }

def list_definitions(path: str) -> dict:
    resolved = resolve_path(path)
    if not resolved:
        return {"error": "blocked: path escapes the workspace"}
    if not os.path.isfile(resolved):
        return {"error": f"File not found: {path}"}
    
    try:
        with open(resolved, 'r', encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"error": f"SyntaxError: {str(e)} - file might not be valid Python"}
    except Exception as e:
        return {"error": str(e)}
    
    class DefinitionVisitor(ast.NodeVisitor):
        def __init__(self):
            self.definitions = []
            
        def visit_FunctionDef(self, node):
            self.definitions.append({
                "kind": "function",
                "name": node.name,
                "line": getattr(node, "lineno", 0),
                "end_line": getattr(node, "end_lineno", 0)
            })
            self.generic_visit(node)
            
        def visit_AsyncFunctionDef(self, node):
            self.definitions.append({
                "kind": "async function",
                "name": node.name,
                "line": getattr(node, "lineno", 0),
                "end_line": getattr(node, "end_lineno", 0)
            })
            self.generic_visit(node)
            
        def visit_ClassDef(self, node):
            self.definitions.append({
                "kind": "class",
                "name": node.name,
                "line": getattr(node, "lineno", 0),
                "end_line": getattr(node, "end_lineno", 0)
            })
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.definitions.append({
                        "kind": "method",
                        "name": child.name,
                        "line": getattr(child, "lineno", 0),
                        "end_line": getattr(child, "end_lineno", 0) 
                    })
            self.generic_visit(node)
            
    visitor = DefinitionVisitor()
    visitor.visit(tree)
    return {"definitions": visitor.definitions}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search file contents for a pattern across the workspace. "
                "Use this before read_file when you don't already know which "
                "files you need."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text or regex to search for."
                    },
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to search, default workspace root."
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Default false."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": f"Cap on matches returned. Default {MAX_GREP_RESULTS}.",
                    }
                },
                "required": ["pattern"],
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_definitions",
            "description": (
                "List the functions and classes declared in a Python file, "
                "with line numbers, without reading the whole file. Use this "
                "right after grep to decide which match is worth reading in "
                "full with read_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to a Python file."
                    },
                },
                "required": ["path"],
            }
        }
    }
]

if __name__ == "__main__":
    print("Searching for top-level function definitions ('def '):")
    
    result = grep("def ", max_results=10)
    print(result)
    
    if result and result.get("matches"):
        first_file = result["matches"][0]["file"]
        print(f"\nOutline of {first_file}:")
        print(list_definitions(first_file))