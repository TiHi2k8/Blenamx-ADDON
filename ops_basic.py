"""Basic utilities for Dynamx addon: License plate summon operator and small helpers"""
import bpy
import math
import re
import os
import shutil
import bmesh
from mathutils import Matrix, Vector, Euler
from .ops_vehicle import organize_scene_collections


def _write_basic_light_png(path, rgb, alpha=1.0):
    """Write a tiny 1x1 PNG for default light textures."""
    try:
        import struct
        import zlib
        r, g, b = rgb
        red = max(0, min(255, int(round(float(r) * 255.0))))
        green = max(0, min(255, int(round(float(g) * 255.0))))
        blue = max(0, min(255, int(round(float(b) * 255.0))))
        alpha_value = max(0.0, min(1.0, float(alpha)))

        def chunk(tag, data):
            return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data) & 0xFFFFFFFF)

        has_alpha = alpha_value < 1.0 or alpha_value != 1.0
        if has_alpha:
            a = max(0, min(255, int(round(alpha_value * 255.0))))
            raw = b'\x00' + bytes((red, green, blue, a))
            png = b'\x89PNG\r\n\x1a\n'
            png += chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
        else:
            raw = b'\x00' + bytes((red, green, blue))
            png = b'\x89PNG\r\n\x1a\n'
            png += chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(raw, 9))
        png += chunk(b'IEND', b'')
        with open(path, 'wb') as f:
            f.write(png)
        return path
    except Exception:
        return None


def _ensure_basic_light_texture_folder(scene=None):
    if scene is None:
        scene = bpy.context.scene

    pack_path = bpy.path.abspath(getattr(scene, 'dynamx_pack_path', ''))
    pack_name = str(getattr(scene, 'dynamx_pack_name', '')).strip()
    vehicle_name = str(getattr(scene, 'dynamx_vehicle_name', '')).strip()

    if pack_path and pack_name and vehicle_name:
        pack_name_safe = pack_name.replace(' ', '_').lower()
        vehicle_name_safe = vehicle_name.replace(' ', '_').lower()
        obj_dir = os.path.join(pack_path, pack_name_safe, 'assets', 'dynamxmod', 'models', 'obj', vehicle_name_safe)
        lights_dir = os.path.join(obj_dir, 'textures', 'lights')
        os.makedirs(lights_dir, exist_ok=True)

        source_textures = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures')
        for filename in ('off.png', 'on.png'):
            src = os.path.join(source_textures, filename)
            dst = os.path.join(lights_dir, filename)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass
            if not os.path.exists(dst):
                try:
                    _write_basic_light_png(dst, (0.75, 0.75, 0.8) if filename == 'off.png' else (1.0, 0.9, 0.35))
                except Exception:
                    pass
        return lights_dir

    addon_dir = os.path.dirname(os.path.abspath(__file__))
    lights_dir = os.path.join(addon_dir, 'Lights')
    os.makedirs(lights_dir, exist_ok=True)
    source_textures = os.path.join(addon_dir, 'textures')
    for filename in ('off.png', 'on.png'):
        src = os.path.join(source_textures, filename)
        dst = os.path.join(lights_dir, filename)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
        if not os.path.exists(dst):
            try:
                _write_basic_light_png(dst, (0.75, 0.75, 0.8) if filename == 'off.png' else (1.0, 0.9, 0.35))
            except Exception:
                pass
    return lights_dir


def _resolve_basic_light_texture_paths(scene, light_key):
    lights_dir = _ensure_basic_light_texture_folder(scene)

    if os.path.exists(os.path.join(lights_dir, 'off.png')) and os.path.exists(os.path.join(lights_dir, 'on.png')):
        return os.path.join(lights_dir, 'off.png'), os.path.join(lights_dir, 'on.png')

    safe_key = re.sub(r'[^a-zA-Z0-9_]+', '_', str(light_key or 'light')).strip('_').lower() or 'light'
    combine = bool(getattr(scene, 'dynamx_combine_main_lights_materials', True))
    base_name = 'lights' if combine else safe_key
    off_path = os.path.join(lights_dir, f'{base_name}_off.png')
    on_path = os.path.join(lights_dir, f'{base_name}_on.png')
    if not os.path.exists(off_path):
        _write_basic_light_png(off_path, (0.75, 0.75, 0.8))
    if not os.path.exists(on_path):
        _write_basic_light_png(on_path, (1.0, 0.9, 0.35))
    return off_path, on_path


def _resolve_basic_light_glass_texture_path(scene):
    glass_path = str(getattr(scene, 'dynamx_main_lights_glass_texture', '') or '').strip()
    if glass_path and os.path.exists(bpy.path.abspath(glass_path)):
        return bpy.path.abspath(glass_path)

    lights_dir = _ensure_basic_light_texture_folder(scene)
    glass_fallback = os.path.join(lights_dir, 'glass.png')
    if not os.path.exists(glass_fallback):
        try:
            _write_basic_light_png(glass_fallback, (0.7, 0.8, 1.0))
        except Exception:
            pass
    return glass_fallback if os.path.exists(glass_fallback) else None


def _apply_basic_light_materials_to_object(obj, light_key, scene=None):
    if obj is None:
        return
    if scene is None:
        scene = bpy.context.scene

    try:
        if hasattr(obj.data, 'materials'):
            obj.data.materials.clear()
    except Exception:
        pass

    off_path, on_path = _resolve_basic_light_texture_paths(scene, light_key)
    glass_path = _resolve_basic_light_glass_texture_path(scene)
    safe_key = re.sub(r'[^a-zA-Z0-9_]+', '_', str(light_key or 'light')).strip('_').lower() or 'light'

    def _ensure_image_texture(material, off_image_path, on_image_path=None):
        if not getattr(material, 'use_nodes', False):
            material.use_nodes = True
        tree = material.node_tree
        if tree is None:
            return None

        for node in list(tree.nodes):
            tree.nodes.remove(node)

        output = tree.nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (500, 0)

        principled = tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = (250, 0)
        if material.name.lower() == 'lights_glass':
            principled.inputs['Alpha'].default_value = 0.5
        else:
            principled.inputs['Alpha'].default_value = 1.0

        def _load_image(path):
            image = bpy.data.images.get(os.path.basename(path))
            if image is None:
                try:
                    image = bpy.data.images.load(path)
                except Exception:
                    image = bpy.data.images.new(name=os.path.basename(path), width=1, height=1, alpha=False, float_buffer=False)
            return image

        off_image = _load_image(off_image_path)
        off_tex = tree.nodes.new(type='ShaderNodeTexImage')
        off_tex.location = (-450, 80)
        off_tex.image = off_image

        if on_image_path:
            on_image = _load_image(on_image_path)
            on_tex = tree.nodes.new(type='ShaderNodeTexImage')
            on_tex.location = (-450, -140)
            on_tex.image = on_image
            mix = tree.nodes.new(type='ShaderNodeMixRGB')
            mix.location = (-150, 0)
            mix.blend_type = 'MIX'
            mix.inputs['Fac'].default_value = 0.0
            tree.links.new(off_tex.outputs['Color'], mix.inputs['Color1'])
            tree.links.new(on_tex.outputs['Color'], mix.inputs['Color2'])
            tree.links.new(mix.outputs['Color'], principled.inputs['Base Color'])

            # Lights glass keeps a fixed alpha value instead of inheriting the alpha from the off/on texture.
            if material.name.lower() == 'lights_glass':
                principled.inputs['Alpha'].default_value = 0.5
        else:
            tree.links.new(off_tex.outputs['Color'], principled.inputs['Base Color'])
            if material.name.lower() == 'lights_glass':
                principled.inputs['Alpha'].default_value = 0.5

        tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])
        return off_image

    combine = bool(getattr(scene, 'dynamx_combine_main_lights_materials', True))
    primary_name = 'lights'
    secondary_name = str(getattr(scene, 'dynamx_main_lights_glass_material', '')).strip() or 'lights_glass'

    if combine:
        material_names = [primary_name, secondary_name]
    else:
        material_names = [primary_name, secondary_name]

    created_mats = []
    for idx, name in enumerate(material_names):
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name=name)
        created_mats.append(mat)
        if idx == 0:
            _ensure_image_texture(mat, off_path, on_path)
        else:
            _ensure_image_texture(mat, off_path, on_path)

    try:
        if getattr(obj, 'data', None) is not None and hasattr(obj.data, 'materials'):
            obj.data.materials.clear()
            for mat in created_mats:
                obj.data.materials.append(mat)
            if len(obj.data.materials) >= 2:
                obj.data.materials[0] = created_mats[0]
                obj.data.materials[1] = created_mats[1]
    except Exception:
        pass

    try:
        if combine:
            scene.dynamx_main_lights_material = 'lights'
            scene.dynamx_main_lights_texture_off = off_path
            scene.dynamx_main_lights_texture_on = on_path
            if glass_path:
                scene.dynamx_main_lights_glass_texture = glass_path
        else:
            mapping = {
                'headlight': ('dynamx_headlight_material', 'dynamx_headlight_texture_off', 'dynamx_headlight_texture_on'),
                'brakelights': ('dynamx_brakelights_material', 'dynamx_brakelights_texture_off', 'dynamx_brakelights_texture_on'),
                'reverselights': ('dynamx_reverselights_material', 'dynamx_reverselights_texture_off', 'dynamx_reverselights_texture_on'),
                'blinker_left': ('dynamx_blinker_left_material', 'dynamx_blinker_left_texture_off', 'dynamx_blinker_left_texture_on'),
                'blinker_right': ('dynamx_blinker_right_material', 'dynamx_blinker_right_texture_off', 'dynamx_blinker_right_texture_on'),
                'sirenlight': ('dynamx_sirenlight_material', 'dynamx_sirenlight_texture_off', 'dynamx_sirenlight_texture_on'),
            }
            key = safe_key if safe_key in mapping else None
            if key is not None:
                mat_name, off_prop, on_prop = mapping.get(key)
                setattr(scene, mat_name, 'lights')
                setattr(scene, off_prop, off_path)
                setattr(scene, on_prop, on_path)
    except Exception:
        pass


