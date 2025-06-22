# zw_mcp/blender_adapter.py
import sys
import json # For potential pretty printing if needed, not directly for to_zw
from pathlib import Path
import argparse
import math # Added for math.radians
from pathlib import Path # Ensure Path is imported for handle_zw_compose_block
from mathutils import Vector, Euler # For ZW-COMPOSE transforms

# Attempt to import bpy, handling the case where the script is not run within Blender
try:
    import bpy
except ImportError:
    print("[!] bpy module not found. This script must be run within Blender's Python environment.")
    bpy = None # Define bpy as None so parts of the script can still be tested if needed

# Try to import parse_zw from zw_mcp.zw_parser
try:
    from zw_parser import parse_zw
except ImportError:
    print("[!] Could not import 'parse_zw' from 'zw_mcp.zw_parser'.")
    try:
        from zw_parser import parse_zw
    except ImportError:
        print("[!] Fallback import of 'parse_zw' also failed.")
        print("[!] Ensure 'zw_parser.py' is accessible and zw_mcp is in PYTHONPATH or script is run appropriately.")
        def parse_zw(text: str) -> dict:
            print("[!] Dummy parse_zw called. Real parsing will not occur.")
            return {}
        # sys.exit(1) # Or exit if critical

# Try to import handle_zw_mesh_block from zw_mesh (relative, package, or direct)
ZW_MESH_IMPORTED = False
HANDLE_ZW_MESH_BLOCK_FUNC = None
try:
    from .zw_mesh import handle_zw_mesh_block as imported_handle_zw_mesh_block
    HANDLE_ZW_MESH_BLOCK_FUNC = imported_handle_zw_mesh_block
    ZW_MESH_IMPORTED = True
    print("Successfully imported handle_zw_mesh_block from .zw_mesh (relative).")
except ImportError:
    # Fallback if relative import fails
    try:
        from zw_mcp.zw_mesh import handle_zw_mesh_block as pkg_imported_handle_zw_mesh_block
        HANDLE_ZW_MESH_BLOCK_FUNC = pkg_imported_handle_zw_mesh_block
        ZW_MESH_IMPORTED = True
        print("Successfully imported handle_zw_mesh_block from zw_mcp.zw_mesh (package).")
    except ImportError as e_pkg_mesh:
        print(f"Failed package import of handle_zw_mesh_block from zw_mcp.zw_mesh: {e_pkg_mesh}")
        try:
            from zw_mesh import handle_zw_mesh_block as direct_imported_handle_zw_mesh_block
            HANDLE_ZW_MESH_BLOCK_FUNC = direct_imported_handle_zw_mesh_block
            ZW_MESH_IMPORTED = True
            print("Successfully imported handle_zw_mesh_block (direct from script directory - fallback).")
        except ImportError as e_direct_mesh:
            print(f"All import attempts for handle_zw_mesh_block failed: {e_direct_mesh}")
            def HANDLE_ZW_MESH_BLOCK_FUNC(mesh_def_dict, collection_context=None): # Ensure dummy has same signature
                print("[Critical Error] zw_mesh.handle_zw_mesh_block was not imported. Cannot process ZW-MESH.")
                return None

# --- Imports for zw_mesh utilities needed by ZW-COMPOSE ---
APPLY_ZW_MESH_MATERIAL_FUNC = None
EXPORT_ZW_MESH_TO_GLB_FUNC = None
ZW_MESH_UTILS_IMPORTED = False
try:
    from .zw_mesh import apply_material as imported_apply_material, export_to_glb as imported_export_glb
    APPLY_ZW_MESH_MATERIAL_FUNC = imported_apply_material
    EXPORT_ZW_MESH_TO_GLB_FUNC = imported_export_glb
    ZW_MESH_UTILS_IMPORTED = True
    print("Successfully imported apply_material, export_to_glb from .zw_mesh (relative).")
except ImportError:
    try:
        from zw_mcp.zw_mesh import apply_material as pkg_imported_apply_material, export_to_glb as pkg_imported_export_glb
        APPLY_ZW_MESH_MATERIAL_FUNC = pkg_imported_apply_material
        EXPORT_ZW_MESH_TO_GLB_FUNC = pkg_imported_export_glb
        ZW_MESH_UTILS_IMPORTED = True
        print("Successfully imported apply_material, export_to_glb from zw_mcp.zw_mesh (package).")
    except ImportError as e_pkg_utils:
        print(f"Failed package import of zw_mesh utils: {e_pkg_utils}")
        try:
            from zw_mesh import apply_material as direct_imported_apply_material, export_to_glb as direct_imported_export_glb
            APPLY_ZW_MESH_MATERIAL_FUNC = direct_imported_apply_material
            EXPORT_ZW_MESH_TO_GLB_FUNC = direct_imported_export_glb
            ZW_MESH_UTILS_IMPORTED = True
            print("Successfully imported zw_mesh utils (direct from script directory - fallback).")
        except ImportError as e_direct_utils:
            print(f"All import attempts for zw_mesh utils (apply_material, export_to_glb) failed: {e_direct_utils}")
            # Define dummies if import failed
            def APPLY_ZW_MESH_MATERIAL_FUNC(obj, material_def):
                print("[Critical Error] zw_mesh.apply_material was not imported. Cannot apply material override in ZW-COMPOSE.")
            def EXPORT_ZW_MESH_TO_GLB_FUNC(blender_obj, export_filepath_str):
                print("[Critical Error] zw_mesh.export_to_glb was not imported. Cannot export in ZW-COMPOSE.")

ZW_INPUT_FILE_PATH = Path("zw_mcp/prompts/blender_scene.zw")

def safe_eval(str_val, default_val):
    if not isinstance(str_val, str): return default_val
    try: return eval(str_val)
    except (SyntaxError, NameError, TypeError, ValueError) as e:
        print(f"    [!] Warning: Could not evaluate string '{str_val}' for attribute: {e}. Using default: {default_val}")
        return default_val

def get_or_create_collection(name: str, parent_collection=None):
    if not bpy: return None
    if parent_collection is None: parent_collection = bpy.context.scene.collection
    existing_collection = parent_collection.children.get(name)
    if existing_collection:
        print(f"    Found existing collection: '{name}' in '{parent_collection.name}'")
        return existing_collection
    else:
        new_collection = bpy.data.collections.new(name=name)
        parent_collection.children.link(new_collection)
        print(f"    Created and linked new collection: '{name}' to '{parent_collection.name}'")
        return new_collection

def parse_color(color_str_val, default_color=(0.8, 0.8, 0.8, 1.0)):
    if not isinstance(color_str_val, str): return default_color
    s = color_str_val.strip()
    if s.startswith("#"):
        hex_color = s.lstrip("#")
        try:
            if len(hex_color) == 6: r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)); return (r, g, b, 1.0)
            elif len(hex_color) == 8: r, g, b, a = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4, 6)); return (r, g, b, a)
        except ValueError: return default_color
    elif s.startswith("(") and s.endswith(")"):
        try:
            parts = [float(p.strip()) for p in s.strip("()").split(",")];
            if len(parts) == 3: return (parts[0], parts[1], parts[2], 1.0)
            if len(parts) == 4: return tuple(parts)
        except ValueError: return default_color
    return default_color

