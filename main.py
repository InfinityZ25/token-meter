import importlib
import argparse
import subprocess
import json
import sys
import threading
import time
import re
import os
import tempfile
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
def get_driver(headless=True, width=1920, height=1080):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--window-size={width},{height}')

    # Add these lines for troubleshooting
    options.add_argument('--verbose')
    options.add_argument('--log-level=3')  # Set log level to DEBUG

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


def extract_code_blocks(text):
    code_blocks = re.findall(r'```(?:python)?(.*?)```', text, re.DOTALL)
    if code_blocks:
        return code_blocks[0].strip()
    return text

# Utility functions that can be used in generated Selenium code


class SeleniumUtils:
    @staticmethod
    def take_screenshot(driver, filename):
        screenshot = driver.get_screenshot_as_png()
        img = Image.open(BytesIO(screenshot))
        img.save(filename)
        return f"Screenshot saved as {filename}"

    @staticmethod
    def wait_for_element(driver, by, value, timeout=10):
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    @staticmethod
    def scroll_to_bottom(driver):
        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);")


def get_command_suggestion(prompt: str, model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> str:
    if validators.url(prompt):
        return prompt

    url = "http://localhost:11434/api/generate"
    temp_prompt = f"""
    {system_prompt_prefix}
    ===
    For the following request, if it's a direct URL, return it. If it's a web search or navigation request, generate a Python function using Selenium to accomplish the task. The function should be named 'custom_selenium_interaction' and take a 'driver' parameter. Include necessary imports at the top of the script.

    You can use the following imports and functions:

    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import time

    # You can also use the following utility functions from the SeleniumUtils class:
    # SeleniumUtils.take_screenshot(driver, filename)
    # SeleniumUtils.wait_for_element(driver, by, value, timeout=10)
    # SeleniumUtils.scroll_to_bottom(driver)

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
        result = extract_code_blocks(result)
    return result


def execute_temp_script(code: str, script_name: str = "temp_script", headless=True) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = os.path.join(temp_dir, f"{script_name}.py")

        # Modify the code to import utility functions
        modified_code = f"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

class SeleniumUtils:
    {SeleniumUtils.take_screenshot.__code__.co_code}
    {SeleniumUtils.wait_for_element.__code__.co_code}
    {SeleniumUtils.scroll_to_bottom.__code__.co_code}

{code}
"""

        with open(script_path, 'w') as f:
            f.write(modified_code)

        try:
            spec = importlib.util.spec_from_file_location(
                script_name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with get_driver(headless=headless) as driver:
                if hasattr(module, 'custom_selenium_interaction'):
                    result = module.custom_selenium_interaction(driver)

                    success_dir = os.path.join(
                        os.getcwd(), "successful_scripts")
                    os.makedirs(success_dir, exist_ok=True)
                    success_path = os.path.join(
                        success_dir, f"{script_name}.py")
                    with open(success_path, 'w') as f:
                        f.write(code)

                    return str(result)
                else:
                    return "Error: custom_selenium_interaction function not found in the code."
        except Exception as e:
            return f"An error occurred while executing the custom code: {str(e)}"


def take_screenshot(driver: webdriver.Chrome, url: str) -> str:
    try:
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


def selenium_web_interaction(url: str, take_screenshot: bool = False, headless=True) -> str:
    if url in url_cache:
        console.print("Using cached content...", style="bold yellow")
        return url_cache[url]

    with get_driver(headless=headless) as driver:
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


def clip_video(input_file, output_file, start_time, duration):
    try:
        command = [
            "ffmpeg",
            "-i", input_file,
            "-ss", start_time,
            "-t", duration,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-strict", "experimental",
            output_file
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return f"Video clipped successfully: {output_file}"
    except Exception as e:
        return f"An error occurred while clipping the video: {str(e)}"


def generate_selenium_code(prompt: str, model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> str:
    url = "http://localhost:11434/api/generate"
    temp_prompt = f"""
    {system_prompt_prefix}
    ===
    Write a Python function using Selenium to accomplish the following task. Follow these guidelines:
    1. Do not include any import statements.
    2. The function should be named 'custom_selenium_interaction' and take a 'driver' parameter.
    3. Use only the following pre-imported modules: selenium, By, WebDriverWait, and EC.
    4. Use the utility functions from SeleniumUtils where appropriate.

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
    console.print("Generating code:", style="bold cyan")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                console.print(data['response'], end="")
                result += data['response']
            if 'done' in data and data['done']:
                break
    console.print()
    return result.strip()


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


def edit_code(code: str) -> str:
    console.print(
        "Enter your edits (type 'done' on a new line when finished):", style="bold yellow")
    edited_code = code + "\n"

    while True:
        line = console.input("[cyan]> [/]")
        if line.strip().lower() == 'done':
            break
        edited_code += line + "\n"

    # Regenerate code based on edits
    regenerated_code = generate_selenium_code(
        edited_code, model='your_model_here')  # Use the appropriate model
    console.print("Updated code:", style="bold magenta")
    console.print(regenerated_code, style="cyan")
    return regenerated_code


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
        elif user_input.lower().startswith('/clip'):
            clip_params = user_input[6:].strip().split()
            if len(clip_params) != 4:
                console.print(
                    "Usage: /clip <input_file> <output_file> <start_time> <duration>", style="bold red")
            else:
                input_file, output_file, start_time, duration = clip_params
                console.print(f"Clipping video: {
                              input_file}", style="bold blue")
                stop_event = threading.Event()
                stop_spinner = Thread(target=spinner, args=(stop_event,))
                stop_spinner.start()
                result = clip_video(input_file, output_file,
                                    start_time, duration)
                stop_event.set()
                stop_spinner.join()
                console.print("Clipping result:", style="bold cyan")
                console.print(result, style="yellow")
        else:
            measure_tps(user_input, model, system_prompt_prefix,
                        system_prompt_suffix)


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
