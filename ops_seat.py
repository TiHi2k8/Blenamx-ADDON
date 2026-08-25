"""Seat-related operators"""
import bpy
import os
import re
import tempfile
from .ops_vehicle import organize_scene_collections

def load_licensed_model(filename):
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(addon_dir, "licensed_models", filename)

    with open(model_path, "r", encoding="utf-8") as file:
        return file.read()


SEAT_OBJ_CONTENT = load_licensed_model("seat.obj")
SEAT_STANDING_OBJ_CONTENT = load_licensed_model("seat_standing.obj")


class DYNMX_OT_summon_seat(bpy.types.Operator):
    """Spawn a Seat object at 0,0,0 inside a 'Seats' collection"""
    bl_idname = "dynamx.summon_seat"
    bl_label = "Summon Seat"
    bl_options = {'REGISTER', 'UNDO'}
    
    is_standing: bpy.props.BoolProperty(
        name="Standing Seat",
        description="Create a standing seat instead of sitting",
        default=False
    )

    @classmethod
    def poll(cls, context):
        try:
            return context.mode == 'OBJECT' and context.workspace and context.workspace.name in ("Dynamx - Car", "Dynamx - Trailer")
        except Exception:
            return False

    def execute(self, context):
        seats_col = bpy.data.collections.get("Seats")
        if not seats_col:
            seats_col = bpy.data.collections.new("Seats")
            context.scene.collection.children.link(seats_col)

        position_type = "standing" if self.is_standing else "sitting"

        has_driver = any((ob.get('Driver', False) is True) for ob in seats_col.objects)

        if not has_driver:
            seat_id = "Driver"
            is_driver = True
        else:
            max_idx = 0
            for ob in seats_col.objects:
                m = re.match(r"^Seat\(Passenger(\d+)\)", ob.name)
                if m:
                    try:
                        idx = int(m.group(1))
                        if idx > max_idx:
                            max_idx = idx
                    except ValueError:
                        pass
            seat_id = f"Passenger{max_idx + 1}"
            is_driver = False
        seat_name = f"Seat({seat_id})"

        obj_content = SEAT_STANDING_OBJ_CONTENT if self.is_standing else SEAT_OBJ_CONTENT
        
        tmpdir = bpy.app.tempdir or tempfile.gettempdir()
        obj_path = os.path.join(tmpdir, "seat_template.obj")
        mtl_path = os.path.join(tmpdir, "steve-model-sitting.mtl")
        try:
            with open(obj_path, 'w', encoding='utf-8') as f:
                f.write(obj_content)
            if not os.path.exists(mtl_path):
                with open(mtl_path, 'w', encoding='utf-8') as f:
                    f.write("newmtl default\nKd 0.8 0.8 0.8\n")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write temp OBJ: {e}")
            return {'CANCELLED'}

        pre_names = set(o.name for o in bpy.data.objects)
        imported = False
        try:
            res = bpy.ops.wm.obj_import(filepath=obj_path)
            imported = (res == {'FINISHED'})
        except Exception:
            pass
        if not imported:
            try:
                res = bpy.ops.import_scene.obj(filepath=obj_path)
                imported = (res == {'FINISHED'})
            except Exception:
                imported = False

        if not imported:
            bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0.0, 0.0, 0.0))
            obj = bpy.context.active_object
            if obj:
                obj.name = seat_name
                if seats_col.name not in [c.name for c in obj.users_collection]:
                    seats_col.objects.link(obj)
                for col in list(obj.users_collection):
                    if col.name != seats_col.name:
                        col.objects.unlink(obj)
            self.report({'WARNING'}, "OBJ importer unavailable. Spawned placeholder cube.")
            return {'FINISHED'}

        post_names = set(o.name for o in bpy.data.objects)
        new_names = list(post_names - pre_names)
        new_objs = [bpy.data.objects[n] for n in new_names]

        if new_objs:
            seat_obj = new_objs[0]
            seat_obj.name = seat_name
            seat_obj.location = (0.0, 0.0, 0.0)
            
            seat_obj.rotation_mode = 'XYZ'
            seat_obj.rotation_euler = (0.0, 0.0, 0.0)
            
            try:
                seat_obj['PlayerPosition'] = position_type
            except Exception:
                pass
            try:
                seat_obj['Driver'] = bool(is_driver)
            except Exception:
                pass
            
            if seats_col.name not in [c.name for c in seat_obj.users_collection]:
                seats_col.objects.link(seat_obj)
            for col in list(seat_obj.users_collection):
                if col.name != seats_col.name:
                    col.objects.unlink(seat_obj)
            
            for ob in new_objs[1:]:
                bpy.data.objects.remove(ob, do_unlink=True)
            
            bpy.ops.object.select_all(action='DESELECT')
            seat_obj.select_set(True)
            context.view_layer.objects.active = seat_obj
        
        # Organize collections
        organize_scene_collections()
        
        self.report({'INFO'}, f"{seat_name} spawned at 0,0,0 in 'Seats' collection (PlayerPosition={position_type}, Driver={is_driver})")
        return {'FINISHED'}


