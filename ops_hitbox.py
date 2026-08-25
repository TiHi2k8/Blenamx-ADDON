"""Hitbox-related operators"""
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import os
import re
from .ops_vehicle import organize_scene_collections


def create_bounding_box(vertices, margin=0.0):
    if not vertices:
        return None

    min_coord = Vector((
        min(v.x for v in vertices) - margin,
        min(v.y for v in vertices) - margin,
        min(v.z for v in vertices) - margin
    ))
    max_coord = Vector((
        max(v.x for v in vertices) + margin,
        max(v.y for v in vertices) + margin,
        max(v.z for v in vertices) + margin
    ))

    center = (min_coord + max_coord) / 2
    size = (max_coord - min_coord) / 2

    return (center, size)


def _bounds_volume(half_extent):
    return (
        max(float(half_extent.x), 1e-9) *
        max(float(half_extent.y), 1e-9) *
        max(float(half_extent.z), 1e-9)
    )

def generate_smart_hitboxes(obj, mesh, max_boxes):
    """Generate up to max_boxes hitbox bounds as (center, half-extent)."""
    if max_boxes < 1:
        return []

    matrix = obj.matrix_world
    vertices = [matrix @ v.co for v in mesh.vertices]
    if not vertices:
        return []

    initial_box = create_bounding_box(vertices, margin=0.0)
    if initial_box is None:
        return []

    current_boxes = [(vertices, initial_box)]
    min_vertices_per_box = max(8, min(64, len(vertices) // max(2, max_boxes * 2)))
    split_quantiles = (0.2, 0.35, 0.5, 0.65, 0.8)

    iterations = 0
    max_iterations = max_boxes * 20

    while len(current_boxes) < max_boxes and iterations < max_iterations:
        iterations += 1

        target_index = None
        target_volume = -1.0
        for i, (box_verts, (_, s)) in enumerate(current_boxes):
            if len(box_verts) < (min_vertices_per_box * 2):
                continue
            vol = _bounds_volume(s)
            if vol > target_volume:
                target_volume = vol
                target_index = i

        if target_index is None:
            break

        box_verts, box_bounds = current_boxes[target_index]
        if not box_verts or len(box_verts) < (min_vertices_per_box * 2):
            break

        _, size = box_bounds
        source_volume = _bounds_volume(size)
        best = None

        for axis in (0, 1, 2):
            if size[axis] <= 1e-6:
                continue

            axis_values = sorted(v[axis] for v in box_verts)
            n = len(axis_values)
            if n < (min_vertices_per_box * 2):
                continue

            for q in split_quantiles:
                idx = int((n - 1) * q)
                split_pos = axis_values[idx]

                left_verts = [v for v in box_verts if v[axis] <= split_pos]
                right_verts = [v for v in box_verts if v[axis] > split_pos]

                if len(left_verts) < min_vertices_per_box or len(right_verts) < min_vertices_per_box:
                    continue

                left_bounds = create_bounding_box(left_verts, margin=0.0)
                right_bounds = create_bounding_box(right_verts, margin=0.0)
                if left_bounds is None or right_bounds is None:
                    continue

                left_vol = _bounds_volume(left_bounds[1])
                right_vol = _bounds_volume(right_bounds[1])
                combined = left_vol + right_vol
                balance_penalty = abs(len(left_verts) - len(right_verts)) / max(len(box_verts), 1)
                score = combined * (1.0 + 0.15 * balance_penalty)

                if best is None or score < best['score']:
                    best = {
                        'score': score,
                        'combined': combined,
                        'left_verts': left_verts,
                        'right_verts': right_verts,
                        'left_bounds': left_bounds,
                        'right_bounds': right_bounds,
                    }

        if best is None:
            break

        # Stop micro-splitting once additional boxes barely reduce occupied volume.
        if (best['combined'] / max(source_volume, 1e-9)) > 0.98 and len(current_boxes) >= max(2, max_boxes // 3):
            break

        current_boxes.pop(target_index)
        current_boxes.append((best['left_verts'], best['left_bounds']))
        current_boxes.append((best['right_verts'], best['right_bounds']))

    result = []
    for _, (center, size) in current_boxes:
        # Add a tiny final padding and avoid zero-sized axes.
        padded = Vector((
            max(size.x * 1.02, 0.005),
            max(size.y * 1.02, 0.005),
            max(size.z * 1.02, 0.005),
        ))
        result.append((center, padded))

    result.sort(key=lambda item: _bounds_volume(item[1]), reverse=True)
    return result[:max_boxes]


class DYNMX_OT_create_hitbox(bpy.types.Operator):
    """Create a single hitbox manually"""
    bl_idname = "dynamx.create_hitbox"
    bl_label = "Create Hitbox"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        
        hitboxes_col = bpy.data.collections.get("Hitboxes")
        if not hitboxes_col:
            hitboxes_col = bpy.data.collections.new("Hitboxes")
            scene.collection.children.link(hitboxes_col)
        
        bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
        hitbox = context.active_object
        hitbox.name = "Hitbox"
        hitbox.display_type = 'WIRE'
        
        for col in hitbox.users_collection:
            col.objects.unlink(hitbox)
        hitboxes_col.objects.link(hitbox)
        
        self.report({'INFO'}, "Hitbox created")
        
        # Organize collections
        from .ops_vehicle import organize_scene_collections
        organize_scene_collections()
        
        return {'FINISHED'}


class DYNMX_OT_auto_generate_hitboxes(bpy.types.Operator):
    """Automatically generate hitboxes for selected objects using convex decomposition"""
    bl_idname = "dynamx.auto_generate_hitboxes"
    bl_label = "Auto Generate Hitboxes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT' and 
                len(context.selected_objects) > 0)

    def execute(self, context):
        scene = context.scene
        max_hitboxes = max(1, int(scene.dynamx_max_hitboxes))
        selected_objects = context.selected_objects.copy()
        
        if not selected_objects:
            self.report({'ERROR'}, "No objects selected")
            return {'CANCELLED'}
        
        hitboxes_col = bpy.data.collections.get("Hitboxes")
        if not hitboxes_col:
            hitboxes_col = bpy.data.collections.new("Hitboxes")
            scene.collection.children.link(hitboxes_col)
        
        mesh_entries = []
        try:
            depsgraph = context.evaluated_depsgraph_get()

            for obj in selected_objects:
                if obj.type != 'MESH':
                    continue

                eval_obj = obj.evaluated_get(depsgraph)
                mesh = eval_obj.to_mesh()
                if not mesh or not mesh.vertices:
                    try:
                        eval_obj.to_mesh_clear()
                    except Exception:
                        pass
                    continue

                world_verts = [obj.matrix_world @ v.co for v in mesh.vertices]
                bounds = create_bounding_box(world_verts, margin=0.0)
                volume = _bounds_volume(bounds[1]) if bounds else 0.0

                mesh_entries.append({
                    'obj': obj,
                    'eval_obj': eval_obj,
                    'mesh': mesh,
                    'volume': volume,
                    'allocation': 0,
                })

            if not mesh_entries:
                self.report({'ERROR'}, "No valid mesh objects selected")
                return {'CANCELLED'}

            mesh_entries.sort(key=lambda e: e['volume'], reverse=True)

            if len(mesh_entries) <= max_hitboxes:
                for entry in mesh_entries:
                    entry['allocation'] = 1
                remaining = max_hitboxes - len(mesh_entries)
            else:
                for entry in mesh_entries[:max_hitboxes]:
                    entry['allocation'] = 1
                remaining = 0

            if remaining > 0:
                allocatable = [e for e in mesh_entries if e['allocation'] > 0]
                total_volume = sum(max(e['volume'], 1e-9) for e in allocatable)

                fractional = []
                assigned = 0
                for entry in allocatable:
                    share = remaining * (max(entry['volume'], 1e-9) / total_volume)
                    extra = int(share)
                    entry['allocation'] += extra
                    assigned += extra
                    fractional.append((share - extra, entry))

                leftover = remaining - assigned
                fractional.sort(key=lambda item: item[0], reverse=True)
                for i in range(leftover):
                    fractional[i % len(fractional)][1]['allocation'] += 1

            total_hitboxes = 0
            for entry in mesh_entries:
                alloc = int(entry.get('allocation', 0))
                if alloc <= 0:
                    continue

                hitboxes = generate_smart_hitboxes(entry['obj'], entry['mesh'], alloc)
                for i, (center, size) in enumerate(hitboxes, start=1):
                    if total_hitboxes >= max_hitboxes:
                        break

                    bpy.ops.mesh.primitive_cube_add(size=2, location=center)
                    hitbox = context.active_object
                    hitbox.name = f"Hitbox_{entry['obj'].name}_{i}"
                    hitbox.scale = size
                    hitbox.display_type = 'WIRE'

                    for col in hitbox.users_collection:
                        col.objects.unlink(hitbox)
                    hitboxes_col.objects.link(hitbox)

                    total_hitboxes += 1

                if total_hitboxes >= max_hitboxes:
                    break

            self.report({'INFO'}, f"Generated {total_hitboxes} hitboxes")
            organize_scene_collections()
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to generate hitboxes: {str(e)}")
            return {'CANCELLED'}
        finally:
            for entry in mesh_entries:
                try:
                    entry['eval_obj'].to_mesh_clear()
                except Exception:
                    pass


class DYNMX_OT_export_hitboxes(bpy.types.Operator):
    """Export all hitboxes to the vehicle_<name>.dynx file in the Hitbox section"""
    bl_idname = "dynamx.export_hitboxes"
    bl_label = "Export Hitboxes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        if not (scene.dynamx_pack_path and scene.dynamx_pack_name and scene.dynamx_vehicle_name):
            return False
        hitboxes_col = bpy.data.collections.get("Hitboxes")
        return hitboxes_col is not None and len(hitboxes_col.objects) > 0

    def execute(self, context):
        scene = context.scene
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip().replace(" ", "_")
        vehicle_name = scene.dynamx_vehicle_name.strip()
        vehicle_name_safe = vehicle_name.replace(" ", "_")

        # choose filename based on active workspace: use trailer_ prefix in Trailer workspace
        try:
            wname = getattr(context.workspace, 'name', '')
        except Exception:
            wname = ''

        if wname == 'Dynamx - Trailer':
            dynx_filename = f"trailer_{vehicle_name_safe}.dynx"
        else:
            dynx_filename = f"vehicle_{vehicle_name_safe}.dynx"

        vehicle_file = os.path.join(pack_path, pack_name, "vehicle", vehicle_name_safe, dynx_filename)
        if not os.path.exists(vehicle_file):
            self.report({'ERROR'}, f"Vehicle file not found: {vehicle_file}")
            return {'CANCELLED'}

        try:
            with open(vehicle_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read vehicle file: {e}")
            return {'CANCELLED'}
        
        hitbox_marker = r'// ------------- Hitbox -------------'
        if hitbox_marker not in content:
            
            sw_match = re.search(r'SteeringWheel\s*\{[^}]*\}', content, re.DOTALL)
            insert_pos = sw_match.end() if sw_match else 0
            content = content[:insert_pos] + ("\n\n" if insert_pos else "") + hitbox_marker + "\n\n" + content[insert_pos:]
        
        hitbox_match = re.search(hitbox_marker, content)
        insert_pos = hitbox_match.end()
        next_section = re.search(r'\n// -------------', content[insert_pos:])
        region_end = insert_pos + next_section.start() if next_section else len(content)
        region = content[insert_pos:region_end]
        
        existing_shapes = {}
        i = 0
        while i < len(region):
            m = re.search(r'Shape_([A-Za-z0-9_\-\.\(\)]+)\s*\{', region[i:])
            if not m:
                break
            name = m.group(1)
            start = i + m.start()
            brace_start = i + m.end() - 1
            depth = 0
            j = brace_start
            while j < len(region):
                if region[j] == '{':
                    depth += 1
                elif region[j] == '}':
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
                j += 1
            else:
                break
            block = region[start:end]
            existing_shapes[name] = block
            i = end
        
        hitboxes_col = bpy.data.collections.get("Hitboxes")
        new_shape_map = {}

        def aabb_world_center_halfextents(obj: bpy.types.Object):
            coords = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
            min_v = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
            max_v = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
            center = (min_v + max_v) / 2
            half = (max_v - min_v) / 2
            return center, half

        for obj in hitboxes_col.objects:
            shapename = obj.name
            center, half = aabb_world_center_halfextents(obj)
            block = f"""Shape_{shapename}{{
    Scale: {half.x:.6f} {half.y:.6f} {half.z:.6f}
    Position: {center.x:.6f} {center.y:.6f} {center.z:.6f}
}}"""
            new_shape_map[shapename] = block
        
        merged = existing_shapes.copy()
        for k, v in new_shape_map.items():
            merged[k] = v
        
        new_region = "\n\n" + "\n\n".join(merged[name] for name in merged) + "\n"
        content = content[:insert_pos] + new_region + content[region_end:]

        try:
            with open(vehicle_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.report({'INFO'}, f"Exported {len(new_shape_map)} hitbox shape(s) to {vehicle_file}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write vehicle file: {e}")
            return {'CANCELLED'}


class DYNMX_OT_delete_hitbox(bpy.types.Operator):
    """Delete selected hitboxes or all hitboxes if none selected"""
    bl_idname = "dynamx.delete_hitbox"
    bl_label = "Delete Hitbox"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        hitboxes_col = bpy.data.collections.get("Hitboxes")
        
        if not hitboxes_col:
            self.report({'WARNING'}, "No Hitboxes collection found")
            return {'CANCELLED'}

        selected = [obj for obj in context.selected_objects if obj.name in hitboxes_col.objects]

        if selected:
            for obj in selected:
                bpy.data.objects.remove(obj, do_unlink=True)
            self.report({'INFO'}, f"Deleted {len(selected)} hitbox(es)")
        else:
            count = len(hitboxes_col.objects)
            for obj in list(hitboxes_col.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
            self.report({'INFO'}, f"Deleted all {count} hitboxes")
        
        return {'FINISHED'}


classes = (
    DYNMX_OT_create_hitbox,
    DYNMX_OT_auto_generate_hitboxes,
    DYNMX_OT_export_hitboxes,
    DYNMX_OT_delete_hitbox,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
