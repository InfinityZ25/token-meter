import time
import requests

def measure_tps(prompt, model="llama3.2:3b"):
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    
    start_time = time.time()
    response = requests.post(url, json=payload)
    end_time = time.time()
    
    result = response.json()
    
    total_tokens = result['prompt_eval_count'] + result['eval_count']
    eval_duration = result['eval_duration'] / 1e9
    tps = total_tokens / eval_duration
    
    print(f"Model: {result['model']}")
    print(f"Input: {prompt}..." if len(prompt) > 50 else f"Input: {prompt}")
    print(f"Output: {result['response'][:50]}..." if len(result['response']) > 50 else f"Output: {result['response']}")
    print(f"Tokens: {total_tokens} (Prompt: {result['prompt_eval_count']}, Response: {result['eval_count']})")
    print(f"Time: {eval_duration:.2f}s (Total: {result['total_duration']/1e9:.2f}s)")
    print(f"Speed: {tps:.2f} tokens/second")

prompt = "Explain quantum computing in simple terms."
measure_tps(prompt)
