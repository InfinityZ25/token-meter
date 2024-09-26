import argparse

from api_client import measure_tps
from interactive_session import interactive_session

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Measure TPS for models and perform web interactions"
    )
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

