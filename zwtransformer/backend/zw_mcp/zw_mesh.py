# zw_mcp/zw_mesh.py
import bpy
import math
from pathlib import Path
from mathutils import Vector # Explicitly import Vector

# Helper function (ensure this is robust or imported from a shared utility module if available)
def safe_eval(str_val, default_val):
    if not isinstance(str_val, str):
        return default_val
    try:
        return eval(str_val)
    except (SyntaxError, NameError, TypeError, ValueError) as e:
        print(f"    [!] Warning (safe_eval in zw_mesh.py): Could not evaluate string '{str_val}': {e}. Using default: {default_val}")
        return default_val

# --- Stub/Placeholder Functions (assumed to exist or be developed) ---
def create_base_mesh(mesh_def: dict):
    """
    Creates a base mesh primitive in Blender based on the 'TYPE' and 'PARAMS'
    in mesh_def.
    Returns the created Blender object or None on failure.
    Placeholder - actual implementation would involve bpy.ops.mesh.primitive_...
    """
    obj_name = mesh_def.get("NAME", "ZWMesh_Object")
    mesh_type = mesh_def.get("TYPE", mesh_def.get("BASE", "cube")).lower() # Check TYPE or BASE
    params = mesh_def.get("PARAMS", {})
    print(f"  [*] (Stub) Creating base mesh: TYPE='{mesh_type}', NAME='{obj_name}', PARAMS={params}")

    # Simple placeholder: creates a cube, ignores most params for now
    if mesh_type == "cube":
        bpy.ops.mesh.primitive_cube_add(size=params.get("SIZE", 1.0))
    elif mesh_type == "ico_sphere":
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=params.get("SUBDIVISIONS", 2),
            radius=params.get("RADIUS", 1.0)
        )
    elif mesh_type == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=params.get("VERTICES", 32),
            radius=params.get("RADIUS", 1.0),
            depth=params.get("DEPTH", 2.0)
        )
    elif mesh_type == "grid":
        bpy.ops.mesh.primitive_grid_add(
            x_subdivisions=params.get("X_SUBDIVISIONS", 10),
            y_subdivisions=params.get("Y_SUBDIVISIONS", 10),
            size=params.get("SIZE", 2.0)
        )
    elif mesh_type == "cone":
        bpy.ops.mesh.primitive_cone_add(
            vertices=params.get("VERTICES", 32),
            radius1=params.get("RADIUS", 1.0), # Assuming RADIUS means radius1 for cone
            depth=params.get("DEPTH", 2.0)
        )
    else:
        print(f"    [Warning] Unknown base mesh TYPE '{mesh_type}'. Creating a default cube.")
        bpy.ops.mesh.primitive_cube_add(size=1.0)

    created_obj = bpy.context.object
    if created_obj:
        created_obj.name = obj_name
    return created_obj

def apply_deformations(blender_obj: bpy.types.Object, deformations_list: list):
    """
    Applies a list of deformations to the Blender object.
    Placeholder - actual implementation would add and configure modifiers.
    """
    print(f"  [*] (Stub) Applying {len(deformations_list)} deformations to '{blender_obj.name}'...")
    for deform in deformations_list:
        deform_type = deform.get("TYPE", "unknown")
        print(f"    - (Stub) Deformation: {deform_type} with params {deform}")
        # Example for twist, if you want to add a simple deform modifier
        if deform_type == "twist" and blender_obj:
            mod = blender_obj.modifiers.new(name="ZWTwist", type='SIMPLE_DEFORM')
            mod.deform_method = 'TWIST'
            mod.angle = math.radians(float(deform.get("ANGLE", 0.0)))
            # mod.deform_axis = deform.get("AXIS", 'Z').upper() # Needs to be enum
            print(f"      Added Simple Deform (Twist) modifier stub for {deform_type}")
        elif deform_type == "displace" and blender_obj:
            # Placeholder for displace
            mod = blender_obj.modifiers.new(name="ZWDisplace", type='DISPLACE')
            tex_name = deform.get("TEXTURE", "noise")
            # A real implementation would create or get bpy.data.textures[tex_name]
            # and configure it based on type (e.g. CLOUDS for "noise")
            # mod.texture = existing_texture
            mod.strength = float(deform.get("STRENGTH", 1.0))
            print(f"      Added Displace modifier stub for {deform_type} (texture '{tex_name}' not fully configured)")
        elif deform_type == "skin" and blender_obj:
            mod = blender_obj.modifiers.new(name="ZWSkin", type='SKIN')
            mod.branch_smoothing = float(deform.get("SMOOTHING", 0.0))
            print(f"      Added Skin modifier stub for {deform_type}")


