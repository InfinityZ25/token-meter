import argparse
import json
import sys
import time

import requests


def measure_tps(prompt, model):
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": True}

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure TPS for Ollama models")
    parser.add_argument("--prompt", type=str, default="Explain quantum computing in simple terms.",
                        help="Custom prompt for the model")
    parser.add_argument("--model", type=str, default="llama3.2:latest",
                        help="Model to use (default: llama3.2:latest)")
    args = parser.parse_args()

    measure_tps(args.prompt, args.model)
