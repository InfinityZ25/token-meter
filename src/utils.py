import re
import threading
import sys
import time
import validators
from rich.panel import Panel
from rich.table import Table
from itertools import cycle
from typing import Dict
from rich.console import Console

console = Console()

# Emojis
ROBOT = "🤖"
GLOBE = "🌐"
CAMERA = "📷"
WRENCH = "🔧"
ROCKET = "🚀"
ERROR = "❌"
SUCCESS = "✅"

# Simple cache for storing webpage content with a size limit
MAX_CACHE_SIZE = 100
url_cache: Dict[str, str] = {}


def extract_code_blocks(text):
    code_blocks = re.findall(r'```(?:python)?(.*?)```', text, re.DOTALL)
    if code_blocks:
        return code_blocks[0].strip()
    return text


def spinner(stop):
    s = cycle(['-', '/', '|', '\\'])
    while not stop.is_set():
        sys.stdout.write(next(s))
        sys.stdout.flush()
        sys.stdout.write('\b')
        time.sleep(0.1)


def edit_code(code: str) -> str:
    console.print(
        "Enter your edits (type 'done' on a new line when finished):", style="bold yellow")
    edited_code = code + "\n"

    while True:
        line = console.input("[cyan]> [/]")
        if line.strip().lower() == 'done':
            break
        edited_code += line + "\n"

    return edited_code


def print_interactive_session_header(model):
    header = Panel(
        f"[bold cyan]Interactive Session with {model}[/]",
        expand=False,
        border_style="bold",
        padding=(1, 1)
    )
    console.print(header)


def print_commands():
    table = Table(show_header=False, expand=False, box=None)
    table.add_column("Emoji", style="cyan", no_wrap=True)
    table.add_column("Command", style="green")
    table.add_column("Description", style="yellow")

    table.add_row("🌐", "/cmd <prompt>",
                  "Web interaction or custom Selenium code")
    table.add_row("📷", "/screenshot",
                  "Take a screenshot of the last visited URL")
    table.add_row("🔧", "/selenium <task>", "Generate custom Selenium code")
    table.add_row("🚀", "exit", "Exit the session")

    commands_panel = Panel(
        table,
        title="[bold]Available Commands[/]",
        expand=False,
        border_style="bold",
        padding=(1, 1)
    )
    console.print(commands_panel)


def print_statistics(model, prompt, tokens, eval_time, speed, total_duration):
    stats = Table(show_header=False, expand=False, box=None)
    stats.add_column("Stat", style="cyan", no_wrap=True)
    stats.add_column("Value", style="yellow")

    stats.add_row("Model", model)
    stats.add_row("Input", (prompt[:47] + "...")
                  if len(prompt) > 50 else prompt)
    stats.add_row("Tokens", str(tokens))
    stats.add_row("Evaluation Time", f"{eval_time:.2f}s")
    stats.add_row("Speed", f"{speed:.2f} tokens/second")
    stats.add_row("Total Duration", f"{total_duration:.2f}s")

    stats_panel = Panel(
        stats,
        title="[bold]Statistics[/]",
        expand=False,
        border_style="bold",
        padding=(1, 1)
    )
    console.print()  # Add a newline before the statistics
    console.print(stats_panel)
