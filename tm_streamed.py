import argparse
import json
import sys
import threading
import time
import urllib.parse
from contextlib import contextmanager
from io import BytesIO
from itertools import cycle
from threading import Thread
from typing import Dict

import requests
import validators
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

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


@contextmanager
def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(
        ChromeDriverManager().install()), options=options)
    try:
        yield driver
    finally:
        driver.quit()


def spinner(stop):
    s = cycle(['-', '/', '|', '\\'])
    while not stop.is_set():
        sys.stdout.write(next(s))
        sys.stdout.flush()
        sys.stdout.write('\b')
        time.sleep(0.1)


def measure_tps(prompt: str, model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> None:
    url = "http://localhost:11434/api/generate"

    temp_prompt = f"""
    {system_prompt_prefix}
    ===
    {prompt}
    ===
    {system_prompt_suffix}
    """

    payload = {"model": model, "prompt": temp_prompt, "stream": True}

    start_time = time.time()
    response = requests.post(url, json=payload, stream=True)

    total_tokens = 0
    response_text = ""
    eval_duration = None

    # Changed to end with a space
    console.print("Output:", style="bold", end=" ")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                console.print(data['response'], end="")
                response_text += data['response']
            if 'done' in data and data['done']:
                total_tokens = data.get(
                    'prompt_eval_count', 0) + data.get('eval_count', 0)
                eval_duration = data.get('eval_duration', 0) / 1e9
                break

    console.print()  # Add a newline after the output

    end_time = time.time()

    if eval_duration is not None:
        tps = total_tokens / eval_duration if eval_duration > 0 else 0
        print_statistics(model, prompt, total_tokens,
                         eval_duration, tps, data.get('total_duration', 0)/1e9)
    else:
        total_duration = end_time - start_time
        console.print(f"\nTotal Time: {total_duration:.2f}s")
        console.print(
            "Note: Detailed timing information not available for this model.")


def get_command_suggestion(prompt: str, model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> str:
    if validators.url(prompt):
        return prompt

    url = "http://localhost:11434/api/generate"
    temp_prompt = f"""
    {system_prompt_prefix}
    ===
    For the following request, if it's a direct URL, return it. If it's a web search or navigation request, generate a Python function using Selenium to accomplish the task. The function should be named 'custom_selenium_interaction' and take a 'driver' parameter.
    Request: {prompt}
    ===
    {system_prompt_suffix}
    """
    payload = {
        "model": model,
        "prompt": temp_prompt,
        "stream": True
    }
    response = requests.post(url, json=payload, stream=True)
    result = ""
    console.print("Generating suggestion:", style="bold cyan")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                console.print(data['response'], end="")
                result += data['response']
            if 'done' in data and data['done']:
                break
    console.print()

    result = result.strip()
    if not validators.url(result):
        return result
    if not result.startswith('http'):
        result = 'https://www.google.com/search?q=' + \
            urllib.parse.quote(result)
    return result


def take_screenshot(driver: webdriver.Chrome, url: str) -> str:
    try:
        driver.set_window_size(1920, 1080)
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))
        screenshot = driver.get_screenshot_as_png()
        img = Image.open(BytesIO(screenshot))
        screenshot_path = f"screenshot_{int(time.time())}.png"
        img.save(screenshot_path)
        return f"Screenshot saved as {screenshot_path}"
    except Exception as e:
        return f"An error occurred while taking the screenshot: {str(e)}"


def selenium_web_interaction(url: str, take_screenshot: bool = False) -> str:
    if url in url_cache:
        console.print("Using cached content...", style="bold yellow")
        return url_cache[url]

    with get_driver() as driver:
        if take_screenshot:
            return take_screenshot(driver, url)

        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")))

            if "github.com" in url:
                readme = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "article.markdown-body"))
                )
                content = f"GitHub README:\n\n{readme.text}"
            else:
                title = driver.title
                content = driver.find_element(By.TAG_NAME, "body").text
                content = f"Title: {title}\n\nContent preview:\n{
                    content[:500]}..."

            if len(url_cache) >= MAX_CACHE_SIZE:
                url_cache.pop(next(iter(url_cache)))
            url_cache[url] = content
            return content
        except Exception as e:
            return f"An error occurred while fetching the webpage: {str(e)}"


