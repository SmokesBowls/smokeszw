# zw_mcp/blender_exporter.py
import sys
import json # For potential pretty printing if needed, not directly for to_zw
from pathlib import Path
import argparse

try:
    import bpy
    from mathutils import Vector # bpy.types.Object.location is a mathutils.Vector
except ImportError:
    print("[!] bpy module not found. This script must be run within Blender's Python environment.")
    bpy = None
    Vector = None # Define Vector as None if mathutils is not available

# Robust import of to_zw from zw_mcp.zw_parser
try:
    # Assumes zw_mcp is in PYTHONPATH or script is run from project root where zw_mcp is a subdir
    from zw_parser import to_zw
except ImportError:
    print("[!] Could not import 'to_zw' from 'zw_mcp.zw_parser'.")
    # Attempt fallback for direct execution if script is in zw_mcp folder
    try:
        from zw_parser import to_zw
    except ImportError:
        print("[!] Fallback import of 'to_zw' also failed.")
        print("[!] Ensure 'zw_parser.py' is accessible.")
        def to_zw(d: dict, current_indent_level: int = 0) -> str:
            print("[!] Dummy to_zw called. Real ZW conversion will not occur.")
            # Create a very basic string representation for the dummy
            error_message = "# ERROR: to_zw function not imported correctly.\n"
            error_message += "# Cannot convert dictionary to ZW format.\n"
            error_message += "# Input dictionary was:\n"
            # Basic dict representation
            for key, value in d.items():
                error_message += f"# {key}: {value}\n"
            return error_message.strip()
        # sys.exit(1) # Or exit if to_zw is critical

def format_vector_to_zw(vector, precision=3) -> str:
    if vector is None:
        return ""
    try:
        return f"({vector[0]:.{precision}f}, {vector[1]:.{precision}f}, {vector[2]:.{precision}f})"
    except Exception: # Catch potential issues if vector is not as expected
        return ""

def format_color_to_zw_hex(rgba_color) -> str:
    if rgba_color is None or not (isinstance(rgba_color, (list, tuple)) and len(rgba_color) >= 3):
        return "" # Return empty string if invalid, to not write "COLOR: "
    try:
        r, g, b = [int(c * 255) for c in rgba_color[:3]]
        return f"\"#{r:02x}{g:02x}{b:02x}\"" # Enclose in quotes as per ZW examples
    except Exception:
        return ""

def get_object_zw_type(blender_obj) -> str:
    if not blender_obj:
        return "Mesh" # Default

    # Check for a custom property first
    if "ZW_TYPE" in blender_obj:
        custom_type = blender_obj["ZW_TYPE"]
        if isinstance(custom_type, str) and custom_type.strip():
            return custom_type.strip()

    # If no custom property, try to infer from mesh data name (common primitives)
    if blender_obj.data and hasattr(blender_obj.data, 'name'):
        data_name_lower = blender_obj.data.name.lower()
        # Check for common primitive names (case-insensitive prefix)
        primitives = ["cube", "sphere", "plane", "cone", "cylinder", "torus"]
        for p_type in primitives:
            if data_name_lower.startswith(p_type):
                return p_type.capitalize() # Return in capitalized form

    return "Mesh" # Generic fallback if no specific type is found