def _enable_basic_light_textures_for_object(obj, light_key, scene=None):
    if scene is None:
        scene = bpy.context.scene
    if not getattr(scene, 'dynamx_use_basic_light_textures', True):
        return
    _apply_basic_light_materials_to_object(obj, light_key, scene=scene)


class DYNMX_OT_summon_license_plate(bpy.types.Operator):
    """Summon a license plate text object with predefined style"""
    bl_idname = "dynamx.summon_license_plate"
    bl_label = "Summon Liscense Plate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        txt = getattr(scene, 'dynamx_license_plate_text', "YC @@ %%%%")
        try:
            from . import utils as _utils
            extras_col = _utils.ensure_collection('Extras', scene=context.scene)
            lp_col = _utils.ensure_collection('liscense Plate', parent=extras_col, scene=context.scene)
        except Exception:
            extras_col = None
            lp_col = None

        next_idx = 1
        try:
            max_idx = 0
            pattern = re.compile(r'^LiscensePlate\((\d+)\)$')
            objs_to_check = []
            if lp_col is not None:
                try:
                    objs_to_check = list(lp_col.objects)
                except Exception:
                    objs_to_check = []
            if not objs_to_check:
                objs_to_check = list(bpy.data.objects)
            for o in objs_to_check:
                try:
                    m = pattern.match(o.name)
                    if m:
                        max_idx = max(max_idx, int(m.group(1)))
                except Exception:
                    pass
            next_idx = max_idx + 1
        except Exception:
            next_idx = 1

        try:
            bpy.ops.object.text_add(location=(0.0, 0.016, 0.0))
            obj = context.active_object
        except Exception:
            txt_data = bpy.data.curves.new(name="LicensePlateCurve", type='FONT')
            obj = bpy.data.objects.new(f"LiscensePlate({next_idx})", txt_data)
            try:
                context.scene.collection.objects.link(obj)
                context.view_layer.objects.active = obj
            except Exception:
                pass

        try:
            obj.data.body = txt
        except Exception:
            try:
                obj.data.splines.clear()
            except Exception:
                pass

        try:
            obj.data.size = 0.146169
        except Exception:
            pass

        try:
            obj.data.align_x = 'CENTER'
        except Exception:
            pass

        try:
            obj.data.align_y = 'TOP'
        except Exception:
            pass

        try:
            obj.data.space_character = 0.9
        except Exception:
            pass
        try:
            obj.data.space_word = 1.4
        except Exception:
            pass
        try:
            obj.data.space_line = 1.0
        except Exception:
            pass

        try:
            if hasattr(obj.data, 'offset_y'):
                obj.data.offset_y = 0.016
            elif hasattr(obj.data, 'offset'):
                try:
                    off = obj.data.offset
                    try:
                        off.y = 0.016
                    except Exception:
                        obj.data.offset = (getattr(off, 'x', 0.0), 0.016, getattr(off, 'z', 0.0))
                except Exception:
                    obj.location.y = 0.016
            else:
                obj.location.y = 0.016
        except Exception:
            try:
                obj.location.y = 0.016
            except Exception:
                pass

        try:
            obj.rotation_mode = 'XYZ'
            obj.rotation_euler = (math.radians(90.0), 0.0, math.radians(-180.0))
        except Exception:
            try:
                obj.rotation_euler = (0.0, 0.0, 0.0)
            except Exception:
                pass

        try:
            eras_font = None
            for font in bpy.data.fonts:
                try:
                    if 'eras' in (font.name or '').lower():
                        eras_font = font
                        break
                except Exception:
                    continue
            if eras_font is None:
                eras_font = bpy.data.fonts.get("Eras Demi ITC Regular")
            if eras_font:
                try:
                    obj.data.font = eras_font
                except Exception:
                    pass
                for attr in ('font_bold', 'font_italic', 'font_bold_italic'):
                    if hasattr(obj.data, attr):
                        try:
                            setattr(obj.data, attr, eras_font)
                        except Exception:
                            pass
        except Exception:
            pass

        try:
            plate_name = f"LiscensePlate({next_idx})"
            obj.name = plate_name
        except Exception:
            pass
        try:
            if getattr(obj, 'data', None) is not None:
                try:
                    obj.data.name = obj.name
                except Exception:
                    pass
        except Exception:
            pass
        try:
            for col in list(obj.users_collection):
                try:
                    col.objects.unlink(obj)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if lp_col is not None:
                try:
                    lp_col.objects.link(obj)
                except Exception:
                    try:
                        context.scene.collection.objects.link(obj)
                    except Exception:
                        pass
        except Exception:
            pass

        self.report({'INFO'}, "License plate summoned")
        organize_scene_collections()
        return {'FINISHED'}


classes = (DYNMX_OT_summon_license_plate,)

def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except RuntimeError as e:
            if "already registered" in str(e):
                pass
            else:
                raise


def unregister():
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass


class DYNMX_OT_summon_storage(bpy.types.Operator):
    """Summon a storage cube into Extras -> BasicAddon collection"""
    bl_idname = "dynamx.summon_storage"
    bl_label = "Summon Storage"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        invspace = int(getattr(scene, 'dynamx_storage_size', 9))

        extras = None
        basic_col = None
        try:
            from . import utils as _utils
            extras = _utils.ensure_collection('Extras', scene=context.scene)
            basic_col = _utils.ensure_collection('BasicAddon', parent=extras, scene=context.scene)
        except Exception:
            extras = None
            basic_col = None

        next_idx = 1
        try:
            max_idx = 0
            import re as _re
            pat = _re.compile(r'^Storage\((\d+)\)_')
            objs = list(basic_col.objects) if basic_col else list(bpy.data.objects)
            for o in objs:
                try:
                    m = pat.match(o.name)
                    if m:
                        max_idx = max(max_idx, int(m.group(1)))
                except Exception:
                    pass
            next_idx = max_idx + 1
        except Exception:
            next_idx = 1

        try:
            bpy.ops.mesh.primitive_cube_add(size=2, location=(0.0, 0.0, 0.0))
            cube = context.active_object
        except Exception:
            mesh = bpy.data.meshes.new('StorageMesh')
            cube = bpy.data.objects.new('Storage', mesh)
            try:
                context.scene.collection.objects.link(cube)
            except Exception:
                pass

        name = f"Storage({next_idx})_{invspace}"
        try:
            cube.name = name
        except Exception:
            pass
        try:
            if getattr(cube, 'data', None) is not None:
                cube.data.name = cube.name
        except Exception:
            pass

        try:
            for col in list(cube.users_collection):
                try:
                    col.objects.unlink(cube)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if basic_col is not None:
                try:
                    basic_col.objects.link(cube)
                except Exception:
                    try:
                        context.scene.collection.objects.link(cube)
                    except Exception:
                        pass
        except Exception:
            pass

        self.report({'INFO'}, f"Summoned storage: {name}")
        organize_scene_collections()
        return {'FINISHED'}


class DYNMX_OT_set_storage(bpy.types.Operator):
    """In Edit Mode: create a storage cube enclosing selected faces"""
    bl_idname = "dynamx.set_storage"
    bl_label = "Set Storage"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        sel_faces = [f for f in bm.faces if f.select]
        if not sel_faces:
            self.report({'ERROR'}, 'No faces selected')
            return {'CANCELLED'}

        verts = set()
        for f in sel_faces:
            for v in f.verts:
                verts.add(v)
        world_pts = [obj.matrix_world @ v.co for v in verts]
        xs = [p.x for p in world_pts]
        ys = [p.y for p in world_pts]
        zs = [p.z for p in world_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)
        world_center = Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
        world_size = Vector((max_x - min_x, max_y - min_y, max_z - min_z))

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        try:
            bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
            cube = context.active_object
        except Exception:
            mesh = bpy.data.meshes.new('StorageMesh')
            cube = bpy.data.objects.new('Storage', mesh)
            try:
                context.scene.collection.objects.link(cube)
            except Exception:
                pass

        try:
            cube.location = world_center
        except Exception:
            try:
                cube.location = obj.matrix_world @ Vector((0.0, 0.0, 0.0))
            except Exception:
                pass
        try:
            sx = world_size.x / 2.0 if world_size.x > 0 else 0.001
            sy = world_size.y / 2.0 if world_size.y > 0 else 0.001
            sz = world_size.z / 2.0 if world_size.z > 0 else 0.001
            cube.scale = Vector((sx, sy, sz))
        except Exception:
            pass

        scene = context.scene
        invspace = int(getattr(scene, 'dynamx_storage_size', 9))
        extras = None
        basic_col = None
        try:
            from . import utils as _utils
            extras = _utils.ensure_collection('Extras', scene=context.scene)
            basic_col = _utils.ensure_collection('BasicAddon', parent=extras, scene=context.scene)
        except Exception:
            extras = None
            basic_col = None

        next_idx = 1
        try:
            max_idx = 0
            import re as _re
            pat = _re.compile(r'^Storage\((\d+)\)_')
            objs = list(basic_col.objects) if basic_col else list(bpy.data.objects)
            for o in objs:
                try:
                    m = pat.match(o.name)
                    if m:
                        max_idx = max(max_idx, int(m.group(1)))
                except Exception:
                    pass
            next_idx = max_idx + 1
        except Exception:
            next_idx = 1

        name = f"Storage({next_idx})_{invspace}"
        try:
            cube.name = name
        except Exception:
            pass
        try:
            if getattr(cube, 'data', None) is not None:
                try:
                    cube.data.name = cube.name
                except Exception:
                    pass
        except Exception:
            pass

        try:
            for col in list(cube.users_collection):
                try:
                    col.objects.unlink(cube)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if basic_col is not None:
                try:
                    basic_col.objects.link(cube)
                except Exception:
                    try:
                        context.scene.collection.objects.link(cube)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
        except Exception:
            pass

        self.report({'INFO'}, f"Set storage: {name}")
        return {'FINISHED'}


