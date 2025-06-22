# zw_mcp_server.py
import argparse
from ollama_handler import query_ollama # Assuming ollama_handler.py is in the same directory or PYTHONPATH
from pathlib import Path
from datetime import datetime

def read_zw_from_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def save_response_to_file(content: str, output_path: str):
    # Ensure the output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

def log_interaction(prompt: str, response: str, log_path: str):
    # Ensure the log directory exists
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n--- Prompt [{datetime.now()}] ---\n{prompt}\n")
        f.write(f"\n--- Response ---\n{response}\n")

def main():
    parser = argparse.ArgumentParser(description="ZW MCP ↔ Ollama")
    parser.add_argument("infile", help="Path to .zw input file (e.g., prompts/example.zw)")
    parser.add_argument("--out", help="Path to save Ollama response (e.g., responses/ollama_response.zw)")
    parser.add_argument("--log", help="Optional log file (e.g., logs/session.log)")

    args = parser.parse_args()

    # Adjust infile path if it's relative to the script location vs. execution location
    # For now, assume paths are relative to where the script is run from.
    zw_prompt = read_zw_from_file(args.infile)

    print("🚀 Sending to Ollama...")
    ollama_response = query_ollama(zw_prompt)

    print("\n🧠 Ollama Response:\n")
    print(ollama_response)

    if args.out:
        save_response_to_file(ollama_response, args.out)
        print(f"\n💾 Saved response to {args.out}")

    if args.log:
        log_interaction(zw_prompt, ollama_response, args.log)
        print(f"\n📝 Logged interaction to {args.log}")

if __name__ == "__main__":
    main()