def handle_zw_object_creation(obj_attributes: dict, parent_bpy_obj=None):
    if not bpy: return None
    obj_type = obj_attributes.get("TYPE")
    if not obj_type or not isinstance(obj_type, str): print(f"    [!] Warning: Missing or invalid 'TYPE' in ZW-OBJECT attributes. Skipping."); return None
    obj_name = obj_attributes.get("NAME", obj_type)
    loc_tuple = safe_eval(obj_attributes.get("LOCATION", "(0,0,0)"), (0,0,0))
    scale_str = obj_attributes.get("SCALE", "(1,1,1)")
    if isinstance(scale_str, (int, float)): scale_tuple = (float(scale_str), float(scale_str), float(scale_str))
    elif isinstance(scale_str, str):
        eval_scale = safe_eval(scale_str, (1,1,1))
        if isinstance(eval_scale, (int, float)): scale_tuple = (float(eval_scale), float(eval_scale), float(eval_scale))
        elif isinstance(eval_scale, tuple) and len(eval_scale) == 3: scale_tuple = eval_scale
        else: scale_tuple = (1,1,1); print(f"    [!] Warning: Invalid SCALE format '{scale_str}'. Defaulting to (1,1,1).")
    else: scale_tuple = (1,1,1); print(f"    [!] Warning: Invalid SCALE type '{type(scale_str)}'. Defaulting to (1,1,1).")
    print(f"[*] Creating Blender object: TYPE='{obj_type}', NAME='{obj_name}', LOC={loc_tuple}, SCALE={scale_tuple}")
    obj_type_lower = obj_type.lower(); created_bpy_obj = None
    try:
        if obj_type_lower == "sphere": bpy.ops.mesh.primitive_uv_sphere_add(location=loc_tuple)
        elif obj_type_lower == "cube": bpy.ops.mesh.primitive_cube_add(location=loc_tuple)
        # ... (other primitive types) ...
        elif obj_type_lower == "plane": bpy.ops.mesh.primitive_plane_add(location=loc_tuple)
        elif obj_type_lower == "cone": bpy.ops.mesh.primitive_cone_add(location=loc_tuple)
        elif obj_type_lower == "cylinder": bpy.ops.mesh.primitive_cylinder_add(location=loc_tuple)
        elif obj_type_lower == "torus": bpy.ops.mesh.primitive_torus_add(location=loc_tuple)
        else: print(f"    [!] Warning: ZW object TYPE '{obj_type}' not recognized. Skipping."); return None
        created_bpy_obj = bpy.context.object
        if created_bpy_obj:
            created_bpy_obj.name = obj_name; created_bpy_obj.scale = scale_tuple
            print(f"    ✅ Created and configured: {created_bpy_obj.name} (Type: {obj_type})")
            if parent_bpy_obj:
                bpy.ops.object.select_all(action='DESELECT'); created_bpy_obj.select_set(True); parent_bpy_obj.select_set(True)
                bpy.context.view_layer.objects.active = parent_bpy_obj
                try: bpy.ops.object.parent_set(type='OBJECT', keep_transform=True); print(f"    Parented '{created_bpy_obj.name}' to '{parent_bpy_obj.name}'")
                except RuntimeError as e: print(f"    [Error] Parenting failed: {e}")
            if hasattr(created_bpy_obj.data, 'materials'):
                mat_name = obj_attributes.get("MATERIAL"); color_str = obj_attributes.get("COLOR")
                shade_str = obj_attributes.get("SHADING", "Smooth").lower(); bsdf_data = obj_attributes.get("BSDF")
                final_mat_name = mat_name or f"{created_bpy_obj.name}_Mat"
                mat = bpy.data.materials.get(final_mat_name) or bpy.data.materials.new(name=final_mat_name)
                if mat.name == final_mat_name and not bpy.data.materials.get(final_mat_name): print(f"    Created new material: {final_mat_name}") # Approx
                else: print(f"    Using existing material: {final_mat_name}")
                mat.use_nodes = True; nodes = mat.node_tree.nodes; links = mat.node_tree.links
                bsdf = nodes.get("Principled BSDF") or nodes.new(type='ShaderNodeBsdfPrincipled')
                out_node = nodes.get('Material Output') or nodes.new(type='ShaderNodeOutputMaterial')
                if not any(link.from_node == bsdf and link.to_node == out_node for link in links): links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
                color_set_by_bsdf = False
                if isinstance(bsdf_data, dict):
                    print(f"    Applying BSDF properties: {bsdf_data}")
                    for k, v_any in bsdf_data.items():
                        bsdf_in_name = k.replace("_", " ").title();
                        if k.lower() == "alpha": bsdf_in_name = "Alpha"
                        if bsdf.inputs.get(bsdf_in_name):
                            try:
                                if "Color" in bsdf_in_name and isinstance(v_any, (str, tuple, list)):
                                    pc = parse_color(str(v_any)); bsdf.inputs[bsdf_in_name].default_value = pc
                                    if bsdf_in_name == "Base Color": color_set_by_bsdf = True
                                    print(f"      Set BSDF.{bsdf_in_name} to {pc}")
                                else: bsdf.inputs[bsdf_in_name].default_value = float(v_any); print(f"      Set BSDF.{bsdf_in_name} to {float(v_any)}")
                            except Exception as e_bsdf: print(f"      [Warning] Failed to set BSDF input {bsdf_in_name}: {e_bsdf}")
                        else: print(f"      [Warning] BSDF input '{bsdf_in_name}' not found.")
                if color_str and not color_set_by_bsdf:
                    pc_val = parse_color(color_str); bsdf.inputs["Base Color"].default_value = pc_val
                    print(f"    Set Base Color to {pc_val} (from COLOR attribute)")
                if not created_bpy_obj.data.materials: created_bpy_obj.data.materials.append(mat)
                else: created_bpy_obj.data.materials[0] = mat
                print(f"    Assigned material '{final_mat_name}' to '{created_bpy_obj.name}'")
                bpy.ops.object.select_all(action='DESELECT'); created_bpy_obj.select_set(True)
                bpy.context.view_layer.objects.active = created_bpy_obj
                if shade_str == "smooth": bpy.ops.object.shade_smooth(); print(f"    Set shading to Smooth.")
                elif shade_str == "flat": bpy.ops.object.shade_flat(); print(f"    Set shading to Flat.")
        else: print(f"    [!] Error: Object creation did not result in an active object."); return None
    except Exception as e: print(f"    [!] Error creating Blender object '{obj_name}': {e}"); return None
    return created_bpy_obj

def apply_array_gn(source_obj: bpy.types.Object, params: dict):
    if not bpy or not source_obj: print("[!] ARRAY: bpy or source_obj missing."); return
    print(f"[*] Applying ARRAY GN to '{source_obj.name}' with {params}")
    host_name = f"{source_obj.name}_ArrayHost"; host_obj = bpy.data.objects.new(host_name, None)
    src_coll = source_obj.users_collection[0] if source_obj.users_collection else bpy.context.scene.collection
    src_coll.objects.link(host_obj); print(f"    Created ARRAY host '{host_name}' in '{src_coll.name}'")
    mod = host_obj.modifiers.new(name="ZW_Array", type='NODES')
    tree_name = f"ZW_Array_{source_obj.name}_GN"; gn_tree = bpy.data.node_groups.get(tree_name)
    if not gn_tree:
        gn_tree = bpy.data.node_groups.new(name=tree_name, type='GeometryNodeTree'); print(f"    Created GN Tree: {tree_name}")
        nodes = gn_tree.nodes; links = gn_tree.links; nodes.clear()
        inp = nodes.new(type='NodeGroupInput'); inp.location=(-400,0); outp = nodes.new(type='NodeGroupOutput'); outp.location=(400,0)
        gn_tree.outputs.new('NodeSocketGeometry', 'Geometry') # Ensure output socket exists
        obj_info = nodes.new('GeometryNodeObjectInfo'); obj_info.location=(-200,200); obj_info.inputs['Object'].default_value=source_obj
        line = nodes.new('NodeGeometryMeshLine'); line.location=(-200,-100)
        line.mode = 'OFFSET'; line.inputs['Count'].default_value = int(params.get("COUNT",5))
        line.inputs['Offset'].default_value = safe_eval(str(params.get("OFFSET","(0,0,1)")),(0,0,1))
        inst = nodes.new('GeometryNodeInstanceOnPoints'); inst.location=(0,0)
        links.new(line.outputs['Mesh'], inst.inputs['Points']); links.new(obj_info.outputs['Geometry'], inst.inputs['Instance'])
        if str(params.get("MODE","INSTANCE")).upper() == "REALIZE":
            realize = nodes.new('GeometryNodeRealizeInstances'); realize.location=(200,0)
            links.new(inst.outputs['Instances'],realize.inputs['Geometry']); links.new(realize.outputs['Geometry'],outp.inputs['Geometry'])
        else: links.new(inst.outputs['Instances'],outp.inputs['Geometry'])
    else: print(f"    Reusing GN Tree: {tree_name}")
    mod.node_group = gn_tree; bpy.context.view_layer.objects.active = host_obj; host_obj.select_set(True)
    print(f"    Applied ARRAY to '{host_name}'")

def apply_displace_noise_gn(target_obj: bpy.types.Object, params: dict):
    if not bpy or not target_obj or target_obj.type != 'MESH': print(f"[!] DISPLACE: Target '{target_obj.name if target_obj else 'None'}' not a MESH. Skipping."); return
    print(f"[*] Applying DISPLACE_NOISE GN to '{target_obj.name}' with {params}")
    mod = target_obj.modifiers.new(name="ZW_DisplaceNoise", type='NODES')
    tree_name = f"ZW_Displace_{target_obj.name}_GN"; gn_tree = bpy.data.node_groups.get(tree_name)
    if not gn_tree:
        gn_tree = bpy.data.node_groups.new(name=tree_name, type='GeometryNodeTree'); print(f"    Created GN Tree: {tree_name}")
        nodes=gn_tree.nodes; links=gn_tree.links; nodes.clear()
        inp=nodes.new('NodeGroupInput'); inp.location=(-600,0); outp=nodes.new('NodeGroupOutput'); outp.location=(400,0)
        gn_tree.inputs.new('NodeSocketGeometry','Geometry'); gn_tree.outputs.new('NodeSocketGeometry','Geometry')
        set_pos=nodes.new('GeometryNodeSetPosition'); set_pos.location=(0,0)
        noise=nodes.new('ShaderNodeTexNoise'); noise.location=(-400,-200); noise.noise_dimensions='3D'
        noise.inputs['Scale'].default_value=float(params.get("SCALE",5.0)); noise.inputs['W'].default_value=float(params.get("SEED",0.0))
        norm=nodes.new('GeometryNodeInputNormal'); norm.location=(-400,0)
        str_scale=nodes.new('ShaderNodeMath'); str_scale.operation='MULTIPLY'; str_scale.location=(-200,-200)
        str_scale.inputs[1].default_value=float(params.get("STRENGTH",0.5)); links.new(noise.outputs['Fac'],str_scale.inputs[0])
        axis=params.get("AXIS","NORMAL").upper(); offset_src_node=None
        if axis in ['X','Y','Z']:
            comb_xyz=nodes.new('ShaderNodeCombineXYZ'); comb_xyz.location=(-200,200)
            if axis=='X': links.new(str_scale.outputs['Value'],comb_xyz.inputs['X'])
            elif axis=='Y': links.new(str_scale.outputs['Value'],comb_xyz.inputs['Y'])
            else: links.new(str_scale.outputs['Value'],comb_xyz.inputs['Z'])
            offset_src_node=comb_xyz
        else: # NORMAL
            vec_mult=nodes.new('ShaderNodeVectorMath'); vec_mult.operation='MULTIPLY'; vec_mult.location=(-200,0)
            links.new(norm.outputs['Normal'],vec_mult.inputs[0]); links.new(str_scale.outputs['Value'],vec_mult.inputs[1])
            offset_src_node=vec_mult; print("    Displacing along Normal.")
        links.new(offset_src_node.outputs['Vector'],set_pos.inputs['Offset'])
        links.new(inp.outputs['Geometry'],set_pos.inputs['Geometry']); links.new(set_pos.outputs['Geometry'],outp.inputs['Geometry'])
    else: print(f"    Reusing GN Tree: {tree_name}")
    mod.node_group=gn_tree; bpy.context.view_layer.objects.active=target_obj; target_obj.select_set(True)
    print(f"    Applied DISPLACE_NOISE to '{target_obj.name}'")