class DYNMX_OT_import_wheel(bpy.types.Operator):
    """Import a wheel .dynx from another vehicle in the same pack and create a wheel parent"""
    bl_idname = "dynamx.import_wheel"
    bl_label = "Import Wheel"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        scene = context.scene
        pack_path = getattr(scene, 'dynamx_pack_path', None)
        pack_name = getattr(scene, 'dynamx_pack_name', None)
        vehicle_name = getattr(scene, 'dynamx_vehicle_name', None)
        if not (pack_path and pack_name and vehicle_name):
            self.report({'ERROR'}, 'Pack path/name or vehicle not set in scene')
            return {'CANCELLED'}
        try:
            pack_path = bpy.path.abspath(pack_path)
            src = self.filepath
            if not src or not os.path.exists(src):
                self.report({'ERROR'}, 'No valid file selected')
                return {'CANCELLED'}
            base = os.path.splitext(os.path.basename(src))[0]
            dst_dir = os.path.join(pack_path, pack_name.replace(' ', '_').lower(), 'vehicle', vehicle_name.replace(' ', '_').lower())
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, f"{base}.dynx")
            try:
                shutil.copy(src, dst)
            except Exception:
                try:
                    with open(src, 'r', encoding='utf-8') as fsrc:
                        data = fsrc.read()
                    with open(dst, 'w', encoding='utf-8') as fdst:
                        fdst.write(data)
                except Exception as e:
                    self.report({'ERROR'}, f'Failed to import wheel file: {e}')
                    return {'CANCELLED'}

            import re as _re
            max_idx = 0
            for ob in bpy.data.objects:
                m = _re.search(r'wheel\((\d+)\)', ob.name)
                if m:
                    try:
                        max_idx = max(max_idx, int(m.group(1)))
                    except Exception:
                        pass
            idx = max_idx + 1
            wheels_root = bpy.data.collections.get('wheels')
            if not wheels_root:
                wheels_root = bpy.data.collections.new('wheels')
                try:
                    context.scene.collection.children.link(wheels_root)
                except Exception:
                    pass
            try:
                empty = bpy.data.objects.new(f"wheel({idx})_{base}", None)
                try:
                    wheels_root.objects.link(empty)
                except Exception:
                    try:
                        context.scene.collection.objects.link(empty)
                    except Exception:
                        pass
                try:
                    attached = f"{pack_name}.{base}"
                    try:
                        empty['AttachedWheel'] = attached
                    except Exception:
                        pass
                    try:
                        is_steer = bool(getattr(scene, 'dynamx_wheel_steerable', False))
                        empty['IsSteerable'] = bool(is_steer)
                    except Exception:
                        pass
                    try:
                        empty['DrivingWheel'] = (not bool(getattr(scene, 'dynamx_wheel_steerable', False)))
                    except Exception:
                        pass
                    try:
                        empty['MaxTurn'] = 0.7 if empty.get('IsSteerable', False) else 0.0
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass

            self.report({'INFO'}, f'Imported wheel {base} as wheel({idx})_{base}')
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to import wheel: {e}')
            return {'CANCELLED'}


