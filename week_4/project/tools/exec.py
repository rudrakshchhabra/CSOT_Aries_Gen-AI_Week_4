import os
import shlex
import subprocess

WORKSPACE_ROOT = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "."))
TIMEOUT_DEFAULT = 10
MAX_OUTPUT_CHARS = 8_000

READ_ONLY_PREFIXES = (
    "grep", "find", "ls", "cat", "head", "tail", "wc", "git log", "git diff", "git status", "git blame", "git show", "pytest", "python -m pytest", "ruff", "flake8", "mypy",
)

DESTRUCTIVE_PATTERNS = (
    "rm", "mv", ">", ">>", "git commit", "git push", "git checkout --", "pip install", "npm install", "curl", "sudo", "chmod",
)

def paths_within_sandbox(command: str, workspace_root: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    for token in tokens:
        if token.startswith("-"):
            continue
        abs_path = os.path.abspath(os.path.join(workspace_root, token))
        if not abs_path.startswith(os.path.abspath(workspace_root)):
            return False
    return True

def classify_command(command: str) -> str:
    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern in command:
            return "ask"
    command_stripped = command.strip()
    for prefix in READ_ONLY_PREFIXES:
        if command_stripped.startswith(prefix):
            return "read_only"
    return "ask"

def run_command(command: str, cwd: str = WORKSPACE_ROOT, timeout: int = TIMEOUT_DEFAULT) -> dict:
    if not paths_within_sandbox(command, cwd):
        return {"error": "blocked: command references a path outside the workspace"}
    if classify_command(command) != "read_only":
        print("\n\033[93mWARNING: the agent wants to run a command that may write, delete or install:\033[0m")
        print(f"    {command}")
        approved = input("Allow this command? [y/N]: ").strip().lower() == "y"
        if not approved:
            return {"error": "blocked: user did not approve this command"}
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
        truncated = False

        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + "\n... [TRUNCATED]"
            truncated = True
        
        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "truncated": truncated
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout} seconds"}
    except Exception as e:
        return {"error": f"execution failed: {str(e)}"}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a shell command in the workspace and return its output. "
                "Use this to search (grep/find), inspect history (git log/diff), "
                "run tests, or make a change. Read-only commands run immediately. "
                "Anything that writes, deletes or installs will pause and ask the "
                "human operator for approval - expect that pause, it's not a failure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Seconds before the command is killed. Default {TIMEOUT_DEFAULT}.",
                    }
                },
                "required": ["command"],
            }
        }
    }
]

if __name__ == "__main__":
    print("Read-only command (Testing Python instead of Git):")
    
    print(run_command("python --version"))

    print("\nDestructive command (Inside the sandbox):")
    print(run_command("rm -rf fake_deleted_file.txt"))