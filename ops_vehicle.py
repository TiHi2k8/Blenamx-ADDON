"""Vehicle and chassis-related operators"""
import bpy
import os
import re
import shlex
import shutil
import struct
import zlib
from mathutils import Vector, Quaternion, Euler, Matrix
import math


def organize_scene_collections():
    """Auto-organize collections: Lights in Model, Seats/Extras/Hitboxes/Wheels in Dynamx"""
    try:
        scene = bpy.context.scene
        
        # Get or create Dynamx collection at scene level
        dynamx_col = bpy.data.collections.get("Dynamx")
        if not dynamx_col:
            dynamx_col = bpy.data.collections.new("Dynamx")
            scene.collection.children.link(dynamx_col)
        
        # Get or create the Model Collection (first non-Dynamx collection at scene level)
        model_col = None
        for col in scene.collection.children:
            if col.name != "Dynamx":
                model_col = col
                break
        
        if not model_col:
            model_col = bpy.data.collections.new("Collection")
            scene.collection.children.link(model_col)
        
        # Helper: Move collection from parent to new parent
        def move_collection(collection_to_move, source_parent, target_parent):
            """Move collection from source to target parent"""
            if not collection_to_move or source_parent is None or target_parent is None:
                return False
            
            # Check if already in target
            for child in target_parent.children:
                if child.name == collection_to_move.name:
                    # Already there, remove from source if different
                    if source_parent != target_parent:
                        try:
                            source_parent.children.unlink(collection_to_move)
                        except:
                            pass
                    return True
            
            # Unlink from source parent if it's the scene collection
            if source_parent == scene.collection:
                try:
                    scene.collection.children.unlink(collection_to_move)
                except:
                    pass
            
            # Link to target parent
            try:
                target_parent.children.link(collection_to_move)
                return True
            except:
                return False
        
        # Process each collection
        lights_col = bpy.data.collections.get("Lights")
        if lights_col:
            move_collection(lights_col, scene.collection, model_col)
        
        seats_col = bpy.data.collections.get("Seats")
        if seats_col:
            move_collection(seats_col, scene.collection, dynamx_col)
        
        extras_col = bpy.data.collections.get("Extras")
        if extras_col:
            move_collection(extras_col, scene.collection, dynamx_col)
        
        hitboxes_col = bpy.data.collections.get("Hitboxes")
        if hitboxes_col:
            move_collection(hitboxes_col, scene.collection, dynamx_col)
        
        wheels_col = bpy.data.collections.get("wheels")
        if wheels_col:
            move_collection(wheels_col, scene.collection, dynamx_col)
    
    except Exception as e:
        pass  # Silently fail if there's an error


def find_steering_wheel_object():
    """Return steering wheel object, preferring original explicit name."""
    try:
        exact = bpy.data.objects.get('steeringwheel')
        if exact is not None:
            return exact
        for obj in bpy.data.objects:
            if obj.get('dynamx_part_name') == 'steeringwheel':
                return obj
        for obj in bpy.data.objects:
            if obj.name.lower().startswith('steeringwheel'):
                return obj
    except Exception:
        pass
    return None


def _set_steering_rotation_from_object(scene, obj):
    if not hasattr(scene, 'dynamx_steering_rotation_deg'):
        return
    try:
        e = obj.matrix_world.to_quaternion().to_euler('XYZ')
        scene.dynamx_steering_rotation_deg = (
            math.degrees(e.x),
            math.degrees(e.y),
            math.degrees(e.z),
        )
    except Exception:
        pass


def _steering_quaternion_from_scene(scene):
    if hasattr(scene, 'dynamx_steering_rotation_deg'):
        rx, ry, rz = scene.dynamx_steering_rotation_deg
        euler = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), 'XYZ')
        return euler.to_quaternion(), euler
    return Quaternion((1.0, 0.0, 0.0, 0.0)), Euler((0.0, 0.0, 0.0), 'XYZ')


def _steering_quaternion_for_export(scene, steering_obj):
    try:
        quat = steering_obj.matrix_world.to_quaternion()
        euler = quat.to_euler('XYZ')
        if hasattr(scene, 'dynamx_steering_rotation_deg'):
            scene.dynamx_steering_rotation_deg = (
                math.degrees(euler.x),
                math.degrees(euler.y),
                math.degrees(euler.z),
            )
        return quat, euler
    except Exception:
        return _steering_quaternion_from_scene(scene)


def _vehicle_dynx_path(scene, workspace_name=''):
    pack_path = bpy.path.abspath(getattr(scene, 'dynamx_pack_path', ''))
    pack_name = getattr(scene, 'dynamx_pack_name', '').strip()
    vehicle_name = getattr(scene, 'dynamx_vehicle_name', '').strip()
    if not all([pack_path, pack_name, vehicle_name]):
        return None

    pack_name_safe = pack_name.replace(' ', '_').lower()
    vehicle_name_safe = vehicle_name.replace(' ', '_').lower()
    if workspace_name == 'Dynamx - Trailer':
        filename = f"trailer_{vehicle_name_safe}.dynx"
    else:
        filename = f"vehicle_{vehicle_name_safe}.dynx"

    return os.path.join(pack_path, pack_name_safe, 'vehicle', vehicle_name_safe, filename)


def _wheel_index_from_name(name):
    m = re.search(r'wheel_\((\d+)\)', name)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0


def _collect_wheel_hitboxes():
    wheels = []
    for obj in bpy.data.objects:
        if re.match(r'^wheel_\(\d+\)$', obj.name):
            wheels.append(obj)
    wheels.sort(key=lambda o: (_wheel_index_from_name(o.name), o.name))
    return wheels


def _vehicle_scale_factor(scene):
    try:
        return float(getattr(scene, 'dynamx_vehicle_scale', 1.0) or 1.0)
    except Exception:
        return 1.0


def _store_original_scale_state():
    """Store original positions and scales as custom properties before any scaling."""
    for obj in bpy.data.objects:
        if obj is None:
            continue
        name = obj.name
        lname = name.lower()
        
        # Don't store for seats, orientations, arrows
        if 'orientation' in lname or 'seat(' in lname or lname.startswith('seat') or 'outside_arrow' in lname:
            continue
        
        # Store original location/scale if not already stored
        if 'dynamx_original_location' not in obj:
            try:
                obj['dynamx_original_location'] = tuple(obj.location)
            except Exception:
                pass
        
        if 'dynamx_original_scale' not in obj:
            try:
                obj['dynamx_original_scale'] = tuple(obj.scale)
            except Exception:
                pass


def _is_top_level_wheel(obj):
    """Check if this is a top-level wheel object (no cylinder/rim children pattern)."""
    if obj is None:
        return False
    name = obj.name
    if re.match(r'^wheel_\(\d+\)$', name):
        return True
    return False


def _is_runtime_scaled_object(obj):
    if obj is None:
        return False
    name = obj.name
    lname = name.lower()

    if 'orientation' in lname or 'seat(' in lname or lname.startswith('seat'):
        return False

    if 'outside_arrow' in lname:
        return False

    # Top-level wheels only (no cylinders/rims)
    if _is_top_level_wheel(obj):
        return True
    
    # Storage and FuelTank
    if re.match(r'^(Storage\(|FuelTank\()', name):
        return True
    if name.startswith('Storage') or name.startswith('FuelTank'):
        return True
    
    # Hitboxes
    if name == 'Hitbox' or name.startswith('Hitbox') or 'hitbox' in lname:
        return True
    
    # Model obj (top-level only)
    if name == 'Armature.001' or name.startswith('model') or lname == 'armature.001':
        return True
    
    return False


def _apply_scale_to_object(obj, factor):
    """Apply scale factor to an object based on its original stored values."""
    if obj is None or not _is_runtime_scaled_object(obj):
        return False

    try:
        if 'dynamx_original_location' in obj:
            orig_loc = Vector(obj['dynamx_original_location'])
            obj.location = orig_loc * factor
        else:
            # Fallback: just apply scale multiplier to current location
            obj.location = Vector((obj.location.x * factor, obj.location.y * factor, obj.location.z * factor))
    except Exception:
        pass

    try:
        if 'dynamx_original_scale' in obj:
            orig_scale = Vector(obj['dynamx_original_scale'])
            obj.scale = orig_scale * factor
        else:
            # Fallback
            obj.scale = Vector((obj.scale.x * factor, obj.scale.y * factor, obj.scale.z * factor))
    except Exception:
        pass

    return True


def _refresh_runtime_scaled_objects(context, factor=None):
    """Reapply scale factor to all runtime objects based on stored original values."""
    scene = context.scene
    if factor is None:
        factor = _vehicle_scale_factor(scene)
    
    # Store originals if not already done
    _store_original_scale_state()
    
    updated = []
    for obj in list(bpy.data.objects):
        if _apply_scale_to_object(obj, factor):
            updated.append(obj.name)

    if getattr(context, 'view_layer', None) is not None:
        try:
            context.view_layer.update()
        except Exception:
            pass

    return updated


def _update_vehicle_scale_callback(scene):
    """Callback for live scale factor updates."""
    try:
        context = bpy.context
        if context and context.scene == scene:
            _refresh_runtime_scaled_objects(context)
    except Exception:
        pass


class DYNMX_OT_update_scaled_parts(bpy.types.Operator):
    """Write scaled parts to vehicle file and update model with new scale values."""
    bl_idname = "dynamx.update_scaled_parts"
    bl_label = "Update Scaled Parts"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        scene = context.scene
        factor = _vehicle_scale_factor(scene)
        if factor <= 0:
            self.report({'ERROR'}, "Vehicle scale must be > 0")
            return {'CANCELLED'}

        # First ensure objects are scaled
        updated = _refresh_runtime_scaled_objects(context, factor)

        # Now write updated values to vehicle file
        try:
            workspace_name = getattr(getattr(context, 'workspace', None), 'name', '')
            success, msg = _export_scaled_parts_to_vehicle(scene, factor, workspace_name)
            if success:
                self.report({'INFO'}, msg)
            else:
                self.report({'WARNING'}, msg)
        except Exception as e:
            self.report({'WARNING'}, f"Scaled {len(updated)} objects but couldn't write to file: {str(e)}")

        return {'FINISHED'}


