# zw_mcp/zw_agent_hub.py
import json
from pathlib import Path
import sys

try:
    from ollama_agent import (
        load_config as load_agent_config,
        load_initial_prompt,
        send_to_daemon,
        append_to_memory,
        log_round_interaction,
        build_composite_prompt
    )
except ImportError:
    print("[!] Error: Could not import functions from ollama_agent.py.")
    sys.exit(1)

PROFILES_PATH = Path("zw_mcp/agent_profiles.json")
DEFAULT_MASTER_SEED_PATH = Path("zw_mcp/prompts/master_seed.zw")

def run_single_agent_session(agent_name: str, agent_config_path_str: str, initial_session_prompt: str) -> str:
    print(f"\n--- Starting session for Agent: {agent_name} ---")
    print(f"[*] Using agent config: {agent_config_path_str}")
    print(f"[*] Initial session prompt for {agent_name}:\n{initial_session_prompt.strip()}")
    print("---")

    try:
        config = load_agent_config(agent_config_path_str)
    except Exception as e:
        print(f"[!] Failed to load config for agent {agent_name} from {agent_config_path_str}: {e}")
        return f"ERROR: Could not load config for {agent_name}"

    current_round_prompt = initial_session_prompt
    if config.get("use_memory_seed", False):
        print(f"[*] Agent '{agent_name}': Memory seeding enabled. Building composite prompt for its first round.")
        current_round_prompt = build_composite_prompt(
            initial_session_prompt,
            config.get("memory_path"),
            config.get("memory_limit", 3),
            config.get("style", "")
        )
    else:
        print(f"[*] Agent '{agent_name}': Memory seeding disabled. Using provided session prompt directly for its first round.")

    if not current_round_prompt.strip().endswith("///"):
        current_round_prompt = current_round_prompt.strip() + "\n///"

    final_output_from_agent = ""
    max_rounds = config.get("max_rounds", 1)
    stop_keywords = config.get("stop_keywords", [])
    log_path = config.get("log_path")
    memory_enabled = config.get("memory_enabled", False)
    memory_path = config.get("memory_path")
    prepend_response = config.get("prepend_previous_response", False)

    for round_num in range(1, max_rounds + 1):
        print(f"\n🔁 Agent '{agent_name}' - Round {round_num} of {max_rounds}")

        response = send_to_daemon(config["host"], config["port"], current_round_prompt)
        final_output_from_agent = response

        print(f"\n🧠 Response (Agent '{agent_name}' - Round {round_num}):\n{response.strip()}")

        if log_path:
            log_round_interaction(log_path, round_num, current_round_prompt, response)

        if memory_enabled and memory_path:
            append_to_memory(memory_path, round_num, current_round_prompt, response)
        elif memory_enabled and not memory_path:
            print(f"[!] Agent '{agent_name}': Memory is enabled but no 'memory_path' is configured.")

        if any(stop_word in response for stop_word in stop_keywords):
            print(f"\n🛑 Stop keyword detected for Agent '{agent_name}'. Ending this agent's session.")
            break

        if round_num == max_rounds:
            print(f"\n🏁 Agent '{agent_name}' reached max rounds. Ending this agent's session.")
            break

        if prepend_response:
            current_round_prompt = response.strip()
        else:
            # Reload this agent's own seed prompt for the next internal round
            print(f"[*] Agent '{agent_name}': Prepending response disabled. Reloading its own seed for next internal round.")
            current_round_prompt = load_initial_prompt(config["prompt_path"])
            # If it uses memory seeding for its own reloaded prompts, it should rebuild
            if config.get("use_memory_seed", False):
                 current_round_prompt = build_composite_prompt(
                    current_round_prompt,
                    config.get("memory_path"),
                    config.get("memory_limit", 3),
                    config.get("style", "")
                )

        if not current_round_prompt.strip().endswith("///"):
             current_round_prompt = current_round_prompt.strip() + "\n///"

    print(f"--- Finished session for Agent: {agent_name} ---")
    return final_output_from_agent

def main():
    try:
        with open(PROFILES_PATH, "r", encoding="utf-8") as f:
            profiles = json.load(f)
    except FileNotFoundError:
        print(f"[!] Error: Agent profiles file not found at '{PROFILES_PATH}'")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"[!] Error: Could not decode JSON from profiles file '{PROFILES_PATH}'")
        sys.exit(1)

    try:
        current_input_for_next_agent = load_initial_prompt(str(DEFAULT_MASTER_SEED_PATH))
    except Exception as e:
        print(f"[!] Agent Hub cannot continue: Failed to load master seed: {e}")
        sys.exit(1)

    print("🚀🚀🚀 Starting Multi-Agent Hub Orchestration 🚀🚀🚀")

    for profile_entry in profiles:
        agent_name = profile_entry.get("name", "UnnamedAgent")
        agent_config_path = profile_entry.get("config")

        if not agent_config_path:
            print(f"[!] Skipping agent '{agent_name}' due to missing 'config' path in profiles.")
            continue

        print(f"\n✨ Orchestrator: Invoking Agent '{agent_name}' ✨")
        agent_output = run_single_agent_session(agent_name, agent_config_path, current_input_for_next_agent)

        if agent_output.startswith("ERROR:"):
            print(f"[!] Agent '{agent_name}' session resulted in an error. Output will be passed as is.")
        current_input_for_next_agent = agent_output

    print("\n✅✅✅ Multi-Agent Hub Orchestration Complete. ✅✅✅")
    print(f"Final output from the chain:\n{current_input_for_next_agent.strip()}")

if __name__ == "__main__":
    main()
