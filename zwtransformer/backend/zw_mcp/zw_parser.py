# zw_mcp/zw_parser.py
import re
import json # Not strictly needed for this version, but good if extending to JSON more directly
from collections import defaultdict # Not strictly needed for this version

def parse_zw(zw_text: str) -> dict:
    """Parses ZW-formatted text into a nested dictionary."""
    result = {}
    # stack keeps track of the current dictionary we're adding to
    # at different indentation levels.
    stack = [result]
    # indent_stack keeps track of the indentation level corresponding
    # to each dictionary on the stack.
    indent_stack = [-1] # Start with -1 to handle first line at indent 0

    lines = zw_text.strip().splitlines()
    for line_number, line_text in enumerate(lines):
        line = line_text # Keep original for potential error reporting later

        if not line.strip() or line.strip().startswith("#"):
            continue  # Skip blank lines or comments

        current_indent = len(line) - len(line.lstrip())

        key_value_part = line.strip()

        parts = key_value_part.split(":", 1)
        key = parts[0].strip()
        value_str = parts[1].strip() if len(parts) > 1 else None

        # Adjust stack for current indentation level
        while current_indent <= indent_stack[-1]:
            stack.pop()
            indent_stack.pop()

        parent_dict = stack[-1]

        if value_str == "" or value_str is None : # Handles `KEY:` (empty value implies dict)
            new_dict = {}
            parent_dict[key] = new_dict
            stack.append(new_dict)
            indent_stack.append(current_indent)
        else: # Handles `KEY: VALUE`
            parent_dict[key] = value_str

    return result

def to_zw(d: dict, current_indent_level: int = 0) -> str: # Renamed for clarity
    """Converts a nested dictionary back to ZW-formatted text."""
    lines = []
    for key, value in d.items():
        line_prefix = " " * current_indent_level

        if isinstance(value, dict):
            lines.append(line_prefix + f"{key}:")
            lines.append(to_zw(value, current_indent_level + 2))
        elif value is None:
             lines.append(line_prefix + f"{key}:")
        else:
            lines.append(line_prefix + f"{key}: {value}")
    return "\n".join(lines)

def validate_zw(zw_text: str) -> bool:
    """Checks if ZW formatting appears structurally valid by attempting to parse it."""
    try:
        parsed = parse_zw(zw_text)
        return isinstance(parsed, dict) and bool(parsed)
    except Exception:
        return False

def prettify_zw(zw_text: str) -> str:
    """Re-indents and formats ZW text cleanly by parsing and re-serializing."""
    try:
        data = parse_zw(zw_text)
        return to_zw(data)
    except Exception as e:
        return zw_text
