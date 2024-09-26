import json
import time

import requests
import validators
from rich.console import Console

from utils import extract_code_blocks, print_statistics

console = Console()


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
        result = extract_code_blocks(result)
    return result


def generate_selenium_code(prompt: str, model: str, system_prompt_prefix: str = '', system_prompt_suffix: str = '') -> str:
    url = "http://localhost:11434/api/generate"
    temp_prompt = f"""
    {system_prompt_prefix}
    ===
    Write a Python function using Selenium to accomplish the following task. Follow these guidelines:
    1. Do not include any import statements.
    2. The function should be named 'custom_selenium_interaction' and take a 'driver' parameter.
    3. Use only the following pre-imported modules: selenium, By, WebDriverWait, and EC.

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