def handle_zw_animation_block(anim_data: dict):
    if not bpy: return
    target_obj_name = anim_data.get("TARGET_OBJECT"); prop_path = anim_data.get("PROPERTY_PATH"); idx_str = anim_data.get("INDEX")
    unit = anim_data.get("UNIT","").lower(); interp_str = anim_data.get("INTERPOLATION","BEZIER").upper(); kf_list = anim_data.get("KEYFRAMES")
    if not all([target_obj_name,prop_path,kf_list]): print(f"[!] ZW-ANIMATION '{anim_data.get('NAME','Unnamed')}' missing required fields. Skipping."); return
    target_obj = bpy.data.objects.get(target_obj_name)
    if not target_obj: print(f"[!] ZW-ANIMATION target '{target_obj_name}' not found. Skipping."); return
    if not target_obj.animation_data: target_obj.animation_data_create()
    act_name = anim_data.get("NAME",f"{target_obj.name}_{prop_path}_Action")
    if not target_obj.animation_data.action or (target_obj.animation_data.action.name != act_name and anim_data.get("NAME")):
        target_obj.animation_data.action = bpy.data.actions.new(name=act_name)
    action = target_obj.animation_data.action; prop_idx = None
    if idx_str is not None:
        try: prop_idx = int(idx_str)
        except ValueError: print(f"    [Warning] Invalid INDEX '{idx_str}'. Ignoring."); prop_idx = None
    print(f"  Animating '{target_obj.name}.{prop_path}' (Idx:{prop_idx if prop_idx is not None else 'All'}) using {interp_str}")
    for kf in kf_list:
        frame = kf.get("FRAME"); val_in = kf.get("VALUE")
        if frame is None or val_in is None: print(f"    [Warning] Keyframe missing FRAME/VALUE. Skipping: {kf}"); continue
        frame = float(frame)
        if prop_idx is not None:
            try:
                val = float(val_in)
                if unit=="degrees" and "rotation" in prop_path.lower(): val = math.radians(val)
                fc = action.fcurves.find(prop_path,index=prop_idx) or action.fcurves.new(prop_path,index=prop_idx,action_group=target_obj.name)
                kp = fc.keyframe_points.insert(frame,val); kp.interpolation = interp_str
            except ValueError: print(f"    [Warning] Invalid scalar VALUE '{val_in}'. Skipping KF.")
        else:
            pt = safe_eval(str(val_in),None)
            if isinstance(pt,tuple) and (len(pt)==3 or len(pt)==4):
                vals = [math.radians(c) if unit=="degrees" and "rotation" in prop_path.lower() else c for c in pt]
                for i,comp_v in enumerate(vals):
                    fc = action.fcurves.find(prop_path,index=i) or action.fcurves.new(prop_path,index=i,action_group=target_obj.name)
                    kp = fc.keyframe_points.insert(frame,comp_v); kp.interpolation = interp_str
            else: print(f"    [Warning] Invalid vector VALUE '{val_in}'. Skipping KF.")
    print(f"    ✅ Finished animation: {act_name}")

def handle_zw_driver_block(driver_data: dict):
    if not bpy: return
    src_name = driver_data.get("SOURCE_OBJECT"); src_prop = driver_data.get("SOURCE_PROPERTY")
    tgt_name = driver_data.get("TARGET_OBJECT"); tgt_prop = driver_data.get("TARGET_PROPERTY")
    expr = driver_data.get("EXPRESSION","var"); drv_name = driver_data.get("NAME",f"ZWDriver_{tgt_name}_{tgt_prop}")
    if not all([src_name,src_prop,tgt_name,tgt_prop]): print(f"[!] ZW-DRIVER '{drv_name}': Missing required fields. Skipping."); return
    src_obj = bpy.data.objects.get(src_name); tgt_obj = bpy.data.objects.get(tgt_name)
    if not src_obj: print(f"[!] ZW-DRIVER '{drv_name}': Source obj '{src_name}' not found. Skipping."); return
    if not tgt_obj: print(f"[!] ZW-DRIVER '{drv_name}': Target obj '{tgt_name}' not found. Skipping."); return
    print(f"[*] Creating ZW-DRIVER '{drv_name}': {src_name}.{src_prop} -> {tgt_name}.{tgt_prop}")
    try:
        path = tgt_prop; idx = -1
        if '[' in tgt_prop and tgt_prop.endswith(']'):
            parts = tgt_prop.split('['); path=parts[0]
            try: idx = int(parts[1].rstrip(']'))
            except ValueError: print(f"    [Error] Invalid index in TARGET_PROPERTY: {tgt_prop}. Skipping."); return
        fc = tgt_obj.driver_add(path,idx) if idx!=-1 else tgt_obj.driver_add(path)
        drv = fc.driver; drv.type='SCRIPTED'; drv.expression=expr
        var = drv.variables.new(); var.name="var"; var.type='SINGLE_PROP'
        var.targets[0].id_type='OBJECT'; var.targets[0].id=src_obj; var.targets[0].data_path=src_prop
        print(f"    ✅ Successfully created driver: '{drv_name}'")
    except Exception as e: print(f"    [!] Error setting up driver '{drv_name}': {e}")

def handle_property_anim_track(target_obj: bpy.types.Object, track_data: dict):
    """
    Handles a generic property animation track, creating keyframes for a specified property.
    This is intended to be called by other handlers like ZW-STAGE's PROPERTY_ANIM track.
    """
    if not bpy: return
    if not target_obj:
        print(f"    [!] PROPERTY_ANIM: Target object is None. Skipping track: {track_data.get('NAME','Unnamed')}")
        return

    property_path_str = track_data.get("PROPERTY_PATH")
    keyframes_list = track_data.get("KEYFRAMES")
    index_str = track_data.get("INDEX") # Optional
    unit_str = track_data.get("UNIT", "").lower() # Optional, e.g., "degrees"
    interpolation_str = track_data.get("INTERPOLATION", "BEZIER").upper() # Optional

    if not all([property_path_str, keyframes_list]):
        print(f"    [!] PROPERTY_ANIM for '{target_obj.name}': Missing PROPERTY_PATH or KEYFRAMES. Skipping.")
        return

    if not isinstance(keyframes_list, list):
        print(f"    [!] PROPERTY_ANIM for '{target_obj.name}': KEYFRAMES is not a list. Skipping.")
        return

    # Ensure animation data and action exist
    if not target_obj.animation_data:
        target_obj.animation_data_create()

    action_name = f"{target_obj.name}_{property_path_str.replace('.','_').replace('[','_').replace(']','')}_PropAnimAction"
    # Use existing action or create a new one if a specific name is given or no action exists
    # This logic could be refined if multiple distinct animations on the same property are common.
    if not target_obj.animation_data.action or \
       (track_data.get("ACTION_NAME") and target_obj.animation_data.action.name != track_data.get("ACTION_NAME")):
        action_name_from_data = track_data.get("ACTION_NAME", action_name)
        target_obj.animation_data.action = bpy.data.actions.new(name=action_name_from_data)

    action = target_obj.animation_data.action

    prop_idx = None
    if index_str is not None:
        try:
            prop_idx = int(index_str)
        except ValueError:
            print(f"    [Warning] PROPERTY_ANIM for '{target_obj.name}': Invalid INDEX '{index_str}'. Assuming non-indexed property.")
            prop_idx = None # Treat as if no index was provided

    print(f"    Animating '{target_obj.name}.{property_path_str}' (Index: {prop_idx if prop_idx is not None else 'All Components'}) using {interpolation_str}")

    for kf_data in keyframes_list:
        if not isinstance(kf_data, dict):
            print(f"    [Warning] PROPERTY_ANIM for '{target_obj.name}': Keyframe data is not a dictionary. Skipping KF: {kf_data}")
            continue

        frame_input = kf_data.get("FRAME")
        value_input = kf_data.get("VALUE")

        if frame_input is None or value_input is None:
            print(f"    [Warning] PROPERTY_ANIM for '{target_obj.name}': Keyframe missing FRAME or VALUE. Skipping KF: {kf_data}")
            continue

        try:
            frame = float(frame_input)
        except ValueError:
            print(f"    [Warning] PROPERTY_ANIM for '{target_obj.name}': Invalid FRAME '{frame_input}'. Skipping KF.")
            continue

        if prop_idx is not None: # Scalar or single component of a vector
            try:
                current_value = float(value_input)
                if unit_str == "degrees" and "rotation" in property_path_str.lower():
                    current_value = math.radians(current_value)

                fcurve = action.fcurves.find(property_path_str, index=prop_idx)
                if not fcurve:
                    fcurve = action.fcurves.new(property_path_str, index=prop_idx, action_group=target_obj.name)

                kf_point = fcurve.keyframe_points.insert(frame, current_value)
                kf_point.interpolation = interpolation_str
            except ValueError:
                print(f"    [Warning] PROPERTY_ANIM for '{target_obj.name}': Invalid scalar VALUE '{value_input}'. Skipping KF.")
            except Exception as e:
                print(f"    [Error] PROPERTY_ANIM for '{target_obj.name}': Failed to insert scalar keyframe for {property_path_str}[{prop_idx}]: {e}")

        else: # Vector/tuple (e.g., location, scale, color) or property without explicit index
            value_tuple = safe_eval(str(value_input), None) # safe_eval expects string

            if not isinstance(value_tuple, (tuple, list)):
                # Could be a single float for a property that is non-array but not explicitly indexed (e.g. "energy" for light)
                try:
                    current_value = float(value_input)
                    # No unit conversion here unless property_path_str implies it universally
                    fcurve = action.fcurves.find(property_path_str) # No index
                    if not fcurve:
                        fcurve = action.fcurves.new(property_path_str, action_group=target_obj.name)
                    kf_point = fcurve.keyframe_points.insert(frame, current_value)
                    kf_point.interpolation = interpolation_str
                except ValueError:
                    print(f"    [Warning] PROPERTY_ANIM for '{target_obj.name}': VALUE '{value_input}' is not a valid tuple/list or single float. Skipping KF.")
                except Exception as e:
                    print(f"    [Error] PROPERTY_ANIM for '{target_obj.name}': Failed to insert non-indexed keyframe for {property_path_str}: {e}")
                continue # Move to next keyframe_data

            # If it was a tuple/list from safe_eval
            if isinstance(value_tuple, (tuple, list)):
                for i, component_val in enumerate(value_tuple):
                    try:
                        current_comp_value = float(component_val) # Ensure component is float
                        if unit_str == "degrees" and "rotation" in property_path_str.lower():
                            current_comp_value = math.radians(current_comp_value)

                        fcurve = action.fcurves.find(property_path_str, index=i)
                        if not fcurve:
                            fcurve = action.fcurves.new(property_path_str, index=i, action_group=target_obj.name)

                        kf_point = fcurve.keyframe_points.insert(frame, current_comp_value)
                        kf_point.interpolation = interpolation_str
                    except ValueError:
                        print(f"    [Warning] PROPERTY_ANIM for '{target_obj.name}': Invalid component VALUE '{component_val}' in '{value_tuple}'. Skipping component.")
                    except Exception as e:
                        print(f"    [Error] PROPERTY_ANIM for '{target_obj.name}': Failed to insert component keyframe for {property_path_str}[{i}]: {e}")

    print(f"    ✅ Finished property animation for: {target_obj.name}.{property_path_str}")

