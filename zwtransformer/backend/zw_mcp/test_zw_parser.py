# zw_mcp/test_zw_parser.py
from zw_parser import parse_zw, to_zw, validate_zw, prettify_zw

sample_zw_text = """
ZW-NARRATIVE-EVENT:
  TITLE: The Awakening
  DIALOGUE:
    - SPEAKER: Tran
      LINE: “This place... I’ve been here before.”
  SCENE_GOAL: Awaken the Crimson Memory
"""

print("Original ZW Text:\n")
print(sample_zw_text)
print("---")

is_valid_before = validate_zw(sample_zw_text)
print(f"✅ Is Valid (before prettify): {is_valid_before}")
print("---")

print("💄 Prettified ZW Text:\n")
prettified_text = prettify_zw(sample_zw_text)
print(prettified_text)
print("---")

is_valid_after = validate_zw(prettified_text)
print(f"✅ Is Valid (after prettify): {is_valid_after}")
print("---")

print("🔍 Parsed ZW (from prettified) → Python Dictionary:\n")
parsed_dict = parse_zw(prettified_text)
import json # For pretty printing the dict
print(json.dumps(parsed_dict, indent=2))
print("---")

print("🔄 Reconstructed ZW (from parsed dict):\n")
reconstructed_zw = to_zw(parsed_dict)
print(reconstructed_zw)
print("---")

# Final validation of reconstructed text
is_valid_reconstructed = validate_zw(reconstructed_zw)
print(f"✅ Is Valid (reconstructed): {is_valid_reconstructed}")
print("---")

# Check if prettified and reconstructed are identical (should be if parser/serializer are consistent)
if prettified_text == reconstructed_zw:
    print("👍 Prettified text and Reconstructed text are identical.")
else:
    print("⚠️ Prettified text and Reconstructed text are DIFFERENT.")
    print("Prettified:")
    print(prettified_text)
    print("Reconstructed:")
    print(reconstructed_zw)