classes = (
    DYNMX_OT_summon_license_plate,
    DYNMX_OT_summon_storage,
    DYNMX_OT_set_storage,
    DYNMX_OT_import_wheel,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


class DYNMX_OT_summon_fueltank(bpy.types.Operator):
    """Summon a fuel tank cube into Extras -> BasicAddon collection"""
    bl_idname = "dynamx.summon_fueltank"
    bl_label = "Summon Fuel Tank"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        invspace = int(getattr(scene, 'dynamx_fueltank_size', 200))

        extras = None
        basic_col = None
        try:
            from . import utils as _utils
            extras = _utils.ensure_collection('Extras', scene=context.scene)
            basic_col = _utils.ensure_collection('BasicAddon', parent=extras, scene=context.scene)
        except Exception:
            extras = None
            basic_col = None

        next_idx = 1
        try:
            max_idx = 0
            import re as _re
            pat = _re.compile(r'^FuelTank\((\d+)\)_')
            objs = list(basic_col.objects) if basic_col else list(bpy.data.objects)
            for o in objs:
                try:
                    m = pat.match(o.name)
                    if m:
                        max_idx = max(max_idx, int(m.group(1)))
                except Exception:
                    pass
            next_idx = max_idx + 1
        except Exception:
            next_idx = 1

        try:
            bpy.ops.mesh.primitive_cube_add(size=2, location=(0.0, 0.0, 0.0))
            cube = context.active_object
        except Exception:
            mesh = bpy.data.meshes.new('FuelTankMesh')
            cube = bpy.data.objects.new('FuelTank', mesh)
            try:
                context.scene.collection.objects.link(cube)
            except Exception:
                pass

        name = f"FuelTank({next_idx})_{invspace}"
        try:
            cube.name = name
        except Exception:
            pass

        try:
            for col in list(cube.users_collection):
                try:
                    col.objects.unlink(cube)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if basic_col is not None:
                try:
                    basic_col.objects.link(cube)
                except Exception:
                    try:
                        context.scene.collection.objects.link(cube)
                    except Exception:
                        pass
        except Exception:
            pass

        self.report({'INFO'}, f"Summoned fuel tank: {name}")
        organize_scene_collections()
        return {'FINISHED'}


class DYNMX_OT_set_fueltank(bpy.types.Operator):
    """In Edit Mode: create a fuel tank cube enclosing selected faces"""
    bl_idname = "dynamx.set_fueltank"
    bl_label = "Set Fuel Tank"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        sel_faces = [f for f in bm.faces if f.select]
        if not sel_faces:
            self.report({'ERROR'}, 'No faces selected')
            return {'CANCELLED'}

        verts = set()
        for f in sel_faces:
            for v in f.verts:
                verts.add(v)
        world_pts = [obj.matrix_world @ v.co for v in verts]
        xs = [p.x for p in world_pts]
        ys = [p.y for p in world_pts]
        zs = [p.z for p in world_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)
        world_center = Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
        world_size = Vector((max_x - min_x, max_y - min_y, max_z - min_z))

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        try:
            bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
            cube = context.active_object
        except Exception:
            mesh = bpy.data.meshes.new('FuelTankMesh')
            cube = bpy.data.objects.new('FuelTank', mesh)
            try:
                context.scene.collection.objects.link(cube)
            except Exception:
                pass

        try:
            cube.location = world_center
        except Exception:
            pass
        try:
            sx = world_size.x / 2.0 if world_size.x > 0 else 0.001
            sy = world_size.y / 2.0 if world_size.y > 0 else 0.001
            sz = world_size.z / 2.0 if world_size.z > 0 else 0.001
            cube.scale = Vector((sx, sy, sz))
        except Exception:
            pass
        scene = context.scene
        invspace = int(getattr(scene, 'dynamx_fueltank_size', 200))
        try:
            from . import utils as _utils
            extras = _utils.ensure_collection('Extras', scene=context.scene)
            basic_col = _utils.ensure_collection('BasicAddon', parent=extras, scene=context.scene)
        except Exception:
            extras = bpy.data.collections.get('Extras')
            basic_col = bpy.data.collections.get('BasicAddon')
            if not extras:
                try:
                    extras = bpy.data.collections.new('Extras')
                    context.scene.collection.children.link(extras)
                except Exception:
                    extras = None
            if basic_col is None and extras is not None:
                try:
                    basic_col = bpy.data.collections.new('BasicAddon')
                    extras.children.link(basic_col)
                except Exception:
                    try:
                        basic_col = bpy.data.collections.new('BasicAddon')
                        context.scene.collection.children.link(basic_col)
                    except Exception:
                        basic_col = None

        next_idx = 1
        try:
            max_idx = 0
            import re as _re
            pat = _re.compile(r'^FuelTank\((\d+)\)_')
            objs = list(basic_col.objects) if basic_col else list(bpy.data.objects)
            for o in objs:
                try:
                    m = pat.match(o.name)
                    if m:
                        max_idx = max(max_idx, int(m.group(1)))
                except Exception:
                    pass
            next_idx = max_idx + 1
        except Exception:
            next_idx = 1

        name = f"FuelTank({next_idx})_{invspace}"
        try:
            cube.name = name
        except Exception:
            pass
        try:
            for col in list(cube.users_collection):
                try:
                    col.objects.unlink(cube)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if basic_col is not None:
                try:
                    basic_col.objects.link(cube)
                except Exception:
                    try:
                        context.scene.collection.objects.link(cube)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
        except Exception:
            pass

        self.report({'INFO'}, f"Set fuel tank: {name}")
        return {'FINISHED'}


class DYNMX_OT_set_light(bpy.types.Operator):
    """Set a named light object or separate selected faces into a light part"""
    bl_idname = "dynamx.set_light"
    bl_label = "Set Light Part"
    bl_options = {'REGISTER', 'UNDO'}

    light_type = bpy.props.EnumProperty(
        items=[('BLINKER','Blinker','Blinker'),('HEAD','Headlight','Headlight'),('BRAKE','Brake','Brake'),('REVERSE','Reverse','Reverse'),('SIREN','Siren','Siren')],
        name='Light Type'
    )
    side = bpy.props.EnumProperty(
        items=[('LEFT','Left','Left'),('RIGHT','Right','Right'),('NONE','None','None')],
        name='Side',
        default='NONE'
    )

    @classmethod
    def poll(cls, context):
        return (context.mode in ('OBJECT','EDIT_MESH'))

    def execute(self, context):
        lt = self.light_type
        side = self.side
        partname = None
        if lt == 'BLINKER':
            partname = f"blinker_{'left' if side=='LEFT' else 'right' if side=='RIGHT' else 'center'}"
            alt = f"left_blinker" if side=='LEFT' else ("right_blinker" if side=='RIGHT' else None)
        elif lt == 'HEAD':
            partname = 'headlight'
            alt = 'headlight'
        elif lt == 'BRAKE':
            partname = 'brakelights'
            alt = 'brakelights'
        elif lt == 'REVERSE':
            partname = 'reverselights'
            alt = 'reverselights'
        elif lt == 'SIREN':
            partname = 'sirenlight'
            alt = 'sirenlight'
        else:
            partname = 'lightpart'
            alt = partname

        if context.mode == 'OBJECT' and context.active_object is not None:
            obj = context.active_object
            try:
                obj.name = partname
            except Exception:
                pass
            try:
                if getattr(obj, 'data', None) is not None:
                    obj.data.name = obj.name
            except Exception:
                pass
            lights_col = bpy.data.collections.get('Lights')
            if not lights_col:
                lights_col = bpy.data.collections.new('Lights')
                try:
                    context.scene.collection.children.link(lights_col)
                except Exception:
                    pass
            try:
                for col in list(obj.users_collection):
                    try:
                        col.objects.unlink(obj)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                if obj.name not in lights_col.objects:
                    lights_col.objects.link(obj)
            except Exception:
                pass
            try:
                _enable_basic_light_textures_for_object(obj, partname, scene=context.scene)
            except Exception:
                pass
            try:
                if obj.name not in lights_col.objects:
                    lights_col.objects.link(obj)
            except Exception:
                pass
            self.report({'INFO'}, f"Set object as {partname}")
            organize_scene_collections()
            return {'FINISHED'}

        if context.mode == 'EDIT_MESH':
            try:
                prev_mode = context.mode
                bpy.ops.mesh.separate(type='SELECTED')
                bpy.ops.object.mode_set(mode='OBJECT')
                new_objs = [o for o in context.selected_objects if o.name != context.active_object.name]
                if not new_objs and context.selected_objects:
                    new_objs = context.selected_objects
                if new_objs:
                    new = new_objs[0]
                    try:
                        new.name = partname
                    except Exception:
                        pass
                    try:
                        if getattr(new, 'data', None) is not None:
                            new.data.name = new.name
                    except Exception:
                        pass
                    lights_col = bpy.data.collections.get('Lights')
                    if not lights_col:
                        lights_col = bpy.data.collections.new('Lights')
                        try:
                            context.scene.collection.children.link(lights_col)
                        except Exception:
                            pass
                    try:
                        for col in list(new.users_collection):
                            try:
                                col.objects.unlink(new)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        lights_col.objects.link(new)
                    except Exception:
                        pass
                    try:
                        _enable_basic_light_textures_for_object(new, partname, scene=context.scene)
                    except Exception:
                        pass
                    try:
                        for o in bpy.data.objects:
                            if o.type == 'MESH' and o.mode == 'EDIT':
                                context.view_layer.objects.active = o
                                break
                        bpy.ops.object.mode_set(mode='EDIT')
                    except Exception:
                        pass
                    self.report({'INFO'}, f"Separated selection into {partname}")
                    organize_scene_collections()
                    return {'FINISHED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to separate faces: {e}")
                return {'CANCELLED'}

        self.report({'ERROR'}, 'No active object or selection to set light')
        return {'CANCELLED'}


def _apply_light_part(context, partname):
    """Helper used by wrapper operators to perform the same work as DYNMX_OT_set_light
    but without going through bpy.ops with kwargs. This renames the active object in
    Object mode or separates selected faces in Edit mode and links the result into
    the 'Lights' collection.
    Returns (True, message) on success, (False, message) on failure.
    """
    if context.mode == 'OBJECT' and context.active_object is not None:
        obj = context.active_object
        try:
            obj.name = partname
        except Exception:
            pass
        try:
            if getattr(obj, 'data', None) is not None:
                obj.data.name = obj.name
        except Exception:
            pass
        lights_col = bpy.data.collections.get('Lights')
        if not lights_col:
            lights_col = bpy.data.collections.new('Lights')
            try:
                context.scene.collection.children.link(lights_col)
            except Exception:
                pass
        try:
            for col in list(obj.users_collection):
                try:
                    col.objects.unlink(obj)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if obj.name not in lights_col.objects:
                lights_col.objects.link(obj)
        except Exception:
            pass
        try:
            _enable_basic_light_textures_for_object(obj, partname, scene=context.scene)
        except Exception:
            pass
        return True, f"Set object as {partname}"

    if context.mode == 'EDIT_MESH':
        try:
            bpy.ops.mesh.separate(type='SELECTED')
            bpy.ops.object.mode_set(mode='OBJECT')
            new_objs = [o for o in context.selected_objects if o.name != context.active_object.name]
            if not new_objs and context.selected_objects:
                new_objs = context.selected_objects
            if new_objs:
                new = new_objs[0]
                try:
                    new.name = partname
                except Exception:
                    pass
                try:
                    if getattr(new, 'data', None) is not None:
                        new.data.name = new.name
                except Exception:
                    pass
                lights_col = bpy.data.collections.get('Lights')
                if not lights_col:
                    lights_col = bpy.data.collections.new('Lights')
                    try:
                        context.scene.collection.children.link(lights_col)
                    except Exception:
                        pass
                try:
                    for col in list(new.users_collection):
                        try:
                            col.objects.unlink(new)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    lights_col.objects.link(new)
                except Exception:
                    pass
                try:
                    _enable_basic_light_textures_for_object(new, partname, scene=context.scene)
                except Exception:
                    pass
                try:
                    _enable_basic_light_textures_for_object(new, partname, scene=context.scene)
                except Exception:
                    pass
                try:
                    for o in bpy.data.objects:
                        if o.type == 'MESH' and o.mode == 'EDIT':
                            context.view_layer.objects.active = o
                            break
                    bpy.ops.object.mode_set(mode='EDIT')
                except Exception:
                    pass
                return True, f"Separated selection into {partname}"
        except Exception as e:
            return False, f"Failed to separate faces: {e}"

    return False, 'No active object or selection to set light'



class DYNMX_OT_set_blinker_left(bpy.types.Operator):
    """Wrapper: set blinker left"""
    bl_idname = 'dynamx.set_blinker_left'
    bl_label = 'Set Blinker Left'

    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'blinker_left')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_blinker_right(bpy.types.Operator):
    """Wrapper: set blinker right"""
    bl_idname = 'dynamx.set_blinker_right'
    bl_label = 'Set Blinker Right'

    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'blinker_right')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_headlight(bpy.types.Operator):
    """Wrapper: set headlight"""
    bl_idname = 'dynamx.set_headlight'
    bl_label = 'Set HeadLight'

    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'headlight')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_brakelights(bpy.types.Operator):
    """Wrapper: set brake lights"""
    bl_idname = 'dynamx.set_brakelights'
    bl_label = 'Set BrakeLights'

    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'brakelights')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_reverse(bpy.types.Operator):
    """Wrapper: set reverse lights"""
    bl_idname = 'dynamx.set_reverse'
    bl_label = 'Set Reverse'

    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'reverselights')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_sirenlight(bpy.types.Operator):
    """Wrapper: set siren light"""
    bl_idname = 'dynamx.set_sirenlight'
    bl_label = 'Set SirenLight'

    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'sirenlight')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_lightbar_blue_l(bpy.types.Operator):
    bl_idname = 'dynamx.set_lightbar_blue_l'
    bl_label = 'Lightbar Blue Left'
    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'lightbar_blue_l')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_lightbar_blue_r(bpy.types.Operator):
    bl_idname = 'dynamx.set_lightbar_blue_r'
    bl_label = 'Lightbar Blue Right'
    def execute(self, context):
        try:
            try:
                if context.mode == 'OBJECT' and context.active_object is None:
                    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0.0, 0.0, 0.0))
            except Exception:
                pass
            ok, msg = _apply_light_part(context, 'lightbar_blue_r')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f'Failed to call set_light: {e}')
            return {'CANCELLED'}


