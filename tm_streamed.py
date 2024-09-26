import argparse
import json
import readline  # for better input handling
import subprocess
import sys
import time

import requests


def measure_tps(prompt, model, system_prompt_prefix='', system_prompt_suffix=''):
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

    print("Output:")
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                sys.stdout.write(data['response'])
                sys.stdout.flush()
                response_text += data['response']
            if 'done' in data and data['done']:
                total_tokens = data['prompt_eval_count'] + data['eval_count']
                eval_duration = data['eval_duration'] / 1e9
                break

    end_time = time.time()

    tps = total_tokens / eval_duration

    print("\n\nStatistics:")
    print(f"Model: {model}")
    print(f"Input: {prompt[:50]}..." if len(
        prompt) > 50 else f"Input: {prompt}")
    print(f"Tokens: {total_tokens} (Prompt: {
          data['prompt_eval_count']}, Response: {data['eval_count']})")
    print(f"Time: {eval_duration:.2f}s (Total: {
          data['total_duration']/1e9:.2f}s)")
    print(f"Speed: {tps:.2f} tokens/second")


def get_command_suggestion(prompt, model, system_prompt_prefix='', system_prompt_suffix=''):
    url = "http://localhost:11434/api/generate"
    temp_prompt = f"""
    {system_prompt_prefix}
    ===
    Suggest a command to {prompt}. Provide only the command, no explanation.
    ===
    {system_prompt_suffix}
    """
    payload = {
        "model": model,
        "prompt": temp_prompt,
        "stream": True
    }
    response = requests.post(url, json=payload, stream=True)
    suggested_cmd = ""
    for line in response.iter_lines():
        if line:
            data = json.loads(line)
            if 'response' in data:
                suggested_cmd += data['response']
            if 'done' in data and data['done']:
                break
    return suggested_cmd.strip()


def interactive_session(model, system_prompt_prefix='', system_prompt_suffix=''):
    print(f"Interactive session with {
          model}. Type 'exit' to quit or '/cmd' for command suggestions.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        elif user_input.lower().startswith('/cmd'):
            # Remove '/cmd ' from the start
            cmd_prompt = user_input[5:].strip()
            suggested_cmd = get_command_suggestion(
                cmd_prompt, model, system_prompt_prefix, system_prompt_suffix)
            # Remove surrounding backticks if present
            suggested_cmd = suggested_cmd.strip('`')
            print(f"Suggested command: {suggested_cmd}")

            # Evaluate the suggested command
            evaluation_prompt = f"Evaluate the safety and correctness of this command: {
                suggested_cmd}"
            evaluation = get_command_suggestion(
                evaluation_prompt, model, system_prompt_prefix, system_prompt_suffix)
            print(f"Command evaluation: {evaluation}")

            confirm = input("Run this command? (y/n): ")
            if confirm.lower() == 'y':
                try:
                    result = subprocess.run(
                        suggested_cmd, shell=True, check=True, text=True, capture_output=True)
                    print("Command output:")
                    print(result.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"Command failed with error: {e}")
            else:
                print("Command not executed.")
        else:
            measure_tps(user_input, model, system_prompt_prefix,
                        system_prompt_suffix)
        print("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure TPS for Ollama models")
    parser.add_argument("--prompt", type=str, default="Explain quantum computing in simple terms.",
                        help="Custom prompt for the model")
    parser.add_argument("--model", type=str, default="llama3.2:latest",
                        help="Model to use (default: llama3.2:latest)")
    parser.add_argument("-i", "--interactive", action="store_true",
                        help="Run in interactive mode")
    parser.add_argument("--system-prompt-prefix", type=str, default="",
                        help="System prompt prefix")
    parser.add_argument("--system-prompt-suffix", type=str, default="",
                        help="System prompt suffix")
    args = parser.parse_args()

    if args.interactive:
        interactive_session(
            args.model, args.system_prompt_prefix, args.system_prompt_suffix)
    else:
        measure_tps(args.prompt, args.model,
                    args.system_prompt_prefix, args.system_prompt_suffix)