def handle_material_override_track(target_obj: bpy.types.Object, track_data: dict):
    """
    Handles a material override track, changing an object's material at a specific frame
    and optionally restoring it, using keyframes with CONSTANT interpolation.
    """
    if not bpy: return
    if not target_obj:
        print(f"    [!] MATERIAL_OVERRIDE: Target object is None. Skipping track: {track_data.get('NAME','Unnamed')}")
        return

    material_name_to_assign_str = track_data.get("MATERIAL_NAME")
    start_frame_str = track_data.get("START_FRAME", "0") # Default to 0 if not specified
    end_frame_int_str = track_data.get("END_FRAME") # Optional
    restore_on_end_str = str(track_data.get("RESTORE_ON_END", "false")).lower()

    if not material_name_to_assign_str:
        print(f"    [!] MATERIAL_OVERRIDE for '{target_obj.name}': Missing MATERIAL_NAME. Skipping.")
        return

    try:
        start_frame_int = int(start_frame_str)
    except ValueError:
        print(f"    [Warning] MATERIAL_OVERRIDE for '{target_obj.name}': Invalid START_FRAME '{start_frame_str}'. Using 0.")
        start_frame_int = 0

    end_frame_int = None
    if end_frame_int_str is not None:
        try:
            end_frame_int = int(end_frame_int_str)
        except ValueError:
            print(f"    [Warning] MATERIAL_OVERRIDE for '{target_obj.name}': Invalid END_FRAME '{end_frame_int_str}'. Restoration at end might not occur.")

    restore = (restore_on_end_str == 'true')

    # Ensure the object has a material slot (typically operates on the first slot)
    if not target_obj.material_slots:
        print(f"    [*] MATERIAL_OVERRIDE for '{target_obj.name}': Object has no material slots. Appending one.")
        # This adds a new empty slot. If using .data.materials, it's slightly different.
        # For simplicity and direct slot animation, ensuring a slot object exists is key.
        target_obj.material_slots.new('') # Create an empty slot if none exist.
        # Alternative if you prefer to ensure data.materials has something:
        # if not target_obj.data.materials: target_obj.data.materials.append(None)

    if not target_obj.material_slots: # Should not happen if the above worked
        print(f"    [!] MATERIAL_OVERRIDE for '{target_obj.name}': Failed to ensure material slot. Skipping.")
        return

    # Get or create the new material
    new_mat = bpy.data.materials.get(material_name_to_assign_str)
    if not new_mat:
        new_mat = bpy.data.materials.new(name=material_name_to_assign_str)
        new_mat.use_nodes = True # Good practice for newly created materials
        print(f"    [*] MATERIAL_OVERRIDE for '{target_obj.name}': Created new material '{material_name_to_assign_str}'.")
    else:
        print(f"    [*] MATERIAL_OVERRIDE for '{target_obj.name}': Using existing material '{material_name_to_assign_str}'.")

    original_mat = None
    if restore and target_obj.material_slots[0].material:
        original_mat = target_obj.material_slots[0].material
        print(f"    [*] MATERIAL_OVERRIDE for '{target_obj.name}': Original material '{original_mat.name}' stored for restoration.")
    elif restore:
        print(f"    [*] MATERIAL_OVERRIDE for '{target_obj.name}': Restoration requested, but no original material in slot 0.")

    slot_path = "material_slots[0].material"

    # Keyframe original material before the switch, if restoring and not starting at the very beginning
    if restore and original_mat and start_frame_int > 0: # Frame 0 is a bit special, use >0
        # Ensure this keyframe is strictly before the new material's keyframe
        # max(0, start_frame_int - 1) could also work if frame 0 is a valid keyframe for other systems
        pre_switch_frame = start_frame_int - 1
        if pre_switch_frame < 0: pre_switch_frame = 0 # Clamp if start_frame_int was 0

        # Only insert if different from new_mat or if it's the first keyframe in a restore sequence
        if target_obj.material_slots[0].material != original_mat or \
           (target_obj.material_slots[0].material == original_mat and not target_obj.animation_data): # crude check
            target_obj.material_slots[0].material = original_mat
            try:
                kp = target_obj.keyframe_insert(data_path=slot_path, frame=pre_switch_frame)
                if kp: kp.interpolation = 'CONSTANT'
                print(f"    Keyframed original material '{original_mat.name}' at frame {pre_switch_frame} for '{target_obj.name}'.")
            except RuntimeError as e:
                 print(f"    [Warning] Failed to keyframe original material at pre-switch frame for '{target_obj.name}': {e}")


    # Keyframe the new material at the start frame
    target_obj.material_slots[0].material = new_mat
    try:
        kp = target_obj.keyframe_insert(data_path=slot_path, frame=start_frame_int)
        if kp: kp.interpolation = 'CONSTANT'
        print(f"    Set and keyframed material of '{target_obj.name}' to '{new_mat.name}' at frame {start_frame_int}.")
    except RuntimeError as e:
        print(f"    [Warning] Failed to keyframe new material for '{target_obj.name}': {e}")


    # Keyframe original material at the end frame, if restoring
    if restore and original_mat and end_frame_int is not None and end_frame_int > start_frame_int:
        target_obj.material_slots[0].material = original_mat
        try:
            kp = target_obj.keyframe_insert(data_path=slot_path, frame=end_frame_int)
            if kp: kp.interpolation = 'CONSTANT'
            print(f"    Restored and keyframed material of '{target_obj.name}' to '{original_mat.name}' at frame {end_frame_int}.")
        except RuntimeError as e:
            print(f"    [Warning] Failed to keyframe restored material for '{target_obj.name}': {e}")

    print(f"    ✅ Finished material override for: {target_obj.name}")