class DYNMX_OT_set_dot_blue_l(bpy.types.Operator):
    bl_idname = 'dynamx.set_dot_blue_l'
    bl_label = 'Dot Blue Left'
    def execute(self, context):
            ok, msg = _apply_light_part(context, 'dot_blue_l')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}


class DYNMX_OT_set_dot_blue_r(bpy.types.Operator):
    bl_idname = 'dynamx.set_dot_blue_r'
    bl_label = 'Dot Blue Right'
    def execute(self, context):
            ok, msg = _apply_light_part(context, 'dot_blue_r')
            if ok:
                self.report({'INFO'}, msg)
                organize_scene_collections()
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, msg)
                return {'CANCELLED'}


class DYNMX_OT_export_lights(bpy.types.Operator):
    """Export configured lights into the vehicle dynx file"""
    bl_idname = 'dynamx.export_lights'
    bl_label = 'Export Lights'

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return bool(getattr(scene, 'dynamx_pack_path', None) and getattr(scene, 'dynamx_pack_name', None) and getattr(scene, 'dynamx_vehicle_name', None))

    def execute(self, context):
        scene = context.scene
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip()
        vehicle_name = scene.dynamx_vehicle_name.strip()
        pack_name_safe = pack_name.replace(' ', '_').lower()
        vehicle_name_safe = vehicle_name.replace(' ', '_').lower()
        try:
            is_trailer_ws = (context.workspace.name == 'Dynamx - Trailer')
        except Exception:
            is_trailer_ws = False
        prefix = 'trailer' if is_trailer_ws else 'vehicle'
        vehicle_file = os.path.join(pack_path, pack_name_safe, 'vehicle', vehicle_name_safe, f"{prefix}_{vehicle_name_safe}.dynx")

        if not os.path.exists(vehicle_file):
            self.report({'ERROR'}, f"Vehicle file not found: {vehicle_file}")
            return {'CANCELLED'}

        blocks = []

        def add_light_block(light_id, partname, textures='on', blink_seq='-1 20'):
            blocks.append((light_id, partname, textures, blink_seq))

        objs = {o.name: o for o in bpy.data.objects}
        def exists(name):
            return name in objs

        way_sender = bool(getattr(scene, 'dynamx_way_sender', False))
        siren_on_token = str(getattr(scene, 'dynamx_sirenlight_on_token', 'lightbar_on')).strip() or 'lightbar_on'

        if exists('blinker_left'):
            add_light_block(2, 'blinker_left', 'on', '8 15')
        if exists('blinker_right'):
            add_light_block(3, 'blinker_right', 'on', '8 15')
        if exists('headlight'):
            add_light_block(4, 'headlight', 'on', '-1 20')
        if exists('brakelights'):
            add_light_block(6, 'brakelights', 'on', '-1 20')
        if exists('reverselights'):
            add_light_block(5, 'reverselights', 'on', '-1 20')
        if exists('sirenlight'):
            add_light_block(7, 'sirenlight', siren_on_token, '-1 20')
        if exists('lightbar_blue_l'):
            add_light_block(7, 'lightbar_blue_l', siren_on_token, '-1 -1 12 14 16 18 20')
        if exists('lightbar_blue_r'):
            add_light_block(7, 'lightbar_blue_r', siren_on_token, '-1 -1 2 4 6 8 20')
        if exists('dot_blue_l'):
            add_light_block(7, 'dot_blue_l', siren_on_token, '-1 -1 12 14 16 18 20')
        if exists('dot_blue_r'):
            add_light_block(7, 'dot_blue_r', siren_on_token, '-1 -1 2 4 6 8 20')

        if way_sender:
            way_parts = [
                (2, 'blitzer', 'on', '2 6 8 12 18'),
                (2, 'blinkeru', 'on', '16 31'),
                (2, 'blinkerl', 'on', '16 31'),
                (2, 'blinkerol', 'on', '16 31'),
                (2, 'blinkerm', 'on', '16 31'),
                (2, 'blinkeror', 'on', '16 31'),
                (3, 'blitzer', 'on', '2 6 8 12 18'),
                (3, 'blinkeru', 'on', '16 31'),
                (3, 'blinkerr', 'on', '16 31'),
                (3, 'blinkerol', 'on', '16 31'),
                (3, 'blinkerm', 'on', '16 31'),
                (3, 'blinkeror', 'on', '16 31'),
            ]
            for (lid, pname, textures, seq) in way_parts:
                if not any((lid == b[0] and pname.lower() == b[1].lower()) for b in blocks):
                    blocks.append((lid, pname, textures, seq))

        basics_lines = []
        basics_lines.append('BasicsAddon#Op{')
        basics_lines.append(f'    HornSound: horn/car')
        if exists('sirenlight') or exists('lightbar_blue_l') or exists('lightbar_blue_r'):
            basics_lines.append('    SirenSound: siren/polizei')
        if way_sender or exists('blinker_left'):
            basics_lines.append('    TurnSignalLeftLightSource: 2')
        if way_sender or exists('blinker_right'):
            basics_lines.append('    TurnSignalRightLightSource: 3')
        if exists('headlight'):
            basics_lines.append('    HeadLightsSource: 4')
        if exists('reverselights'):
            basics_lines.append('    ReverseLightsSource: 5')
        if exists('brakelights'):
            basics_lines.append('    BrakeLightsSource: 6')
        if exists('sirenlight') or exists('lightbar_blue_l') or exists('lightbar_blue_r'):
            basics_lines.append('    SirenLightSource: 7')
        basics_lines.append('}')

        def _category_for(pname):
            name = pname.lower()
            if 'lightbar' in name or 'siren' in name:
                return 'RTK'
            if 'dot' in name:
                return 'Dot'
            return 'Lights'

        general_blocks = []
        rtk_blocks = []
        dot_blocks = []
        for (lid, pname, textures, seq) in blocks:
            name = pname.lower()
            is_rtk = ('lightbar' in name) or ('siren' in name)
            is_dot = 'dot' in name
            if is_rtk:
                rtk_blocks.append((lid, pname, textures, seq))
            if is_dot:
                dot_blocks.append((lid, pname, textures, seq))
            if 'blitzer' in name:
                general_blocks.append((lid, pname, textures, seq))
            elif not is_rtk and not is_dot:
                general_blocks.append((lid, pname, textures, seq))

        def _fmt_block(lid, pname, textures, seq):
            s = f"Light_{pname}#Op{{\n"
            s += f"    LightId: {lid}\n"
            s += f"    PartName: {pname}\n"
            s += f"    Textures: {textures}\n"
            s += f"    BlinkSequenceTicks: {seq}\n"
            s += f"}}\n"
            return s

        light_text = ''
        for (lid, pname, textures, seq) in general_blocks:
            light_text += _fmt_block(lid, pname, textures, seq)

        rtk_text = ''
        for (lid, pname, textures, seq) in rtk_blocks:
            rtk_text += _fmt_block(lid, pname, textures, seq)

        dot_text = ''
        for (lid, pname, textures, seq) in dot_blocks:
            dot_text += _fmt_block(lid, pname, textures, seq)

        rtk_header = "// ------------- <RTK> --------------\n"
        dot_header = "// ------------- <DOT> --------------\n"

        try:
            with open(vehicle_file, 'r', encoding='utf-8') as vf:
                vtext = vf.read()
        except Exception:
            vtext = ''

        try:
            try:
                vtext_clean = re.sub(r'(?is)BasicsAddon#Op\s*\{.*?\}', '', vtext)
                vtext_clean = re.sub(r'(?is)Light_[^\s#]+#Op\s*\{.*?\}\s*', '', vtext_clean)
                vtext_clean = re.sub(r'(?mi)^\s*//\s*-+\s*<RTK>\s*-+\s*\n', '', vtext_clean)
                vtext_clean = re.sub(r'(?mi)^\s*//\s*-+\s*<DOT>\s*-+\s*\n', '', vtext_clean)
            except Exception:
                vtext_clean = vtext


            m = re.search(r'(?mi)^.*LIGHTS.*$', vtext_clean)
            if m:
                marker_start = m.start()
                marker_line_end_idx = vtext_clean.find('\n', m.end())
                if marker_line_end_idx == -1:
                    marker_line_end_idx = len(vtext_clean)
                else:
                    marker_line_end_idx += 1
                before = vtext_clean[:marker_start].rstrip('\n') + '\n\n'
                marker_line = vtext_clean[marker_start:marker_line_end_idx].rstrip('\n') + '\n'
                rest = vtext_clean[marker_line_end_idx:]
                rest = '\n' + rest.lstrip('\n') if rest is not None else ''
                basics_str = '\n'.join(basics_lines)
                light_str = light_text.rstrip('\n')
                insert_block = marker_line + '\n' + basics_str + '\n\n'
                if light_str:
                    insert_block += light_str + '\n\n'
                if rtk_text:
                    insert_block = insert_block.rstrip('\n') + '\n' + rtk_header + rtk_text.rstrip('\n') + '\n\n'
                if dot_text:
                    insert_block = insert_block.rstrip('\n') + '\n' + dot_header + dot_text.rstrip('\n') + '\n\n'
                new_text = before + insert_block + rest.lstrip('\n')
            else:
                basics_str = '\n'.join(basics_lines)
                light_str = light_text.rstrip('\n')
                new_text = vtext_clean.rstrip('\n') + '\n' + basics_str + '\n\n'
                if light_str:
                    new_text += light_str + '\n\n'
                if rtk_text:
                    new_text = new_text.rstrip('\n') + '\n' + rtk_header + rtk_text.rstrip('\n') + '\n\n'
                if dot_text:
                    new_text = new_text.rstrip('\n') + '\n' + dot_header + dot_text.rstrip('\n') + '\n\n'

            with open(vehicle_file, 'w', encoding='utf-8') as vf:
                vf.write(new_text)
        except Exception as e:
            self.report({'ERROR'}, f'Failed to write lights to vehicle file: {e}')
            return {'CANCELLED'}

        self.report({'INFO'}, f'Exported lights (count={len(blocks)}) to vehicle file')
        return {'FINISHED'}


