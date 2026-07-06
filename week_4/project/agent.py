import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone
from openai import OpenAI
from dotenv import load_dotenv

# Import tools
import tools.web as web
import tools.files as files
import tools.papers as papers
import tools.exec as exec_tools
import tools.search as search
import tools.plan as plan

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

MODEL = "openrouter/free"
MAX_ITERATIONS = 15
SESSIONS_DIR = ".agent/sessions"

MASTER_TOOLS = (
    files.FILE_TOOLS + 
    exec_tools.TOOLS + 
    search.TOOLS + 
    plan.TOOLS +
    [] 
)

def build_system_prompt() -> str:
    prompt = "You are Code Scout, an autonomous software engineering agent."
    if os.path.exists("AGENTS.md"):
        with open("AGENTS.md", "r", encoding="utf-8") as f:
            prompt += f"\n\n{f.read()}"
    return prompt

def save_session(session_id: str, messages: list, title: str = "Untitled") -> None:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    
    data = {
        "id": session_id, 
        "title": title, 
        "created_at": now, 
        "updated_at": now, 
        "messages": messages
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_session(session_id: str) -> dict:
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class Agent:
    def __init__(self, session_id: str = None):
        self.session_id = session_id or uuid.uuid4().hex[:8]
        session_data = load_session(self.session_id)
        self.messages = session_data.get("messages", []) if session_data else [{"role": "system", "content": build_system_prompt()}]

    def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        save_session(self.session_id, self.messages)
        return self._run_loop()

    def run_once(self, prompt: str) -> str:
        return self.chat(prompt)

    def _run_loop(self) -> str:
        for _ in range(MAX_ITERATIONS):
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.messages,
                tools=MASTER_TOOLS
            )
            
            assistant_msg = response.choices[0].message
            # CONVERT TO DICT TO PREVENT JSON SERIALIZATION ERRORS
            self.messages.append(assistant_msg.model_dump())
            save_session(self.session_id, self.messages)

            if assistant_msg.tool_calls:
                for tool_call in assistant_msg.tool_calls:
                    tool_output = self.dispatch(tool_call)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": tool_output
                    })
                save_session(self.session_id, self.messages)
                continue
            
            # Logic check for remaining todos
            todos_state = plan.get_todos()
            if isinstance(todos_state, dict) and "todos" in todos_state:
                unfinished = [t for t in todos_state["todos"] if t["status"] in ["pending", "in_progress"]]
                if unfinished:
                    self.messages.append({"role": "user", "content": "SYSTEM: Continue working on remaining todo items."})
                    continue
            return assistant_msg.content or ""
        return "Max iterations reached."

    def dispatch(self, tool_call) -> str:
        name = tool_call.function.name
        
        # Safe JSON decoding to prevent crashes from malformed LLM tool arguments
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return "Error: Malformed JSON arguments in tool call. Please ensure your syntax and string escaping are valid JSON and try again."
        
        try:
            if name == "run_command": res = exec_tools.run_command(**args)
            elif name == "grep": res = search.grep(**args)
            elif name == "list_definitions": res = search.list_definitions(**args)
            elif name == "add_todos": res = plan.add_todos(**args)
            elif name == "get_todos": res = plan.get_todos(**args)
            elif name == "mark_todo": res = plan.mark_todo(**args)
            elif name == "read_file": res = files.read_file(**args)
            elif name == "write_file": res = files.write_file(**args)
            elif name == "edit_file": res = files.edit_file(**args)
            elif name == "list_files": res = files.list_files(**args)
            else: res = {"error": f"Unknown tool: {name}"}
        except Exception as e: 
            res = {"error": f"Execution error in {name}: {str(e)}"}
            
        return json.dumps(res) if not isinstance(res, str) else res

class REPLAgent(Agent):
    def run(self) -> None:
        while True:
            try:
                inp = input("\n> ")
                if inp.strip() in ["/quit", "/exit"]: 
                    break
                if not inp.strip(): 
                    continue
                print(self.chat(inp))
            except (KeyboardInterrupt, EOFError):
                break

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?")
    args = parser.parse_args()
    agent = REPLAgent()
    if args.prompt: 
        print(agent.run_once(args.prompt))
    else: 
        agent.run()

if __name__ == "__main__":
    main()