def handle_shader_switch_track(target_obj: bpy.types.Object, track_data: dict):
    """
    Handles a shader switch track, changing an input value on a specified shader node
    within a material associated with the target object, and keyframes it.
    """
    if not bpy: return
    if not target_obj:
        print(f"    [!] SHADER_SWITCH: Target object is None. Skipping track: {track_data.get('NAME','Unnamed')}")
        return

    material_name_str = track_data.get("MATERIAL_NAME") # Optional, specifies which material if multiple or not on object
    target_node_name_str = track_data.get("TARGET_NODE")
    input_name_str = track_data.get("INPUT_NAME")
    new_value_any_type = track_data.get("NEW_VALUE")
    frame_str = track_data.get("FRAME", "0")

    if not all([target_node_name_str, input_name_str, new_value_any_type is not None]): # new_value can be False or 0
        print(f"    [!] SHADER_SWITCH for '{target_obj.name}': Missing TARGET_NODE, INPUT_NAME, or NEW_VALUE. Skipping.")
        return

    try:
        frame_int = int(frame_str)
    except ValueError:
        print(f"    [Warning] SHADER_SWITCH for '{target_obj.name}': Invalid FRAME '{frame_str}'. Using 0.")
        frame_int = 0

    mat_to_modify = None
    # 1. Try explicit material_name_str
    if material_name_str:
        mat_candidate = bpy.data.materials.get(material_name_str)
        if mat_candidate:
            # Check if this material is actually on the object
            is_on_object = False
            for slot in target_obj.material_slots:
                if slot.material == mat_candidate:
                    mat_to_modify = mat_candidate
                    is_on_object = True
                    break
            if not is_on_object:
                print(f"    [Warning] SHADER_SWITCH: Material '{material_name_str}' found but not on object '{target_obj.name}'. Will try object's active/first material.")
        else:
            print(f"    [Warning] SHADER_SWITCH: Specified MATERIAL_NAME '{material_name_str}' not found. Will try object's active/first material.")

    # 2. If not found by name or name not given, try active material
    if not mat_to_modify and target_obj.active_material:
        mat_to_modify = target_obj.active_material
        print(f"    [*] SHADER_SWITCH: Using active material '{mat_to_modify.name}' of '{target_obj.name}'.")

    # 3. Else, try first material slot
    if not mat_to_modify and target_obj.material_slots and target_obj.material_slots[0].material:
        mat_to_modify = target_obj.material_slots[0].material
        print(f"    [*] SHADER_SWITCH: Using material '{mat_to_modify.name}' from slot 0 of '{target_obj.name}'.")

    if not mat_to_modify:
        print(f"    [!] SHADER_SWITCH for '{target_obj.name}': No suitable material found. Skipping.")
        return

    if not mat_to_modify.use_nodes or not mat_to_modify.node_tree:
        print(f"    [Warning] SHADER_SWITCH: Material '{mat_to_modify.name}' on '{target_obj.name}' does not use nodes or has no node tree. Skipping.")
        return

    target_node = mat_to_modify.node_tree.nodes.get(target_node_name_str)
    if not target_node:
        print(f"    [Warning] SHADER_SWITCH: Target node '{target_node_name_str}' not found in material '{mat_to_modify.name}'. Skipping.")
        return

    socket_input = target_node.inputs.get(input_name_str)
    if not socket_input:
        print(f"    [Warning] SHADER_SWITCH: Input socket '{input_name_str}' not found on node '{target_node_name_str}' in material '{mat_to_modify.name}'. Skipping.")
        return

    parsed_value = None
    try:
        if socket_input.type == 'RGBA':
            parsed_value = parse_color(str(new_value_any_type)) # parse_color expects string
        elif socket_input.type == 'VALUE': # Float
            parsed_value = float(new_value_any_type)
        elif socket_input.type == 'VECTOR': # Usually expects tuple (X,Y,Z)
            parsed_value = safe_eval(str(new_value_any_type), (0,0,0)) # safe_eval expects string
        elif socket_input.type == 'INT':
            parsed_value = int(new_value_any_type)
        elif socket_input.type == 'BOOLEAN':
            if isinstance(new_value_any_type, str):
                parsed_value = new_value_any_type.lower() == 'true'
            else:
                parsed_value = bool(new_value_any_type)
        else:
            print(f"    [Warning] SHADER_SWITCH: Unsupported socket type '{socket_input.type}' for input '{input_name_str}'. Skipping.")
            return
    except ValueError as e:
        print(f"    [Warning] SHADER_SWITCH: Error parsing NEW_VALUE '{new_value_any_type}' for socket type '{socket_input.type}': {e}. Skipping.")
        return

    if parsed_value is None and socket_input.type != 'BOOLEAN': # Boolean can correctly parse to False which is like None
         print(f"    [Warning] SHADER_SWITCH: Parsed value is None for NEW_VALUE '{new_value_any_type}' and socket type '{socket_input.type}'. This might be an error or intended. Proceeding with None if socket allows.")
         # Some sockets might accept None, others might error. Default_value assignment will handle this.

    try:
        socket_input.default_value = parsed_value
        kp = socket_input.keyframe_insert(data_path="default_value", frame=frame_int)
        if kp:
            kp.interpolation = 'CONSTANT' # Switches are typically constant
        print(f"    Set and keyframed material '{mat_to_modify.name}' node '{target_node_name_str}'.{input_name_str} to {parsed_value} at frame {frame_int}.")
    except Exception as e:
        print(f"    [Error] SHADER_SWITCH: Failed to set/keyframe socket '{input_name_str}' on node '{target_node_name_str}': {e}")

    print(f"    ✅ Finished shader switch for: {target_obj.name} on material {mat_to_modify.name}")

def handle_zw_camera_block(camera_data: dict, current_bpy_collection: bpy.types.Collection):
    if not bpy: return
    name = camera_data.get("NAME","ZWCamera"); loc_str=camera_data.get("LOCATION","(0,0,0)"); rot_str=camera_data.get("ROTATION","(0,0,0)")
    fov=float(camera_data.get("FOV",50.0)); clip_start=float(camera_data.get("CLIP_START",0.1)); clip_end=float(camera_data.get("CLIP_END",1000.0))
    track_tgt_name=camera_data.get("TRACK_TARGET"); explicit_coll=camera_data.get("COLLECTION")
    loc=safe_eval(loc_str,(0,0,0)); rot_deg=safe_eval(rot_str,(0,0,0)); rot_rad=tuple(math.radians(a) for a in rot_deg)
    print(f"[*] Creating Camera '{name}': LOC={loc}, ROT_RAD={rot_rad}, FOV_MM={fov}")
    try:
        bpy.ops.object.camera_add(location=loc,rotation=rot_rad); cam_obj=bpy.context.active_object
        if not cam_obj: print(f"    [Error] Failed to create camera object '{name}'."); return
        cam_obj.name=name; cam_data=cam_obj.data; cam_data.lens=fov; cam_data.clip_start=clip_start; cam_data.clip_end=clip_end
        print(f"    Set camera data for '{name}'.")
        final_coll = get_or_create_collection(explicit_coll, bpy.context.scene.collection) if explicit_coll else current_bpy_collection
        if final_coll:
            for c in cam_obj.users_collection: c.objects.unlink(cam_obj)
            final_coll.objects.link(cam_obj); print(f"    Linked '{name}' to collection '{final_coll.name}'")
        if track_tgt_name:
            track_to=bpy.data.objects.get(track_tgt_name)
            if track_to:
                constr=cam_obj.constraints.new(type='TRACK_TO'); constr.target=track_to
                constr.track_axis='TRACK_NEGATIVE_Z'; constr.up_axis='UP_Y'; print(f"    Added 'TRACK_TO' constraint to '{track_tgt_name}'")
            else: print(f"    [Warning] Track target '{track_tgt_name}' not found.")
        print(f"    ✅ Successfully created camera '{name}'.")
    except Exception as e: print(f"    [Error] Failed to create/configure camera '{name}': {e}")

def handle_zw_light_block(light_data: dict, current_bpy_collection: bpy.types.Collection):
    if not bpy: return
    name=light_data.get("NAME","ZWLight"); loc_str=light_data.get("LOCATION","(0,0,0)"); rot_str=light_data.get("ROTATION","(0,0,0)")
    type_str=light_data.get("TYPE","POINT").upper(); color_str=light_data.get("COLOR","#FFFFFF")
    energy=float(light_data.get("ENERGY",100.0 if type_str=="POINT" else 10.0 if type_str=="SPOT" else 1.0))
    shadow=str(light_data.get("SHADOW","true")).lower()=="true"
    size=float(light_data.get("SIZE",0.25 if type_str in ["POINT","SPOT"] else (0.1 if type_str=="SUN" else 1.0)))
    explicit_coll=light_data.get("COLLECTION"); loc=safe_eval(loc_str,(0,0,0)); rot_deg=safe_eval(rot_str,(0,0,0))
    rot_rad=tuple(math.radians(a) for a in rot_deg); color_rgb=parse_color(color_str)[:3]
    print(f"[*] Creating Light '{name}': TYPE={type_str}, LOC={loc}, ROT_RAD={rot_rad}, COLOR={color_rgb}, ENERGY={energy}")
    try:
        bpy_light_data=bpy.data.lights.new(name=f"{name}_data",type=type_str)
        bpy_light_data.color=color_rgb; bpy_light_data.energy=energy
        if hasattr(bpy_light_data,'use_shadow'): bpy_light_data.use_shadow=shadow
        if type_str in ['POINT','SPOT']: bpy_light_data.shadow_soft_size=size
        elif type_str=='AREA': bpy_light_data.size=size
        elif type_str=='SUN': bpy_light_data.angle=size
        light_obj=bpy.data.objects.new(name=name,object_data=bpy_light_data)
        light_obj.location=loc; light_obj.rotation_euler=rot_rad
        final_coll=get_or_create_collection(explicit_coll,bpy.context.scene.collection) if explicit_coll else current_bpy_collection
        if final_coll: final_coll.objects.link(light_obj); print(f"    Linked '{name}' to collection '{final_coll.name}'")
        else: print(f"    [Warning] No target collection for light '{name}'.")
        print(f"    ✅ Successfully created light '{name}'.")
    except Exception as e: print(f"    [Error] Failed to create/configure light '{name}': {e}")