def export_scene_to_zw(output_filepath_str: str, export_all_meshes: bool = False):
    if not bpy:
        print("[X] Blender (bpy) not available. Cannot export scene.")
        return

    output_filepath = Path(output_filepath_str)
    output_filepath.parent.mkdir(parents=True, exist_ok=True)

    zw_blocks = ["# Exported from Blender by ZW Exporter v0.1"]

    objects_to_export = []
    if not export_all_meshes and bpy.context.selected_objects:
        objects_to_export = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
        if not objects_to_export: # If selection is not meshes, fallback to all meshes
            print("[*] No mesh objects selected. Falling back to exporting all mesh objects in the scene.")
            objects_to_export = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    else:
        if export_all_meshes:
            print("[*] Exporting all mesh objects in the scene.")
        else: # No selection and not --all, so export all
            print("[*] No objects selected and --all not specified. Exporting all mesh objects in the scene.")
        objects_to_export = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

    if not objects_to_export:
        print("[!] No mesh objects found to export.")
        zw_blocks.append("# No mesh objects found in the scene to export.")
    else:
        print(f"[*] Found {len(objects_to_export)} mesh objects to export.")

    for obj in objects_to_export:
        attributes_dict = {}
        attributes_dict["TYPE"] = get_object_zw_type(obj)
        attributes_dict["NAME"] = obj.name

        loc_str = format_vector_to_zw(obj.location)
        if loc_str: attributes_dict["LOCATION"] = loc_str

        scale_str = format_vector_to_zw(obj.scale)
        if scale_str: attributes_dict["SCALE"] = scale_str

        rot_str = format_vector_to_zw(obj.rotation_euler) # Radians
        if rot_str: attributes_dict["ROTATION_EULER_XYZ_RADIANS"] = rot_str # Clarify unit

        if obj.data.materials and obj.data.materials[0]:
            mat = obj.data.materials[0]
            attributes_dict["MATERIAL"] = mat.name
            if mat.use_nodes and mat.node_tree:
                principled_bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if principled_bsdf:
                    base_color_input = principled_bsdf.inputs.get("Base Color")
                    if base_color_input:
                        color_hex = format_color_to_zw_hex(base_color_input.default_value)
                        if color_hex: attributes_dict["COLOR"] = color_hex
                    # Could add more BSDF properties here if needed
                    # e.g. METALLIC: principled_bsdf.inputs.get("Metallic").default_value

        if obj.parent:
            attributes_dict["PARENT"] = obj.parent.name

        if obj.users_collection and obj.users_collection[0]:
            # Only export collection if it's not the scene's master collection
            # (or handle this logic based on how collections are typically used)
            # For now, let's just export the first collection's name.
            # More sophisticated logic might be needed for multi-collection objects
            # or to decide which collection is "primary".
            # Also, ensure it's not the default "Scene Collection" if that's not desired.
            # For simplicity:
            attributes_dict["COLLECTION"] = obj.users_collection[0].name

        zw_object_data_for_to_zw = {"ZW-OBJECT": attributes_dict}

        try:
            zw_block_str = to_zw(zw_object_data_for_to_zw)
            zw_blocks.append(zw_block_str)
        except Exception as e_to_zw:
            print(f"[!] Error converting object '{obj.name}' to ZW: {e_to_zw}")
            zw_blocks.append(f"# ERROR: Could not convert object {obj.name} to ZW.\n# Attributes: {attributes_dict}")

    final_zw_string = "\n///\n".join(zw_blocks)
    if not final_zw_string.endswith("///") and zw_blocks: # Add trailing /// if content exists
        if len(zw_blocks) > 1 or (len(zw_blocks) == 1 and zw_blocks[0].strip() != "# Exported from Blender by ZW Exporter v0.1"):
             final_zw_string += "\n///"
    elif not zw_blocks: # If only the initial comment was there
        final_zw_string = "# No content exported."

    try:
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(final_zw_string)
        print(f"[*] Successfully exported ZW data to: {output_filepath.resolve()}")
    except Exception as e:
        print(f"[X] Error writing ZW output to file '{output_filepath}': {e}")

if __name__ == "__main__":
    if not bpy:
        print("[X] This script is intended to be run within Blender. Exiting.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Export Blender scene/selection to ZW format.")
    parser.add_argument("-o", "--output", type=str, required=True, help="Output .zw file path.")
    parser.add_argument("-a", "--all", action="store_true", help="Export all mesh objects in the scene, not just selection.")

    # Handle arguments when script is run with 'blender --python script.py -- [args]'
    argv = sys.argv
    if "--" in argv:
        script_args = argv[argv.index("--") + 1:]
    else:
        script_args = [] # No arguments provided to the script, or run from Blender text editor

    try:
        args = parser.parse_args(args=script_args)
        print(f"[*] Starting ZW Exporter with output: {args.output}, export all: {args.all}")
        export_scene_to_zw(args.output, args.all)
    except SystemExit: # Argparse throws SystemExit on error or -h
        print("[*] Argument parsing failed or help invoked. Ensure correct arguments if running via CLI.")
        # Blender's text editor run won't pass args, so this might be expected.
        # Provide a default behavior or clearer message if run from Blender UI without args.
        if not script_args: # Likely run from Blender UI
            print("[!] Note: No CLI arguments detected. This is normal if run from Blender's Text Editor.")
            print("[!] To use custom output path/options, run Blender from command line with arguments after '--'.")
            # Example: blender --python your_script.py -- --output /path/to/output.zw
            # Or, you can hardcode a default output for UI runs:
            # default_ui_output = str(Path.home() / "blender_export.zw")
            # print(f"[*] Example usage: export_scene_to_zw('{default_ui_output}')")
    except Exception as e:
        print(f"[X] An unexpected error occurred in main: {e}")

    print("[*] ZW Exporter script finished.")
```
