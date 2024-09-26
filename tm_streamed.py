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
from colorama import Fore, Style, init
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Initialize colorama
init(autoreset=True)

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

    print("Output:")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                sys.stdout.write(data['response'])
                sys.stdout.flush()
                response_text += data['response']
            if 'done' in data and data['done']:
                total_tokens = data.get(
                    'prompt_eval_count', 0) + data.get('eval_count', 0)
                eval_duration = data.get('eval_duration', 0) / 1e9
                break

    end_time = time.time()

    print("\n\nStatistics:")
    print(f"Model: {model}")
    print(f"Input: {prompt[:50]}..." if len(
        prompt) > 50 else f"Input: {prompt}")
    print(f"Tokens: {total_tokens}")

    if eval_duration is not None:
        tps = total_tokens / eval_duration if eval_duration > 0 else 0
        print(f"Evaluation Time: {eval_duration:.2f}s")
        print(f"Speed: {tps:.2f} tokens/second")
    else:
        total_duration = end_time - start_time
        print(f"Total Time: {total_duration:.2f}s")
        print("Note: Detailed timing information not available for this model.")

    print(f"Total Duration: {data.get('total_duration', 0)/1e9:.2f}s")


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
    print("Generating suggestion:")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                sys.stdout.write(data['response'])
                sys.stdout.flush()
                result += data['response']
            if 'done' in data and data['done']:
                break
    print("\n")  # Add a newline after the streamed output

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
        print("Using cached content...")
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
    Write a Python function using Selenium to accomplish the following task. Include comments explaining the code:
    {prompt}
    The function should be named 'custom_selenium_interaction' and take a 'driver' parameter.
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
    print("Generating Selenium code:")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                sys.stdout.write(data['response'])
                sys.stdout.flush()
                generated_code += data['response']
            if 'done' in data and data['done']:
                break
    print("\n")  # Add a newline after the streamed output
    return generated_code.strip()


def execute_custom_selenium_code(code: str) -> str:
    with get_driver() as driver:
        try:
            # Create a restricted local environment
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


def print_fancy(text, color=Fore.WHITE, emoji=""):
    print(f"\n{emoji} {color}{text}{Style.RESET_ALL}")


def interactive_session(model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> None:
    print_fancy(f"Interactive session with {model}", Fore.CYAN, ROBOT)
    print_fancy("Commands:", Fore.YELLOW)
    print(f"  {GLOBE}  /cmd <prompt>    - Web interaction or custom Selenium code")
    print(f"  {CAMERA}  /screenshot      - Take a screenshot of the last visited URL")
    print(f"  {WRENCH}  /selenium <task> - Generate custom Selenium code")
    print(f"  {ROCKET}  exit             - Exit the session")

    last_url = None
    last_selenium_code = None
    while True:
        user_input = input(f"\n{Fore.GREEN}You:{Style.RESET_ALL} ").strip()
        if user_input.lower() == 'exit':
            print_fancy("Goodbye!", Fore.MAGENTA, ROCKET)
            break
        elif user_input.lower().startswith('/cmd'):
            cmd_prompt = user_input[5:].strip()
            result = get_command_suggestion(
                cmd_prompt, model, system_prompt_prefix, system_prompt_suffix)

            if validators.url(result):
                print_fancy(f"Navigating to URL: {result}", Fore.BLUE, GLOBE)
                stop_event = threading.Event()
                stop_spinner = Thread(target=spinner, args=(stop_event,))
                stop_spinner.start()
                webpage_content = selenium_web_interaction(result)
                stop_event.set()
                stop_spinner.join()
                print_fancy("Content retrieved:", Fore.CYAN)
                print(f"{Fore.YELLOW}{webpage_content}{Style.RESET_ALL}")
                last_url = result
            else:
                print_fancy("Generated custom Selenium code:",
                            Fore.MAGENTA, WRENCH)
                print(f"{Fore.CYAN}{result}{Style.RESET_ALL}")
                last_selenium_code = result
                handle_selenium_code(last_selenium_code)
        elif user_input.lower() == '/screenshot' and last_url:
            print_fancy(f"Taking screenshot of {
                        last_url}...", Fore.BLUE, CAMERA)
            stop_event = threading.Event()
            stop_spinner = Thread(target=spinner, args=(stop_event,))
            stop_spinner.start()
            result = selenium_web_interaction(last_url, take_screenshot=True)
            stop_event.set()
            stop_spinner.join()
            print_fancy("Screenshot result:", Fore.CYAN)
            print(f"{Fore.YELLOW}{result}{Style.RESET_ALL}")
        elif user_input.lower() == '/screenshot':
            print_fancy(
                "No previous URL to screenshot. Use /cmd first.", Fore.RED, ERROR)
        elif user_input.lower().startswith('/selenium'):
            selenium_prompt = user_input[9:].strip()
            generated_code = generate_selenium_code(
                selenium_prompt, model, system_prompt_prefix, system_prompt_suffix)
            print_fancy("Generated Selenium code:", Fore.MAGENTA, WRENCH)
            print(f"{Fore.CYAN}{generated_code}{Style.RESET_ALL}")
            last_selenium_code = generated_code
            handle_selenium_code(last_selenium_code)
        else:
            measure_tps(user_input, model, system_prompt_prefix,
                        system_prompt_suffix)


def handle_selenium_code(code: str) -> None:
    while True:
        action = input(f"\n{Fore.YELLOW}Do you want to (r)un, (e)dit, or (c)ancel this code? {
                       Style.RESET_ALL}").lower()
        if action == 'r':
            print_fancy("Executing custom Selenium code...", Fore.BLUE, ROCKET)
            stop_event = threading.Event()
            stop_spinner = Thread(target=spinner, args=(stop_event,))
            stop_spinner.start()
            result = execute_custom_selenium_code(code)
            stop_event.set()
            stop_spinner.join()
            print_fancy("Execution result:", Fore.CYAN)
            print(f"{Fore.YELLOW}{result}{Style.RESET_ALL}")
            break
        elif action == 'e':
            code = edit_code(code)
        elif action == 'c':
            print_fancy("Code execution cancelled.", Fore.RED)
            break
        else:
            print_fancy(
                "Invalid option. Please choose (r)un, (e)dit, or (c)ancel.", Fore.RED, ERROR)


def edit_code(code: str) -> str:
    print_fancy(
        "Enter your edits (type 'done' on a new line when finished):", Fore.YELLOW, WRENCH)
    edited_code = code + "\n"  # Start with the existing code
    while True:
        line = input(f"{Fore.CYAN}> {Style.RESET_ALL}")
        if line.strip().lower() == 'done':
            break
        edited_code += line + "\n"
    print_fancy("Updated code:", Fore.MAGENTA)
    print(f"{Fore.CYAN}{edited_code}{Style.RESET_ALL}")
    return edited_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure TPS for Ollama models and perform web interactions")
    parser.add_argument("--prompt", type=str, default="Explain quantum computing in simple terms.",
                        help="Custom prompt for the model")
    parser.add_argument("--model", type=str, default="llama2",
                        help="Model to use (default: llama2)")
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