class DYNMX_OT_duplicate_seat(bpy.types.Operator):
    """Spawn a new seat at the same location as the selected seat"""
    bl_idname = "dynamx.duplicate_seat"
    bl_label = "Duplicate Seat"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            if context.mode != 'OBJECT' or not context.active_object:
                return False
            if not context.workspace or context.workspace.name not in ("Dynamx - Car", "Dynamx - Trailer"):
                return False
            seats_col = bpy.data.collections.get("Seats")
            if not seats_col:
                return False
            return context.active_object.name in seats_col.objects
        except Exception:
            return False

    def execute(self, context):
        seats_col = bpy.data.collections.get("Seats")
        if not seats_col:
            seats_col = bpy.data.collections.new("Seats")
            context.scene.collection.children.link(seats_col)

        root = context.active_object
        if not root:
            self.report({'ERROR'}, "No active object to duplicate")
            return {'CANCELLED'}

        seat_location = root.matrix_world.translation.copy()

        try:
            pp = root.get('PlayerPosition', None)
            if pp is None:
                m = re.search(r"\| (sit|stand)$", root.name)
                position_type = 'standing' if (m and m.group(1) == 'stand') else 'sitting'
            else:
                position_type = pp
        except Exception:
            position_type = 'sitting'
        is_standing = (position_type == 'standing')

        max_idx = 0
        for ob in seats_col.objects:
            m = re.match(r"^Seat\(Passenger(\d+)\)", ob.name)
            if m:
                try:
                    idx = int(m.group(1))
                    if idx > max_idx:
                        max_idx = idx
                except ValueError:
                    pass
        new_seat_id = f"Passenger{max_idx + 1}"
        new_seat_name = f"Seat({new_seat_id})"

        obj_content = SEAT_STANDING_OBJ_CONTENT if is_standing else SEAT_OBJ_CONTENT

        tmpdir = bpy.app.tempdir or tempfile.gettempdir()
        obj_path = os.path.join(tmpdir, "seat_template.obj")
        mtl_path = os.path.join(tmpdir, "steve-model-sitting.mtl")
        try:
            with open(obj_path, 'w', encoding='utf-8') as f:
                f.write(obj_content)
            if not os.path.exists(mtl_path):
                with open(mtl_path, 'w', encoding='utf-8') as f:
                    f.write("newmtl default\nKd 0.8 0.8 0.8\n")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write temp OBJ: {e}")
            return {'CANCELLED'}

        pre_names = set(o.name for o in bpy.data.objects)
        imported = False
        try:
            res = bpy.ops.wm.obj_import(filepath=obj_path)
            imported = (res == {'FINISHED'})
        except Exception:
            pass
        if not imported:
            try:
                res = bpy.ops.import_scene.obj(filepath=obj_path)
                imported = (res == {'FINISHED'})
            except Exception:
                imported = False

        if not imported:
            bpy.ops.mesh.primitive_cube_add(size=0.5, location=seat_location)
            obj = bpy.context.active_object
            if obj:
                obj.name = new_seat_name
                if seats_col.name not in [c.name for c in obj.users_collection]:
                    seats_col.objects.link(obj)
                for col in list(obj.users_collection):
                    if col.name != seats_col.name:
                        col.objects.unlink(obj)
            self.report({'WARNING'}, "OBJ importer unavailable. Spawned placeholder cube.")
            return {'FINISHED'}

        post_names = set(o.name for o in bpy.data.objects)
        new_names = list(post_names - pre_names)
        new_objs = [bpy.data.objects[n] for n in new_names]

        if new_objs:
            seat_obj = new_objs[0]
            seat_obj.name = new_seat_name

            seat_obj.matrix_world = root.matrix_world.copy()

            if seats_col.name not in [c.name for c in seat_obj.users_collection]:
                seats_col.objects.link(seat_obj)
            for col in list(seat_obj.users_collection):
                if col.name != seats_col.name:
                    col.objects.unlink(seat_obj)

            for ob in new_objs[1:]:
                bpy.data.objects.remove(ob, do_unlink=True)

            bpy.ops.object.select_all(action='DESELECT')
            seat_obj.select_set(True)
            context.view_layer.objects.active = seat_obj

            try:
                seat_obj['PlayerPosition'] = position_type
            except Exception:
                pass
            try:
                seat_obj['Driver'] = False
            except Exception:
                pass

        self.report({'INFO'}, f"{new_seat_name} spawned at selected seat location (PlayerPosition={position_type})")
        return {'FINISHED'}