def handle_zw_stage_block(stage_data: dict):
    if not bpy: return
    tracks_list = stage_data.get("TRACKS")
    stage_name = stage_data.get('NAME', 'UnnamedStage')
    print(f"[*] Processing stage: {stage_name}")
    if not isinstance(tracks_list, list) or not tracks_list:
        print(f"    [Warning] No TRACKS found or TRACKS is not a list in ZW-STAGE '{stage_name}'. Skipping.")
        return
    for track_item_dict in tracks_list:
        if not isinstance(track_item_dict, dict):
            print(f"    [Warning] Track item is not a dictionary in ZW-STAGE '{stage_name}'. Skipping track: {track_item_dict}")
            continue
        track_type = track_item_dict.get("TYPE")
        target_name = track_item_dict.get("TARGET")
        start_frame_str = track_item_dict.get("START", "1")
        try: start_frame = int(start_frame_str)
        except ValueError: print(f"    [Warning] Invalid START frame '{start_frame_str}'. Defaulting to 1."); start_frame = 1
        end_frame_str = track_item_dict.get("END"); end_frame = None
        if end_frame_str is not None:
            try: end_frame = int(end_frame_str)
            except ValueError: print(f"    [Warning] Invalid END frame '{end_frame_str}'. END frame ignored.")
        target_obj = bpy.data.objects.get(target_name) if target_name else None
        print(f"  Processing track: TYPE='{track_type}', TARGET='{target_name}', START={start_frame}")

        if track_type == "CAMERA":
            if target_obj and target_obj.type == 'CAMERA':
                bpy.context.scene.camera = target_obj
                bpy.context.scene.keyframe_insert(data_path="camera", frame=start_frame)
                print(f"    Set active camera to '{target_obj.name}' at frame {start_frame}")
            else: print(f"    [Warning] Target '{target_name}' for CAMERA track is not valid or not found.")
        elif track_type == "VISIBILITY":
            if target_obj:
                state_str = str(track_item_dict.get("STATE", "SHOW")).upper()
                hide_val = True if state_str == "HIDE" else False
                target_obj.hide_viewport = hide_val; target_obj.keyframe_insert(data_path="hide_viewport", frame=start_frame)
                target_obj.hide_render = hide_val; target_obj.keyframe_insert(data_path="hide_render", frame=start_frame)
                print(f"    Set visibility of '{target_obj.name}' to {'HIDDEN' if hide_val else 'VISIBLE'} at frame {start_frame}")
            else: print(f"    [Warning] Target object '{target_name}' for VISIBILITY track not found.")
        elif track_type == "LIGHT_INTENSITY":
            if target_obj and target_obj.type == 'LIGHT':
                light_data_block = target_obj.data; value_at_start_str = track_item_dict.get("VALUE")
                if value_at_start_str is not None:
                    try:
                        value_at_start = float(value_at_start_str)
                        light_data_block.energy = value_at_start
                        light_data_block.keyframe_insert(data_path="energy", frame=start_frame)
                        print(f"    Set energy of light '{target_obj.name}' to {value_at_start} at frame {start_frame}")
                    except ValueError: print(f"    [Warning] Invalid VALUE '{value_at_start_str}' for LIGHT_INTENSITY on '{target_name}'.")
                else: print(f"    [Warning] Missing VALUE for LIGHT_INTENSITY on '{target_name}' at frame {start_frame}.")
                end_value_str = track_item_dict.get("END_VALUE")
                if end_frame is not None and end_value_str is not None:
                    try:
                        value_at_end = float(end_value_str)
                        light_data_block.energy = value_at_end
                        light_data_block.keyframe_insert(data_path="energy", frame=end_frame)
                        print(f"    Animated energy of light '{target_obj.name}' to {value_at_end} at frame {end_frame}")
                    except ValueError: print(f"    [Warning] Invalid END_VALUE '{end_value_str}' for LIGHT_INTENSITY on '{target_name}'.")
            else: print(f"    [Warning] Target '{target_name}' for LIGHT_INTENSITY track is not valid or not found.")

        elif track_type == "PROPERTY_ANIM":
            if target_obj: # Ensure target_obj was found
                print(f"    Dispatching to handle_property_anim_track for {target_name}")
                # Pass the whole track_item_dict as it contains all necessary params for the handler
                handle_property_anim_track(target_obj, track_item_dict)
            else:
                print(f"    [Warning] Target object '{target_name}' not found for PROPERTY_ANIM track.")

        elif track_type == "MATERIAL_OVERRIDE":
            if target_obj: # Ensure target_obj was found
                print(f"    Dispatching to handle_material_override_track for {target_name}")
                # Pass relevant parts or the whole dict. Handler expects specific keys.
                # track_item_dict contains "MATERIAL_NAME", "START_FRAME", "END_FRAME", "RESTORE_ON_END"
                # Need to make sure START_FRAME is passed if not already part of base extraction
                track_data_for_handler = track_item_dict.copy()
                track_data_for_handler["START_FRAME"] = start_frame # Ensure start_frame from loop is used
                if end_frame is not None: # Ensure end_frame from loop is used
                    track_data_for_handler["END_FRAME"] = end_frame
                handle_material_override_track(target_obj, track_data_for_handler)
            else:
                print(f"    [Warning] Target object '{target_name}' not found for MATERIAL_OVERRIDE track.")

        elif track_type == "SHADER_SWITCH":
            if target_obj: # Ensure target_obj was found
                print(f"    Dispatching to handle_shader_switch_track for {target_name}")
                # Pass relevant parts or the whole dict. Handler expects specific keys.
                # track_item_dict contains "TARGET_NODE", "INPUT_NAME", "NEW_VALUE", "FRAME" (optional, defaults to start_frame)
                # Need to make sure FRAME is passed correctly.
                track_data_for_handler = track_item_dict.copy()
                track_data_for_handler["FRAME"] = track_item_dict.get("FRAME", start_frame) # Use specific FRAME or default to track's START
                handle_shader_switch_track(target_obj, track_data_for_handler)
            else:
                print(f"    [Warning] Target object '{target_name}' not found for SHADER_SWITCH track.")
        else:
            print(f"    [Warning] Unknown ZW-STAGE track TYPE: '{track_type}'")
    print(f"[*] Finished processing stage: {stage_name}")

def handle_zw_camera_block(camera_data: dict, current_bpy_collection: bpy.types.Collection):
    if not bpy: return
    name = camera_data.get("NAME","ZWCamera"); loc_str=camera_data.get("LOCATION","(0,0,0)"); rot_str=camera_data.get("ROTATION","(0,0,0)")
    fov=float(camera_data.get("FOV",50.0)); clip_start=float(camera_data.get("CLIP_START",0.1)); clip_end=float(camera_data.get("CLIP_END",1000.0))
    track_tgt_name=camera_data.get("TRACK_TARGET"); explicit_coll=camera_data.get("COLLECTION")
    loc=safe_eval(loc_str,(0,0,0)); rot_deg=safe_eval(rot_str,(0,0,0)); rot_rad=tuple(math.radians(a) for a in rot_deg)
    print(f"[*] Creating Camera '{name}': LOC={loc}, ROT_RAD={rot_rad}, FOV_MM={fov}")
    try:
        bpy.ops.object.camera_add(location=loc,rotation=rot_rad); cam_obj=bpy.context.active_object
        if not cam_obj: print(f"    [Error] Failed to create camera object '{name}'."); return
        cam_obj.name=name; cam_data=cam_obj.data; cam_data.lens=fov; cam_data.clip_start=clip_start; cam_data.clip_end=clip_end
        print(f"    Set camera data for '{name}'.")
        final_coll = get_or_create_collection(explicit_coll, bpy.context.scene.collection) if explicit_coll else current_bpy_collection
        if final_coll:
            for c in cam_obj.users_collection: c.objects.unlink(cam_obj)
            final_coll.objects.link(cam_obj); print(f"    Linked '{name}' to collection '{final_coll.name}'")
        if track_tgt_name:
            track_to=bpy.data.objects.get(track_tgt_name)
            if track_to:
                constr=cam_obj.constraints.new(type='TRACK_TO'); constr.target=track_to
                constr.track_axis='TRACK_NEGATIVE_Z'; constr.up_axis='UP_Y'; print(f"    Added 'TRACK_TO' constraint to '{track_tgt_name}'")
            else: print(f"    [Warning] Track target '{track_tgt_name}' not found.")
        print(f"    ✅ Successfully created camera '{name}'.")
    except Exception as e: print(f"    [Error] Failed to create/configure camera '{name}': {e}")

