# Ollama TPS Meter

This tool measures the Tokens Per Second (TPS) performance of Ollama language models while streaming their output in real-time.

## Features

- Streams model output in real-time to the terminal
- Calculates and displays performance metrics:
  - Total tokens generated
  - Evaluation time
  - Tokens per second (TPS)
- Supports custom prompts and model selection via command-line arguments

## Requirements

- Python 3.12
- Ollama running locally on port 11434
- `requests` library (`pip install requests`)

## Usage

Run the script with default settings:

```
python ollama_tps_meter.py
```

Specify a custom model and prompt:

```
python ollama_tps_meter.py --model "llama2:7b" --prompt "Explain the theory of relativity"
```

### Arguments

- `--model`: Specifies the Ollama model to use (default: "llama3.2:latest")
- `--prompt`: Custom prompt for the model (default: "Explain quantum computing in simple terms.")

## Output

The script will:

1. Stream the model's response in real-time to the terminal
2. Display performance statistics after completion:
   - Model used
   - Input prompt
   - Token counts (total, prompt, and response)
   - Evaluation time
   - Tokens per second (TPS)

## Note

Ensure that Ollama is running and accessible at `http://localhost:11434` before using this tool.