class DYNMX_OT_export_basics(bpy.types.Operator):
    """Export basic addon objects (license plates, storage, fuel tanks) into vehicle dynx file"""
    bl_idname = 'dynamx.export_basics'
    bl_label = 'Export Basic Addon'

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return bool(getattr(scene, 'dynamx_pack_path', None) and getattr(scene, 'dynamx_pack_name', None) and getattr(scene, 'dynamx_vehicle_name', None))

    def execute(self, context):
        scene = context.scene
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip()
        vehicle_name = scene.dynamx_vehicle_name.strip()
        pack_name_safe = pack_name.replace(' ', '_').lower()
        vehicle_name_safe = vehicle_name.replace(' ', '_').lower()
        try:
            is_trailer_ws = (context.workspace.name == 'Dynamx - Trailer')
        except Exception:
            is_trailer_ws = False
        prefix = 'trailer' if is_trailer_ws else 'vehicle'
        vehicle_file = os.path.join(pack_path, pack_name_safe, 'vehicle', vehicle_name_safe, f"{prefix}_{vehicle_name_safe}.dynx")

        if not os.path.exists(vehicle_file):
            self.report({'ERROR'}, f"Vehicle file not found: {vehicle_file}")
            return {'CANCELLED'}

        blocks = []

        lp_objs = []
        try:
            for o in bpy.data.objects:
                if o.name.startswith('LiscensePlate(') or o.name.startswith('LiscensePlate'):
                    lp_objs.append(o)
        except Exception:
            lp_objs = []

        for o in lp_objs:
            try:
                m = re.match(r'^LiscensePlate\((\d+)\)', o.name)
                idx = int(m.group(1)) if m else 0
            except Exception:
                idx = 0
            try:
                pos = o.matrix_world.to_translation()
                pos_str = f"{pos.x:.6f} {pos.y:.6f} {pos.z:.6f}"
            except Exception:
                pos_str = "0.0 0.0 0.0"
            try:
                sc = o.matrix_world.to_scale()
                scale_str = f"{sc.x:.6f} {sc.y:.6f} {sc.z:.6f}"
            except Exception:
                scale_str = "1.0 1.0 1.0"
            try:
                rot = o.matrix_world.to_euler('XYZ')
                rx = math.degrees(rot.x) - 90.0
                ry = math.degrees(rot.y)
                rz = math.degrees(rot.z) + 180.0
                rot_str = f"{rx:.2f} {rz:.2f} {ry:.2f}"
            except Exception:
                rot_str = "0.0 0.0 0.0"
            try:
                pattern = getattr(o, 'data', None)
                if pattern and hasattr(pattern, 'body'):
                    pat = pattern.body.strip()
                else:
                    pat = ''
            except Exception:
                pat = ''
            block_name = f"ImmatriculationPlate_{idx}%Op"
            block_lines = [f"{block_name}{{", f"    Position: {pos_str}", f"    Scale: {scale_str}", f"    Rotation: {rot_str}", f"    Pattern: {pat}", f"}}\n"]
            blocks.append('\n'.join(block_lines))

        try:
            import re as _re
            storages = []
            for o in bpy.data.objects:
                if o.name.startswith('Storage(') or o.name.startswith('Storage'):
                    storages.append(o)
        except Exception:
            storages = []

        for o in storages:
            try:
                m = re.match(r'^Storage\((\d+)\)_(\d+)', o.name)
                if m:
                    idx = int(m.group(1))
                    size_val = int(m.group(2))
                else:
                    m2 = re.match(r'^Storage\((\d+)\)', o.name)
                    idx = int(m2.group(1)) if m2 else 0
                    size_val = int(getattr(scene, 'dynamx_storage_size', 9))
            except Exception:
                idx = 0
                size_val = int(getattr(scene, 'dynamx_storage_size', 9))
            try:
                sc = o.matrix_world.to_scale()
                scale_str = f"{sc.x:.6f} {sc.y:.6f} {sc.z:.6f}"
            except Exception:
                scale_str = "1.0 1.0 1.0"
            try:
                pos = o.matrix_world.to_translation()
                pos_str = f"{pos.x:.6f} {pos.y:.6f} {pos.z:.6f}"
            except Exception:
                pos_str = "0.0 0.0 0.0"
            sname = f"Storage_{idx}#Op"
            sblock = [f"{sname}{{", f"    Scale: {scale_str}", f"    Position: {pos_str}", f"    StorageSize: {size_val}", f"}}\n"]
            blocks.append('\n'.join(sblock))

        try:
            fuel_objs = []
            for o in bpy.data.objects:
                if o.name.startswith('FuelTank(') or o.name.startswith('FuelTank'):
                    fuel_objs.append(o)
        except Exception:
            fuel_objs = []

        for o in fuel_objs:
            try:
                m = re.match(r'^FuelTank\((\d+)\)_(\d+)', o.name)
                if m:
                    idx = int(m.group(1))
                    tank_size = int(m.group(2))
                else:
                    m2 = re.match(r'^FuelTank\((\d+)\)', o.name)
                    idx = int(m2.group(1)) if m2 else 0
                    tank_size = int(getattr(scene, 'dynamx_fueltank_size', 200))
            except Exception:
                idx = 0
                tank_size = int(getattr(scene, 'dynamx_fueltank_size', 200))
            try:
                pos = o.matrix_world.to_translation()
                pos_str = f"{pos.x:.6f} {pos.y:.6f} {pos.z:.6f}"
            except Exception:
                pos_str = "0.0 0.0 0.0"
            try:
                sc = o.matrix_world.to_scale()
                scale_str = f"{sc.x:.6f} {sc.y:.6f} {sc.z:.6f}"
            except Exception:
                scale_str = "1.0 1.0 1.0"
            fname = f"FuelTank_{idx}#Op"
            fblock = [f"{fname}{{", f"    Position: {pos_str}", f"    Scale: {scale_str}", f"    TankSize: {tank_size}", f"    FuelConsumption: 1", f"}}\n"]
            blocks.append('\n'.join(fblock))

        try:
            try:
                with open(vehicle_file, 'r', encoding='utf-8') as vf:
                    vtext = vf.read()
            except Exception:
                vtext = ''

            vtext_clean = vtext
            try:
                vtext_clean = re.sub(r'(?is)ImmatriculationPlate_\d+#Op\s*\{.*?\}\s*', '', vtext_clean)
                vtext_clean = re.sub(r'(?is)Storage_\d+#Op\s*\{.*?\}\s*', '', vtext_clean)
                vtext_clean = re.sub(r'(?is)FuelTank_\d+#Op\s*\{.*?\}\s*', '', vtext_clean)
            except Exception:
                vtext_clean = vtext

            extras_text = ''
            if blocks:
                extras_text = '\n'.join(blocks)

            m = re.search(r'(?mi)^.*EXTRAS.*$', vtext_clean)
            if m:
                marker_start = m.start()
                marker_line_end_idx = vtext_clean.find('\n', m.end())
                if marker_line_end_idx == -1:
                    marker_line_end_idx = len(vtext_clean)
                else:
                    marker_line_end_idx += 1
                before = vtext_clean[:marker_start].rstrip('\n') + '\n\n'
                marker_line = vtext_clean[marker_start:marker_line_end_idx].rstrip('\n') + '\n'
                rest = vtext_clean[marker_line_end_idx:]

                insert_block = marker_line + '\n' + extras_text.rstrip('\n') + '\n\n'
                new_text = before + insert_block + rest.lstrip('\n')
            else:
                new_text = vtext_clean.rstrip('\n')
                if extras_text:
                    new_text += '\n\n' + extras_text.rstrip('\n') + '\n\n'

            with open(vehicle_file, 'w', encoding='utf-8') as vf:
                vf.write(new_text)
        except Exception as e:
            self.report({'ERROR'}, f'Failed to write basics to vehicle file: {e}')
            return {'CANCELLED'}

        self.report({'INFO'}, f'Exported Basic Addon blocks (count={len(blocks)})')
        return {'FINISHED'}