def handle_zw_light_block(light_data: dict, current_bpy_collection: bpy.types.Collection):
    if not bpy: return
    name=light_data.get("NAME","ZWLight"); loc_str=light_data.get("LOCATION","(0,0,0)"); rot_str=light_data.get("ROTATION","(0,0,0)")
    type_str=light_data.get("TYPE","POINT").upper(); color_str=light_data.get("COLOR","#FFFFFF")
    energy=float(light_data.get("ENERGY",100.0 if type_str=="POINT" else 10.0 if type_str=="SPOT" else 1.0))
    shadow=str(light_data.get("SHADOW","true")).lower()=="true"
    size=float(light_data.get("SIZE",0.25 if type_str in ["POINT","SPOT"] else (0.1 if type_str=="SUN" else 1.0)))
    explicit_coll=light_data.get("COLLECTION"); loc=safe_eval(loc_str,(0,0,0)); rot_deg=safe_eval(rot_str,(0,0,0))
    rot_rad=tuple(math.radians(a) for a in rot_deg); color_rgb=parse_color(color_str)[:3]
    print(f"[*] Creating Light '{name}': TYPE={type_str}, LOC={loc}, ROT_RAD={rot_rad}, COLOR={color_rgb}, ENERGY={energy}")
    try:
        bpy_light_data=bpy.data.lights.new(name=f"{name}_data",type=type_str)
        bpy_light_data.color=color_rgb; bpy_light_data.energy=energy
        if hasattr(bpy_light_data,'use_shadow'): bpy_light_data.use_shadow=shadow
        if type_str in ['POINT','SPOT']: bpy_light_data.shadow_soft_size=size
        elif type_str=='AREA': bpy_light_data.size=size
        elif type_str=='SUN': bpy_light_data.angle=size
        light_obj=bpy.data.objects.new(name=name,object_data=bpy_light_data)
        light_obj.location=loc; light_obj.rotation_euler=rot_rad
        final_coll=get_or_create_collection(explicit_coll,bpy.context.scene.collection) if explicit_coll else current_bpy_collection
        if final_coll: final_coll.objects.link(light_obj); print(f"    Linked '{name}' to collection '{final_coll.name}'")
        else: print(f"    [Warning] No target collection for light '{name}'.")
        print(f"    ✅ Successfully created light '{name}'.")
    except Exception as e: print(f"    [Error] Failed to create/configure light '{name}': {e}")

# --- Main Processing Logic ---
def process_zw_structure(data_dict: dict, parent_bpy_obj=None, current_bpy_collection=None):
    if not bpy: return
    if current_bpy_collection is None: current_bpy_collection = bpy.context.scene.collection
    if not isinstance(data_dict, dict): return
    for key, value in data_dict.items():
        created_bpy_object_for_current_zw_object = None
        obj_attributes_for_current_zw_object = None
        target_collection_for_this_object = current_bpy_collection
        if key.upper().startswith("ZW-COLLECTION"):
            collection_name = key.split(":", 1)[1].strip() if ":" in key else key.replace("ZW-COLLECTION", "").strip()
            if not collection_name: collection_name = "Unnamed_ZW_Collection"
            print(f"[*] Processing ZW-COLLECTION block: '{collection_name}' under '{current_bpy_collection.name}'")
            block_bpy_collection = get_or_create_collection(collection_name, parent_collection=current_bpy_collection)
            if isinstance(value, dict) and "CHILDREN" in value and isinstance(value["CHILDREN"], list):
                for child_def_item in value["CHILDREN"]:
                    if isinstance(child_def_item, dict):
                        process_zw_structure(child_def_item, parent_bpy_obj=parent_bpy_obj, current_bpy_collection=block_bpy_collection)
            elif isinstance(value, dict) :
                process_zw_structure(value, parent_bpy_obj=parent_bpy_obj, current_bpy_collection=block_bpy_collection)
            continue
        elif key.upper() == "ZW-FUNCTION":
            if isinstance(value, dict):
                print(f"[*] Processing ZW-FUNCTION block: {value.get('NAME', 'Unnamed Function')}")
                handle_zw_function_block(value)
            else: print(f"[!] Warning: ZW-FUNCTION value is not a dictionary: {value}")
            continue
        elif key.upper() == "ZW-DRIVER":
            if isinstance(value, dict):
                print(f"[*] Processing ZW-DRIVER block: {value.get('NAME', 'Unnamed Driver')}")
                handle_zw_driver_block(value)
            else: print(f"[!] Warning: ZW-DRIVER value is not a dictionary: {value}")
            continue
        elif key.upper() == "ZW-ANIMATION":
            if isinstance(value, dict):
                print(f"  Processing ZW-ANIMATION block: {value.get('NAME', 'UnnamedAnimation')}")
                handle_zw_animation_block(value)
            else: print(f"    [Warning] Value for 'ZW-ANIMATION' key is not a dictionary. Value: {value}")
            continue
        elif key.upper() == "ZW-CAMERA":
            if isinstance(value, dict):
                print(f"  Processing ZW-CAMERA block for: {value.get('NAME', 'UnnamedCamera')}")
                handle_zw_camera_block(value, current_bpy_collection)
            else: print(f"    [Warning] Value for 'ZW-CAMERA' key is not a dictionary. Value: {value}")
            continue
        elif key.upper() == "ZW-LIGHT":
            if isinstance(value, dict):
                print(f"  Processing ZW-LIGHT block for: {value.get('NAME', 'UnnamedLight')}")
                handle_zw_light_block(value, current_bpy_collection)
            else: print(f"    [Warning] Value for 'ZW-LIGHT' key is not a dictionary. Value: {value}")
            continue
        elif key.upper() == "ZW-STAGE":
            if isinstance(value, dict):
                print(f"  Processing ZW-STAGE block: {value.get('NAME', 'UnnamedStage')}")
                handle_zw_stage_block(value)
            else: print(f"    [Warning] Value for 'ZW-STAGE' key is not a dictionary. Value: {value}")
            continue
        elif key == "ZW-MESH": # Assuming ZW-MESH is a key, and its value is the definition dictionary
            if isinstance(value, dict):
                if ZW_MESH_IMPORTED and HANDLE_ZW_MESH_BLOCK_FUNC:
                    print(f"  Processing ZW-MESH block: {value.get('NAME', 'UnnamedZWMesh')}")
                    # Pass the current_bpy_collection so zw_mesh.py can link the new object correctly
                    HANDLE_ZW_MESH_BLOCK_FUNC(value, current_bpy_collection)
                else:
                    print("    [Error] ZW-MESH block found, but zw_mesh.handle_zw_mesh_block function was not imported.")
            else:
                print(f"    [Warning] Value for 'ZW-MESH' key is not a dictionary. Value: {value}")
            continue # Added continue to ensure it doesn't fall through to ZW-OBJECT or generic dict processing
        if key.upper() == "ZW-OBJECT":
            if isinstance(value, dict): obj_attributes_for_current_zw_object = value
            elif isinstance(value, str): obj_attributes_for_current_zw_object = {"TYPE": value}
        elif key.lower() in ["sphere", "cube", "plane", "cone", "cylinder", "torus"] and isinstance(value, dict):
            obj_attributes_for_current_zw_object = value.copy()
            obj_attributes_for_current_zw_object["TYPE"] = key
        if obj_attributes_for_current_zw_object:
            created_bpy_object_for_current_zw_object = handle_zw_object_creation(obj_attributes_for_current_zw_object, parent_bpy_obj)
            if created_bpy_object_for_current_zw_object:
                explicit_collection_name = obj_attributes_for_current_zw_object.get("COLLECTION")
                if explicit_collection_name:
                    target_collection_for_this_object = get_or_create_collection(explicit_collection_name, parent_collection=bpy.context.scene.collection)
                if target_collection_for_this_object:
                    for coll in created_bpy_object_for_current_zw_object.users_collection:
                        coll.objects.unlink(created_bpy_object_for_current_zw_object)
                    target_collection_for_this_object.objects.link(created_bpy_object_for_current_zw_object)
                    print(f"    Linked '{created_bpy_object_for_current_zw_object.name}' to collection '{target_collection_for_this_object.name}'")
                children_list = obj_attributes_for_current_zw_object.get("CHILDREN")
                if children_list and isinstance(children_list, list):
                    print(f"[*] Processing CHILDREN for '{created_bpy_object_for_current_zw_object.name}' in collection '{target_collection_for_this_object.name}'")
                    for child_item_definition in children_list:
                        if isinstance(child_item_definition, dict):
                            process_zw_structure(child_item_definition,
                                                 parent_bpy_obj=created_bpy_object_for_current_zw_object,
                                                 current_bpy_collection=target_collection_for_this_object)
                        else: print(f"    [!] Warning: Item in CHILDREN list is not a dictionary: {child_item_definition}")
                elif children_list is not None: print(f"    [!] Warning: CHILDREN attribute for an object is not a list: {type(children_list)}")
            continue
        elif isinstance(value, dict):
            if key.upper() == "ZW-NESTED-DETAILS":
                print(f"[*] Processing ZW-NESTED-DETAILS (semantic parent link: {value.get('PARENT')}). Using collection '{current_bpy_collection.name}'")
            process_zw_structure(value, parent_bpy_obj=parent_bpy_obj, current_bpy_collection=current_bpy_collection)

def run_blender_adapter():
    print("--- Starting ZW Blender Adapter ---")
    if not bpy: print("[X] Blender Python environment (bpy) not detected. Cannot proceed."); print("--- ZW Blender Adapter Finished (with errors) ---"); return
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    try:
        with open(ZW_INPUT_FILE_PATH, "r", encoding="utf-8") as f: zw_text_content = f.read()
        print(f"[*] Successfully read ZW file: {ZW_INPUT_FILE_PATH}")
    except FileNotFoundError: print(f"[X] Error: ZW input file not found at '{ZW_INPUT_FILE_PATH}'"); print("--- ZW Blender Adapter Finished (with errors) ---"); return
    except Exception as e: print(f"[X] Error reading ZW file '{ZW_INPUT_FILE_PATH}': {e}"); print("--- ZW Blender Adapter Finished (with errors) ---"); return
    if not zw_text_content.strip(): print("[X] Error: ZW input file is empty."); print("--- ZW Blender Adapter Finished (with errors) ---"); return
    try:
        print("[*] Parsing ZW text..."); parsed_zw_data = parse_zw(zw_text_content)
        if not parsed_zw_data: print("[!] Warning: Parsed ZW data is empty. No objects will be created.")
    except Exception as e: print(f"[X] Error parsing ZW text: {e}"); print("--- ZW Blender Adapter Finished (with errors) ---"); return
    try:
        print("[*] Processing ZW structure for Blender object creation...")
        process_zw_structure(parsed_zw_data, current_bpy_collection=bpy.context.scene.collection)
        print("[*] Finished processing ZW structure.")
    except Exception as e: print(f"[X] Error during ZW structure processing for Blender: {e}"); print("--- ZW Blender Adapter Finished (with errors) ---"); return
    print("--- ZW Blender Adapter Finished Successfully ---")

