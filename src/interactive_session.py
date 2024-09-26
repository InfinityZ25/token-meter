import threading
import time

import validators
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from api_client import (generate_selenium_code, get_command_suggestion,
                        measure_tps)
from selenium_utils import execute_temp_script, selenium_web_interaction
from utils import (edit_code, print_commands, print_interactive_session_header,
                   print_statistics, spinner)

console = Console()


def interactive_session(model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> None:
    print_interactive_session_header(model)
    print_commands()

    last_url = None
    last_selenium_code = None
    while True:
        user_input = console.input("[bold green]You:[/] ")
        if user_input.lower() == 'exit':
            console.print("[bold magenta]Goodbye! 🚀[/]")
            break
        elif user_input.lower().startswith('/cmd'):
            cmd_prompt = user_input[5:].strip()
            result = get_command_suggestion(
                cmd_prompt, model, system_prompt_prefix, system_prompt_suffix)

            if validators.url(result):
                console.print(f"Navigating to URL: {
                              result}", style="bold blue")
                stop_event = threading.Event()
                stop_spinner = threading.Thread(
                    target=spinner, args=(stop_event,))
                stop_spinner.start()
                webpage_content = selenium_web_interaction(result)
                stop_event.set()
                stop_spinner.join()
                console.print("Content retrieved:", style="bold cyan")
                console.print(webpage_content, style="yellow")
                last_url = result
            else:
                console.print("Generated custom Selenium code:",
                              style="bold magenta")
                console.print(result, style="cyan")
                last_selenium_code = result
                handle_selenium_code(last_selenium_code)
        elif user_input.lower() == '/screenshot' and last_url:
            console.print(f"Taking screenshot of {
                          last_url}...", style="bold blue")
            stop_event = threading.Event()
            stop_spinner = threading.Thread(target=spinner, args=(stop_event,))
            stop_spinner.start()
            result = selenium_web_interaction(last_url, take_screenshot=True)
            stop_event.set()
            stop_spinner.join()
            console.print("Screenshot result:", style="bold cyan")
            console.print(result, style="yellow")
        elif user_input.lower().startswith('/selenium'):
            selenium_prompt = user_input[9:].strip()
            generated_code = generate_selenium_code(
                selenium_prompt, model, system_prompt_prefix, system_prompt_suffix)
            console.print("Generated Selenium code:", style="bold magenta")
            console.print(generated_code, style="cyan")
            last_selenium_code = generated_code
            handle_selenium_code(last_selenium_code)
        else:
            measure_tps(user_input, model, system_prompt_prefix,
                        system_prompt_suffix)


def handle_selenium_code(code: str) -> None:
    while True:
        action = console.input(
            "[bold yellow]Do you want to (r)un, (e)dit, or (c)ancel this code? [/]").lower()
        if action == 'r':
            console.print("Executing custom Selenium code...",
                          style="bold blue")
            stop_event = threading.Event()
            stop_spinner = threading.Thread(target=spinner, args=(stop_event,))
            stop_spinner.start()
            result = execute_temp_script(code, f"selenium_script_{
                                         int(time.time())}", headless=False)
            stop_event.set()
            stop_spinner.join()
            console.print("Execution result:", style="bold cyan")
            console.print(result, style="yellow")
            break
        elif action == 'e':
            code = edit_code(code)
        elif action == 'c':
            console.print("Code execution cancelled.", style="bold red")
            break
        else:
            console.print(
                "Invalid option. Please choose (r)un, (e)dit, or (c)ancel.", style="bold red")