def _export_scaled_parts_to_vehicle(scene, factor, workspace_name=''):
    """Export hitboxes, wheels, storage, tank, and model with new scaled values."""
    vehicle_file = _vehicle_dynx_path(scene, workspace_name)
    if not vehicle_file:
        return False, "Pack path, pack name and vehicle name are required"

    if not os.path.exists(vehicle_file):
        return False, f"Vehicle file not found: {vehicle_file}"

    try:
        with open(vehicle_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Failed to read vehicle file: {e}"

    # Update model scale if applicable
    model_name = str(getattr(scene, 'dynamx_model', '')).strip()
    if model_name and factor != 1.0:
        model_pattern = r'\bModel\s*:\s*' + re.escape(model_name)
        if re.search(model_pattern, content):
            # Model found, but we don't modify the reference, just the scale value if it exists
            pass

    # The wheels, hitboxes, storage, and tank are already scaled in the scene
    # We need to export them with their new positions/scales
    # This would typically be done by re-running the export operators
    # For now, just mark it as scaled
    
    updated_sections = []
    
    # Try to add a scale marker to the file if not already there
    if f'// Scale: {factor:.3f}' not in content:
        # Add scale info after the Name line
        name_match = re.search(r'^(Name\s*:\s*[^\n]+)', content, re.MULTILINE)
        if name_match:
            end_pos = name_match.end()
            content = content[:end_pos] + f"\n// Scale: {factor:.3f}" + content[end_pos:]
        updated_sections.append("Scale info")
    
    try:
        with open(vehicle_file, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return False, f"Failed to write vehicle file: {e}"

    return True, f"Updated {len(updated_sections)} sections with scale {factor:.3f}. Re-export wheels/hitboxes/basics to apply scaled positions."


def _wheel_outside_reference_basis():
    """Return center/basis used to determine wheel outside direction."""
    chassis = bpy.data.objects.get('chassis')
    if chassis is not None:
        try:
            return chassis.matrix_world.translation.copy(), chassis.matrix_world.to_3x3()
        except Exception:
            pass

    wheels = _collect_wheel_hitboxes()
    if wheels:
        try:
            center = Vector((0.0, 0.0, 0.0))
            for obj in wheels:
                center += obj.matrix_world.translation
            center /= float(len(wheels))
            return center, Matrix.Identity(3)
        except Exception:
            pass

    return Vector((0.0, 0.0, 0.0)), Matrix.Identity(3)


def _wheel_outside_direction_world(wheel_obj):
    """Compute normalized world-space direction that points to the wheel outside."""
    center, basis = _wheel_outside_reference_basis()
    wheel_pos = wheel_obj.matrix_world.translation.copy()
    direction = wheel_pos - center
    direction.z = 0.0

    if direction.length < 1e-6:
        rel = wheel_pos - center
        try:
            rel_local = basis.inverted() @ rel
        except Exception:
            rel_local = rel
        side_sign = 1.0 if rel_local.x >= 0.0 else -1.0
        try:
            direction = basis @ Vector((side_sign, 0.0, 0.0))
        except Exception:
            direction = Vector((side_sign, 0.0, 0.0))

    if direction.length < 1e-6:
        direction = Vector((1.0, 0.0, 0.0))
    direction.normalize()
    return direction


def _ensure_wheel_outside_arrow(wheel_obj):
    """Create/update an outside arrow child for a wheel hitbox."""
    if wheel_obj is None:
        return None

    wheel_idx = _wheel_index_from_name(wheel_obj.name)
    arrow_name = f"wheel_outside_arrow_({wheel_idx})" if wheel_idx > 0 else f"{wheel_obj.name}_outside_arrow"

    arrow_obj = None
    for child in wheel_obj.children:
        if bool(child.get('dynamx_wheel_outside_arrow', False)):
            arrow_obj = child
            break

    if arrow_obj is None:
        existing = bpy.data.objects.get(arrow_name)
        if existing is not None and bool(existing.get('dynamx_wheel_outside_arrow', False)):
            arrow_obj = existing

    if arrow_obj is None:
        arrow_obj = bpy.data.objects.new(arrow_name, None)
        try:
            arrow_obj.empty_display_type = 'SINGLE_ARROW'
        except Exception:
            pass
        try:
            target_col = wheel_obj.users_collection[0] if wheel_obj.users_collection else bpy.context.scene.collection
            target_col.objects.link(arrow_obj)
        except Exception:
            pass

    arrow_obj.name = arrow_name
    arrow_obj['dynamx_wheel_outside_arrow'] = True
    try:
        arrow_obj.empty_display_type = 'SINGLE_ARROW'
    except Exception:
        pass
    try:
        arrow_obj.empty_display_size = 0.35
    except Exception:
        pass

    wheel_pos = wheel_obj.matrix_world.translation.copy()
    direction = _wheel_outside_direction_world(wheel_obj)
    offset = max(0.2, wheel_obj.dimensions.x * 0.35)
    world_pos = wheel_pos + (direction * offset)

    try:
        quat = direction.to_track_quat('Z', 'Y')
        arrow_obj.matrix_world = Matrix.Translation(world_pos) @ quat.to_matrix().to_4x4()
    except Exception:
        arrow_obj.location = world_pos

    try:
        arrow_obj.parent = wheel_obj
        arrow_obj.matrix_parent_inverse = wheel_obj.matrix_world.inverted()
    except Exception:
        pass

    return arrow_obj


def _bool_text(value):
    return 'true' if bool(value) else 'false'


def _normalize_wheel_def_name(raw_name, default_token='wheel'):
    token = str(raw_name or '').strip()
    if token:
        token = token.split('.')[-1]
    token = token.replace(' ', '_')
    token = re.sub(r'[^A-Za-z0-9_\-]+', '_', token).strip('_').lower()
    if not token:
        token = str(default_token).strip().lower()
    if not token.startswith('wheel_'):
        token = f"wheel_{token}"
    return token


def _attached_wheel_value(scene, wheel_obj):
    raw = str(wheel_obj.get('AttachedWheel', '')).strip()
    if raw and raw.lower() != 'none':
        return raw

    wheel_def_name = str(wheel_obj.get('WheelDefName', '')).strip()
    if wheel_def_name:
        wheel_def_name = _normalize_wheel_def_name(wheel_def_name, 'wheel')
        if '.' in wheel_def_name:
            return wheel_def_name
        pack_name = str(getattr(scene, 'dynamx_pack_name', '')).strip()
        if pack_name:
            return f"{pack_name}.{wheel_def_name}"
        return wheel_def_name

    pack_name = str(getattr(scene, 'dynamx_pack_name', '')).strip()
    wheel_model = str(getattr(scene, 'dynamx_wheel_model', '')).strip()
    vehicle_name = str(getattr(scene, 'dynamx_vehicle_name', '')).strip().replace(' ', '_')
    if pack_name and wheel_model:
        fallback = f"wheel_{vehicle_name}" if vehicle_name else 'wheel'
        return f"{pack_name}.{_normalize_wheel_def_name(wheel_model, fallback)}"
    if pack_name and vehicle_name:
        return f"{pack_name}.{_normalize_wheel_def_name('', f'wheel_{vehicle_name}')}"
    return f"wheel_{vehicle_name}" if vehicle_name else "wheel"


def _build_wheel_blocks(scene, wheel_objs):
    positions = [w.matrix_world.translation.copy() for w in wheel_objs]
    mean_x = sum(p.x for p in positions) / max(1, len(positions))
    mean_y = sum(p.y for p in positions) / max(1, len(positions))

    # Export order: front wheels first, then rear wheels.
    ordered = []
    for wheel_obj, pos in zip(wheel_objs, positions):
        is_right = pos.x < mean_x
        is_back = pos.y > mean_y
        base_name = f"wheel_{'b' if is_back else 'f'}{'r' if is_right else 'l'}"
        ordered.append((wheel_obj, pos, is_right, is_back, base_name))

    name_order = {
        'wheel_fl': 0,
        'wheel_fr': 1,
        'wheel_bl': 2,
        'wheel_br': 3,
    }
    ordered.sort(key=lambda it: (name_order.get(it[4], 99), _wheel_index_from_name(it[0].name), it[0].name))

    name_counts = {}
    blocks = []

    for wheel_obj, pos, is_right, is_back, base_name in ordered:
        count = name_counts.get(base_name, 0) + 1
        name_counts[base_name] = count
        wheel_name = base_name if count == 1 else f"{base_name}_{count}"

        is_steerable = bool(wheel_obj.get('IsSteerable', getattr(scene, 'dynamx_wheel_steerable', False)))
        max_turn = float(wheel_obj.get('MaxTurn', 0.7 if is_steerable else 0.0))
        driving_wheel = bool(wheel_obj.get('DrivingWheel', not is_steerable))
        attached = _attached_wheel_value(scene, wheel_obj)

        block = (
            f"{wheel_name}{{\n"
            f"    AttachedWheel: {attached}\n"
            f"    IsRight: {_bool_text(is_right)}\n"
            f"    Position: {pos.x:.6f} {pos.y:.6f} {pos.z:.6f}\n"
            f"    IsSteerable: {_bool_text(is_steerable)}\n"
            f"    MaxTurn: {max_turn:.6f}\n"
            f"    DrivingWheel: {_bool_text(driving_wheel)}\n"
            f"}}"
        )
        blocks.append(block)

    return blocks


def _export_all_wheels_to_vehicle(context):
    scene = context.scene
    wheels = _collect_wheel_hitboxes()
    if not wheels:
        return False, "No wheel hitboxes found (expected names like wheel_(1))"

    workspace_name = getattr(getattr(context, 'workspace', None), 'name', '')
    vehicle_file = _vehicle_dynx_path(scene, workspace_name)
    if not vehicle_file:
        return False, "Pack path, pack name and vehicle name are required"

    os.makedirs(os.path.dirname(vehicle_file), exist_ok=True)

    if os.path.exists(vehicle_file):
        try:
            with open(vehicle_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return False, f"Failed to read vehicle file: {e}"
    else:
        vehicle_name = getattr(scene, 'dynamx_vehicle_name', '').strip()
        content = (
            f"Name: {vehicle_name}\n\n"
            "// ------------- WHEELS -------------\n"
        )

    wheels_marker = '// ------------- WHEELS -------------'
    if wheels_marker not in content:
        seat_match = re.search(r'\n// ------------- SEATS', content)
        if seat_match:
            idx = seat_match.start()
            content = content[:idx] + f"\n{wheels_marker}\n" + content[idx:]
        else:
            content = content.rstrip() + f"\n\n{wheels_marker}\n"

    start = content.find(wheels_marker) + len(wheels_marker)
    next_section = re.search(r'\n// -------------', content[start:])
    end = start + next_section.start() if next_section else len(content)

    wheel_blocks = _build_wheel_blocks(scene, wheels)
    new_region = "\n\n" + "\n\n".join(wheel_blocks) + "\n"
    updated = content[:start] + new_region + content[end:]

    try:
        with open(vehicle_file, 'w', encoding='utf-8') as f:
            f.write(updated)
    except Exception as e:
        return False, f"Failed to write vehicle file: {e}"

    return True, f"Exported {len(wheel_blocks)} wheel block(s) to {vehicle_file}"


def _collect_material_variant_tokens(scene):
    variants = []
    for item in getattr(scene, 'dynamx_material_variants', []):
        raw = str(getattr(item, 'name', '')).strip()
        tex = str(getattr(item, 'texture_path', '')).strip()
        if not raw:
            continue
        if not tex:
            continue
        variants.append(re.sub(r'\s+', '_', raw))
    return variants


def _export_material_variants_to_vehicle(scene, workspace_name=''):
    vehicle_file = _vehicle_dynx_path(scene, workspace_name)
    if not vehicle_file:
        return False, "Pack path, pack name and vehicle name are required"
    if not os.path.exists(vehicle_file):
        return False, f"Vehicle file not found: {vehicle_file}"

    variants = _collect_material_variant_tokens(scene)
    if not variants:
        return False, "No material variants configured"

    try:
        with open(vehicle_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Failed to read vehicle file: {e}"

    colors_marker = '// ------------- COLORS -------------'
    if colors_marker not in content:
        doors_match = re.search(r'\n// ------------- DOORS', content)
        if doors_match:
            idx = doors_match.start()
            content = content[:idx] + f"\n{colors_marker}\n" + content[idx:]
        else:
            content = content.rstrip() + f"\n\n{colors_marker}\n"

    start = content.find(colors_marker) + len(colors_marker)
    next_section = re.search(r'\n// -------------', content[start:])
    end = start + next_section.start() if next_section else len(content)

    region = content[start:end]
    region = re.sub(r'\n*MaterialVariants\s*\{[^}]*\}\s*', '\n', region, flags=re.DOTALL)

    variants_line = ' '.join(variants)
    block = (
        "MaterialVariants{\n"
        f"    Variants: {variants_line}\n"
        "}\n"
    )
    new_region = "\n\n" + block + "\n"
    updated = content[:start] + new_region + content[end:]

    try:
        with open(vehicle_file, 'w', encoding='utf-8') as f:
            f.write(updated)
    except Exception as e:
        return False, f"Failed to write vehicle file: {e}"

    return True, f"Exported material variants to {vehicle_file}"


class DYNMX_PG_material_variant(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Variant",
        description="Material variant name",
        default=""
    )
    texture_path: bpy.props.StringProperty(
        name="Texture Path",
        description="Image file used for this color variant",
        default="",
        subtype='FILE_PATH'
    )


class DYNMX_OT_set_car(bpy.types.Operator):
    """Create vehicle configuration files and folders"""
    bl_idname = "dynamx.set_car"
    bl_label = "Set Car"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.dynamx_pack_path and scene.dynamx_pack_name and 
                scene.dynamx_vehicle_name and context.mode == 'OBJECT')

    def execute(self, context):
        scene = context.scene
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip()
        vehicle_name = scene.dynamx_vehicle_name.strip()
        vehicle_desc = scene.dynamx_vehicle_description.strip()
        empty_mass = scene.dynamx_empty_mass
        cog = tuple(scene.dynamx_cog_offset) if hasattr(scene, 'dynamx_cog_offset') else (0.0, 0.0, 0.0)
        shape_y_offset = getattr(scene, 'dynamx_shape_y_offset', 0.0)
        drag_coef = scene.dynamx_drag_coefficient
        zoom_level = scene.dynamx_zoom_level
        max_speed = scene.dynamx_max_speed

        model_val = scene.dynamx_model.strip() if hasattr(scene, 'dynamx_model') else ""
        default_engine_val = scene.dynamx_default_engine.strip() if hasattr(scene, 'dynamx_default_engine') else ""
        default_sounds_val = scene.dynamx_default_sounds.strip() if hasattr(scene, 'dynamx_default_sounds') else ""

        if not all([pack_path, pack_name, vehicle_name]):
            self.report({'ERROR'}, "Pack path, pack name and vehicle name are required")
            return {'CANCELLED'}

        pack_name_safe = pack_name.replace(" ", "_").lower()
        vehicle_name_safe = vehicle_name.replace(" ", "_").lower()

        if not model_val:
            model_val = f"obj/{vehicle_name_safe}/{vehicle_name_safe}.obj"
        if not default_engine_val:
            default_engine_val = f"{pack_name}.engine_{vehicle_name_safe}"
        if not default_sounds_val:
            default_sounds_val = f"{pack_name}.sounds_{vehicle_name_safe}"

        try:
            vehicle_dir = os.path.join(pack_path, pack_name_safe, "vehicle", vehicle_name_safe)
            os.makedirs(vehicle_dir, exist_ok=True)

            vehicle_file = os.path.join(vehicle_dir, f"vehicle_{vehicle_name_safe}.dynx")

            default_top = [
                f"Name: {vehicle_name}",
                f"Description: {vehicle_desc}",
                "",
                f"EmptyMass: {empty_mass:.0f}",
                f"DragCoefficient: {drag_coef:.2f}",
                f"DefaultZoomLevel: {zoom_level:.0f}",
                f"MaxVehicleSpeed: {max_speed:.0f}",
                "",
                f"Model: {model_val}",
                f"ShapeYOffset: {shape_y_offset:.2f}",
                "",
                f"DefaultEngine: {default_engine_val}",
                f"DefaultSounds: {default_sounds_val}",
                "",
                f"CenterOfGravityOffset: {cog[0]:.2f} {cog[1]:.2f} {cog[2]:.2f}",
                "",
            ]

            if os.path.exists(vehicle_file):
                try:
                    with open(vehicle_file, 'r', encoding='utf-8') as f:
                        existing = f.read()
                except Exception:
                    existing = ''

                def replace_or_insert(text, key, line_value):
                    pattern = re.compile(rf'^{re.escape(key)}:.*$', re.MULTILINE)
                    if pattern.search(text):
                        return pattern.sub(line_value, text)
                    else:
                        sec = re.search(r'\n// -------------', text)
                        insert_at = sec.start() if sec else 0
                        return text[:insert_at] + line_value + '\n' + text[insert_at:]

                existing = replace_or_insert(existing, 'Name', f'Name: {vehicle_name}')
                existing = replace_or_insert(existing, 'Description', f'Description: {vehicle_desc}')
                existing = replace_or_insert(existing, 'EmptyMass', f'EmptyMass: {empty_mass:.0f}')
                existing = replace_or_insert(existing, 'DragCoefficient', f'DragCoefficient: {drag_coef:.2f}')
                existing = replace_or_insert(existing, 'DefaultZoomLevel', f'DefaultZoomLevel: {zoom_level:.0f}')
                existing = replace_or_insert(existing, 'MaxVehicleSpeed', f'MaxVehicleSpeed: {max_speed:.0f}')
                existing = replace_or_insert(existing, 'Model', f'Model: {model_val}')
                existing = replace_or_insert(existing, 'ShapeYOffset', f'ShapeYOffset: {shape_y_offset:.2f}')
                existing = replace_or_insert(existing, 'DefaultEngine', f'DefaultEngine: {default_engine_val}')
                existing = replace_or_insert(existing, 'DefaultSounds', f'DefaultSounds: {default_sounds_val}')
                existing = replace_or_insert(existing, 'CenterOfGravityOffset', f'CenterOfGravityOffset: {cog[0]:.2f} {cog[1]:.2f} {cog[2]:.2f}')

                with open(vehicle_file, 'w', encoding='utf-8') as f:
                    f.write(existing)
            else:
                vehicle_content = '\n'.join(default_top) + '\n'
                vehicle_content += ("SteeringWheel{\n"
                                    "    PartName: steeringwheel\n"
                                    "    BaseRotationQuat: 1 0 0 0\n"
                                    "}\n\n"
                                    "// ------------- Hitbox -------------\n\n"
                                    "// ------------- WHEELS -------------\n\n"
                                    "// ------------- SEATS --------------\n\n"
                                    "// ------------- LIGHTS -------------\n\n"
                                    "// ------------- <RTK> --------------\n\n"
                                    "// ------------- <DOT> --------------\n\n"
                                    "// ------------- EXTRAS -------------\n\n"
                                    "// ------------- COLORS -------------\n\n"
                                    "// ------------- DOORS --------------\n\n"
                                    "// ------------- HIDEABLE PARTS -----\n")
                with open(vehicle_file, 'w', encoding='utf-8') as f:
                    f.write(vehicle_content)

            engine_file = os.path.join(vehicle_dir, f"engine_{vehicle_name_safe}.dynx")
            if not os.path.exists(engine_file):
                engine_content = (
                    "Power: 5000\n"
                    "MaxRPM: 5500\n"
                    "Braking: 40\n"
                    "\n"
                    "Point_1{\n"
                    "    RPMPower: 0 0\n"
                    "}\n"
                    "Point_2{\n"
                    "    RPMPower: 900 0.25\n"
                    "}\n"
                    "Point_3{\n"
                    "    RPMPower: 1400 0.35\n"
                    "}\n"
                    "Point_4{\n"
                    "    RPMPower: 1900 0.4\n"
                    "}\n"
                    "Point_5{\n"
                    "    RPMPower: 2400 0.3\n"
                    "}\n"
                    "Point_6{\n"
                    "    RPMPower: 2900 0.1\n"
                    "}\n"
                    "Point_7{\n"
                    "    RPMPower: 3400 0.05\n"
                    "}\n"
                    "Point_8{\n"
                    "    RPMPower: 4000 0.02\n"
                    "}\n"
                    "Point_9{\n"
                    "    RPMPower: 4600 0.01\n"
                    "}\n"
                    "Point_10{\n"
                    "    RPMPower: 5500 0.00\n"
                    "}\n"
                    "\n"
                    "Gear_0{\n"
                    "    SpeedRange: 0 -30\n"
                    "    RPMRange: 800 5500\n"
                    "}\n"
                    "Gear_1{\n"
                    "    SpeedRange: -1000000 1000000\n"
                    "    RPMRange: 0 5500\n"
                    "}\n"
                    "Gear_2{\n"
                    "    SpeedRange: 0 20\n"
                    "    RPMRange: 800 2750\n"
                    "}\n"
                    "Gear_3{\n"
                    "    SpeedRange: 15 40\n"
                    "    RPMRange: 900 2750\n"
                    "}\n"
                    "Gear_4{\n"
                    "    SpeedRange: 35 60\n"
                    "    RPMRange: 900 2750\n"
                    "}\n"
                    "Gear_5{\n"
                    "    SpeedRange: 55 80\n"
                    "    RPMRange: 900 2750\n"
                    "}\n"
                    "Gear_6{\n"
                    "    SpeedRange: 75 110\n"
                    "    RPMRange: 900 2900\n"
                    "}\n"
                    "Gear_7{\n"
                    "    SpeedRange: 90 200\n"
                    "    RPMRange: 1050 5500\n"
                    "}\n"
                )
                with open(engine_file, 'w', encoding='utf-8') as f:
                    f.write(engine_content)

            sounds_file = os.path.join(vehicle_dir, f"sounds_{vehicle_name_safe}.dynx")
            if not os.path.exists(sounds_file):
                sounds_content = (
                    "Engine{\n"
                    "    Interior{\n"
                    "        Starting{\n"
                    "            Sound: start\n"
                    "        }\n"
                    "        0-5500{\n"
                    "            Sound: int_idle\n"
                    "        }\n"
                    "    }\n"
                    "    Exterior{\n"
                    "        Starting{\n"
                    "            Sound: start\n"
                    "        }\n"
                    "        0-5500{\n"
                    "            Sound: ext_idle\n"
                    "        }\n"
                    "    }\n"
                    "}\n"
                )
                with open(sounds_file, 'w', encoding='utf-8') as f:
                    f.write(sounds_content)

            self.report({'INFO'}, f"Vehicle '{vehicle_name}' configuration created in {vehicle_dir}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to create vehicle files: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_generate_hitboxes(bpy.types.Operator):
    """Generate hitboxes for the active object by recursive spatial splitting with OBB fit"""
    bl_idname = "dynamx.generate_hitboxes"
    bl_label = "Generate Hitboxes"
    bl_options = {'REGISTER', 'UNDO'}

    max_depth: int = bpy.props.IntProperty(name="Max Depth", default=3, min=1, max=6)
    min_vertices: int = bpy.props.IntProperty(name="Min Vertices", default=80, min=4)
    margin: float = bpy.props.FloatProperty(name="Margin", default=0.02, min=0.0)
    reduction_threshold: float = bpy.props.FloatProperty(name="Reduction Threshold", default=0.95, min=0.0, max=1.0)
    sample_splits: int = bpy.props.IntProperty(name="Sample Splits", default=3, min=1, max=5)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'OBJECT' and getattr(context.active_object, 'type', '') == 'MESH'

    def execute(self, context):
        obj = context.active_object
        depsgraph = context.evaluated_depsgraph_get()

        try:
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            verts = [obj.matrix_world @ v.co for v in mesh.vertices]
            try:
                bpy.data.meshes.remove(mesh)
            except Exception:
                pass
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read mesh vertices: {e}")
            return {'CANCELLED'}

        if not verts:
            self.report({'ERROR'}, "No vertices found on active object")
            return {'CANCELLED'}

        hitboxes_col = bpy.data.collections.get("Hitboxes")
        if not hitboxes_col:
            hitboxes_col = bpy.data.collections.new("Hitboxes")
            try:
                context.scene.collection.children.link(hitboxes_col)
            except Exception:
                pass

        for o in list(hitboxes_col.objects):
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass

        counter = {'i': 0}

        def make_box_for(vlist):
            if not vlist:
                return
            n = len(vlist)
            cx = sum(v.x for v in vlist) / n
            cy = sum(v.y for v in vlist) / n
            cz = sum(v.z for v in vlist) / n
            
            cxx = cxy = cxz = cyy = cyz = czz = 0.0
            for v in vlist:
                dx = v.x - cx
                dy = v.y - cy
                dz = v.z - cz
                cxx += dx * dx
                cxy += dx * dy
                cxz += dx * dz
                cyy += dy * dy
                cyz += dy * dz
                czz += dz * dz
            invn = 1.0 / max(n, 1)
            cxx *= invn; cxy *= invn; cxz *= invn; cyy *= invn; cyz *= invn; czz *= invn

            v_ax = Vector((1.0, 0.0, 0.0))
            for _ in range(20):
                vx = cxx * v_ax.x + cxy * v_ax.y + cxz * v_ax.z
                vy = cxy * v_ax.x + cyy * v_ax.y + cyz * v_ax.z
                vz = cxz * v_ax.x + cyz * v_ax.y + czz * v_ax.z
                v_new = Vector((vx, vy, vz))
                if v_new.length == 0:
                    break
                v_new.normalize()
                v_ax = v_new

            axis1 = v_ax.normalized()
            if abs(axis1.dot(Vector((0.0, 0.0, 1.0)))) < 0.9:
                tmp = Vector((0.0, 0.0, 1.0))
            else:
                tmp = Vector((0.0, 1.0, 0.0))
            axis2 = axis1.cross(tmp).normalized()
            axis3 = axis1.cross(axis2).normalized()

            local_coords = []
            for v in vlist:
                dx = v - Vector((cx, cy, cz))
                lx = dx.dot(axis1)
                ly = dx.dot(axis2)
                lz = dx.dot(axis3)
                local_coords.append((lx, ly, lz))

            lxs = [c[0] for c in local_coords]
            lys = [c[1] for c in local_coords]
            lzs = [c[2] for c in local_coords]
            min_l = Vector((min(lxs), min(lys), min(lzs)))
            max_l = Vector((max(lxs), max(lys), max(lzs)))
            half = (max_l - min_l) * 0.5
            center_local = (max_l + min_l) * 0.5

            center_world = Vector((cx, cy, cz)) + axis1 * center_local.x + axis2 * center_local.y + axis3 * center_local.z

            try:
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=center_world)
                box = context.active_object
                box.name = f"Shape_{obj.name}_{counter['i']}"
                counter['i'] += 1
                R = Matrix((axis1, axis2, axis3)).transposed()
                try:
                    box.rotation_mode = 'QUATERNION'
                    box.rotation_quaternion = R.to_4x4().to_quaternion()
                except Exception:
                    try:
                        box.rotation_euler = R.to_euler()
                    except Exception:
                        pass
                box.scale = Vector((max(half.x, 1e-6), max(half.y, 1e-6), max(half.z, 1e-6))) * (1.0 + float(self.margin))
                try:
                    box.display_type = 'WIRE'
                except Exception:
                    pass
                for col in list(box.users_collection):
                    try:
                        col.objects.unlink(box)
                    except Exception:
                        pass
                try:
                    hitboxes_col.objects.link(box)
                except Exception:
                    pass
            except Exception:
                return

        def split_recursive(vlist, depth):
            if not vlist:
                return
            if depth <= 0 or len(vlist) <= int(self.min_vertices):
                make_box_for(vlist)
                return

            xs = [v.x for v in vlist]
            ys = [v.y for v in vlist]
            zs = [v.z for v in vlist]
            rx = max(xs) - min(xs)
            ry = max(ys) - min(ys)
            rz = max(zs) - min(zs)
            if rx >= ry and rx >= rz:
                axis = 0
            elif ry >= rz:
                axis = 1
            else:
                axis = 2

            coords = [v[axis] for v in vlist]
            coords_sorted = sorted(coords)
            orig_vol = max(rx, 1e-9) * max(ry, 1e-9) * max(rz, 1e-9)

            best_split = None
            best_combined_vol = orig_vol

            n = len(coords_sorted)
            for k in range(1, int(self.sample_splits) + 1):
                idx = int(n * k / (int(self.sample_splits) + 1))
                if idx <= 0 or idx >= n:
                    continue
                pos = coords_sorted[idx]
                left = [v for v in vlist if v[axis] <= pos]
                right = [v for v in vlist if v[axis] > pos]
                if not left or not right:
                    continue
                lxs = [v.x for v in left]
                lys = [v.y for v in left]
                lzs = [v.z for v in left]
                rxs = [v.x for v in right]
                rys = [v.y for v in right]
                rzs = [v.z for v in right]
                lvol = max(max(lxs) - min(lxs), 1e-9) * max(max(lys) - min(lys), 1e-9) * max(max(lzs) - min(lzs), 1e-9)
                rvol = max(max(rxs) - min(rxs), 1e-9) * max(max(rys) - min(rys), 1e-9) * max(max(rzs) - min(rzs), 1e-9)
                combined = lvol + rvol
                if combined < best_combined_vol:
                    best_combined_vol = combined
                    best_split = (pos, left, right)

            if not best_split:
                make_box_for(vlist)
                return

            if best_combined_vol / max(orig_vol, 1e-9) >= float(self.reduction_threshold):
                make_box_for(vlist)
                return

            _, left, right = best_split
            split_recursive(left, depth - 1)
            split_recursive(right, depth - 1)

        try:
            split_recursive(verts, int(self.max_depth))
            organize_scene_collections()
            self.report({'INFO'}, f"Generated {counter['i']} hitboxes for {obj.name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Hitbox generation failed: {e}")
            return {'CANCELLED'}


class DYNMX_OT_select_vehicle(bpy.types.Operator):
    """Select and load an existing vehicle file"""
    bl_idname = "dynamx.select_vehicle"
    bl_label = "Select Vehicle"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.dynx", options={'HIDDEN'})
    filename_ext = ".dynx"

    def execute(self, context):
        scene = context.scene
        fp = os.path.normpath(os.path.expanduser(str(self.filepath).strip())) if self.filepath else ""
        
        if not fp or not os.path.exists(fp):
            self.report({'ERROR'}, f"Invalid file path: {fp}")
            return {'CANCELLED'}

        filename = os.path.basename(fp)
        if not filename.lower().endswith('.dynx') or not filename.startswith('vehicle_'):
            self.report({'ERROR'}, "Please select a vehicle_*.dynx file")
            return {'CANCELLED'}

        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open file: {e}")
            return {'CANCELLED'}

        vehicle_name_from_file = filename.replace('vehicle_', '').replace('.dynx', '')

        def parse_value(key, default=''):
            m = re.search(rf'^{re.escape(key)}:\s*(.+)$', content, re.MULTILINE)
            return m.group(1).strip() if m else default

        # Load all vehicle properties
        scene.dynamx_vehicle_name = parse_value('Name', vehicle_name_from_file)
        scene.dynamx_vehicle_description = parse_value('Description', 'A custom vehicle')
        
        try:
            scene.dynamx_empty_mass = float(parse_value('EmptyMass', '5000'))
        except Exception:
            pass
        
        try:
            scene.dynamx_drag_coefficient = float(parse_value('DragCoefficient', '0.3'))
        except Exception:
            pass
        
        try:
            scene.dynamx_zoom_level = float(parse_value('DefaultZoomLevel', '20.0'))
        except Exception:
            pass
        
        try:
            scene.dynamx_max_speed = float(parse_value('MaxVehicleSpeed', '250.0'))
        except Exception:
            pass
        
        try:
            scene.dynamx_model = parse_value('Model', 'obj/model/model.obj')
        except Exception:
            pass
        
        try:
            scene.dynamx_shape_y_offset = float(parse_value('ShapeYOffset', '0.0'))
        except Exception:
            pass
        
        try:
            scene.dynamx_default_engine = parse_value('DefaultEngine', '')
        except Exception:
            pass
        
        try:
            scene.dynamx_default_sounds = parse_value('DefaultSounds', '')
        except Exception:
            pass
        
        try:
            cog_str = parse_value('CenterOfGravityOffset', '0.0 0.0 0.0')
            cog_vals = [float(x) for x in cog_str.split()]
            if len(cog_vals) == 3 and hasattr(scene, 'dynamx_cog_offset'):
                scene.dynamx_cog_offset = tuple(cog_vals)
        except Exception:
            pass

        self.report({'INFO'}, f"Loaded vehicle: {scene.dynamx_vehicle_name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DYNMX_OT_set_steering_wheel(bpy.types.Operator):
    """Align selected steering wheel and create a wireframe bounding box"""
    bl_idname = "dynamx.set_steering_wheel"
    bl_label = "Set Steering Wheel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object

        try:
            original_orientation = context.scene.transform_orientation_slots[0].type
        except Exception:
            original_orientation = 'GLOBAL'

        try:
            context.scene.transform_orientation_slots[0].type = 'LOCAL'
        except Exception:
            pass

        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        try:
            obj.name = "steeringwheel"
            if getattr(obj, 'data', None):
                obj.data.name = "steeringwheel"

            bounds_old = bpy.data.objects.get("steeringwheel_bounds")
            if bounds_old is not None:
                try:
                    bpy.data.objects.remove(bounds_old, do_unlink=True)
                except Exception:
                    pass

            wpts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            wx = [p.x for p in wpts]
            wy = [p.y for p in wpts]
            wz = [p.z for p in wpts]
            minx, maxx = min(wx), max(wx)
            miny, maxy = min(wy), max(wy)
            minz, maxz = min(wz), max(wz)
            center = Vector(((minx + maxx) * 0.5, (miny + maxy) * 0.5, (minz + maxz) * 0.5))
            size = Vector((maxx - minx, maxy - miny, maxz - minz))

            margin = 1.10
            half_scale = Vector((max(size.x * 0.5, 1e-6), max(size.y * 0.5, 1e-6), max(size.z * 0.5, 1e-6))) * margin

            bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
            box = context.active_object
            box.name = "steeringwheel_bounds"
            box.scale = half_scale
            try:
                box.display_type = 'WIRE'
            except Exception:
                pass

            box.parent = obj
            box.matrix_parent_inverse = obj.matrix_world.inverted()
            for col in obj.users_collection:
                if box not in col.objects:
                    col.objects.link(box)
            for col in list(box.users_collection):
                if col.name not in [c.name for c in obj.users_collection]:
                    col.objects.unlink(box)

            _set_steering_rotation_from_object(context.scene, obj)
            self.report({'INFO'}, f"Steering wheel set and bounds created: {box.name}")

            try:
                context.scene.transform_orientation_slots[0].type = original_orientation
            except Exception:
                pass

            return {'FINISHED'}
        except Exception as e:
            try:
                context.scene.transform_orientation_slots[0].type = original_orientation
            except Exception:
                pass
            self.report({'ERROR'}, f"Failed to set steering wheel: {e}")
            return {'CANCELLED'}


class DYNMX_OT_apply_steering_wheel_rotation(bpy.types.Operator):
    """Apply steering wheel rotation from panel values"""
    bl_idname = "dynamx.apply_steering_wheel_rotation"
    bl_label = "Apply Steering Rotation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return find_steering_wheel_object() is not None and hasattr(context.scene, 'dynamx_steering_rotation_deg')

    def execute(self, context):
        steering_obj = find_steering_wheel_object()
        if steering_obj is None:
            self.report({'ERROR'}, "No steering wheel object set")
            return {'CANCELLED'}

        quat, euler = _steering_quaternion_from_scene(context.scene)
        try:
            steering_obj.rotation_mode = 'XYZ'
            steering_obj.rotation_euler = euler
        except Exception as e:
            self.report({'ERROR'}, f"Failed to apply steering rotation: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Steering rotation applied (quat: {quat.w:.6f} {quat.x:.6f} {quat.y:.6f} {quat.z:.6f})")
        return {'FINISHED'}


class DYNMX_OT_export_steering_wheel(bpy.types.Operator):
    """Export steering wheel rotation to vehicle file and delete bounds"""
    bl_idname = "dynamx.export_steering_wheel"
    bl_label = "Export Steering Wheel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not (scene.dynamx_pack_path and scene.dynamx_pack_name and scene.dynamx_vehicle_name):
            return False
        return bpy.data.objects.get("steeringwheel") is not None

    def execute(self, context):
        scene = context.scene
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip()
        vehicle_name = scene.dynamx_vehicle_name.strip()

        pack_name_safe = pack_name.replace(" ", "_").lower()
        vehicle_name_safe = vehicle_name.replace(" ", "_").lower()

        vehicle_file = os.path.join(pack_path, pack_name_safe, "vehicle", vehicle_name_safe, f"vehicle_{vehicle_name_safe}.dynx")

        if not os.path.exists(vehicle_file):
            self.report({'ERROR'}, f"Vehicle file not found: {vehicle_file}")
            return {'CANCELLED'}

        wheel_obj = bpy.data.objects.get("steeringwheel")
        if not wheel_obj:
            self.report({'ERROR'}, "Steering wheel object 'steeringwheel' not found")
            return {'CANCELLED'}

        bounds_obj = bpy.data.objects.get("steeringwheel_bounds")
        if not bounds_obj:
            self.report({'ERROR'}, "Steering wheel bounds 'steeringwheel_bounds' not found. Please run 'Set Steering Wheel' first.")
            return {'CANCELLED'}

        quat = bounds_obj.matrix_world.to_quaternion()
        quat_str = f"{quat.w:.6f} {quat.x:.6f} {quat.y:.6f} {quat.z:.6f}"

        try:
            with open(vehicle_file, 'r', encoding='utf-8') as f:
                content = f.read()

            pattern = re.compile(
                r'SteeringWheel\s*\{[^}]*\}',
                re.MULTILINE | re.DOTALL
            )

            new_block = f"""SteeringWheel{{
    PartName: steeringwheel
    BaseRotationQuat: {quat_str}
}}"""

            if pattern.search(content):
                content = pattern.sub(new_block, content)
            else:
                hitbox_match = re.search(r'// ------------- Hitbox -------------', content)
                if hitbox_match:
                    insert_pos = hitbox_match.start()
                    content = content[:insert_pos] + new_block + '\n\n' + content[insert_pos:]
                else:
                    content = content.rstrip() + '\n\n' + new_block + '\n'

            with open(vehicle_file, 'w', encoding='utf-8') as f:
                f.write(content)

            bounds_obj = bpy.data.objects.get("steeringwheel_bounds")
            if bounds_obj:
                bpy.data.objects.remove(bounds_obj, do_unlink=True)

            _set_steering_rotation_from_object(scene, wheel_obj)
            self.report({'INFO'}, f"Steering wheel exported with rotation: {quat_str}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export steering wheel: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_set_chassis(bpy.types.Operator):
    """Set chassis object"""
    bl_idname = "dynamx.set_chassis"
    bl_label = "Set Chassis"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'OBJECT'

    def execute(self, context):
        obj = context.active_object
        if obj:
            obj.name = "chassis"
            self.report({'INFO'}, "Chassis set")
        return {'FINISHED'}


class DYNMX_OT_save_wheel(bpy.types.Operator):
    """Save wheel configuration"""
    bl_idname = "dynamx.save_wheel"
    bl_label = "Save Wheel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        for wheel_obj in _collect_wheel_hitboxes():
            _ensure_wheel_outside_arrow(wheel_obj)
        ok, msg = _export_all_wheels_to_vehicle(context)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_set_wheel(bpy.types.Operator):
    """Create wheel with rim hitbox (select 1-2 objects: auto-size or biggest=wheel, smallest=rim)"""
    bl_idname = "dynamx.set_wheel"
    bl_label = "Set Wheel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and len(context.selected_objects) > 0

    def execute(self, context):
        scene = context.scene
        selected = context.selected_objects
        
        if len(selected) > 2:
            self.report({'ERROR'}, "Select 1-2 objects maximum")
            return {'CANCELLED'}
        
        # Check required scene properties
        pack_path = bpy.path.abspath(getattr(scene, 'dynamx_pack_path', ''))
        pack_name = getattr(scene, 'dynamx_pack_name', '').strip()
        vehicle_name = getattr(scene, 'dynamx_vehicle_name', '').strip()
        
        if not all([pack_path, pack_name, vehicle_name]):
            self.report({'ERROR'}, 'Pack path, pack name, and vehicle name required')
            return {'CANCELLED'}
        
        try:
            # Get or create wheels collection in Dynamx
            dynamx_col = bpy.data.collections.get("Dynamx")
            if not dynamx_col:
                dynamx_col = bpy.data.collections.new("Dynamx")
                scene.collection.children.link(dynamx_col)
            
            wheels_col = bpy.data.collections.get('wheels')
            if not wheels_col:
                wheels_col = bpy.data.collections.new('wheels')
                try:
                    dynamx_col.children.link(wheels_col)
                except Exception:
                    scene.collection.children.link(wheels_col)
            
            # Get or create wheel and wheel_model subcollections
            wheel_col = bpy.data.collections.get('wheel')
            if not wheel_col:
                wheel_col = bpy.data.collections.new('wheel')
                try:
                    wheels_col.children.link(wheel_col)
                except Exception:
                    pass
            
            wheel_model_col = bpy.data.collections.get('wheel_model')
            if not wheel_model_col:
                wheel_model_col = bpy.data.collections.new('wheel_model')
                try:
                    wheels_col.children.link(wheel_model_col)
                except Exception:
                    pass
            
            # Find next wheel index
            import re as _re
            max_idx = 0
            for ob in bpy.data.objects:
                m = _re.search(r'wheel_\((\d+)\)', ob.name)
                if m:
                    try:
                        max_idx = max(max_idx, int(m.group(1)))
                    except Exception:
                        pass
            wheel_idx = max_idx + 1
            
            # Get object sizes to determine wheel vs rim
            objs_by_size = sorted(selected, key=lambda o: (o.dimensions.x * o.dimensions.z) if o.type == 'MESH' else 0, reverse=True)
            
            wheel_obj = objs_by_size[0]  # Largest = wheel
            rim_obj = objs_by_size[1] if len(objs_by_size) > 1 else None

            # Helper function to get geometry center
            def get_geometry_center(obj):
                bbox_center = sum((Vector(b) for b in obj.bound_box), Vector()) / 8
                return obj.matrix_world @ bbox_center
            
            def move_mesh_and_origin_to_zero(obj, target_center):
                if obj is None or getattr(obj, 'type', '') != 'MESH' or getattr(obj, 'data', None) is None:
                    return
                try:
                    # Bake world transform into mesh, then recenter mesh so origin and geometry pivot are at 0/0/0.
                    obj.data.transform(obj.matrix_world)
                    obj.matrix_world = Matrix.Identity(4)
                    obj.data.transform(Matrix.Translation(-target_center))
                except Exception:
                    pass
            
            # Extract wheel dimensions
            wheel_radius = wheel_obj.dimensions.x / 2 if wheel_obj.dimensions.x > 0 else 1.0
            wheel_width = wheel_obj.dimensions.y if wheel_obj.dimensions.y > 0 else 0.5
            wheel_center = get_geometry_center(wheel_obj)
            rim_radius = (rim_obj.dimensions.y / 2 if rim_obj and rim_obj.dimensions.y > 0 else wheel_radius * 0.7)
            
            # Get suspension properties for cylinder positioning
            susp_rest = getattr(scene, 'dynamx_wheel_suspension_rest_length', 0.13)
            cylinder_offset = -susp_rest
            
            # Create cylinder first (before hitbox to avoid parent scaling)
            bpy.ops.mesh.primitive_cylinder_add(radius=wheel_width / 2, depth=wheel_radius * 2, location=wheel_center)
            wheel_cylinder = context.active_object
            wheel_cylinder.name = f"wheel_cylinder_({wheel_idx})"
            wheel_cylinder.display_type = 'WIRE'
            # Rotate cylinder on Y axis
            wheel_cylinder.rotation_euler = (0, math.radians(90), 0)
            
            # Create wheel hitbox box
            bpy.ops.mesh.primitive_cube_add(location=wheel_center)
            wheel_hitbox = context.active_object
            wheel_hitbox.name = f"wheel_({wheel_idx})"
            wheel_hitbox.display_type = 'WIRE'
            # Scale the box (not in edit mode) - Y and Z same scale
            wheel_hitbox.scale = (wheel_radius, wheel_width / 2, wheel_width / 2)
            
            # Set wheel_hitbox as parent to cylinder
            wheel_cylinder.parent = wheel_hitbox
            # Reset cylinder location to parent space with suspension offset
            wheel_cylinder.location = (0, 0, cylinder_offset)
            # Compensate for parent scale so cylinder doesn't get distorted
            wheel_cylinder.scale = (2 / wheel_width, 2 / wheel_width, 1 / wheel_radius)
            # Link cylinder to same collection
            for col in list(wheel_cylinder.users_collection):
                try:
                    col.objects.unlink(wheel_cylinder)
                except Exception:
                    pass
            try:
                wheel_col.objects.link(wheel_cylinder)
            except Exception:
                pass
            # Select the box again as active object
            context.view_layer.objects.active = wheel_hitbox
            wheel_hitbox.select_set(True)
            
            # Set custom properties on wheel hitbox
            pack_name_safe = pack_name.replace(" ", "_").lower()
            vehicle_name_safe = vehicle_name.replace(" ", "_").lower()
            wheel_hitbox['IsSteerable'] = bool(getattr(scene, 'dynamx_wheel_steerable', False))
            wheel_hitbox['DrivingWheel'] = not bool(getattr(scene, 'dynamx_wheel_steerable', False))
            wheel_hitbox['MaxTurn'] = 0.7 if wheel_hitbox.get('IsSteerable', False) else 0.0
            
            # Unlink and link to wheel collection
            for col in list(wheel_hitbox.users_collection):
                try:
                    col.objects.unlink(wheel_hitbox)
                except Exception:
                    pass
            try:
                wheel_col.objects.link(wheel_hitbox)
            except Exception:
                pass
            
            # Create rim if 2 objects selected
            if rim_obj:
                rim_width = rim_obj.dimensions.y if rim_obj.dimensions.y > 0 else wheel_width * 0.8
                
                # Keep rim centered on the wheel pivot; local coordinates must stay 0/0/0.
                bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, location=wheel_center)
                rim_cylinder = context.active_object
                rim_cylinder.name = f"rim_cylinder_({wheel_idx})"
                rim_cylinder.display_type = 'WIRE'
                # Rotate cylinder on Y axis (90° + additional 90° = 180°)
                rim_cylinder.rotation_euler = (0, math.radians(180), 0)
                
                # Set wheel_cylinder as parent to rim_cylinder
                rim_cylinder.parent = wheel_cylinder
                # Rim local coordinates should remain centered at the wheel origin.
                rim_cylinder.location = (0.0, 0.0, 0.0)
                # Scale: X=rim_width/2, Y=X, Z=wheel_radius
                rim_cylinder.scale = (rim_width / 2, rim_width / 2, wheel_radius)
                
                # Link rim cylinder to wheel collection
                for col in list(rim_cylinder.users_collection):
                    try:
                        col.objects.unlink(rim_cylinder)
                    except Exception:
                        pass
                try:
                    wheel_col.objects.link(rim_cylinder)
                except Exception:
                    pass
            
            # Rename original wheel objects
            wheel_obj.name = "tyre"
            wheel_obj.data.name = "tyre"
            wheel_hitbox.data.name = f"wheel_({wheel_idx})"
            wheel_cylinder.data.name = f"wheel_cylinder_({wheel_idx})"
            if rim_obj:
                rim_obj.name = "rim"
                rim_obj.data.name = "rim"
                rim_cylinder.data.name = f"rim_cylinder_({wheel_idx})"
            
            # Create wheel model collection with wheel(letter) subcollection
            wheel_letter_idx = 0
            for col in wheel_model_col.children:
                if col.name.startswith('wheel(') and col.name.endswith(')'):
                    try:
                        letter = col.name[6]  # Extract letter from wheel(x)
                        letter_num = ord(letter.lower()) - ord('a')
                        wheel_letter_idx = max(wheel_letter_idx, letter_num + 1)
                    except Exception:
                        pass
            wheel_letter = chr(ord('a') + wheel_letter_idx)

            default_wheel_def = f"wheel_{vehicle_name_safe}_{wheel_letter}"
            wheel_model_name = str(getattr(scene, 'dynamx_wheel_model', '')).strip()
            wheel_def_name = _normalize_wheel_def_name(wheel_model_name, default_wheel_def)
            wheel_hitbox['AttachedWheel'] = f"{pack_name}.{wheel_def_name}" if pack_name else wheel_def_name
            wheel_hitbox['WheelDefName'] = wheel_def_name
            
            wheel_letter_col = bpy.data.collections.get(f'wheel({wheel_letter})')
            if not wheel_letter_col:
                wheel_letter_col = bpy.data.collections.new(f'wheel({wheel_letter})')
                try:
                    wheel_model_col.children.link(wheel_letter_col)
                except Exception:
                    pass
            wheel_letter_col['WheelDefName'] = wheel_def_name
            
            # Move wheel and rim objects to wheel(letter) collection
            for col in list(wheel_obj.users_collection):
                try:
                    col.objects.unlink(wheel_obj)
                except Exception:
                    pass
            try:
                wheel_letter_col.objects.link(wheel_obj)
            except Exception:
                pass
            wheel_obj['WheelDefName'] = wheel_def_name
            
            if rim_obj:
                for col in list(rim_obj.users_collection):
                    try:
                        col.objects.unlink(rim_obj)
                    except Exception:
                        pass
                try:
                    wheel_letter_col.objects.link(rim_obj)
                except Exception:
                    pass
                rim_obj['WheelDefName'] = wheel_def_name

            # Wheel model mesh should be centered for clean exports.
            move_mesh_and_origin_to_zero(wheel_obj, wheel_center)
            if rim_obj:
                move_mesh_and_origin_to_zero(rim_obj, wheel_center)

            _ensure_wheel_outside_arrow(wheel_hitbox)
            
            # Create wheel .dynx file
            try:
                vehicle_dir = os.path.join(pack_path, pack_name_safe, "vehicle", vehicle_name_safe)
                os.makedirs(vehicle_dir, exist_ok=True)
                
                wheel_file = os.path.join(vehicle_dir, f"{wheel_def_name}.dynx")
                
                # Get values from scene properties
                friction = getattr(scene, 'dynamx_wheel_friction', 1.0)
                brake_force = getattr(scene, 'dynamx_wheel_brake_force', 100.0)
                roll_influence = getattr(scene, 'dynamx_wheel_roll_influence', 1.0)
                susp_rest = getattr(scene, 'dynamx_wheel_suspension_rest_length', 0.13)
                susp_stiff = getattr(scene, 'dynamx_wheel_suspension_stiffness', 20.0)
                susp_max = getattr(scene, 'dynamx_wheel_suspension_max_force', 1000000.0)
                damp_relax = getattr(scene, 'dynamx_wheel_damping_relaxation', 0.45)
                damp_comp = getattr(scene, 'dynamx_wheels_damping_compression', 0.2)
                
                # Create wheel dynx content
                wheel_content = (
                    f"Model: obj/{vehicle_name_safe}/{wheel_def_name}.obj\n"
                    f"Width: {wheel_radius:.3f}\n"
                    f"Radius: {wheel_width / 2:.3f}\n"
                    f"RimRadius: {rim_radius:.3f}\n"
                    f"Friction: {friction:.6f}\n"
                    f"BrakeForce: {brake_force:.6f}\n"
                    f"RollInInfluence: {roll_influence:.6f}\n"
                    f"SuspensionRestLength: {susp_rest:.6f}\n"
                    f"SuspensionStiffness: {susp_stiff:.6f}\n"
                    f"SuspensionMaxForce: {susp_max:.6f}\n"
                    f"WheelDampingRelaxation: {damp_relax:.6f}\n"
                    f"WheelsDampingCompression: {damp_comp:.6f}\n"
                )
                
                with open(wheel_file, 'w', encoding='utf-8') as f:
                    f.write(wheel_content)
                
                self.report({'INFO'}, f"Created wheel .dynx: {os.path.basename(wheel_file)}")
            except Exception as e:
                self.report({'WARNING'}, f"Created wheel but .dynx file failed: {str(e)}")
            
            organize_scene_collections()
            if rim_obj:
                self.report({'INFO'}, f"Created wheel_({wheel_idx}) with rim (type: {wheel_def_name})")
            else:
                self.report({'INFO'}, f"Created wheel_({wheel_idx}) (type: {wheel_def_name})")
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Failed to set wheel: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_export_wheels(bpy.types.Operator):
    """Export all wheel blocks to vehicle/trailer dynx file"""
    bl_idname = "dynamx.export_wheels"
    bl_label = "Export Wheels"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        for wheel_obj in _collect_wheel_hitboxes():
            _ensure_wheel_outside_arrow(wheel_obj)
        ok, msg = _export_all_wheels_to_vehicle(context)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_duplicate_wheel(bpy.types.Operator):
    """Duplicate the selected wheel (wheel_(x) objects from wheels collection)"""
    bl_idname = "dynamx.duplicate_wheel"
    bl_label = "Duplicate Wheel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.active_object is None or context.mode != 'OBJECT':
            return False
        # Check if active object is a wheel hitbox
        return 'wheel_(' in context.active_object.name and ')' in context.active_object.name

    def execute(self, context):
        try:
            wheel_obj = context.active_object
            if not wheel_obj:
                self.report({'ERROR'}, "No wheel selected")
                return {'CANCELLED'}
            
            # Find next wheel index
            import re as _re
            max_idx = 0
            for ob in bpy.data.objects:
                m = _re.search(r'wheel_\((\d+)\)', ob.name)
                if m:
                    try:
                        max_idx = max(max_idx, int(m.group(1)))
                    except Exception:
                        pass
            new_idx = max_idx + 1
            
            # Select wheel and all its children for duplication
            bpy.ops.object.select_all(action='DESELECT')
            wheel_obj.select_set(True)
            
            # Also select all children recursively
            def select_children(obj):
                for child in obj.children:
                    child.select_set(True)
                    select_children(child)
            
            select_children(wheel_obj)
            context.view_layer.objects.active = wheel_obj
            
            # Duplicate all selected objects
            bpy.ops.object.duplicate()
            
            # Find the duplicated wheel (active object after duplicate)
            duplicated = context.active_object
            
            # Rename duplicated wheel and remove .001 etc.
            new_name = f"wheel_({new_idx})"
            duplicated.name = new_name
            # Remove .001 .002 etc from data name
            duplicated.data.name = new_name
            
            # Rename children (cylinder objects)
            for child in duplicated.children:
                if "cylinder" in child.name.lower():
                    # Extract old index from original wheel object name
                    old_idx_str = wheel_obj.name.split('(')[1].rstrip(')')
                    # Remove .001 from old name first
                    old_child_base = child.name.split('.')[0]
                    new_child_name = old_child_base.replace(f"({old_idx_str})", f"({new_idx})")
                    
                    child.name = new_child_name
                    if child.data:
                        child.data.name = new_child_name
                    
                    # Also rename grandchildren
                    for grandchild in child.children:
                        old_grandchild_base = grandchild.name.split('.')[0]
                        new_grandchild_name = old_grandchild_base.replace(f"({old_idx_str})", f"({new_idx})")
                        
                        grandchild.name = new_grandchild_name
                        if grandchild.data:
                            grandchild.data.name = new_grandchild_name

            # Keep rim cylinders centered on their parent wheel cylinder.
            for child in duplicated.children:
                if "wheel_cylinder" not in child.name.lower():
                    continue
                for grandchild in child.children:
                    if "rim_cylinder" in grandchild.name.lower():
                        grandchild.location = (0.0, 0.0, 0.0)

            _ensure_wheel_outside_arrow(duplicated)
            
            self.report({'INFO'}, f"Duplicated wheel as wheel_({new_idx})")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to duplicate wheel: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_delete_wheel(bpy.types.Operator):
    """Delete the selected wheel"""
    bl_idname = "dynamx.delete_wheel"
    bl_label = "Delete Wheel"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.active_object is None or context.mode != 'OBJECT':
            return False
        # Check if active object is a wheel hitbox
        return 'wheel_(' in context.active_object.name and ')' in context.active_object.name

    def execute(self, context):
        try:
            wheel_obj = context.active_object
            if not wheel_obj:
                self.report({'ERROR'}, "No wheel selected")
                return {'CANCELLED'}
            
            wheel_name = wheel_obj.name
            
            # Collect all objects to delete recursively
            def collect_children(obj, children_list):
                for child in obj.children:
                    children_list.append(child)
                    collect_children(child, children_list)
            
            children_to_delete = []
            collect_children(wheel_obj, children_to_delete)
            
            # Delete wheel and all its children
            bpy.data.objects.remove(wheel_obj, do_unlink=True)
            
            # Delete children and grandchildren
            for child in children_to_delete:
                try:
                    bpy.data.objects.remove(child, do_unlink=True)
                except Exception:
                    pass
            
            self.report({'INFO'}, f"Deleted wheel: {wheel_name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to delete wheel: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_set_trailer(bpy.types.Operator):
    """Create trailer configuration"""
    bl_idname = "dynamx.set_trailer"
    bl_label = "Set Trailer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.dynamx_pack_path and scene.dynamx_pack_name and 
                scene.dynamx_vehicle_name and context.mode == 'OBJECT')

    def execute(self, context):
        self.report({'INFO'}, "Trailer configured")
        return {'FINISHED'}


class DYNMX_OT_select_trailer(bpy.types.Operator):
    """Select trailer file"""
    bl_idname = "dynamx.select_trailer"
    bl_label = "Select Trailer"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.dynx", options={'HIDDEN'})

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class DYNMX_OT_create_trailer_attach(bpy.types.Operator):
    """Create trailer attachment point"""
    bl_idname = "dynamx.create_trailer_attach"
    bl_label = "Create Trailer Attach"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'OBJECT'

    def execute(self, context):
        self.report({'INFO'}, "Trailer attach point created")
        return {'FINISHED'}


class DYNMX_OT_save_trailer_attach(bpy.types.Operator):
    """Save trailer attachment"""
    bl_idname = "dynamx.save_trailer_attach"
    bl_label = "Save Trailer Attach"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.mode == 'OBJECT'

    def execute(self, context):
        self.report({'INFO'}, "Trailer attach saved")
        return {'FINISHED'}


class DYNMX_OT_add_material_variant(bpy.types.Operator):
    """Add one material variant entry"""
    bl_idname = "dynamx.add_material_variant"
    bl_label = "Add Material Variant"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        variants = getattr(scene, 'dynamx_material_variants', None)
        if variants is None:
            self.report({'ERROR'}, "Material variants are not available")
            return {'CANCELLED'}

        item = variants.add()
        item.name = ""
        if hasattr(scene, 'dynamx_material_variants_index'):
            scene.dynamx_material_variants_index = len(variants) - 1

        return {'FINISHED'}


class DYNMX_OT_remove_material_variant(bpy.types.Operator):
    """Remove one material variant entry"""
    bl_idname = "dynamx.remove_material_variant"
    bl_label = "Remove Material Variant"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty(default=-1, min=-1)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        variants = getattr(scene, 'dynamx_material_variants', None)
        if variants is None or len(variants) == 0:
            self.report({'WARNING'}, "No material variants to remove")
            return {'CANCELLED'}

        idx = self.index
        if idx < 0 or idx >= len(variants):
            idx = int(getattr(scene, 'dynamx_material_variants_index', len(variants) - 1))
        if idx < 0 or idx >= len(variants):
            self.report({'WARNING'}, "Invalid variant index")
            return {'CANCELLED'}

        variants.remove(idx)
        if hasattr(scene, 'dynamx_material_variants_index'):
            if len(variants) == 0:
                scene.dynamx_material_variants_index = 0
            else:
                scene.dynamx_material_variants_index = min(idx, len(variants) - 1)

        return {'FINISHED'}


class DYNMX_OT_export_material_variants(bpy.types.Operator):
    """Export material variants into COLORS section"""
    bl_idname = "dynamx.export_material_variants"
    bl_label = "Export Material Variants"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (
            context.mode == 'OBJECT'
            and bool(getattr(scene, 'dynamx_pack_path', '').strip())
            and bool(getattr(scene, 'dynamx_pack_name', '').strip())
            and bool(getattr(scene, 'dynamx_vehicle_name', '').strip())
        )

    def execute(self, context):
        workspace_name = getattr(getattr(context, 'workspace', None), 'name', '')
        ok, msg = _export_material_variants_to_vehicle(context.scene, workspace_name)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_organize_collections(bpy.types.Operator):
    """Auto-organize scene collections for DynamX"""
    bl_idname = "dynamx.organize_collections"
    bl_label = "Organize Collections"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        try:
            organize_scene_collections()
            self.report({'INFO'}, "Collections organized")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f"Failed to organize collections: {exc}")
            return {'CANCELLED'}
class DYNMX_OT_export_obj(bpy.types.Operator):
    """Export vehicle model as OBJ file and wheel types as separate wheel OBJ files"""
    bl_idname = "dynamx.export_obj"
    bl_label = "Export OBJ"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.dynamx_pack_path and scene.dynamx_pack_name and 
                scene.dynamx_vehicle_name and context.mode == 'OBJECT')

    def execute(self, context):
        scene = context.scene
        
        # Organize collections
        organize_scene_collections()
        
        # Get all objects except those in Dynamx collection and Lights
        export_objs = []
        dynamx_col = bpy.data.collections.get("Dynamx")
        
        for obj in context.scene.objects:
            # Skip if in Dynamx collection
            if dynamx_col and obj.name in dynamx_col.all_objects:
                continue
            # Skip Lights
            if obj.type == 'LIGHT':
                continue
            export_objs.append(obj)
        
        if not export_objs:
            self.report({'ERROR'}, "No objects to export (main model is empty)")
            return {'CANCELLED'}
        
        # Select only export objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in export_objs:
            obj.select_set(True)
        
        context.view_layer.objects.active = export_objs[0]
        
        # Determine filepath: pack_path/pack_name/assets/dynamxmod/models/obj/<vehicle>/
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name_safe = scene.dynamx_pack_name.strip().replace(" ", "_").lower()
        vehicle_name = scene.dynamx_vehicle_name.strip().replace(" ", "_").lower()
        
        export_dir = os.path.join(pack_path, pack_name_safe, "assets", "dynamxmod", "models", "obj", vehicle_name)
        os.makedirs(export_dir, exist_ok=True)
        
        obj_filepath = os.path.join(export_dir, f"{vehicle_name}.obj")
        mtl_filepath = obj_filepath.replace('.obj', '.mtl')
        mtl_mode = getattr(scene, 'dynamx_mtl_export_mode', 'REPLACE')
        copied_texture_count = 0
        rewritten_texture_refs = 0
        updated_material_paths = 0
        copied_color_texture_count = 0
        inserted_color_map_refs = 0
        copied_light_texture_count = 0
        updated_light_material_count = 0
        exported_color_tokens = 0
        
        # Backup old MTL before export (for ADD mode to merge, for NONE mode to restore)
        old_mtl_backup = None
        if os.path.exists(mtl_filepath):
            old_mtl_backup = mtl_filepath + '.backup'
            try:
                import shutil
                shutil.copy2(mtl_filepath, old_mtl_backup)
            except Exception:
                old_mtl_backup = None
        
        # Export OBJ using wm.obj_export (Blender 3.2+)
        try:
            bpy.ops.wm.obj_export(filepath=obj_filepath, export_selected_objects=True, forward_axis='NEGATIVE_Z', up_axis='Y')
            export_success = True
        except Exception as e:
            self.report({'ERROR'}, f"OBJ Export failed: {str(e)}")
            bpy.ops.object.select_all(action='DESELECT')
            return {'CANCELLED'}
        
        # Handle MTL based on export mode
        if mtl_mode == 'NONE':
            # Restore old MTL and remove mtllib reference from OBJ
            if old_mtl_backup and os.path.exists(old_mtl_backup):
                try:
                    import shutil
                    shutil.copy2(old_mtl_backup, mtl_filepath)
                    os.remove(old_mtl_backup)
                except Exception:
                    pass
            # Remove MTL reference from OBJ
            try:
                with open(obj_filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                with open(obj_filepath, 'w', encoding='utf-8') as f:
                    for line in lines:
                        if not line.startswith('mtllib'):
                            f.write(line)
            except Exception:
                pass
        
        elif mtl_mode == 'ADD':
            # Merge old MTL with new MTL - only add new materials
            if old_mtl_backup and os.path.exists(old_mtl_backup):
                self._merge_mtl_files(old_mtl_backup, mtl_filepath)
                try:
                    os.remove(old_mtl_backup)
                except Exception:
                    pass
            try:
                self._ensure_generated_color_textures(export_objs, mtl_filepath, export_dir)
            except Exception:
                pass
        
        elif mtl_mode == 'REPLACE':
            # Replace entire MTL (default, Blender export already does this)
            try:
                copied_texture_count, rewritten_texture_refs, updated_material_paths = self._localize_export_textures(
                    export_objs,
                    mtl_filepath,
                    export_dir,
                )
            except Exception as e:
                self.report({'WARNING'}, f"Textures were not fully localized: {e}")

            try:
                self._ensure_generated_color_textures(export_objs, mtl_filepath, export_dir)
            except Exception:
                pass

            try:
                mt_entries = self._collect_multitexture_entries(scene)
                mt_material = str(getattr(scene, 'dynamx_multitexture_material', '')).strip()
                if mt_entries and not mt_material:
                    self.report({'WARNING'}, "Multitexture material is empty; set a material to write color map_Kd lines")

                copied_color_texture_count, inserted_color_map_refs = self._apply_multitexture_variants_to_mtl(
                    scene,
                    mtl_filepath,
                    export_dir,
                )
                if copied_color_texture_count > 0 and inserted_color_map_refs == 0 and mt_material:
                    self.report({'WARNING'}, "Multitexture material not found or not set; color map_Kd lines were not written")
            except Exception as e:
                self.report({'WARNING'}, f"Multitexture variants were not fully applied: {e}")

            try:
                copied_light_texture_count, updated_light_material_count = self._apply_light_material_maps(
                    scene,
                    mtl_filepath,
                    export_dir,
                )
            except Exception as e:
                self.report({'WARNING'}, f"Light material maps were not fully applied: {e}")

            try:
                workspace_name = getattr(getattr(context, 'workspace', None), 'name', '')
                tokens = _collect_material_variant_tokens(scene)
                if tokens:
                    ok, msg = _export_material_variants_to_vehicle(scene, workspace_name)
                    if ok:
                        exported_color_tokens = len(tokens)
                    else:
                        self.report({'WARNING'}, f"Failed to export COLORS variants: {msg}")
            except Exception:
                pass

            if old_mtl_backup and os.path.exists(old_mtl_backup):
                try:
                    os.remove(old_mtl_backup)
                except Exception:
                    pass

        wheel_obj_exports = 0
        wheel_obj_skipped = 0
        wheel_export_errors = []
        try:
            wheel_obj_exports, wheel_obj_skipped, wheel_export_errors = self._export_wheel_type_objs(
                context,
                scene,
                export_dir,
                mtl_mode,
            )
        except Exception as e:
            self.report({'WARNING'}, f"Wheel OBJ export failed: {e}")

        if wheel_export_errors:
            preview = '; '.join(wheel_export_errors[:3])
            if len(wheel_export_errors) > 3:
                preview += '; ...'
            self.report({'WARNING'}, f"Some wheel OBJ exports failed: {preview}")

        wheel_summary = f"{wheel_obj_exports} wheel OBJ file(s) exported"
        if wheel_obj_skipped > 0:
            wheel_summary += f", {wheel_obj_skipped} skipped"
        
        bpy.ops.object.select_all(action='DESELECT')
        if mtl_mode == 'REPLACE' and (copied_texture_count > 0 or copied_color_texture_count > 0 or inserted_color_map_refs > 0 or copied_light_texture_count > 0 or updated_light_material_count > 0):
            self.report({'INFO'}, f"Exported model to {obj_filepath} ({copied_texture_count} textures copied, {rewritten_texture_refs} MTL refs updated, {updated_material_paths} Blender image paths changed, {copied_color_texture_count} color textures copied, {inserted_color_map_refs} color map_Kd lines, {copied_light_texture_count} light textures copied, {updated_light_material_count} light materials updated, {exported_color_tokens} COLORS tokens; {wheel_summary})")
        else:
            self.report({'INFO'}, f"Exported model to {obj_filepath} ({wheel_summary})")
        return {'FINISHED'}

    @staticmethod
    def _extract_wheel_def_name_for_export(scene, wheel_col, mesh_objs, fallback_name):
        raw = str(wheel_col.get('WheelDefName', '')).strip()

        if not raw:
            for obj in mesh_objs:
                raw = str(obj.get('WheelDefName', '')).strip()
                if raw:
                    break

        if not raw:
            col_name = str(getattr(wheel_col, 'name', '')).strip().lower()
            m = re.match(r'^wheel\(([a-z])\)$', col_name)
            if m:
                hitbox_idx = ord(m.group(1)) - ord('a') + 1
                hitbox = bpy.data.objects.get(f"wheel_({hitbox_idx})")
                if hitbox is not None:
                    raw = str(hitbox.get('WheelDefName', '')).strip()
                    if not raw:
                        raw = str(hitbox.get('AttachedWheel', '')).strip()

        if not raw:
            raw = str(getattr(scene, 'dynamx_wheel_model', '')).strip()

        return _normalize_wheel_def_name(raw, fallback_name)

    @staticmethod
    def _export_wheel_type_objs(context, scene, export_dir, mtl_mode):
        wheel_model_col = bpy.data.collections.get('wheel_model')
        if wheel_model_col is None:
            return 0, 0, []

        vehicle_name_safe = str(getattr(scene, 'dynamx_vehicle_name', '')).strip().replace(' ', '_').lower()
        if not vehicle_name_safe:
            vehicle_name_safe = 'vehicle'

        exported = 0
        skipped = 0
        errors = []
        used_defs = set()

        wheel_cols = sorted(list(wheel_model_col.children), key=lambda c: str(c.name).lower())
        for col_idx, wheel_col in enumerate(wheel_cols, start=1):
            mesh_objs = [obj for obj in wheel_col.objects if getattr(obj, 'type', '') == 'MESH']
            if not mesh_objs:
                skipped += 1
                continue

            letter = ''
            m = re.match(r'^wheel\(([a-z])\)$', str(getattr(wheel_col, 'name', '')).strip().lower())
            if m:
                letter = m.group(1)
            fallback_name = f"wheel_{vehicle_name_safe}_{letter or col_idx}"

            wheel_def_name = DYNMX_OT_export_obj._extract_wheel_def_name_for_export(
                scene,
                wheel_col,
                mesh_objs,
                fallback_name,
            )

            if wheel_def_name in used_defs:
                skipped += 1
                continue
            used_defs.add(wheel_def_name)

            obj_filepath = os.path.join(export_dir, f"{wheel_def_name}.obj")
            mtl_filepath = obj_filepath.replace('.obj', '.mtl')

            old_mtl_backup = None
            if os.path.exists(mtl_filepath):
                old_mtl_backup = mtl_filepath + '.backup'
                try:
                    shutil.copy2(mtl_filepath, old_mtl_backup)
                except Exception:
                    old_mtl_backup = None

            bpy.ops.object.select_all(action='DESELECT')
            for obj in mesh_objs:
                obj.select_set(True)
            context.view_layer.objects.active = mesh_objs[0]

            try:
                bpy.ops.wm.obj_export(filepath=obj_filepath, export_selected_objects=True, forward_axis='NEGATIVE_Z', up_axis='Y')
            except Exception as exc:
                errors.append(f"{wheel_def_name}: {exc}")
                if old_mtl_backup and os.path.exists(old_mtl_backup):
                    try:
                        os.remove(old_mtl_backup)
                    except Exception:
                        pass
                continue

            if mtl_mode == 'NONE':
                if old_mtl_backup and os.path.exists(old_mtl_backup):
                    try:
                        shutil.copy2(old_mtl_backup, mtl_filepath)
                        os.remove(old_mtl_backup)
                    except Exception:
                        pass
                try:
                    with open(obj_filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    with open(obj_filepath, 'w', encoding='utf-8') as f:
                        for line in lines:
                            if not line.startswith('mtllib'):
                                f.write(line)
                except Exception:
                    pass
            elif mtl_mode == 'ADD':
                if old_mtl_backup and os.path.exists(old_mtl_backup):
                    DYNMX_OT_export_obj._merge_mtl_files(old_mtl_backup, mtl_filepath)
                    try:
                        os.remove(old_mtl_backup)
                    except Exception:
                        pass
            else:
                try:
                    DYNMX_OT_export_obj._localize_export_textures(mesh_objs, mtl_filepath, export_dir)
                except Exception:
                    pass
                try:
                    DYNMX_OT_export_obj._ensure_generated_color_textures(mesh_objs, mtl_filepath, export_dir)
                except Exception:
                    pass
                if old_mtl_backup and os.path.exists(old_mtl_backup):
                    try:
                        os.remove(old_mtl_backup)
                    except Exception:
                        pass

            exported += 1

        return exported, skipped, errors

    @staticmethod
    def _is_supported_image_file(path):
        ext = os.path.splitext(path)[1].lower()
        return ext in {
            '.png', '.jpg', '.jpeg', '.bmp', '.tga', '.tif', '.tiff',
            '.webp', '.exr', '.hdr', '.dds'
        }

    @staticmethod
    def _collect_material_image_paths(export_objs):
        image_paths = []
        seen = set()

        for obj in export_objs:
            for slot in getattr(obj, 'material_slots', []):
                mat = getattr(slot, 'material', None)
                if mat is None or not getattr(mat, 'use_nodes', False) or mat.node_tree is None:
                    continue

                for node in mat.node_tree.nodes:
                    if getattr(node, 'type', '') != 'TEX_IMAGE':
                        continue
                    image = getattr(node, 'image', None)
                    if image is None:
                        continue

                    raw_path = str(getattr(image, 'filepath', '') or '').strip()
                    if not raw_path:
                        continue

                    abs_path = os.path.normpath(bpy.path.abspath(raw_path))
                    if not os.path.isfile(abs_path):
                        continue
                    if not DYNMX_OT_export_obj._is_supported_image_file(abs_path):
                        continue

                    key = os.path.normcase(abs_path)
                    if key in seen:
                        continue

                    seen.add(key)
                    image_paths.append(abs_path)

        return image_paths

    @staticmethod
    def _unique_texture_path(textures_dir, filename):
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(textures_dir, filename)
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(textures_dir, f"{base}_{idx}{ext}")
            idx += 1
        return candidate

    @staticmethod
    def _paths_refer_same_file(path_a, path_b):
        try:
            return os.path.samefile(path_a, path_b)
        except Exception:
            return os.path.normcase(os.path.normpath(path_a)) == os.path.normcase(os.path.normpath(path_b))

    @staticmethod
    def _copy_texture_with_fallback(src, target_dir, filename, max_attempts=6):
        target = os.path.join(target_dir, filename)

        if os.path.exists(target) and DYNMX_OT_export_obj._paths_refer_same_file(src, target):
            return target, False

        last_exc = None
        switched_to_unique = False
        for _ in range(max_attempts):
            try:
                shutil.copy2(src, target)
                return target, True
            except (PermissionError, OSError) as exc:
                # Prefer overwrite semantics. Only switch to unique filenames when target is locked.
                last_exc = exc
                if not switched_to_unique:
                    target = DYNMX_OT_export_obj._unique_texture_path(target_dir, filename)
                    switched_to_unique = True
                else:
                    target = DYNMX_OT_export_obj._unique_texture_path(target_dir, filename)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Failed to copy texture: {src}")

    @staticmethod
    def _copy_textures_to_export_dir(image_paths, export_dir):
        textures_dir = os.path.join(export_dir, 'textures')
        os.makedirs(textures_dir, exist_ok=True)

        source_to_rel = {}
        basename_to_rel = {}
        source_to_abs = {}
        basename_to_abs = {}

        for src in image_paths:
            src_norm = os.path.normcase(os.path.normpath(src))
            if src_norm in source_to_rel:
                continue

            filename = os.path.basename(src)
            try:
                target, _ = DYNMX_OT_export_obj._copy_texture_with_fallback(src, textures_dir, filename)
            except Exception:
                # Continue with other textures instead of aborting the entire localization pass.
                continue

            rel_path = os.path.join('textures', os.path.basename(target)).replace('\\', '/')
            source_to_rel[src_norm] = rel_path
            source_to_abs[src_norm] = os.path.normpath(target)

            base_key = os.path.basename(src).lower()
            if base_key not in basename_to_rel:
                basename_to_rel[base_key] = rel_path
            if base_key not in basename_to_abs:
                basename_to_abs[base_key] = os.path.normpath(target)

        return source_to_rel, basename_to_rel, source_to_abs, basename_to_abs

    @staticmethod
    def _apply_blender_material_texture_paths(export_objs, source_to_abs, basename_to_abs):
        changed = 0
        changed_images = set()

        for obj in export_objs:
            for slot in getattr(obj, 'material_slots', []):
                mat = getattr(slot, 'material', None)
                if mat is None or not getattr(mat, 'use_nodes', False) or mat.node_tree is None:
                    continue

                for node in mat.node_tree.nodes:
                    if getattr(node, 'type', '') != 'TEX_IMAGE':
                        continue
                    image = getattr(node, 'image', None)
                    if image is None:
                        continue

                    current_raw = str(getattr(image, 'filepath', '') or '').strip()
                    if not current_raw:
                        continue

                    current_abs = os.path.normpath(bpy.path.abspath(current_raw))
                    current_key = os.path.normcase(current_abs)
                    new_abs = source_to_abs.get(current_key)

                    if not new_abs:
                        new_abs = basename_to_abs.get(os.path.basename(current_abs).lower())
                    if not new_abs:
                        continue

                    if os.path.normcase(os.path.normpath(new_abs)) == current_key:
                        continue

                    image_id = id(image)
                    if image_id in changed_images:
                        continue

                    try:
                        image.filepath = new_abs
                    except Exception:
                        try:
                            image.filepath_raw = new_abs
                        except Exception:
                            continue

                    try:
                        image.reload()
                    except Exception:
                        pass

                    changed_images.add(image_id)
                    changed += 1

        return changed

    @staticmethod
    def _collect_multitexture_entries(scene):
        entries = []
        seen_paths = set()

        for item in getattr(scene, 'dynamx_material_variants', []):
            variant_name = str(getattr(item, 'name', '')).strip()
            texture_raw = str(getattr(item, 'texture_path', '')).strip()
            if not variant_name or not texture_raw:
                continue

            abs_path = os.path.normpath(bpy.path.abspath(texture_raw))
            if not os.path.isfile(abs_path):
                continue
            if not DYNMX_OT_export_obj._is_supported_image_file(abs_path):
                continue

            token = re.sub(r'\s+', '-', variant_name)
            path_key = os.path.normcase(abs_path)
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            entries.append((token, abs_path))

        return entries

    @staticmethod
    def _collect_selected_material_base_texture(material_name):
        material_name = str(material_name or '').strip()
        if not material_name:
            return None

        mat = bpy.data.materials.get(material_name)
        if mat is None or not getattr(mat, 'use_nodes', False) or mat.node_tree is None:
            return None

        def _resolve_image_path(image):
            if image is None:
                return None
            raw = str(getattr(image, 'filepath', '') or '').strip()
            if not raw:
                return None
            abs_path = os.path.normpath(bpy.path.abspath(raw))
            if not os.path.isfile(abs_path):
                return None
            if not DYNMX_OT_export_obj._is_supported_image_file(abs_path):
                return None
            return abs_path

        # Prefer texture linked to Principled Base Color.
        for node in mat.node_tree.nodes:
            if getattr(node, 'type', '') != 'BSDF_PRINCIPLED':
                continue
            base_input = node.inputs.get('Base Color') if hasattr(node, 'inputs') else None
            if base_input is None or not getattr(base_input, 'is_linked', False):
                continue
            for link in getattr(base_input, 'links', []):
                from_node = getattr(link, 'from_node', None)
                if from_node is None or getattr(from_node, 'type', '') != 'TEX_IMAGE':
                    continue
                resolved = _resolve_image_path(getattr(from_node, 'image', None))
                if resolved:
                    return resolved

        # Fallback: first image texture node in material.
        for node in mat.node_tree.nodes:
            if getattr(node, 'type', '') != 'TEX_IMAGE':
                continue
            resolved = _resolve_image_path(getattr(node, 'image', None))
            if resolved:
                return resolved

        return None

    @staticmethod
    def _copy_multitexture_textures(entries, export_dir):
        colors_dir = os.path.join(export_dir, 'textures', 'colors')
        os.makedirs(colors_dir, exist_ok=True)

        copied = []
        source_to_rel = {}
        for token, src in entries:
            src_key = os.path.normcase(os.path.normpath(src))
            if src_key in source_to_rel:
                copied.append((token, source_to_rel[src_key]))
                continue

            filename = os.path.basename(src)
            try:
                target, _ = DYNMX_OT_export_obj._copy_texture_with_fallback(src, colors_dir, filename)
            except Exception:
                continue

            rel = os.path.join('textures', 'colors', os.path.basename(target)).replace('\\', '/')
            source_to_rel[src_key] = rel
            copied.append((token, rel))

        return copied, source_to_rel

    @staticmethod
    def _copy_single_color_texture(src, export_dir):
        if not src:
            return None

        colors_dir = os.path.join(export_dir, 'textures', 'colors')
        os.makedirs(colors_dir, exist_ok=True)

        filename = os.path.basename(src)
        try:
            target, _ = DYNMX_OT_export_obj._copy_texture_with_fallback(src, colors_dir, filename)
        except Exception:
            return None

        return os.path.join('textures', 'colors', os.path.basename(target)).replace('\\', '/')

    @staticmethod
    def _inject_color_map_kd_lines(mtl_filepath, material_name, variant_entries, base_rel_path=None):
        if not material_name or (not variant_entries and not base_rel_path) or not os.path.exists(mtl_filepath):
            return 0

        try:
            with open(mtl_filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return 0

        material_name = material_name.strip()
        newmtl_indices = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower().startswith('newmtl '):
                newmtl_indices.append(idx)

        target_start = None
        target_end = None
        for i, start in enumerate(newmtl_indices):
            end = newmtl_indices[i + 1] if i + 1 < len(newmtl_indices) else len(lines)
            header = lines[start].strip()
            current_name = header.split(None, 1)[1].strip() if len(header.split(None, 1)) > 1 else ''
            if current_name == material_name:
                target_start = start
                target_end = end
                break

        def _extract_map_kd_path(line):
            stripped = line.strip()
            if not stripped.lower().startswith('map_kd '):
                return None
            try:
                tokens = shlex.split(stripped, posix=False)
            except Exception:
                tokens = stripped.split()
            if len(tokens) < 2:
                return None
            return tokens[-1].strip('"').replace('\\', '/')

        inserted_lines = []
        inserted_count = 0

        if target_start is None:
            append_block = [
                "\n",
                f"newmtl {material_name}\n",
                "Ns 250.000000\n",
                "Ka 1.000000 1.000000 1.000000\n",
                "Ks 0.500000 0.500000 0.500000\n",
                "Ke 0.000000 0.000000 0.000000\n",
                "Ni 1.500000\n",
                "d 1.000000\n",
                "illum 2\n",
            ]

            existing_paths = set()
            if base_rel_path:
                base_norm = base_rel_path.replace('\\', '/')
                if base_norm not in existing_paths:
                    base_token = f'"{base_norm}"' if ' ' in base_norm else base_norm
                    inserted_lines.append(f"map_Kd {base_token}\n")
                    existing_paths.add(base_norm)

            for token, rel_path in variant_entries:
                rel_norm = rel_path.replace('\\', '/')
                if rel_norm in existing_paths:
                    continue
                path_token = f'"{rel_norm}"' if ' ' in rel_norm else rel_norm
                inserted_lines.append(f"map_Kd {path_token} {token}\n")
                existing_paths.add(rel_norm)
                inserted_count += 1

            append_block.extend(inserted_lines)
            if append_block and append_block[-1].strip():
                append_block.append('\n')
            lines.extend(append_block)
        else:
            block = lines[target_start:target_end]
            filtered = []
            existing_paths = set()
            for line in block:
                stripped = line.strip().lower()
                if stripped.startswith('map_kd '):
                    continue
                filtered.append(line)

                existing = _extract_map_kd_path(line)
                if existing:
                    existing_paths.add(existing)

            if base_rel_path:
                base_norm = base_rel_path.replace('\\', '/')
                if base_norm not in existing_paths:
                    base_token = f'"{base_norm}"' if ' ' in base_norm else base_norm
                    inserted_lines.append(f"map_Kd {base_token}\n")
                    existing_paths.add(base_norm)

            for token, rel_path in variant_entries:
                rel_norm = rel_path.replace('\\', '/')
                if rel_norm in existing_paths:
                    continue
                path_token = f'"{rel_norm}"' if ' ' in rel_norm else rel_norm
                inserted_lines.append(f"map_Kd {path_token} {token}\n")
                existing_paths.add(rel_norm)
                inserted_count += 1

            new_block = filtered + inserted_lines
            new_block = DYNMX_OT_export_obj._move_map_kd_to_end(new_block)
            new_block = DYNMX_OT_export_obj._force_glass_mtl_d_value(new_block, material_name)
            if new_block and new_block[-1].strip():
                new_block.append('\n')
            lines = lines[:target_start] + new_block + lines[target_end:]

        try:
            with open(mtl_filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception:
            return 0

        return inserted_count

    @staticmethod
    def _apply_multitexture_variants_to_mtl(scene, mtl_filepath, export_dir):
        material_name = str(getattr(scene, 'dynamx_multitexture_material', '')).strip()
        if not material_name:
            return 0, 0

        entries = DYNMX_OT_export_obj._collect_multitexture_entries(scene)
        base_texture = DYNMX_OT_export_obj._collect_selected_material_base_texture(material_name)
        if not entries and not base_texture:
            return 0, 0

        copied_count = 0
        copied = []
        source_to_rel = {}
        if entries:
            copied, source_to_rel = DYNMX_OT_export_obj._copy_multitexture_textures(entries, export_dir)
            copied_count += len(copied)

        base_rel = None
        if base_texture:
            base_key = os.path.normcase(os.path.normpath(base_texture))
            base_rel = source_to_rel.get(base_key)
            if not base_rel:
                base_rel = DYNMX_OT_export_obj._copy_single_color_texture(base_texture, export_dir)
                if base_rel:
                    copied_count += 1

        inserted = DYNMX_OT_export_obj._inject_color_map_kd_lines(mtl_filepath, material_name, copied, base_rel_path=base_rel)
        return copied_count, inserted

    @staticmethod
    def _resolve_configured_image_path(raw_path):
        raw = str(raw_path or '').strip()
        if not raw:
            return None

        abs_path = os.path.normpath(bpy.path.abspath(raw))
        if not os.path.isfile(abs_path):
            return None
        if not DYNMX_OT_export_obj._is_supported_image_file(abs_path):
            return None
        return abs_path

    @staticmethod
    def _collect_light_material_configs(scene):
        configs = []

        def _add_config(material_name, off_raw, on_raw, on_token, subdir):
            mat = str(material_name or '').strip()
            off_abs = DYNMX_OT_export_obj._resolve_configured_image_path(off_raw)
            on_abs = DYNMX_OT_export_obj._resolve_configured_image_path(on_raw)
            token = re.sub(r'\s+', '_', str(on_token or '').strip())
            if not token:
                token = 'on'

            if not mat or not off_abs or not on_abs:
                return

            configs.append({
                'material': mat,
                'off_abs': off_abs,
                'on_abs': on_abs,
                'token': token,
                'subdir': subdir,
            })

        combine = bool(getattr(scene, 'dynamx_combine_main_lights_materials', True))
        if combine:
            _add_config(
                getattr(scene, 'dynamx_main_lights_material', ''),
                getattr(scene, 'dynamx_main_lights_texture_off', ''),
                getattr(scene, 'dynamx_main_lights_texture_on', ''),
                'on',
                ('textures', 'lights'),
            )
            glass_mat = str(getattr(scene, 'dynamx_main_lights_glass_material', '') or '').strip()
            if glass_mat:
                glass_off = getattr(scene, 'dynamx_main_lights_texture_off', '')
                glass_on = getattr(scene, 'dynamx_main_lights_texture_on', '')
                _add_config(glass_mat, glass_off, glass_on, 'on', ('textures', 'lights'))
        else:
            per_light = (
                ('dynamx_headlight_material', 'dynamx_headlight_texture_off', 'dynamx_headlight_texture_on'),
                ('dynamx_brakelights_material', 'dynamx_brakelights_texture_off', 'dynamx_brakelights_texture_on'),
                ('dynamx_reverselights_material', 'dynamx_reverselights_texture_off', 'dynamx_reverselights_texture_on'),
                ('dynamx_blinker_left_material', 'dynamx_blinker_left_texture_off', 'dynamx_blinker_left_texture_on'),
                ('dynamx_blinker_right_material', 'dynamx_blinker_right_texture_off', 'dynamx_blinker_right_texture_on'),
            )
            for mat_prop, off_prop, on_prop in per_light:
                _add_config(
                    getattr(scene, mat_prop, ''),
                    getattr(scene, off_prop, ''),
                    getattr(scene, on_prop, ''),
                    'on',
                    ('textures', 'lights'),
                )

        _add_config(
            getattr(scene, 'dynamx_sirenlight_material', ''),
            getattr(scene, 'dynamx_sirenlight_texture_off', ''),
            getattr(scene, 'dynamx_sirenlight_texture_on', ''),
            getattr(scene, 'dynamx_sirenlight_on_token', 'lightbar_on'),
            ('textures', 'lights'),
        )

        deduped = []
        seen_mats = set()
        for cfg in configs:
            key = cfg['material']
            if key in seen_mats:
                continue
            seen_mats.add(key)
            deduped.append(cfg)
        return deduped

    @staticmethod
    def _copy_light_texture(src_abs, export_dir, subdir_parts, source_to_rel):
        src_key = os.path.normcase(os.path.normpath(src_abs))
        if src_key in source_to_rel:
            return source_to_rel[src_key], False

        target_dir = os.path.join(export_dir, *subdir_parts)
        os.makedirs(target_dir, exist_ok=True)

        filename = os.path.basename(src_abs)
        try:
            target, copied_file = DYNMX_OT_export_obj._copy_texture_with_fallback(src_abs, target_dir, filename)
        except Exception:
            return None, False

        rel_path = os.path.join(*subdir_parts, os.path.basename(target)).replace('\\', '/')
        source_to_rel[src_key] = rel_path
        return rel_path, copied_file

    @staticmethod
    def _build_light_mtl_block(material_name, off_rel_path, on_rel_path, on_token):
        off_token = f'"{off_rel_path}"' if ' ' in off_rel_path else off_rel_path
        on_token_path = f'"{on_rel_path}"' if ' ' in on_rel_path else on_rel_path
        d_value = 'd 0.500000\n' if 'glass' in str(material_name).lower() else 'd 1.000000\n'
        return [
            f"newmtl {material_name}\n",
            "Ns 250.000000\n",
            "Ka 1.000000 1.000000 1.000000\n",
            "Ks 0.500000 0.500000 0.500000\n",
            "Ke 0.000000 0.000000 0.000000\n",
            "Ni 1.450000\n",
            d_value,
            "illum 2\n",
            f"map_Kd {off_token}\n",
            f"map_Kd {on_token_path} {on_token}\n",
            "\n",
        ]

    @staticmethod
    def _apply_light_material_maps(scene, mtl_filepath, export_dir):
        if not os.path.exists(mtl_filepath):
            return 0, 0

        configs = DYNMX_OT_export_obj._collect_light_material_configs(scene)
        if not configs:
            return 0, 0

        source_to_rel = {}
        copied_count = 0
        material_blocks = {}
        for cfg in configs:
            off_rel, copied_off = DYNMX_OT_export_obj._copy_light_texture(
                cfg['off_abs'],
                export_dir,
                cfg['subdir'],
                source_to_rel,
            )
            on_rel, copied_on = DYNMX_OT_export_obj._copy_light_texture(
                cfg['on_abs'],
                export_dir,
                cfg['subdir'],
                source_to_rel,
            )
            if not off_rel or not on_rel:
                continue
            if copied_off:
                copied_count += 1
            if copied_on:
                copied_count += 1

            material_blocks[cfg['material']] = DYNMX_OT_export_obj._build_light_mtl_block(
                cfg['material'],
                off_rel,
                on_rel,
                cfg['token'],
            )

        try:
            with open(mtl_filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return copied_count, 0

        newmtl_indices = []
        for idx, line in enumerate(lines):
            if line.strip().lower().startswith('newmtl '):
                newmtl_indices.append(idx)

        ranges = []
        for idx, start in enumerate(newmtl_indices):
            end = newmtl_indices[idx + 1] if idx + 1 < len(newmtl_indices) else len(lines)
            header = lines[start].strip()
            parts = header.split(None, 1)
            mat_name = parts[1].strip() if len(parts) > 1 else ''
            ranges.append((start, end, mat_name))

        output = []
        updated_material_count = 0
        pending = dict(material_blocks)

        if ranges:
            output.extend(lines[:ranges[0][0]])
            for start, end, mat_name in ranges:
                if mat_name in pending:
                    output.extend(pending.pop(mat_name))
                    updated_material_count += 1
                else:
                    output.extend(lines[start:end])
        else:
            output.extend(lines)

        if pending:
            if output and output[-1].strip():
                output.append('\n')
            for mat_name, block in pending.items():
                output.extend(block)
                updated_material_count += 1

        try:
            with open(mtl_filepath, 'w', encoding='utf-8') as f:
                f.writelines(output)
        except Exception:
            return copied_count, 0

        return copied_count, updated_material_count

    @staticmethod
    def _rewrite_mtl_texture_paths(mtl_filepath, source_to_rel, basename_to_rel):
        if not os.path.exists(mtl_filepath):
            return 0

        try:
            with open(mtl_filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return 0

        texture_directives = {
            'map_ka', 'map_kd', 'map_ks', 'map_ke', 'map_ns', 'map_d',
            'map_bump', 'bump', 'disp', 'decal', 'refl', 'norm'
        }
        mtl_dir = os.path.dirname(mtl_filepath)
        changed = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            first = stripped.split(None, 1)
            if len(first) < 2:
                continue

            if first[0].lower() not in texture_directives:
                continue

            try:
                tokens = shlex.split(stripped, posix=False)
            except Exception:
                tokens = stripped.split()

            if len(tokens) < 2:
                continue

            old_path_token = tokens[-1].strip('"')
            resolved = old_path_token
            if not os.path.isabs(resolved):
                resolved = os.path.normpath(os.path.join(mtl_dir, resolved))

            resolved_key = os.path.normcase(os.path.normpath(resolved))
            new_rel = source_to_rel.get(resolved_key)
            if not new_rel:
                new_rel = basename_to_rel.get(os.path.basename(old_path_token).lower())
            if not new_rel:
                continue

            new_token = f'"{new_rel}"' if ' ' in new_rel else new_rel
            if tokens[-1] == new_token:
                continue

            tokens[-1] = new_token
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = indent + ' '.join(tokens) + '\n'
            changed += 1

        if changed <= 0:
            return 0

        try:
            with open(mtl_filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception:
            return 0

        return changed

    @staticmethod
    @staticmethod
    def _sanitize_material_filename(name):
        safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(name or 'material')).strip('_')
        safe = safe or 'material'
        return safe

    @staticmethod
    def _material_has_real_texture(material):
        if material is None:
            return False
        if not getattr(material, 'use_nodes', False) or material.node_tree is None:
            return False
        for node in material.node_tree.nodes:
            if getattr(node, 'type', '') != 'TEX_IMAGE':
                continue
            image = getattr(node, 'image', None)
            if image is not None:
                return True
        return False

    @staticmethod
    def _material_has_base_color_image(material):
        if material is None or not getattr(material, 'use_nodes', False) or material.node_tree is None:
            return False

        for node in material.node_tree.nodes:
            if getattr(node, 'type', '') != 'BSDF_PRINCIPLED':
                continue
            base_input = node.inputs.get('Base Color') if hasattr(node, 'inputs') else None
            if base_input is None:
                continue
            for link in getattr(base_input, 'links', []):
                from_node = getattr(link, 'from_node', None)
                if from_node is not None and getattr(from_node, 'type', '') == 'TEX_IMAGE':
                    return True
        return False

    @staticmethod
    def _force_material_base_color_images(export_objs):
        changed = 0
        for obj in export_objs:
            for slot in getattr(obj, 'material_slots', []):
                mat = getattr(slot, 'material', None)
                if mat is None:
                    continue
                if not getattr(mat, 'use_nodes', False):
                    mat.use_nodes = True
                if mat.node_tree is None:
                    continue

                principal = None
                for node in mat.node_tree.nodes:
                    if getattr(node, 'type', '') == 'BSDF_PRINCIPLED':
                        principal = node
                        break
                if principal is None:
                    principal = mat.node_tree.nodes.new(type='BSDF_PRINCIPLED')
                    principal.location = (300, 0)

                base_input = principal.inputs.get('Base Color') if hasattr(principal, 'inputs') else None
                if base_input is None:
                    continue

                for link in list(getattr(base_input, 'links', [])):
                    try:
                        mat.node_tree.links.remove(link)
                    except Exception:
                        pass

                tex_nodes = [
                    node for node in mat.node_tree.nodes
                    if getattr(node, 'type', '') == 'TEX_IMAGE' and getattr(node, 'image', None) is not None
                ]
                if not tex_nodes:
                    continue

                for tex_node in tex_nodes:
                    try:
                        mat.node_tree.links.new(tex_node.outputs['Color'], base_input)
                        changed += 1
                        break
                    except Exception:
                        continue

        return changed

    @staticmethod
    def _ensure_base_color_image_link(material, preferred_image=None):
        if material is None:
            return False

        if not getattr(material, 'use_nodes', False):
            material.use_nodes = True
        if material.node_tree is None:
            return False

        principal = None
        for node in material.node_tree.nodes:
            if getattr(node, 'type', '') == 'BSDF_PRINCIPLED':
                principal = node
                break

        if principal is None:
            principal = material.node_tree.nodes.new(type='BSDF_PRINCIPLED')
            principal.location = (300, 0)

        color_input = principal.inputs.get('Base Color') if hasattr(principal, 'inputs') else None
        if color_input is None:
            return False

        for link in list(getattr(color_input, 'links', [])):
            try:
                material.node_tree.links.remove(link)
            except Exception:
                pass

        candidate = None
        for node in material.node_tree.nodes:
            if getattr(node, 'type', '') != 'TEX_IMAGE':
                continue
            if preferred_image is not None and getattr(node, 'image', None) == preferred_image:
                candidate = node
                break
            if candidate is None and getattr(node, 'image', None) is not None:
                candidate = node

        if candidate is None:
            candidate = material.node_tree.nodes.new(type='TEX_IMAGE')
            candidate.location = (0, 200)

        if preferred_image is not None:
            try:
                candidate.image = preferred_image
            except Exception:
                pass

        if getattr(candidate, 'image', None) is None:
            return False

        try:
            candidate.image_user.use_generated = False
        except Exception:
            pass

        try:
            material.node_tree.links.new(candidate.outputs['Color'], color_input)
            return True
        except Exception:
            return False

    @staticmethod
    def _material_color_value(material):
        if material is None:
            return None

        if getattr(material, 'use_nodes', False) and material.node_tree is not None:
            for node in material.node_tree.nodes:
                if getattr(node, 'type', '') != 'BSDF_PRINCIPLED':
                    continue
                base_input = node.inputs.get('Base Color') if hasattr(node, 'inputs') else None
                if base_input is None:
                    continue
                value = getattr(base_input, 'default_value', None)
                if value is None:
                    continue
                rgba = tuple(float(v) for v in value[:4])
                if len(rgba) >= 3:
                    return rgba[:3]

        color = getattr(material, 'diffuse_color', None)
        if color is not None:
            try:
                rgba = tuple(float(v) for v in color[:4])
            except Exception:
                try:
                    rgba = tuple(float(v) for v in color)
                except Exception:
                    rgba = (1.0, 1.0, 1.0)
            if len(rgba) >= 3:
                return rgba[:3]

        return None

    @staticmethod
    def _write_1x1_png(path, rgb):
        r, g, b = rgb
        red = max(0, min(255, int(round(float(r) * 255.0))))
        green = max(0, min(255, int(round(float(g) * 255.0))))
        blue = max(0, min(255, int(round(float(b) * 255.0))))

        def chunk(tag, data):
            return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data) & 0xFFFFFFFF)

        raw = b'\x00' + bytes((red, green, blue))
        png = b'\x89PNG\r\n\x1a\n'
        png += chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(raw, 9))
        png += chunk(b'IEND', b'')

        with open(path, 'wb') as f:
            f.write(png)

        return path

    @staticmethod
    def _assign_generated_color_image_to_material(material, image_path):
        if material is None:
            return

        if not getattr(material, 'use_nodes', False):
            material.use_nodes = True
        if material.node_tree is None:
            material.use_nodes = True

        image_name = os.path.basename(image_path)
        image = bpy.data.images.get(image_name)
        if image is None:
            image = bpy.data.images.new(name=image_name, width=1, height=1, alpha=False, float_buffer=False)

        try:
            image.filepath = image_path
            image.source = 'FILE'
            image.reload()
        except Exception:
            pass

        principal = None
        for node in material.node_tree.nodes:
            if getattr(node, 'type', '') == 'BSDF_PRINCIPLED':
                principal = node
                break

        if principal is None:
            principal = material.node_tree.nodes.new(type='BSDF_PRINCIPLED')
            principal.location = (300, 0)

        color_input = principal.inputs.get('Base Color') if hasattr(principal, 'inputs') else None
        if color_input is None:
            return

        tex_node = None
        for node in material.node_tree.nodes:
            if getattr(node, 'type', '') == 'TEX_IMAGE' and getattr(node, 'image', None) == image:
                tex_node = node
                break

        if tex_node is None:
            tex_node = material.node_tree.nodes.new(type='TEX_IMAGE')
            tex_node.name = f"{material.name}_generated_color"
            tex_node.label = 'Generated Color'

        tex_node.image = image
        tex_node.image_user.use_generated = False
        tex_node.location = (0, 200)

        for link in list(getattr(color_input, 'links', [])):
            if getattr(link, 'from_node', None) is None or getattr(link.from_node, 'type', '') != 'TEX_IMAGE':
                material.node_tree.links.remove(link)

        if not any(link.to_node == principal and getattr(link.from_node, 'type', '') == 'TEX_IMAGE' and link.from_node == tex_node for link in material.node_tree.links):
            try:
                material.node_tree.links.new(tex_node.outputs['Color'], color_input)
            except Exception:
                pass

        if hasattr(tex_node, 'select'):
            tex_node.select = True
        material.node_tree.nodes.active = tex_node

    @staticmethod
    def _move_map_kd_to_end(block):
        kept = []
        map_lines = []
        for line in block:
            stripped = line.strip()
            if stripped.lower().startswith('map_kd '):
                map_lines.append(line.rstrip('\n') + '\n')
                continue
            if stripped:
                kept.append(line.rstrip('\n') + '\n')

        if map_lines:
            kept.extend(map_lines)
            if kept and kept[-1].strip():
                kept.append('\n')
        return kept

    @staticmethod
    def _force_mtl_d_value_to_one(block):
        lines = list(block)
        fixed = []
        seen_d = False
        for line in lines:
            stripped = line.strip().lower()
            if stripped.startswith('d '):
                if not seen_d:
                    fixed.append('d 1.000000\n')
                    seen_d = True
                continue
            fixed.append(line)

        if not seen_d:
            inserted = False
            for idx, line in enumerate(fixed):
                if line.strip().lower().startswith('illum '):
                    fixed.insert(idx, 'd 1.000000\n')
                    inserted = True
                    break
            if not inserted:
                fixed.append('d 1.000000\n')
        return fixed

    @staticmethod
    def _force_glass_mtl_d_value(block, material_name):
        if not material_name or 'glass' not in material_name.lower():
            return list(block)

        lines = list(block)
        fixed = []
        seen_d = False
        for line in lines:
            stripped = line.strip().lower()
            if stripped.startswith('d '):
                if not seen_d:
                    fixed.append('d 0.500000\n')
                    seen_d = True
                continue
            fixed.append(line)

        if not seen_d:
            inserted = False
            for idx, line in enumerate(fixed):
                if line.strip().lower().startswith('illum '):
                    fixed.insert(idx, 'd 0.500000\n')
                    inserted = True
                    break
            if not inserted:
                fixed.append('d 0.500000\n')
        return fixed

    @staticmethod
    def _inject_generated_color_map(mtl_filepath, material_name, rel_path, rgb):
        if not material_name or not rel_path or not os.path.exists(mtl_filepath):
            return 0

        try:
            with open(mtl_filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return 0

        target_name = material_name.strip()
        ranges = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower().startswith('newmtl '):
                ranges.append(idx)

        match_start = None
        match_end = None
        for i, start in enumerate(ranges):
            end = ranges[i + 1] if i + 1 < len(ranges) else len(lines)
            header = lines[start].strip()
            current_name = header.split(None, 1)[1].strip() if len(header.split(None, 1)) > 1 else ''
            if current_name == target_name:
                match_start = start
                match_end = end
                break

        rel_token = f'"{rel_path}"' if ' ' in rel_path else rel_path
        kd_line = f"Kd {float(rgb[0]):.6f} {float(rgb[1]):.6f} {float(rgb[2]):.6f}\n"

        if match_start is None:
            block = [
                '\n',
                f'newmtl {target_name}\n',
                "Ns 250.000000\n",
                "Ka 1.000000 1.000000 1.000000\n",
                kd_line,
                "Ks 0.500000 0.500000 0.500000\n",
                "Ke 0.000000 0.000000 0.000000\n",
                "Ni 1.500000\n",
                "d 1.000000\n",
                "illum 2\n",
                f'map_Kd {rel_token}\n',
            ]
            lines.extend(block)
        else:
            block = lines[match_start:match_end]
            new_block = []
            inserted_kd = False
            for line in block:
                stripped = line.strip().lower()
                if stripped.startswith('kd '):
                    new_block.append(kd_line)
                    inserted_kd = True
                    continue
                if stripped.startswith('map_kd '):
                    continue
                new_block.append(line)

            if not inserted_kd:
                if new_block and not new_block[0].strip().lower().startswith('newmtl '):
                    new_block.insert(0, kd_line)
                else:
                    new_block.insert(1, kd_line)

            new_block = DYNMX_OT_export_obj._move_map_kd_to_end(new_block)
            new_block.append(f'map_Kd {rel_token}\n')
            new_block = DYNMX_OT_export_obj._move_map_kd_to_end(new_block)
            new_block = DYNMX_OT_export_obj._force_glass_mtl_d_value(new_block, target_name)
            if new_block and new_block[-1].strip():
                new_block.append('\n')

            lines = lines[:match_start] + new_block + lines[match_end:]

        try:
            with open(mtl_filepath, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception:
            return 0

        return 1

    @staticmethod
    def _prune_missing_generated_color_materials(mtl_filepath, export_objs):
        if not os.path.exists(mtl_filepath):
            return 0

        active_materials = set()
        for obj in export_objs:
            for slot in getattr(obj, 'material_slots', []):
                mat = getattr(slot, 'material', None)
                if mat is not None:
                    active_materials.add(mat.name)

        try:
            with open(mtl_filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return 0

        newmtl_indices = []
        for idx, line in enumerate(lines):
            if line.strip().lower().startswith('newmtl '):
                newmtl_indices.append(idx)

        if not newmtl_indices:
            return 0

        kept = []
        removed = 0
        for idx, start in enumerate(newmtl_indices):
            end = newmtl_indices[idx + 1] if idx + 1 < len(newmtl_indices) else len(lines)
            block = lines[start:end]
            header = block[0].strip()
            mat_name = header.split(None, 1)[1].strip() if len(header.split(None, 1)) > 1 else ''
            has_generated_color_map = any(
                line.strip().lower().startswith('map_kd ') and 'textures/colors/' in line.lower()
                for line in block
            )
            if has_generated_color_map and mat_name not in active_materials:
                removed += 1
                continue
            kept.extend(block)

        if removed <= 0:
            return 0

        try:
            with open(mtl_filepath, 'w', encoding='utf-8') as f:
                f.writelines(kept)
        except Exception:
            return 0

        return removed

    @staticmethod
    def _ensure_generated_color_textures(export_objs, mtl_filepath, export_dir):
        generated = 0
        if not export_objs:
            return generated

        DYNMX_OT_export_obj._prune_missing_generated_color_materials(mtl_filepath, export_objs)

        colors_dir = os.path.join(export_dir, 'textures', 'colors')
        os.makedirs(colors_dir, exist_ok=True)
        seen_materials = set()

        for obj in export_objs:
            for slot in getattr(obj, 'material_slots', []):
                mat = getattr(slot, 'material', None)
                if mat is None:
                    continue
                if mat.name in seen_materials:
                    continue

                color = DYNMX_OT_export_obj._material_color_value(mat)
                if color is None:
                    seen_materials.add(mat.name)
                    continue

                if DYNMX_OT_export_obj._material_has_real_texture(mat):
                    seen_materials.add(mat.name)
                    continue

                file_name = f"{DYNMX_OT_export_obj._sanitize_material_filename(mat.name)}_color.png"
                file_path = os.path.join(colors_dir, file_name)
                DYNMX_OT_export_obj._write_1x1_png(file_path, color)

                rel_path = os.path.join('textures', 'colors', os.path.basename(file_path)).replace('\\', '/')
                generated += DYNMX_OT_export_obj._inject_generated_color_map(mtl_filepath, mat.name, rel_path, color)
                seen_materials.add(mat.name)

        return generated

    @staticmethod
    def _localize_export_textures(export_objs, mtl_filepath, export_dir):
        image_paths = DYNMX_OT_export_obj._collect_material_image_paths(export_objs)
        if not image_paths:
            return 0, 0, 0

        source_to_rel, basename_to_rel, source_to_abs, basename_to_abs = DYNMX_OT_export_obj._copy_textures_to_export_dir(image_paths, export_dir)
        rewritten = DYNMX_OT_export_obj._rewrite_mtl_texture_paths(mtl_filepath, source_to_rel, basename_to_rel)
        changed_paths = DYNMX_OT_export_obj._apply_blender_material_texture_paths(export_objs, source_to_abs, basename_to_abs)
        return len(source_to_rel), rewritten, changed_paths
    
    @staticmethod
    def _parse_mtl_materials(mtl_filepath):
        """Parse MTL file and extract material names and their definitions"""
        materials = {}
        header = ""
        try:
            with open(mtl_filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by 'newmtl' to get each material block
            blocks = content.split('newmtl ')
            header = blocks[0]  # Everything before first material
            
            for block in blocks[1:]:
                lines = block.split('\n')
                if not lines[0]:
                    continue
                mat_name = lines[0].strip()
                # Clean up the material content: normalize whitespace
                mat_content = 'newmtl ' + block.rstrip() + '\n'
                materials[mat_name] = mat_content
        except Exception:
            pass
        
        return materials, header
    
    @staticmethod
    def _merge_mtl_files(old_mtl_path, new_mtl_path):
        """Merge old MTL with new MTL - keep existing materials, add new ones"""
        try:
            # Parse both MTL files
            old_materials, old_header = DYNMX_OT_export_obj._parse_mtl_materials(old_mtl_path)
            new_materials, new_header = DYNMX_OT_export_obj._parse_mtl_materials(new_mtl_path)
            
            # Merge: start with old materials (to keep them intact)
            merged_materials = dict(old_materials)
            
            # Add new materials that don't exist in old
            for mat_name, mat_content in new_materials.items():
                if mat_name not in merged_materials:
                    merged_materials[mat_name] = mat_content
            
            # Write merged MTL to new file with proper formatting
            with open(new_mtl_path, 'w', encoding='utf-8') as f:
                # Keep the new header from export
                if new_header:
                    f.write(new_header)
                # Write all materials with exactly one blank line between them
                mat_list = list(merged_materials.values())
                for i, mat_content in enumerate(mat_list):
                    f.write(mat_content)
                    # Add blank line between materials (but not after the last one)
                    if i < len(mat_list) - 1:
                        f.write('\n')
        except Exception:
            pass


class DYNMX_OT_export_mtl_only(bpy.types.Operator):
    """Export only MTL file (apply materials without OBJ export)"""
    bl_idname = "dynamx.export_mtl_only"
    bl_label = "Export MTL Only"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        mtl_mode = getattr(scene, 'dynamx_mtl_export_mode', 'REPLACE')
        return (scene.dynamx_pack_path and scene.dynamx_pack_name and 
                scene.dynamx_vehicle_name and context.mode == 'OBJECT' and
                mtl_mode in ('ADD', 'REPLACE'))

    def execute(self, context):
        scene = context.scene
        
        # Get export objects (same as export_obj)
        export_objs = []
        dynamx_col = bpy.data.collections.get("Dynamx")
        
        for obj in context.scene.objects:
            if dynamx_col and obj.name in dynamx_col.all_objects:
                continue
            if obj.type == 'LIGHT':
                continue
            export_objs.append(obj)
        
        if not export_objs:
            self.report({'ERROR'}, "No objects to export materials for")
            return {'CANCELLED'}
        
        # Select export objects temporarily to export materials
        bpy.ops.object.select_all(action='DESELECT')
        for obj in export_objs:
            obj.select_set(True)
        context.view_layer.objects.active = export_objs[0]
        
        # Determine filepath
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name_safe = scene.dynamx_pack_name.strip().replace(" ", "_").lower()
        vehicle_name = scene.dynamx_vehicle_name.strip().replace(" ", "_").lower()
        
        export_dir = os.path.join(pack_path, pack_name_safe, "assets", "dynamxmod", "models", "obj", vehicle_name)
        os.makedirs(export_dir, exist_ok=True)
        
        obj_filepath = os.path.join(export_dir, f"{vehicle_name}.obj")
        mtl_filepath = obj_filepath.replace('.obj', '.mtl')
        mtl_mode = getattr(scene, 'dynamx_mtl_export_mode', 'REPLACE')
        
        # Backup old MTL if ADD mode
        old_mtl_backup = None
        if mtl_mode == 'ADD' and os.path.exists(mtl_filepath):
            old_mtl_backup = mtl_filepath + '.backup'
            try:
                import shutil
                shutil.copy2(mtl_filepath, old_mtl_backup)
            except Exception:
                pass
        
        # Export only materials (temporary OBJ export, then keep only MTL)
        try:
            bpy.ops.wm.obj_export(filepath=obj_filepath, export_selected_objects=True, forward_axis='NEGATIVE_Z', up_axis='Y')
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export materials: {str(e)}")
            bpy.ops.object.select_all(action='DESELECT')
            return {'CANCELLED'}

        try:
            DYNMX_OT_export_obj._localize_export_textures(export_objs, mtl_filepath, export_dir)
        except Exception:
            pass
        try:
            DYNMX_OT_export_obj._ensure_generated_color_textures(export_objs, mtl_filepath, export_dir)
        except Exception:
            pass

        # Handle MTL merging
        if mtl_mode == 'ADD' and old_mtl_backup and os.path.exists(old_mtl_backup):
            DYNMX_OT_export_obj._merge_mtl_files(old_mtl_backup, mtl_filepath)
            try:
                os.remove(old_mtl_backup)
            except Exception:
                pass

        # Keep the OBJ file in place; only update the MTL from it.
        bpy.ops.object.select_all(action='DESELECT')
        self.report({'INFO'}, f"Exported MTL to {mtl_filepath} (OBJ kept in place)")
        return {'FINISHED'}


classes = (
    DYNMX_PG_material_variant,
    DYNMX_OT_set_car,
    DYNMX_OT_generate_hitboxes,
    DYNMX_OT_select_vehicle,
    DYNMX_OT_set_steering_wheel,
    DYNMX_OT_apply_steering_wheel_rotation,
    DYNMX_OT_export_steering_wheel,
    DYNMX_OT_set_chassis,
    DYNMX_OT_save_wheel,
    DYNMX_OT_set_wheel,
    DYNMX_OT_export_wheels,
    DYNMX_OT_duplicate_wheel,
    DYNMX_OT_delete_wheel,
    DYNMX_OT_update_scaled_parts,
    DYNMX_OT_set_trailer,
    DYNMX_OT_select_trailer,
    DYNMX_OT_create_trailer_attach,
    DYNMX_OT_save_trailer_attach,
    DYNMX_OT_add_material_variant,
    DYNMX_OT_remove_material_variant,
    DYNMX_OT_export_material_variants,
    DYNMX_OT_organize_collections,
    DYNMX_OT_export_obj,
    DYNMX_OT_export_mtl_only,
)


def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except Exception:
            pass


def unregister():
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
    