# --- ZW-COMPOSE Handler ---
def handle_zw_compose_block(compose_data: dict, default_collection: bpy.types.Collection):
    if not bpy:
        print("[Error] bpy module not available in handle_zw_compose_block. Cannot process ZW-COMPOSE.")
        return

    compose_name = compose_data.get("NAME", "ZWComposition")
    print(f"    Creating ZW-COMPOSE assembly: {compose_name}")

    # Create parent Empty for the composition
    bpy.ops.object.empty_add(type='PLAIN_AXES')
    parent_empty = bpy.context.active_object
    if not parent_empty: # Should not happen if ops.empty_add worked
        print(f"      [Error] Failed to create parent Empty for {compose_name}. Aborting ZW-COMPOSE.")
        return
    parent_empty.name = compose_name

    # Handle transform for the parent_empty itself
    loc_str = compose_data.get("LOCATION", "(0,0,0)")
    rot_str = compose_data.get("ROTATION", "(0,0,0)")
    scale_str = compose_data.get("SCALE", "(1,1,1)")
    parent_empty.location = safe_eval(loc_str, (0,0,0))
    rot_deg = safe_eval(rot_str, (0,0,0))
    parent_empty.rotation_euler = Euler([math.radians(a) for a in rot_deg], 'XYZ')

    scale_eval = safe_eval(scale_str, (1,1,1))
    if isinstance(scale_eval, (int, float)): # Uniform scale
        parent_empty.scale = (float(scale_eval), float(scale_eval), float(scale_eval))
    else: # Tuple scale
        parent_empty.scale = scale_eval
    print(f"      Parent Empty '{parent_empty.name}' transform: L={parent_empty.location}, R={parent_empty.rotation_euler}, S={parent_empty.scale}")


    # Assign parent_empty to a collection
    comp_coll_name = compose_data.get("COLLECTION")
    target_collection_for_empty = default_collection # Default to the collection context from process_zw_structure

    if comp_coll_name: # If a specific collection is named for the ZW-COMPOSE root
        target_collection_for_empty = get_or_create_collection(comp_coll_name, parent_collection=bpy.context.scene.collection)

    # Link parent_empty to its target collection, ensure it's not in others (like default scene collection)
    current_collections = [coll for coll in parent_empty.users_collection]
    for coll in current_collections:
        coll.objects.unlink(parent_empty)
    if parent_empty.name not in target_collection_for_empty.objects: # Check to avoid duplicate link error
        target_collection_for_empty.objects.link(parent_empty)
    print(f"      Parent Empty '{parent_empty.name}' linked to collection '{target_collection_for_empty.name}'")


    # Process BASE_MODEL
    base_model_name = compose_data.get("BASE_MODEL")
    base_model_obj = None
    if base_model_name:
        original_base_obj = bpy.data.objects.get(base_model_name)
        if original_base_obj:
            # Duplicate the object and its data to make it independent for this composition
            base_model_obj = original_base_obj.copy()
            if original_base_obj.data:
                base_model_obj.data = original_base_obj.data.copy()
            base_model_obj.name = f"{base_model_name}_base_of_{compose_name}"

            # Link duplicated base_model_obj to the same collection as parent_empty
            target_collection_for_empty.objects.link(base_model_obj)

            base_model_obj.parent = parent_empty
            base_model_obj.location = (0,0,0) # Reset local transforms relative to parent_empty
            base_model_obj.rotation_euler = (0,0,0)
            base_model_obj.scale = (1,1,1)
            print(f"      Added BASE_MODEL: '{base_model_name}' as '{base_model_obj.name}', parented to '{parent_empty.name}'")
        else:
            print(f"      [Warning] BASE_MODEL object '{base_model_name}' not found in scene.")

    # Process ATTACHMENTS
    attachments_list = compose_data.get("ATTACHMENTS", [])
    if not isinstance(attachments_list, list): attachments_list = []

    for i, attach_def in enumerate(attachments_list):
        if not isinstance(attach_def, dict):
            print(f"        [Warning] Attachment item {i} is not a dictionary, skipping.")
            continue

        attach_obj_source_name = attach_def.get("OBJECT")
        original_attach_obj = bpy.data.objects.get(attach_obj_source_name)

        if original_attach_obj:
            attached_obj = original_attach_obj.copy()
            if original_attach_obj.data:
                attached_obj.data = original_attach_obj.data.copy()
            attached_obj.name = f"{attach_obj_source_name}_attach{i}_to_{compose_name}"
            target_collection_for_empty.objects.link(attached_obj) # Link to same collection as parent_empty

            attached_obj.parent = parent_empty # Parent to the main composition Empty

            # Apply local transforms for the attachment
            attach_loc_str = attach_def.get("LOCATION", "(0,0,0)")
            attach_rot_str = attach_def.get("ROTATION", "(0,0,0)")
            attach_scale_str = attach_def.get("SCALE", "(1,1,1)")

            attached_obj.location = safe_eval(attach_loc_str, (0,0,0))
            attach_rot_deg = safe_eval(attach_rot_str, (0,0,0))
            attached_obj.rotation_euler = Euler([math.radians(a) for a in attach_rot_deg], 'XYZ')

            attach_scale_eval = safe_eval(attach_scale_str, (1,1,1))
            if isinstance(attach_scale_eval, (int, float)):
                attached_obj.scale = (float(attach_scale_eval), float(attach_scale_eval), float(attach_scale_eval))
            else:
                attached_obj.scale = attach_scale_eval
            print(f"        Added ATTACHMENT: '{attach_obj_source_name}' as '{attached_obj.name}', parented to '{parent_empty.name}'")
            print(f"          Local Transform: L={attached_obj.location}, R={attached_obj.rotation_euler}, S={attached_obj.scale}")


            # Handle MATERIAL_OVERRIDE for this attachment
            material_override_def = attach_def.get("MATERIAL_OVERRIDE")
            if isinstance(material_override_def, dict):
                if ZW_MESH_UTILS_IMPORTED and APPLY_ZW_MESH_MATERIAL_FUNC:
                    print(f"          Applying MATERIAL_OVERRIDE to '{attached_obj.name}'")
                    if 'NAME' not in material_override_def:
                        material_override_def['NAME'] = f"{attached_obj.name}_OverrideMat"
                    APPLY_ZW_MESH_MATERIAL_FUNC(attached_obj, material_override_def)
                else:
                    print(f"          [Warning] MATERIAL_OVERRIDE found for '{attached_obj.name}', but zw_mesh.apply_material function was not imported.")
        else:
            print(f"        [Warning] ATTACHMENT source object '{attach_obj_source_name}' not found.")

    # Process EXPORT for the entire assembly
    export_def = compose_data.get("EXPORT")
    if export_def and isinstance(export_def, dict):
        export_format = export_def.get("FORMAT", "").lower()
        export_file_str = export_def.get("FILE")
        if export_format == "glb" and export_file_str:
            print(f"      Exporting composition '{compose_name}' to GLB: {export_file_str}")

            export_path = Path(export_file_str)
            # Attempt to make path absolute relative to a project root if not already.
            # This part assumes PROJECT_ROOT might be defined globally in blender_adapter.py or passed.
            # For now, we'll rely on Blender's relative path handling or user providing absolute paths.
            # if not export_path.is_absolute() and 'PROJECT_ROOT' in globals():
            #     export_path = PROJECT_ROOT / export_path

            try:
                export_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e_mkdir_export:
                print(f"        [Warning] Could not create directory for GLB export '{export_path.parent}': {e_mkdir_export}")

            # Select parent_empty and all its children for export
            bpy.ops.object.select_all(action='DESELECT')
            parent_empty.select_set(True) # Select the parent empty
            # Also select all children recursively
            for child in parent_empty.children_recursive:
                child.select_set(True)
            bpy.context.view_layer.objects.active = parent_empty # Ensure parent is active for some export options

            try:
                bpy.ops.export_scene.gltf(
                    filepath=str(export_path), # Use str() for older Blender versions if Path object not fully supported by op
                    export_format='GLB',
                    use_selection=True,
                    export_apply=True,  # Apply modifiers
                    export_materials='EXPORT',
                    export_texcoords=True,
                    export_normals=True,
                    export_cameras=False, # Usually False for component exports
                    export_lights=False   # Usually False for component exports
                )
                print(f"        Successfully exported composition '{compose_name}' to '{export_path.resolve() if export_path.exists() else export_path}'") # Check if resolve() is safe if file creation failed
            except RuntimeError as e_export:
                print(f"        [Error] Failed to export composition '{compose_name}' to GLB: {e_export}")
        else:
            print(f"      [Warning] EXPORT block for '{compose_name}' is missing format/file or format not 'glb'.")
    print(f"    ✅ Finished ZW-COMPOSE assembly: {compose_name}")


if __name__ == "__main__":
    run_blender_adapter()