class DYNMX_OT_set_door(bpy.types.Operator):
    """Set the selected object as a Door: create a Door proxy that fully encloses the object's WORLD AABB.
    The operator will NOT move the object's visible geometry; it will move the object's origin to the AABB center
    while keeping world vertex positions unchanged, and it stores door metadata on the original object as custom props.
    """
    bl_idname = 'dynamx.set_door'
    bl_label = 'Set Door'

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        door_name = getattr(scene, 'dynamx_door_name', 'door')
        open_angle = float(getattr(scene, 'dynamx_door_open_angle', 1.0))
        axis = getattr(scene, 'dynamx_door_axis', 'Z_ROT')

        try:
            from . import utils as _utils
            extras_col = _utils.ensure_collection('Extras', scene=context.scene)
            doors_col = _utils.ensure_collection('Doors', parent=extras_col, scene=context.scene)
        except Exception:
            doors_col = bpy.data.collections.get('Doors')
            if not doors_col:
                doors_col = bpy.data.collections.new('Doors')
                try:
                    extras = bpy.data.collections.get('Extras')
                    if extras:
                        extras.children.link(doors_col)
                    else:
                        context.scene.collection.children.link(doors_col)
                except Exception:
                    try:
                        context.scene.collection.children.link(doors_col)
                    except Exception:
                        pass

        original_origin = obj.matrix_world.to_translation()

        try:
            bb_local = [Vector(c) for c in obj.bound_box]
            world_pts = [obj.matrix_world @ p for p in bb_local]
            xs = [p.x for p in world_pts]
            ys = [p.y for p in world_pts]
            zs = [p.z for p in world_pts]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            min_z, max_z = min(zs), max(zs)
            center = Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
            size = Vector((max_x - min_x, max_y - min_y, max_z - min_z))
        except Exception:
            center = obj.matrix_world.to_translation()
            size = obj.dimensions if getattr(obj, 'dimensions', None) is not None else Vector((0.001, 0.001, 0.001))

        try:
            hx = size.x / 2.0 if size.x > 0 else 0.001
            hy = size.y / 2.0 if size.y > 0 else 0.001
            hz = size.z / 2.0 if size.z > 0 else 0.001

            corners_world = [
                Vector((center.x - hx, center.y - hy, center.z - hz)),
                Vector((center.x + hx, center.y - hy, center.z - hz)),
                Vector((center.x + hx, center.y + hy, center.z - hz)),
                Vector((center.x - hx, center.y + hy, center.z - hz)),
                Vector((center.x - hx, center.y - hy, center.z + hz)),
                Vector((center.x + hx, center.y - hy, center.z + hz)),
                Vector((center.x + hx, center.y + hy, center.z + hz)),
                Vector((center.x - hx, center.y + hy, center.z + hz)),
            ]

            try:
                rot_euler = obj.matrix_world.to_euler('XYZ')
                rot_mat3 = rot_euler.to_matrix()
            except Exception:
                rot_mat3 = Matrix.Identity(3)

            try:
                inv_rot = rot_mat3.inverted()
            except Exception:
                inv_rot = Matrix.Identity(3)

            local_verts = [inv_rot @ (pt - original_origin) for pt in corners_world]

            faces = [
                (0, 1, 2, 3),
                (4, 5, 6, 7),
                (0, 1, 5, 4),
                (1, 2, 6, 5),
                (2, 3, 7, 6),
                (3, 0, 4, 7),
            ]

            mesh_name = f"DoorMesh_{door_name}"
            obj_name = f"Door_{door_name}"
            mesh = bpy.data.meshes.new(mesh_name)
            mesh.from_pydata([tuple(v) for v in local_verts], [], faces)
            mesh.update()

            cube = bpy.data.objects.new(obj_name, mesh)
            try:
                mw = rot_mat3.to_4x4()
                mw.translation = original_origin
                cube.matrix_world = mw
            except Exception:
                cube.matrix_world = Matrix.Translation(original_origin)

            try:
                ang = float(open_angle)
                try:
                    cur_world_eul = cube.matrix_world.to_euler('XYZ')
                except Exception:
                    cur_world_eul = Euler((0.0, 0.0, 0.0), 'XYZ')

                if axis == 'X_ROT':
                    cur_world_eul.x += ang
                elif axis == 'Y_ROT':
                    cur_world_eul.z += ang
                else:
                    cur_world_eul.y += ang

                try:
                    new_mw = cur_world_eul.to_matrix().to_4x4()
                    new_mw.translation = cube.matrix_world.to_translation()
                    cube.matrix_world = new_mw
                except Exception:
                    try:
                        cube.rotation_mode = 'XYZ'
                        cube.rotation_euler = cur_world_eul
                    except Exception:
                        pass
            except Exception:
                pass
            cube.scale = Vector((1.0, 1.0, 1.0))

            try:
                context.scene.collection.objects.link(cube)
            except Exception:
                try:
                    doors_col.objects.link(cube)
                except Exception:
                    pass
        except Exception:
            try:
                bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
                cube = context.active_object
                cube.location = center
                cube.scale = Vector((hx, hy, hz))
            except Exception:
                mesh = bpy.data.meshes.new('DoorProxyMesh')
                cube = bpy.data.objects.new('DoorProxy', mesh)
                try:
                    context.scene.collection.objects.link(cube)
                except Exception:
                    pass

        try:
            old_t = cube.matrix_world.to_translation()
            target_t = original_origin
            delta_world = old_t - target_t
            try:
                local_shift = cube.matrix_world.to_3x3().inverted() @ delta_world
            except Exception:
                local_shift = Vector((delta_world.x, delta_world.y, delta_world.z))

            if getattr(cube, 'type', None) == 'MESH' and getattr(cube.data, 'vertices', None):
                prev_mode = None
                try:
                    if cube.mode == 'EDIT':
                        prev_mode = cube.mode
                        bpy.ops.object.mode_set(mode='OBJECT')
                except Exception:
                    prev_mode = None

                try:
                    for v in cube.data.vertices:
                        v.co += local_shift
                    cube.data.update()
                except Exception:
                    pass

                try:
                    if prev_mode == 'EDIT':
                        context.view_layer.objects.active = cube
                        bpy.ops.object.mode_set(mode='EDIT')
                except Exception:
                    pass

            try:
                mw = cube.matrix_world.copy()
                mw.translation = target_t
                cube.matrix_world = mw
            except Exception:
                pass
        except Exception:
            pass

        try:
            cube['dynamx_door_preview_axis'] = axis
            cube['dynamx_door_preview_angle'] = float(open_angle)
        except Exception:
            pass

        try:
            cube.name = f"DoorProxy_{door_name}"
        except Exception:
            pass
        try:
            for c in list(cube.users_collection):
                try:
                    c.objects.unlink(cube)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            doors_col.objects.link(cube)
        except Exception:
            try:
                context.scene.collection.objects.link(cube)
            except Exception:
                pass


        try:
            new_name = str(door_name).strip()
            if new_name:
                try:
                    obj.name = new_name
                except Exception:
                    pass
                try:
                    if getattr(obj, 'data', None) is not None:
                        obj.data.name = f"{new_name}_data"
                except Exception:
                    try:
                        if getattr(obj, 'data', None) is not None:
                            obj.data.name = new_name
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            obj['dynamx_door_name'] = door_name
        except Exception:
            pass
        try:
            obj['dynamx_door_open_angle'] = float(open_angle)
        except Exception:
            pass
        try:
            obj['dynamx_door_axis'] = axis
        except Exception:
            pass

        self.report({'INFO'}, f"Set door '{door_name}' and created proxy {cube.name}")
        return {'FINISHED'}


