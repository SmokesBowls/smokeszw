# zw_mcp/ollama_agent.py
import socket
import json
from pathlib import Path
from datetime import datetime # Added for logging timestamp consistency

CONFIG_PATH = Path("zw_mcp/agent_config.json") # Default config path for standalone runs
BUFFER_SIZE = 4096 # Consistent with other scripts

def load_config(config_file_path_str: str = None): # Added optional argument
    target_path = None
    if config_file_path_str:
        target_path = Path(config_file_path_str)
    else:
        target_path = CONFIG_PATH # Fallback to global default

    try:
        print(f"[*] Loading agent configuration from: {target_path.resolve()}") # Added print
        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[!] Error: Agent configuration file not found at '{target_path}'")
        raise
    except json.JSONDecodeError:
        print(f"[!] Error: Could not decode JSON from '{target_path}'")
        raise
    except Exception as e:
        print(f"[!] Error loading agent configuration from '{target_path}': {e}")
        raise

def load_initial_prompt(path_str: str) -> str: # Renamed for clarity
    prompt_path = Path(path_str)
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
            # Ensure initial prompt also ends with /// for consistency with daemon expectation
            return text if text.endswith("///") else text + "\n///"
    except FileNotFoundError:
        print(f"[!] Error: Initial prompt file not found at '{prompt_path}'")
        raise
    except Exception as e:
        print(f"[!] Error loading initial prompt file '{prompt_path}': {e}")
        raise

def send_to_daemon(host: str, port: int, prompt: str) -> str:
    # print(f"[*] Connecting to ZW MCP Daemon at {host}:{port}...") # Reduced verbosity for loops
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            # print(f"[*] Connected. Sending prompt for current round...") # Reduced verbosity
            s.sendall(prompt.encode("utf-8"))
            s.shutdown(socket.SHUT_WR)

            response_parts = []
            while True:
                try:
                    chunk = s.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    response_parts.append(chunk.decode("utf-8"))
                except socket.timeout:
                    print("[!] Socket timeout waiting for response.")
                    break
                except Exception as e:
                    print(f"[!] Error receiving response chunk: {e}")
                    break

            if not response_parts:
                # print("[!] No response received from server for current round.") # Daemon should ideally always respond
                return "ERROR: No response received from server"
            return "".join(response_parts)

    except socket.error as e:
        print(f"[!] Socket error during round: {e}")
        return f"ERROR: Socket error during round - {e}"
    except Exception as e:
        print(f"[!] Unexpected error during round: {e}")
        return f"ERROR: Unexpected error during round - {e}"

def log_round_interaction(log_path_str: str, round_num: int, prompt: str, response: str): # Renamed for clarity
    if not log_path_str:
        # print("[*] Log path not configured. Skipping round logging.") # Can be noisy in loops
        return

    log_file = Path(log_path_str)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"--- ZW Agent Round {round_num} [{timestamp}] ---\n"
    log_entry += f">>> Prompt:\n{prompt}\n"
    log_entry += f"<<< Response:\n{response}\n---\n"

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[!] Error writing to round log file '{log_file}': {e}")

def append_to_memory(memory_path_str: str, round_num: int, prompt: str, response: str): # Renamed for clarity
    if not memory_path_str:
        print("[!] Memory path not configured. Skipping memory append.")
        return

    memory_file = Path(memory_path_str)
    memory_file.parent.mkdir(parents=True, exist_ok=True)

    current_interaction = {"round": round_num, "prompt": prompt, "response": response}

    memory_history = []
    if memory_file.exists() and memory_file.stat().st_size > 0: # Check if file exists and is not empty
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                memory_history = json.load(f)
            if not isinstance(memory_history, list): # Ensure it's a list
                print(f"[!] Warning: Memory file '{memory_file}' did not contain a list. Starting new memory.")
                memory_history = []
        except json.JSONDecodeError:
            print(f"[!] Warning: Could not decode JSON from memory file '{memory_file}'. Starting new memory.")
            memory_history = []
        except Exception as e:
            print(f"[!] Error reading memory file '{memory_file}': {e}. Starting new memory.")
            memory_history = []

    memory_history.append(current_interaction)

    try:
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(memory_history, f, indent=2)
        # print(f"[*] Round {round_num} interaction saved to memory: '{memory_file.resolve()}'") # Can be noisy
    except Exception as e:
        print(f"[!] Error writing to memory file '{memory_file}': {e}")

