# zw_mcp/client_example.py
import socket
import sys
from pathlib import Path

DEFAULT_PROMPT_FILE = Path("zw_mcp/prompts/example.zw")
BUFFER_SIZE = 4096
DEFAULT_PORT = 7421
DEFAULT_HOST = "127.0.0.1"

def send_prompt(host: str, port: int, zw_file_path: str):
    try:
        with open(zw_file_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    except FileNotFoundError:
        print(f"[!] Error: Prompt file not found at '{zw_file_path}'")
        return
    except Exception as e:
        print(f"[!] Error reading prompt file '{zw_file_path}': {e}")
        return

    if not prompt:
        print(f"[!] Error: Prompt file '{zw_file_path}' is empty.")
        return

    if not prompt.endswith("///"):
        prompt += "\n///"

    print(f"[*] Connecting to ZW MCP Daemon at {host}:{port}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            print(f"[*] Connected. Sending prompt from '{zw_file_path}'...")
            s.sendall(prompt.encode("utf-8"))
            s.shutdown(socket.SHUT_WR) # Signal that sending is done

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
                print("[!] No response received from server.")
                return

    except socket.error as e:
        print(f"[!] Socket error: {e}")
        return
    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        return

    full_response = "".join(response_parts)
    print("\n🧠 ZW MCP Response:\n")
    print(full_response)

if __name__ == "__main__":
    host = DEFAULT_HOST
    port = DEFAULT_PORT

    # Use provided file path or default
    if len(sys.argv) > 1:
        zw_file_arg = sys.argv[1]
        # Attempt to resolve relative paths, e.g. prompts/example.zw
        # This assumes the client might be run from the root, or `zw_mcp` dir
        possible_paths = [
            Path(zw_file_arg),
            Path("zw_mcp") / zw_file_arg
        ]
        selected_path = None
        for p_path in possible_paths:
            if p_path.exists():
                selected_path = p_path
                break

        if selected_path:
            zw_file = str(selected_path)
        else:
            # If not found with common prefixes, use as is and let open() handle error
            zw_file = zw_file_arg
            print(f"[*] Warning: Prompt file '{zw_file_arg}' not found in common locations, trying path as is.")

    else:
        zw_file = str(DEFAULT_PROMPT_FILE)
        if not DEFAULT_PROMPT_FILE.exists():
            print(f"[!] Error: Default prompt file '{DEFAULT_PROMPT_FILE}' not found.")
            sys.exit(1)

    print(f"[*] Using prompt file: {Path(zw_file).resolve()}")
    send_prompt(host, port, zw_file)
