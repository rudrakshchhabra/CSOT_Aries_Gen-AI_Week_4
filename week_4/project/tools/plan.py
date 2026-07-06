import uuid
import json

_todos = {}

VALID_STATUSES = ["pending", "in_progress", "completed", "blocked"]

def add_todos(tasks: list) -> dict:
    added_ids = []
    for task in tasks:
        if not all(k in task for k in ("title", "description", "verification_method")):
            return {"error": "blocked: every todo must include a title, description and verification_method."}
        task_id = str(uuid.uuid4())[:8]
        _todos[task_id] = {
            "id": task_id,
            "title": task["title"],
            "description": task["description"],
            "verification_method": task["verification_method"],
            "status": "pending",
            "evidence": None
        }
        added_ids.append(task_id)
    return get_todos()

def get_todos()-> dict:
    if not _todos:
        return {"content": "The todo list is currently empty."}
    return {"todos": list(_todos.values())}

def mark_todo(todo_id: str, status: str, evidence: str = "") -> dict:
    if todo_id not in _todos:
        return {"error": f"blocked: todo_id '{todo_id}' does not exist."}
    if status not in VALID_STATUSES:
        return {"error": f"blocked: invalid status. Must be one of {VALID_STATUSES}."}
    if status == "completed":
        if not evidence or not evidence.strip():
            return {
                "error": (
                    "cannot mark completed: you must provide concrete evidence "
                    "(e.g., 'pytest exit code 0' or command output). Fix the issue, "
                    "run the verification command, and try again."
                )
            }
    _todos[todo_id]["status"] = status
    if evidence:
        _todos[todo_id]["evidence"] = evidence
    return get_todos()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_todos",
            "description": (
                "Record your task list for this request. Call this BEFORE starting "
                "multi-step work to write your plan. Every task MUST have a concrete "
                "verification_method (e.g., 'run pytest and get exit code 0')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string"
                                },
                                "description": {
                                    "type": "string"
                                },
                                "verification_method": {
                                    "type": "string",
                                    "description": "Exactly how you will prove this is done."
                                }
                            },
                            "required": ["title", "description", "verification_method"]
                        }
                    }
                },
                "required": ["tasks"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_todos",
            "description": "Read the current state of your task list.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mark_todo",
            "description": (
                "Update the status of a task. If marking as 'completed', you MUST "
                "provide the 'evidence' parameter citing the exact exit code or output "
                "from run_command that proves the fix worked. Do NOT batch updates to the end."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "todo_id": {
                        "type": "string"
                    },
                    "status": {
                        "type": "string",
                        "enum": VALID_STATUSES
                    },
                    "evidence": {
                        "type": "string",
                        "description": "Required if status is 'completed'. The proof (e.g., exit code 0)."
                    }
                },
                "required": ["todo_id", "status"]
            }
        }
    }
]

if __name__ == "__main__":
    print("\n--- 1. Adding Todos ---")
    intial_plan = add_todos([
        {
        "title": "Fix Auth Bug",
        "description": "Locate and patch the null pointer in auth.py",
        "verification_method": "run 'pytest tests/test_auth.py' and get exit code 0"
        }
    ])
    print(json.dumps(intial_plan, indent=2))
    task_id = intial_plan["todos"][0]["id"]
    print("\n-- 2. Marking In Progress ---")
    print(json.dumps(mark_todo(task_id, "in_progress"), indent=2))
    print("\n-- 3. Attempting Completion WITHOUT Evidence (Should Fail) ---")
    fail_result = mark_todo(task_id, "completed")
    print(json.dumps(fail_result, indent=2))
    print("\n--- 4. Attempting Completion WITH Evidence (Should Succeed) ---")
    success_result = mark_todo(task_id, "completed", evidence="pytest tests/test_auth.py returned exit code 0")
    print(json.dumps(success_result, indent=2))

