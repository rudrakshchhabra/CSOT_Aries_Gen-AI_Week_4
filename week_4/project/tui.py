from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual import work

import week_4.project.agent as agent

class TUIAgent(agent.Agent):
    def __init__(self, session_id: str = None):
        super().__init__(session_id)
        self.app = ResearchApp(self)

    def run(self) -> None:
        self.app.run()

    def _emit(self, event: str, **data) -> None:
        if event == "tool_call":
            self.app.log_tool(data.get("name"), data.get("args"))

class ResearchApp(App):
    TITLE = "Research Desk"
    CSS = """
    Screen { layout: vertical; }
    RichLog { height: 1fr; border: solid $primary; padding: 0 1; }
    Input { dock: bottom; height: 3; }
    """

    def __init__(self, agent_instance):
        super().__init__()
        self.agent = agent_instance

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", wrap=True, markup=True)
        yield Input(id="chat_input", placeholder="Ask the Research Desk...")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write(f"[bold green]Session Initialized:[/bold green] {self.agent.session_id}\n")
        self.query_one(Input).focus()

    def log_tool(self, tool_name: str, args: str) -> None:
        try:
            self.call_from_thread(
                self.query_one("#log", RichLog).write, 
                f"[bold magenta]Invoking Tool:[/bold magenta] {tool_name}"
            )
        except Exception:
            pass 

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text: 
            return
        
        inp = self.query_one(Input)
        inp.clear()
        inp.disabled = True 

        log = self.query_one('#log', RichLog)
        log.write(f"\n[bold cyan][You][/bold cyan] {user_text}")
        log.write("[dim]Agent is thinking...[/dim]")

        self.process_chat(user_text)

    @work(thread=True)
    def process_chat(self, user_text: str) -> None:
        try:
            response = self.agent.chat(user_text)
            self.call_from_thread(self.display_response, response)
        except Exception as e:
            self.call_from_thread(self.display_response, f"[red]Error: {str(e)}[/red]")

    def display_response(self, response_text: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(f"[bold green][Agent][/bold green]\n{response_text}\n")
        
        inp = self.query_one(Input)
        inp.disabled = False 
        inp.focus()