def generate_selenium_code(prompt: str, model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> str:
    url = "http://localhost:11434/api/generate"
    temp_prompt = f"""
    {system_prompt_prefix}
    ===
    Write a Python function using Selenium to accomplish the following task. Follow these guidelines:
    1. Do not include any import statements.
    2. The function should be named 'custom_selenium_interaction' and take a 'driver' parameter.
    3. Use only the following pre-imported modules: selenium, By, WebDriverWait, EC
    4. Do not create or quit the driver within the function.
    5. Return the result directly from the function.
    6. Include brief comments explaining the code.

    Task: {prompt}
    ===
    {system_prompt_suffix}
    """
    payload = {
        "model": model,
        "prompt": temp_prompt,
        "stream": True
    }
    response = requests.post(url, json=payload, stream=True)
    generated_code = ""
    console.print("Generating Selenium code:", style="bold cyan")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                console.print(data['response'], end="")
                generated_code += data['response']
            if 'done' in data and data['done']:
                break
    console.print()
    return generated_code.strip()


def execute_custom_selenium_code(code: str) -> str:
    with get_driver() as driver:
        try:
            local_env = {'driver': driver, 'By': By,
                         'WebDriverWait': WebDriverWait, 'EC': EC}
            exec(code, {'__builtins__': {}}, local_env)
            if 'custom_selenium_interaction' in local_env:
                result = local_env['custom_selenium_interaction'](driver)
                return str(result)
            else:
                return "Error: custom_selenium_interaction function not found in the code."
        except Exception as e:
            return f"An error occurred while executing the custom code: {str(e)}"


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
                stop_spinner = Thread(target=spinner, args=(stop_event,))
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
            stop_spinner = Thread(target=spinner, args=(stop_event,))
            stop_spinner.start()
            result = selenium_web_interaction(last_url, take_screenshot=True)
            stop_event.set()
            stop_spinner.join()
            console.print("Screenshot result:", style="bold cyan")
            console.print(result, style="yellow")
        elif user_input.lower() == '/screenshot':
            console.print(
                "No previous URL to screenshot. Use /cmd first.", style="bold red")
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
            stop_spinner = Thread(target=spinner, args=(stop_event,))
            stop_spinner.start()
            result = execute_custom_selenium_code(code)
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


def edit_code(code: str) -> str:
    console.print(
        "Enter your edits (type 'done' on a new line when finished):", style="bold yellow")
    edited_code = code + "\n"
    while True:
        line = console.input("[cyan]> [/]")
        if line.strip().lower() == 'done':
            break
        edited_code += line + "\n"
    console.print("Updated code:", style="bold magenta")
    console.print(edited_code, style="cyan")
    return edited_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure TPS for Ollama models and perform web interactions")
    parser.add_argument("--prompt", type=str, default="Explain quantum computing in simple terms.",
                        help="Custom prompt for the model")
    parser.add_argument("--model", type=str, default="llama3.2:3b",
                        help="Model to use (default: llama3.2:3b)")
    parser.add_argument("-i", "--interactive",
                        action="store_true", help="Run in interactive mode")
    parser.add_argument("--system-prompt-prefix", type=str,
                        default="", help="System prompt prefix")
    parser.add_argument("--system-prompt-suffix", type=str,
                        default="", help="System prompt suffix")
    args = parser.parse_args()

    if args.interactive:
        interactive_session(
            args.model, args.system_prompt_prefix, args.system_prompt_suffix)
    else:
        measure_tps(args.prompt, args.model,
                    args.system_prompt_prefix, args.system_prompt_suffix)