class DYNMX_OT_export_doors(bpy.types.Operator):
    """Export Doors found in Doors collection into vehicle file under EXTRAS"""
    bl_idname = 'dynamx.export_doors'
    bl_label = 'Export Doors'

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return bool(getattr(scene, 'dynamx_pack_path', None) and getattr(scene, 'dynamx_pack_name', None) and getattr(scene, 'dynamx_vehicle_name', None))

    def execute(self, context):
        scene = context.scene
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip()
        vehicle_name = scene.dynamx_vehicle_name.strip()
        pack_name_safe = pack_name.replace(' ', '_').lower()
        vehicle_name_safe = vehicle_name.replace(' ', '_').lower()
        try:
            is_trailer_ws = (context.workspace.name == 'Dynamx - Trailer')
        except Exception:
            is_trailer_ws = False
        prefix = 'trailer' if is_trailer_ws else 'vehicle'
        vehicle_file = os.path.join(pack_path, pack_name_safe, 'vehicle', vehicle_name_safe, f"{prefix}_{vehicle_name_safe}.dynx")

        if not os.path.exists(vehicle_file):
            self.report({'ERROR'}, f"Vehicle file not found: {vehicle_file}")
            return {'CANCELLED'}

        blocks = []
        doors_col = bpy.data.collections.get('Doors')
        if doors_col:
            objs = list(doors_col.objects)
        else:
            objs = []

        for o in objs:
            try:
                if o.name.startswith('DoorProxy_'):
                    doorname = o.name[len('DoorProxy_'):]
                else:
                    doorname = str(o.get('dynamx_door_name', o.name))
                doorname = doorname.strip()
            except Exception:
                doorname = o.name.replace(' ', '_')

            try:
                orig = bpy.data.objects.get(doorname)
            except Exception:
                orig = None

            try:
                car_pos = o.matrix_world.to_translation()
                car_pos_str = f"{car_pos.x:.4f} {car_pos.y:.4f} {car_pos.z:.4f}"
            except Exception:
                car_pos_str = "0.0000 0.0000 0.0000s"

            try:
                if orig is not None:
                    door_pos = orig.matrix_world.to_translation()
                else:
                    door_pos = o.matrix_world.to_translation()
                door_pos_str = f"{door_pos.x:.6f} {door_pos.y:.6f} {door_pos.z:.6f}"
            except Exception:
                door_pos_str = car_pos_str

            try:
                if orig is not None and 'dynamx_door_axis' in orig:
                    axis_val = orig['dynamx_door_axis']
                elif 'dynamx_door_preview_axis' in o:
                    axis_val = o['dynamx_door_preview_axis']
                else:
                    axis_val = 'Z_ROT'
            except Exception:
                axis_val = 'Z_ROT'

            try:
                if orig is not None and 'dynamx_door_open_angle' in orig:
                    ang = float(orig['dynamx_door_open_angle'])
                else:
                    ang = float(o.get('dynamx_door_preview_angle', 0.0))
            except Exception:
                ang = 0.0

            try:
                if ang < 0.0:
                    opened_limit = f"{ang:.2f} 0.00"
                else:
                    opened_limit = f"0.00 {ang:.2f}"
            except Exception:
                opened_limit = "0.00 0.00"

            closed_limit = "0.00 0.00"

            try:
                sign = -1 if ang < 0.0 else 1
                open_force = f"{sign} 200"
                close_force = f"{-sign} 300"
            except Exception:
                open_force = "1 200"
                close_force = "-1 300"

            try:
                name_safe = doorname.replace(' ', '_')
                b_lines = [
                    f"door{name_safe} {{",
                    f"\tPartName: {doorname}",
                    f"\tLocalCarAttachPoint: {car_pos_str}",
                    f"\tLocalDoorAttachPoint: {door_pos_str}",
                    "",
                    f"\tAxis: {axis_val}",
                    f"\tOpenedDoorAngleLimit: {opened_limit}",
                    f"\tClosedDoorAngleLimit: {closed_limit}",
                    f"\tDoorOpenForce: {open_force}",
                    f"\tDoorCloseForce: {close_force}",
                    f"}}\n",
                ]
                blocks.append('\n'.join(b_lines))
            except Exception:
                try:
                    pos = o.matrix_world.to_translation()
                    pos_str = f"{pos.x:.6f} {pos.y:.6f} {pos.z:.6f}"
                except Exception:
                    pos_str = "0.000000 0.000000 0.000000"
                blocks.append(f"door{name_safe} {{\n\tLocalCarAttachPoint: {pos_str}\n}}\n")

        try:
            try:
                with open(vehicle_file, 'r', encoding='utf-8') as vf:
                    vtext = vf.read()
            except Exception:
                vtext = ''

            vtext_clean = vtext
            try:
                vtext_clean = re.sub(r'(?is)(Door_[^\s#]+#Op\s*\{.*?\}\s*|door[^\s{]+\s*\{.*?\}\s*)', '', vtext_clean)
            except Exception:
                vtext_clean = vtext

            extras_text = ''
            if blocks:
                extras_text = '\n'.join(blocks)

            m = re.search(r'(?mi)^.*DOORS.*$', vtext_clean)
            if m:
                marker_start = m.start()
                marker_line_end_idx = vtext_clean.find('\n', m.end())
                if marker_line_end_idx == -1:
                    marker_line_end_idx = len(vtext_clean)
                else:
                    marker_line_end_idx += 1
                before = vtext_clean[:marker_start].rstrip('\n') + '\n\n'
                marker_line = vtext_clean[marker_start:marker_line_end_idx].rstrip('\n') + '\n'
                rest = vtext_clean[marker_line_end_idx:]
                insert_block = marker_line + '\n' + extras_text.rstrip('\n') + '\n\n'
                new_text = before + insert_block + rest.lstrip('\n')
            else:
                new_text = vtext_clean.rstrip('\n')
                if extras_text:
                    new_text += '\n\n' + extras_text.rstrip('\n') + '\n\n'

            with open(vehicle_file, 'w', encoding='utf-8') as vf:
                vf.write(new_text)
        except Exception as e:
            self.report({'ERROR'}, f'Failed to write doors to vehicle file: {e}')
            return {'CANCELLED'}

        self.report({'INFO'}, f'Exported doors (count={len(blocks)})')
        return {'FINISHED'}


class DYNMX_OT_set_hide_parts(bpy.types.Operator):
    """Take selected objects and write a HideablePart block into the vehicle file"""
    bl_idname = 'dynamx.set_hide_parts'
    bl_label = 'Set Parts'

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0 and bool(getattr(context.scene, 'dynamx_pack_path', None))

    def execute(self, context):
        scene = context.scene
        part_name = getattr(scene, 'dynamx_hide_part_name', 'part')
        default_state = bool(getattr(scene, 'dynamx_hide_default_state', True))

        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_name = scene.dynamx_pack_name.strip()
        vehicle_name = scene.dynamx_vehicle_name.strip()
        pack_name_safe = pack_name.replace(' ', '_').lower()
        vehicle_name_safe = vehicle_name.replace(' ', '_').lower()
        vehicle_file = os.path.join(pack_path, pack_name_safe, 'vehicle', vehicle_name_safe, f"vehicle_{vehicle_name_safe}.dynx")

        if not os.path.exists(vehicle_file):
            self.report({'ERROR'}, f"Vehicle file not found: {vehicle_file}")
            return {'CANCELLED'}

        names = [o.name for o in context.selected_objects]
        names_str = ' '.join(names)
        for o in context.selected_objects:
            try:
                o['dynamx_hide_part'] = part_name
                o['dynamx_hide_default_state'] = 'ON' if default_state else 'OFF'
            except Exception:
                pass

        try:
            with open(vehicle_file, 'r', encoding='utf-8') as vf:
                vtext = vf.read()
        except Exception:
            vtext = ''

        existing = re.findall(r'(?is)HideablePart(\d+)#Op\s*\{.*?\}', vtext)
        max_idx = 0
        try:
            for m in existing:
                try:
                    max_idx = max(max_idx, int(m))
                except Exception:
                    pass
        except Exception:
            pass
        next_idx = max_idx + 1

        block_name = f"HideablePart{next_idx}#Op"
        default_state_str = 'ON' if default_state else 'OFF'
        block_lines = [
            f"{block_name}{{",
            f"    PartName: {part_name}",
            f"    ObjectNames: {names_str}",
            f"    DefaultState: {default_state_str}",
            f"}}\n"
        ]
        block_text = '\n'.join(block_lines)

        try:
            pattern = re.compile(r'(?is)HideablePart\d+#Op\s*\{.*?PartName:\s*' + re.escape(part_name) + r'.*?\}', re.MULTILINE)
            vtext_clean = re.sub(pattern, '', vtext)
        except Exception:
            vtext_clean = vtext

        try:
            m = re.search(r'(?mi)^.*HIDEABLE PARTS.*$', vtext_clean)
            if m:
                marker_start = m.start()
                marker_line_end_idx = vtext_clean.find('\n', m.end())
                if marker_line_end_idx == -1:
                    marker_line_end_idx = len(vtext_clean)
                else:
                    marker_line_end_idx += 1
                before = vtext_clean[:marker_start].rstrip('\n') + '\n\n'
                marker_line = vtext_clean[marker_start:marker_line_end_idx].rstrip('\n') + '\n'
                rest = vtext_clean[marker_line_end_idx:]
                insert_block = marker_line + '\n' + block_text.rstrip('\n') + '\n\n'
                new_text = before + insert_block + rest.lstrip('\n')
            else:
                new_text = vtext_clean.rstrip('\n')
                new_text += '\n\n' + block_text.rstrip('\n') + '\n\n'

            with open(vehicle_file, 'w', encoding='utf-8') as vf:
                vf.write(new_text)
        except Exception as e:
            self.report({'ERROR'}, f'Failed to write hide part to vehicle file: {e}')
            return {'CANCELLED'}

        self.report({'INFO'}, f'Wrote HideablePart: {part_name} (objects={len(names)})')
        return {'FINISHED'}


classes = (
    DYNMX_OT_summon_license_plate,
    DYNMX_OT_summon_storage,
    DYNMX_OT_set_storage,
    DYNMX_OT_import_wheel,
    DYNMX_OT_summon_fueltank,
    DYNMX_OT_set_fueltank,
    DYNMX_OT_set_light,
    DYNMX_OT_set_blinker_left,
    DYNMX_OT_set_blinker_right,
    DYNMX_OT_set_headlight,
    DYNMX_OT_set_brakelights,
    DYNMX_OT_set_reverse,
    DYNMX_OT_set_sirenlight,
    DYNMX_OT_set_lightbar_blue_l,
    DYNMX_OT_set_lightbar_blue_r,
    DYNMX_OT_set_dot_blue_l,
    DYNMX_OT_set_dot_blue_r,
    DYNMX_OT_export_lights,
    DYNMX_OT_export_basics,
    DYNMX_OT_set_door,
    DYNMX_OT_export_doors,
    DYNMX_OT_set_hide_parts,
)


def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except RuntimeError as e:
            if "already registered" in str(e):
                pass
            else:
                raise


def unregister():
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass

