import os
import glob as glob_module

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
MAX_READ_CHARS = 12_000

def resolve_path(path: str) -> str:
    full_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, path))
    if not full_path.startswith(WORKSPACE_ROOT):
        raise ValueError(f"Security Alert: Path '{path}' attempts to escape workspace sandbox.")
    return full_path

def read_file(path: str, start_line: int = 1, read_lines: int = 200) -> dict:
    try:
        real_path = resolve_path(path)
        if not os.path.exists(real_path):
            return {"error": f"File not found: {path}"}
        with open(real_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        total_lines = len(lines)
        start_idx = max(0, start_line-1)
        end_idx = min(total_lines, start_idx + read_lines)
        sliced_lines = lines[start_idx:end_idx]
        output_blocks = []
        current_chars = 0
        truncated = False
        for idx, line in enumerate(sliced_lines):
            actual_line_num = start_idx + idx + 1
            formatted_line = f"{actual_line_num:4d} {line}"
            if current_chars + len(formatted_line) > MAX_READ_CHARS:
                truncated = True
                break
            output_blocks.append(formatted_line)
            current_chars += len(formatted_line)
        return {
            "content": "".join(output_blocks),
            "metadata": {
                "total_lines": total_lines,
                "start_line": start_line,
                "lines_returned": len(output_blocks),
                "has_more": (end_idx < total_lines) or truncated
            }
        }
    except Exception as e:
        return {"error": str(e)}

def write_file(path: str, content: str) -> dict:
    # WHAT: The Lesson 1 Safety Gate applied to writing files.
    # HOW: Prompts the human operator in the terminal and waits for a strict 'y' input.
    # WHY: Fulfills the Week 4 requirement that any tool altering the codebase must explicitly pause and request human approval before executing.
    print(f"\n\033[93mWARNING: The agent wants to WRITE a new file at: {path}\033[0m")
    if input("Allow this write? [y/N]: ").strip().lower() != 'y':
        return {"error": "blocked: user did not approve file write."}
        
    try:
        real_path = resolve_path(path)
        os.makedirs(os.path.dirname(real_path), exist_ok=True)

        with open(real_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return {"content": f"Successfully wrote file contents straight to: '{path}'"}
    except Exception as e:
        return {"error": str(e)}
    
def edit_file(path: str, operation: str, start_line: int, end_line: int | None = None, content: str| None = None) -> dict:
    # WHAT: The Lesson 1 Safety Gate applied to editing files.
    # HOW: Notifies the user of the specific operation (replace, delete, append) and target path, waiting for 'y'.
    # WHY: Ensures the model cannot stealthily overwrite or delete existing code without your explicit say-so.
    print(f"\n\033[93mWARNING: The agent wants to {operation.upper()} in file: {path}\033[0m")
    if input("Allow this edit? [y/N]: ").strip().lower() != 'y':
        return {"error": "blocked: user did not approve file edit."}
        
    try:
        real_path = resolve_path(path)
        if not os.path.exists(real_path):
            return {"error": f"File target not found: {path}"}
        with open(real_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        original_line_count = len(lines)
        start_idx = start_line-1
        
        def clean_content(text: str):
            # FIXED -> Changed 'fo' to 'for'
            return [l+"\n" if not l.endswith("\n") else l for l in text.splitlines()]
            
        if operation == "replace":
            if end_line is None or content is None:
                return {"error": "Operation 'replace' required explicit 'end_line' and 'content' targets."}
            lines[start_idx:end_line] = clean_content(content)
        elif operation == "delete":
            if end_line is None:
                return {"error": "Operation 'delete' requires explicit 'end_line' designation."}
            del lines[start_idx:end_line]
        elif operation=='append':
            if content is None:
                return {"error": "Operation 'append' requires explicit 'content' data parameters."}
            insert_idx = max(0, start_line)
            lines[insert_idx:insert_idx] = clean_content(content)
        else:
            return {"error": f"Unsupported file modification operation action: '{operation}'"}
        
        with open(real_path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        
        return {
            "content": f"Surgically applied '{operation}' successfully starting at target coordinates.",
            "diff_preview": f"Original lines total: {original_line_count} -> Updated line volume: {len(lines)}"
        }
    
    except Exception as e:
        return {"error": str(e)}

def list_files(path: str = ".", pattern: str = "*") -> dict:
    try:
        real_base = resolve_path(path)
        full_pattern = os.path.join(real_base, pattern)

        if not os.path.abspath(full_pattern).startswith(WORKSPACE_ROOT):
            return {"error": "Glob syntax parameters violation tracking out of bounds."}
        
        raw_matches = glob_module.glob(full_pattern, recursive = True)
        clean_relative_paths = []
        for match in raw_matches:
            relative = os.path.relpath(match, WORKSPACE_ROOT)
            if not relative.startswith(".."):
                clean_relative_paths.append(relative)
        return {"files": clean_relative_paths}
    except Exception as e:
        return {"error": str(e)}

# WHAT: Tool schemas for the file operations.
# HOW: A JSON array mapping function names to descriptions and expected parameters.
# WHY: Allows `agent.py` to seamlessly import `files.FILE_TOOLS` into the MASTER_TOOLS array.
FILE_TOOLS = [
    {
        "type": "function", 
        "function": {
            "name": "read_file", 
            "description": "Read a file with line numbers appended.", 
            "parameters": {
                "type": "object", 
                "properties": {
                    "path": {"type": "string"}, 
                    "start_line": {"type": "integer"}, 
                    "read_lines": {"type": "integer"}
                }, 
                "required": ["path"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "write_file", 
            "description": "Create a new file.", 
            "parameters": {
                "type": "object", 
                "properties": {
                    "path": {"type": "string"}, 
                    "content": {"type": "string"}
                }, 
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "edit_file", 
            "description": "Surgically edit a file.", 
            "parameters": {
                "type": "object", 
                "properties": {
                    "path": {"type": "string"}, 
                    "operation": {"type": "string", "enum": ["replace", "delete", "append"]}, 
                    "start_line": {"type": "integer"}, 
                    "end_line": {"type": "integer"}, 
                    "content": {"type": "string"}
                }, 
                "required": ["path", "operation", "start_line"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "list_files", 
            "description": "List files in the workspace.", 
            "parameters": {
                "type": "object", 
                "properties": {
                    "path": {"type": "string"}, 
                    "pattern": {"type": "string"}
                }, 
                "required": ["path"]
            }
        }
    }
]