class DYNMX_OT_delete_seat(bpy.types.Operator):
    """Delete the selected seat and all its children"""
    bl_idname = "dynamx.delete_seat"
    bl_label = "Delete Seat"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT' or not context.active_object:
            return False
        seats_col = bpy.data.collections.get("Seats")
        if not seats_col:
            return False
        return context.active_object.name in seats_col.objects

    def execute(self, context):
        seat_obj = context.active_object
        seat_name = seat_obj.name
        
        bpy.data.objects.remove(seat_obj, do_unlink=True)
        
        self.report({'INFO'}, f"Deleted seat '{seat_name}'")
        return {'FINISHED'}


class DYNMX_OT_export_seats(bpy.types.Operator):
    """Export all seats to the vehicle_<name>.dynx file"""
    bl_idname = "dynamx.export_seats"
    bl_label = "Export Seats"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            scene = context.scene
            if not (scene.dynamx_pack_path and scene.dynamx_pack_name and scene.dynamx_vehicle_name):
                return False
            if not context.workspace or context.workspace.name not in ("Dynamx - Car", "Dynamx - Trailer"):
                return False
            seats_col = bpy.data.collections.get("Seats")
            return seats_col is not None and len(seats_col.objects) > 0
        except Exception:
            return False

    def execute(self, context):
        scene = context.scene
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip()
        vehicle_name = scene.dynamx_vehicle_name.strip()

        pack_name_safe = pack_name.replace(" ", "_")
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

        vehicle_file = os.path.join(pack_path, pack_name_safe, "vehicle", vehicle_name_safe, dynx_filename)

        if not os.path.exists(vehicle_file):
            self.report({'ERROR'}, f"Vehicle file not found: {vehicle_file}")
            return {'CANCELLED'}

        try:
            with open(vehicle_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read vehicle file: {e}")
            return {'CANCELLED'}

        seats_col = bpy.data.collections.get("Seats")
        if not seats_col:
            self.report({'ERROR'}, "No Seats collection found")
            return {'CANCELLED'}

        seat_objects = [obj for obj in seats_col.objects]

        if not seat_objects:
            self.report({'WARNING'}, "No seat objects found in Seats collection")
            return {'CANCELLED'}

        seat_entries = []
        for seat_obj in seat_objects:
            m = re.match(r"^Seat\((.+?)\)", seat_obj.name)
            if not m:
                continue
            seat_type = m.group(1)

            player_position = seat_obj.get('PlayerPosition', 'sitting')
            is_driver = seat_obj.get('Driver', False)

            pos = seat_obj.matrix_world.translation

            import math
            quat_blender = seat_obj.matrix_world.to_quaternion()
            quat_file_space = quat_blender

            w, x, y, z = quat_file_space.w, quat_file_space.x, quat_file_space.y, quat_file_space.z
            converted_quat = (w, x, z, y)

            euler_file = quat_file_space.to_euler('XYZ')
            camera_rotation_z = math.degrees(euler_file.z)

            is_driver_str = "true" if bool(is_driver) else "false"

            seat_entry = (
                f"Seat_{seat_type}{{\n"
                f"    Position: {pos.x:.6f} {pos.y:.6f} {pos.z:.6f}\n"
                f"    CameraRotation: {camera_rotation_z:.6f}\n"
                f"    Rotation: {converted_quat[0]:.6f} {converted_quat[1]:.6f} {converted_quat[2]:.6f} {converted_quat[3]:.6f}\n"
                f"    PlayerPosition: {player_position}\n"
                f"    Driver: {is_driver_str}\n"
                f"}}"
            )
            seat_entries.append(seat_entry)

        seats_match = re.search(r'//\s*-+\s*SEATS', content, re.IGNORECASE)
        if seats_match:
            nl = content.find('\n', seats_match.end())
            if nl != -1:
                insert_pos = nl + 1
            else:
                insert_pos = seats_match.end()
        else:
            next_section = re.search(r'\n// -------------', content)
            if next_section:
                insert_pos = next_section.start()
            else:
                insert_pos = len(content)

        next_section = re.search(r'\n// -------------', content[insert_pos:])
        if next_section:
            seats_region_end = insert_pos + next_section.start()
        else:
            seats_region_end = len(content)

        existing_region = content[insert_pos:seats_region_end]

        existing_seats = {}
        i = 0
        while i < len(existing_region):
            m = re.search(r'Seat_([A-Za-z0-9_\(\)]+)\s*\{', existing_region[i:])
            if not m:
                break
            name = m.group(1)
            start = i + m.start()
            brace_start = i + m.end() - 1 
            depth = 0
            j = brace_start
            while j < len(existing_region):
                if existing_region[j] == '{':
                    depth += 1
                elif existing_region[j] == '}':
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
                j += 1
            else:
                break
            block = existing_region[start:end]
            existing_seats[name] = block
            i = end

        new_seat_map = {}
        for entry in seat_entries:
            m = re.match(r'Seat_([A-Za-z0-9_\(\)]+)\{', entry)
            if m:
                key = m.group(1)
            else:
                key = entry
            new_seat_map[key] = entry

        replace_flag = getattr(context.scene, 'dynamx_replace_seats', False)

        merged_seats = existing_seats.copy()
        for k, v in new_seat_map.items():
            if k in merged_seats:
                if replace_flag:
                    merged_seats[k] = v
                else:
                    pass
            else:
                merged_seats[k] = v

        seats_block = "\n\n" + "\n\n".join(merged_seats[s] for s in merged_seats) + "\n"

        canonical_marker = "// ------------- SEATS --------------\n\n"
        insert_marker = '' if re.search(r'//\s*-+\s*SEATS', content, re.IGNORECASE) else canonical_marker

        content = content[:insert_pos] + insert_marker + seats_block + content[seats_region_end:]

        try:
            with open(vehicle_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.report({'INFO'}, f"Exported {len(seat_entries)} seat(s) to {vehicle_file}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write vehicle file: {e}")
            return {'CANCELLED'}


classes = (DYNMX_OT_summon_seat, DYNMX_OT_duplicate_seat, DYNMX_OT_delete_seat, DYNMX_OT_export_seats)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    def _update_seat_standing(self, context):
        try:
            seats_col = bpy.data.collections.get("Seats")
            if not seats_col or self.name not in seats_col.objects:
                return
        except Exception:
            return

        desired = bool(self.dynamx_is_standing)
        base_name = None
        m = re.match(r'^(Seat\(.+?\)) \| (sit|stand)$', self.name)
        if m:
            base_name = m.group(1)
        else:
            base_name = self.name.split('|')[0].strip()

        suffix = 'stand' if desired else 'sit'
        try:
            self.name = f"{base_name} | {suffix}"
        except Exception:
            pass

        try:
            tmpdir = bpy.app.tempdir or tempfile.gettempdir()
            obj_path = os.path.join(tmpdir, "seat_template.obj")
            mtl_path = os.path.join(tmpdir, "steve-model-sitting.mtl")
            with open(obj_path, 'w', encoding='utf-8') as f:
                f.write(SEAT_STANDING_OBJ_CONTENT if desired else SEAT_OBJ_CONTENT)
            if not os.path.exists(mtl_path):
                with open(mtl_path, 'w', encoding='utf-8') as f:
                    f.write("newmtl default\nKd 0.8 0.8 0.8\n")

            pre_objs = set(o.name for o in bpy.data.objects)
            imported = False
            try:
                res = bpy.ops.wm.obj_import(filepath=obj_path)
                imported = (res == {'FINISHED'})
            except Exception:
                pass
            if not imported:
                try:
                    res = bpy.ops.import_scene.obj(filepath=obj_path)
                    imported = (res == {'FINISHED'})
                except Exception:
                    imported = False

            if imported:
                post_objs = set(o.name for o in bpy.data.objects)
                new_names = list(post_objs - pre_objs)
                if new_names:
                    new_obj = bpy.data.objects[new_names[0]]
                    try:
                        old_data = self.data
                        self.data = new_obj.data
                        bpy.data.objects.remove(new_obj, do_unlink=True)
                        if old_data and getattr(old_data, 'users', 1) == 0:
                            bpy.data.meshes.remove(old_data)
                    except Exception:
                        try:
                            bpy.data.objects.remove(new_obj, do_unlink=True)
                        except Exception:
                            pass
        except Exception:
            pass

    if not hasattr(bpy.types.Object, 'dynamx_is_standing'):
        bpy.types.Object.dynamx_is_standing = bpy.props.BoolProperty(
            name="Standing Seat",
            description="Toggle this seat between standing and sitting and update the model",
            default=False,
            update=_update_seat_standing,
        )


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    if hasattr(bpy.types.Object, 'dynamx_is_standing'):
        try:
            del bpy.types.Object.dynamx_is_standing
        except Exception:
            pass