# --- New Functions to be Added ---

def add_uv_mapping(blender_obj: bpy.types.Object):
    """
    Adds UV mapping to the given Blender object using Smart UV Project.
    """
    if not blender_obj or blender_obj.type != 'MESH':
        print(f"  [!] UV Mapping: '{blender_obj.name if blender_obj else 'None'}' is not a valid mesh object. Skipping UV unwrapping.")
        return

    print(f"  [*] Adding UV mapping to '{blender_obj.name}'...")
    bpy.ops.object.select_all(action='DESELECT')
    blender_obj.select_set(True)
    bpy.context.view_layer.objects.active = blender_obj

    current_mode = bpy.context.object.mode
    if current_mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.01)

    if bpy.context.object.mode != current_mode: # Revert to original mode
        bpy.ops.object.mode_set(mode=current_mode)
    print(f"    ✅ UV mapping (Smart Project) applied to '{blender_obj.name}'.")

def apply_texture_to_material_nodes(principled_bsdf_node: bpy.types.ShaderNode,
                                    texture_definition: dict,
                                    current_blender_object: bpy.types.Object):
    """
    Applies texture nodes to a material's Principled BSDF based on texture_definition.
    """
    if not principled_bsdf_node or not texture_definition or not current_blender_object:
        print("  [!] Apply Texture: Missing BSDF node, texture definition, or Blender object. Skipping.")
        return

    tex_type = texture_definition.get("TYPE", "").lower()
    mat_node_tree = principled_bsdf_node.id_data.node_tree # Material's node tree
    nodes = mat_node_tree.nodes
    links = mat_node_tree.links

    print(f"    [*] Applying texture type: '{tex_type}'")

    if tex_type == "image":
        file_path_str = texture_definition.get("FILE")
        if not file_path_str:
            print("      [!] Image texture: Missing 'FILE' path. Skipping.")
            return

        # Resolve path relative to project root if not absolute
        # Assuming PROJECT_ROOT is defined if this script is part of a larger project structure
        # For now, let's assume Path(file_path_str) works or is absolute for simplicity here.
        # A more robust solution would ensure PROJECT_ROOT is available or paths are absolute.
        image_path = Path(file_path_str)
        if not image_path.is_absolute():
             # This assumes zw_mesh.py is in zw_mcp, and PROJECT_ROOT is its parent.
             # This might need adjustment depending on actual script location and how paths are managed.
            try:
                script_dir_parent = Path(__file__).resolve().parent.parent
                image_path = script_dir_parent / file_path_str
            except NameError: # __file__ not defined (e.g. Blender Text Editor)
                 # Fallback: try to resolve from current working directory if in Blender
                if bpy.data.filepath: # If blend file is saved
                    image_path = Path(bpy.data.filepath).parent / file_path_str
                else: # If blend file not saved, this is tricky. Assume path is findable by Blender.
                    pass # image_path remains as Path(file_path_str)

        print(f"      Attempting to load image from: {image_path.resolve()}")

        mapping_type = texture_definition.get("MAPPING", "UV").upper()
        scale_str = texture_definition.get("SCALE", "(1.0,1.0,1.0)") # Expect 3D for mapping node
        uv_scale_tuple = safe_eval(scale_str, (1.0,1.0,1.0))
        if isinstance(uv_scale_tuple, (int, float)): # if single value, make it 2D/3D
            uv_scale = (float(uv_scale_tuple), float(uv_scale_tuple), 1.0)
        elif len(uv_scale_tuple) == 2:
            uv_scale = (uv_scale_tuple[0], uv_scale_tuple[1], 1.0)
        elif len(uv_scale_tuple) == 3:
            uv_scale = uv_scale_tuple
        else:
            uv_scale = (1.0, 1.0, 1.0)


        img_tex_node = nodes.new('ShaderNodeTexImage')
        img_tex_node.location = principled_bsdf_node.location - Vector((400, 0))

        try:
            img = bpy.data.images.load(filepath=str(image_path.resolve()), check_existing=True)
            img_tex_node.image = img
            print(f"        Image '{img.name}' loaded and assigned to Image Texture node.")
        except RuntimeError as e:
            print(f"      [!] Error loading image '{image_path.resolve()}': {e}. Skipping image texture.")
            nodes.remove(img_tex_node)
            return

        links.new(img_tex_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])

        if mapping_type == "UV":
            if not current_blender_object.data.uv_layers:
                print("      [Warning] UV Mapping requested for image texture, but object has no UV layers. UVs may not apply correctly.")
            else:
                uv_map_node = nodes.new('ShaderNodeUVMap')
                uv_map_node.location = img_tex_node.location - Vector((250, -50))
                # Try to set the active UV map, or the first one if active isn't obvious
                if current_blender_object.data.uv_layers.active:
                     uv_map_node.uv_map = current_blender_object.data.uv_layers.active.name
                elif current_blender_object.data.uv_layers:
                     uv_map_node.uv_map = current_blender_object.data.uv_layers[0].name

                mapping_node = nodes.new('ShaderNodeMapping')
                mapping_node.location = img_tex_node.location - Vector((200, 50))
                mapping_node.inputs['Scale'].default_value = uv_scale

                links.new(uv_map_node.outputs['UV'], mapping_node.inputs['Vector'])
                links.new(mapping_node.outputs['Vector'], img_tex_node.inputs['Vector'])
                print(f"        UV Map and Mapping nodes configured with scale {uv_scale}.")

    elif tex_type == "noise":
        noise_scale = float(texture_definition.get("SCALE", 5.0))
        # noise_strength_as_color_factor = float(texture_definition.get("STRENGTH", 1.0)) # Not used directly for base color mix here

        noise_tex_node = nodes.new('ShaderNodeTexNoise')
        noise_tex_node.location = principled_bsdf_node.location - Vector((350, 100))
        noise_tex_node.inputs['Scale'].default_value = noise_scale
        # Could add Detail, Roughness, Distortion from texture_definition if needed

        # Example: Connect Noise Factor to Base Color (monochromatic) or Noise Color to Base Color
        # For simplicity, let's use Factor to influence Base Color via a MixRGB or directly if that's desired.
        # Direct connection to Base Color might not always be what's wanted.
        # A common use is to mix with an existing color or use factor for roughness/bump.
        # Here, we'll connect its 'Color' output to BSDF 'Base Color'.
        links.new(noise_tex_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
        print(f"        Noise Texture node configured (Scale: {noise_scale}) and linked to Base Color.")
    else:
        print(f"    [Warning] Unknown texture TYPE: '{tex_type}'. Skipping texture application.")


def apply_material(blender_obj: bpy.types.Object, material_def: dict):
    """
    Applies or creates and applies a material to the Blender object.
    Handles base color, emission, and now textures.
    """
    if not blender_obj or not material_def:
        print("  [!] Apply Material: Missing Blender object or material definition. Skipping.")
        return

    mat_name = material_def.get("NAME", f"{blender_obj.name}_Material")
    print(f"  [*] Applying material '{mat_name}' to '{blender_obj.name}'...")

    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        print(f"    Created new material: {mat_name}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Get or create Principled BSDF
    principled_bsdf = None
    output_node = None

    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled_bsdf = node
            break
    if not principled_bsdf:
        principled_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled_bsdf.location = (0,0)

    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
            break
    if not output_node: # Should always exist by default, but good check
        output_node = nodes.new(type='ShaderNodeOutputMaterial')
        output_node.location = (300,0)

    # Link BSDF to output if not already linked
    is_linked = False
    for link in links:
        if link.from_node == principled_bsdf and link.to_node == output_node:
            if link.from_socket == principled_bsdf.outputs['BSDF'] and link.to_socket == output_node.inputs['Surface']:
                is_linked = True
                break
    if not is_linked:
        links.new(principled_bsdf.outputs['BSDF'], output_node.inputs['Surface'])

    # Apply base color if not overridden by texture
    texture_data = material_def.get("TEXTURE")
    texture_will_set_base_color = False
    if isinstance(texture_data, dict) and texture_data.get("TYPE", "").lower() in ["image", "noise"]:
        texture_will_set_base_color = True # Assume texture connection replaces base color input

    if not texture_will_set_base_color and "BASE_COLOR" in material_def:
        base_color_val = parse_color(material_def["BASE_COLOR"], (0.8, 0.8, 0.8, 1.0))
        principled_bsdf.inputs["Base Color"].default_value = base_color_val
        print(f"    Set Base Color to: {base_color_val}")

    if "EMISSION" in material_def:
        emission_strength = float(material_def.get("EMISSION", 0.0))
        principled_bsdf.inputs["Emission Strength"].default_value = emission_strength
        print(f"    Set Emission Strength to: {emission_strength}")
        if "EMISSION_COLOR" in material_def:
            emission_color_val = parse_color(material_def["EMISSION_COLOR"], (0.0,0.0,0.0,1.0)) # Default black if parse fails
            principled_bsdf.inputs["Emission Color"].default_value = emission_color_val
            print(f"    Set Emission Color to: {emission_color_val}")
        elif emission_strength > 0: # If strength but no color, use base color or white
             principled_bsdf.inputs["Emission Color"].default_value = principled_bsdf.inputs["Base Color"].default_value

    # Apply Texture
    if isinstance(texture_data, dict):
        print(f"    Processing TEXTURE block for material '{mat_name}'")
        apply_texture_to_material_nodes(principled_bsdf, texture_data, blender_obj)
    else:
        print(f"    No TEXTURE block or invalid format in material_def for '{mat_name}'.")


    # Assign material to object
    if blender_obj.data.materials:
        blender_obj.data.materials[0] = mat
    else:
        blender_obj.data.materials.append(mat)
    print(f"    ✅ Material '{mat_name}' applied and configured on '{blender_obj.name}'.")


def export_to_glb(blender_obj: bpy.types.Object, export_filepath_str: str):
    """
    Exports the given Blender object to a GLB file.
    """
    if not blender_obj:
        print("  [!] Export GLB: No Blender object provided. Skipping export.")
        return
    if not export_filepath_str:
        print("  [!] Export GLB: No export file path provided. Skipping export.")
        return

    export_path = Path(export_filepath_str)
    # Try to resolve relative to project root if not absolute
    if not export_path.is_absolute():
        try:
            script_dir_parent = Path(__file__).resolve().parent.parent
            export_path = script_dir_parent / export_filepath_str
        except NameError: # __file__ not defined
            if bpy.data.filepath:
                export_path = Path(bpy.data.filepath).parent / export_filepath_str
            else: # Cannot make it absolute, proceed with relative path
                 pass

    print(f"  [*] Exporting '{blender_obj.name}' to GLB: {export_path.resolve()}")

    try:
        export_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e_mkdir:
        print(f"    [!] Error creating export directory '{export_path.parent}': {e_mkdir}. Export may fail.")
        # Optionally, could decide to return here if directory creation is critical

    bpy.ops.object.select_all(action='DESELECT')
    blender_obj.select_set(True)
    bpy.context.view_layer.objects.active = blender_obj

    try:
        bpy.ops.export_scene.gltf(
            filepath=str(export_path.resolve()),
            export_format='GLB',
            use_selection=True,
            export_apply=True, # Apply modifiers
            export_materials='EXPORT',
            export_texcoords=True,
            export_normals=True,
            export_images='AUTOMATIC' # Embeds if not packed, references if packed/already path. Or use 'EMBED'
        )
        print(f"    ✅ Successfully exported '{blender_obj.name}' to '{export_path.resolve()}'.")
    except Exception as e:
        print(f"    [!] Error exporting '{blender_obj.name}' to GLB: {e}")

# --- Main Handler ---
def handle_zw_mesh_block(mesh_def: dict, collection_to_link=None):
    """
    Handles a ZW-MESH definition block to create and configure a procedural mesh.
    """
    if not bpy:
        print("[Critical Error] bpy module not available. Cannot process ZW-MESH.")
        return None
    if not isinstance(mesh_def, dict):
        print("[Error] ZW-MESH definition is not a dictionary. Skipping.")
        return None

    obj_name = mesh_def.get("NAME", "Unnamed_ZWMesh")
    print(f"[*] Processing ZW-MESH: {obj_name}")

    created_obj = None
    try:
        created_obj = create_base_mesh(mesh_def)
        if not created_obj:
            raise ValueError(f"Base mesh creation failed for {obj_name}")

        # Set transform after creation
        loc_str = mesh_def.get("LOCATION", "(0,0,0)")
        rot_str = mesh_def.get("ROTATION", "(0,0,0)")
        scale_str = mesh_def.get("SCALE", "(1,1,1)")

        created_obj.location = safe_eval(loc_str, (0,0,0))
        # Rotation needs conversion from degrees (ZW convention) to radians (Blender)
        rot_deg = safe_eval(rot_str, (0,0,0))
        created_obj.rotation_euler = [math.radians(a) for a in rot_deg]

        scale_val = safe_eval(scale_str, (1,1,1))
        if isinstance(scale_val, (int, float)): # Uniform scale
             created_obj.scale = (float(scale_val), float(scale_val), float(scale_val))
        else: # Tuple scale
             created_obj.scale = scale_val

        print(f"    Set Transform: LOC={created_obj.location}, ROT_EULER={created_obj.rotation_euler}, SCALE={created_obj.scale}")

        # UV Unwrapping (conditional, before material that might use UVs)
        material_data = mesh_def.get("MATERIAL", {})
        texture_data = material_data.get("TEXTURE", {})
        if texture_data.get("MAPPING", "").upper() == "UV" and texture_data.get("TYPE", "").lower() == "image":
            print(f"    UV mapping required for image texture on '{obj_name}'.")
            add_uv_mapping(created_obj)

        # Apply Deformations
        deformations = mesh_def.get("DEFORMATIONS")
        if isinstance(deformations, list) and deformations:
            apply_deformations(created_obj, deformations)

        # Apply Material
        if isinstance(material_data, dict) and material_data: # Check if material_data is a non-empty dict
            apply_material(created_obj, material_data)

        # Link to collection
        target_collection_name = mesh_def.get("COLLECTION")
        if target_collection_name:
            # Logic to get/create and link to target_collection_name
            # This part might need a helper like blender_adapter's get_or_create_collection
            # For now, simple link to existing or new top-level.
            coll = bpy.data.collections.get(target_collection_name)
            if not coll:
                coll = bpy.data.collections.new(target_collection_name)
                bpy.context.scene.collection.children.link(coll)

            # Unlink from current collections (usually default scene collection)
            for c in created_obj.users_collection:
                c.objects.unlink(created_obj)
            coll.objects.link(created_obj)
            print(f"    Linked '{obj_name}' to collection '{coll.name}'.")

        elif collection_to_link: # Fallback to context collection from blender_adapter
             for c in created_obj.users_collection:
                c.objects.unlink(created_obj)
             collection_to_link.objects.link(created_obj)
             print(f"    Linked '{obj_name}' to passed collection '{collection_to_link.name}'.")


        # Export if defined
        export_def = mesh_def.get("EXPORT")
        if isinstance(export_def, dict) and export_def.get("FORMAT", "").lower() == "glb":
            file_path_str = export_def.get("FILE")
            if file_path_str:
                export_to_glb(created_obj, file_path_str)
            else:
                print("    [Warning] EXPORT block found with format 'glb' but no 'FILE' path specified.")

        print(f"  ✅ Successfully processed ZW-MESH: {obj_name}")
        return created_obj

    except Exception as e:
        print(f"  [Error] Failed to process ZW-MESH '{obj_name}': {e}")
        if created_obj: # If object was created but error occurred later, remove partial object
            bpy.data.objects.remove(created_obj, do_unlink=True)
        # Fallback: create an error cube
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=safe_eval(mesh_def.get("LOCATION", "(0,0,0)"), (0,0,0)))
        error_cube = bpy.context.object
        error_cube.name = f"ERROR_{obj_name}"
        print(f"    Created fallback error cube: {error_cube.name}")
        return error_cube

if __name__ == "__main__":
    # This block is for direct testing of zw_mesh.py within Blender's Python environment.
    # It won't run if imported by blender_adapter.py.
    print("--- Running zw_mesh.py directly (for testing) ---")

    # Example ZW-MESH definition for testing
    example_mesh_def = {
        "NAME": "Test_UV_ImageExport_Cylinder",
        "TYPE": "cylinder",
        "PARAMS": {"VERTICES": 16, "RADIUS": 0.7, "DEPTH": 2.2},
        "DEFORMATIONS": [
            {"TYPE": "twist", "AXIS": "Z", "ANGLE": 45},
            {"TYPE": "displace", "TEXTURE": "noise", "STRENGTH": 0.15}
        ],
        "MATERIAL": {
            "NAME": "TestCylinderMat",
            "BASE_COLOR": "#A0A0FF", # Light Blue
            "EMISSION": 0.05,
            "TEXTURE": {
                "TYPE": "image",
                # IMPORTANT: Create a dummy 'assets/textures/test_uv_grid.png' or similar for this to work
                # Or use an absolute path to an existing image on your system.
                "FILE": "assets/textures/test_uv_grid.png",
                "MAPPING": "UV",
                "SCALE": "(2.0, 2.0)"
            }
        },
        "LOCATION": "(3, 0, 1.1)", # Z = DEPTH / 2
        "ROTATION": "(0, 0, 0)",
        "SCALE": "(1,1,1)",
        "COLLECTION": "TestMeshes",
        "EXPORT": {
            "FORMAT": "glb",
            "FILE": "exports/test_cylinder.glb"
        }
    }

    # Ensure dummy texture file and directories exist for test to run fully
    # For example, create:
    # project_root/assets/textures/test_uv_grid.png (e.g., a 128x128 UV grid image)
    # project_root/exports/

    # Create dummy texture and directories if they don't exist, for the example to run
    try:
        assets_dir = Path("assets/textures")
        assets_dir.mkdir(parents=True, exist_ok=True)
        dummy_texture_path = assets_dir / "test_uv_grid.png"
        if not dummy_texture_path.exists():
            # Create a tiny placeholder PNG image using bpy if possible, or skip if too complex for here
            # For simplicity, we'll just note if it's missing.
            print(f"[Test Setup] Dummy texture {dummy_texture_path} not found. Image texturing might fail or use pink.")
            # bpy.ops.image.new(name="test_uv_grid", width=64, height=64, color=(0.8,0.1,0.8,1), alpha=False)
            # if bpy.data.images.get("test_uv_grid"): bpy.data.images["test_uv_grid"].filepath_raw = str(dummy_texture_path); bpy.data.images["test_uv_grid"].save()

        exports_dir = Path("exports")
        exports_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e_test_setup:
        print(f"[Test Setup Error] Could not create dummy assets/exports for testing: {e_test_setup}")

    # Process the example
    test_obj = handle_zw_mesh_block(example_mesh_def)
    if test_obj:
        print(f"Test ZW-MESH processed. Resulting object: {test_obj.name}")
    else:
        print("Test ZW-MESH processing failed.")

    print("--- Direct test of zw_mesh.py finished ---")