def build_composite_prompt(seed_prompt_text: str, memory_path_str: str, limit: int, style: str) -> str:
    memory_history = []
    if memory_path_str:
        memory_file = Path(memory_path_str)
        if memory_file.exists() and memory_file.stat().st_size > 0:
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    loaded_memory = json.load(f)
                if isinstance(loaded_memory, list):
                    memory_history = loaded_memory
                else:
                    print(f"[!] Warning: Memory file '{memory_file}' did not contain a list. Ignoring memory.")
            except json.JSONDecodeError:
                print(f"[!] Warning: Could not decode JSON from memory file '{memory_file}'. Ignoring memory.")
            except Exception as e:
                print(f"[!] Error reading memory file '{memory_file}': {e}. Ignoring memory.")

    limit = max(0, limit)
    recent_memory_entries = memory_history[-limit:]

    memory_block_parts = []
    for entry in recent_memory_entries:
        response_text = entry.get("response")
        if isinstance(response_text, str):
            memory_block_parts.append(response_text.strip().rstrip("///").strip())
        elif response_text is not None:
            print(f"[!] Warning: Non-string response in memory: {type(response_text)}. Skipping.")

    composite_parts = []
    if style and style.strip():
        composite_parts.append(f"ZW-AGENT-STYLE:\n  ROLE: {style.strip()}\n///")

    if memory_block_parts:
        memory_seed_content = "\n///\n".join(memory_block_parts)
        if memory_seed_content: # Only add if there's actual content after stripping/joining
             composite_parts.append(f"ZW-MEMORY-SEED:\n{memory_seed_content}\n///")

    cleaned_seed_prompt = seed_prompt_text.strip().rstrip("///").strip()
    if cleaned_seed_prompt: # Only add if there's actual seed prompt content
        composite_parts.append(cleaned_seed_prompt)

    if not composite_parts:
        return "///" # Minimal valid ZW prompt if everything is empty

    final_composite_prompt = "\n".join(composite_parts)

    if not final_composite_prompt.endswith("///"):
        final_composite_prompt += "\n///"

    return final_composite_prompt

def main():
    try:
        config = load_config()
        seed_prompt_text = load_initial_prompt(config["prompt_path"])
    except Exception:
        print("[!] Agent cannot continue due to configuration or initial prompt loading errors.")
        return

    # current_prompt will be used to start the loop
    if config.get("use_memory_seed", False):
        print("[*] Memory seeding is enabled. Building composite prompt...")
        current_prompt = build_composite_prompt(
            seed_prompt_text,
            config.get("memory_path"),
            config.get("memory_limit", 3),
            config.get("style", "")
        )
    else:
        print("[*] Memory seeding is disabled. Using initial prompt directly.")
        current_prompt = seed_prompt_text

    host = config["host"]
    port = config["port"]
    max_rounds = config.get("max_rounds", 1) # Default to 1 if not specified
    stop_keywords = config.get("stop_keywords", [])
    log_path = config.get("log_path")
    memory_enabled = config.get("memory_enabled", False)
    memory_path = config.get("memory_path")
    prepend_response = config.get("prepend_previous_response", False)

    for round_num in range(1, max_rounds + 1):
        print(f"\n🔁 Round {round_num} of {max_rounds}")
        print(f"[*] Sending prompt for round {round_num}...")
        # print(f"Current prompt to send:\n{current_prompt}") # For debugging

        response = send_to_daemon(host, port, current_prompt)

        print(f"\n🧠 Response (Round {round_num}):\n{response}")

        if log_path:
            log_round_interaction(log_path, round_num, current_prompt, response)

        if memory_enabled and memory_path:
            append_to_memory(memory_path, round_num, current_prompt, response)
        elif memory_enabled and not memory_path:
            print("[!] Memory is enabled but no 'memory_path' is configured. Cannot save to memory.")


        if any(stop_word in response for stop_word in stop_keywords):
            print(f"\n🛑 Stop keyword detected in response (Round {round_num}). Ending agent loop.")
            break

        if round_num == max_rounds:
            print("\n🏁 Max rounds reached. Ending agent loop.")
            break

        if prepend_response:
            current_prompt = response.strip()
            if not current_prompt.endswith("///"):
                 current_prompt += "\n///"
        else:
            # If not prepending, how should the next prompt be formed?
            # For now, let's assume if not prepending, it reuses the *initial* prompt.
            # This might need further clarification based on desired behavior.
            # Or, if prepend_previous_response is false, maybe the loop should not modify the prompt at all,
            # and send the same initial prompt every time?
            # The user's code for this `else` was `prompt = response` which is same as `prepend_previous_response=True`
            # I will clarify this in the README. For now, if not prepending, it will send the *original* initial prompt.
            print("[*] Prepending response is disabled. Reusing initial prompt for next round (if any).")
            # Need to use the original seed_prompt_text, not potentially composite one
            current_prompt = load_initial_prompt(config["prompt_path"])


if __name__ == "__main__":
    main()
