"""Block-related operators"""
import bpy
import os
import re
from mathutils import Vector
from .ops_vehicle import DYNMX_OT_export_obj


def _safe_name(value):
    return re.sub(r'[^A-Za-z0-9]+', '_', str(value).strip()).strip('_').lower()


def _format_float(value):
    text = f"{float(value):.6f}".rstrip('0').rstrip('.')
    if '.' not in text:
        text += '.0'
    return text


def _format_vector(values):
    return ' '.join(_format_float(value) for value in values)


def _block_dynx_path(scene):
    pack_path = bpy.path.abspath(getattr(scene, 'dynamx_pack_path', ''))
    pack_name = getattr(scene, 'dynamx_pack_name', '').strip()
    block_name = getattr(scene, 'dynamx_block_name', '').strip()
    if not all([pack_path, pack_name, block_name]):
        return None

    block_name_safe = _safe_name(block_name)
    return os.path.join(pack_path, pack_name, 'block', block_name_safe, f'block_{block_name_safe}.dynx')


def _shape_bounds(obj):
    coords = [obj.matrix_world @ Vector(vertex) for vertex in obj.bound_box]
    min_v = Vector((min(coord.x for coord in coords), min(coord.y for coord in coords), min(coord.z for coord in coords)))
    max_v = Vector((max(coord.x for coord in coords), max(coord.y for coord in coords), max(coord.z for coord in coords)))
    center = (min_v + max_v) / 2
    half = (max_v - min_v) / 2
    return center, half


def _build_shape_blocks(hitboxes_col):
    if not hitboxes_col:
        return []

    blocks = []
    used_names = set()
    for index, obj in enumerate(hitboxes_col.objects, start=1):
        section_name = f"Shape{_safe_name(obj.name)}"
        if section_name == "Shape":
            section_name = f"Shape{index}"
        while section_name in used_names:
            section_name = f"{section_name}_{index}"
        used_names.add(section_name)

        center, half = _shape_bounds(obj)
        blocks.append(
            f"{section_name}{{\n"
            f"    Type: BOX\n"
            f"    Position: {_format_vector(center)}\n"
            f"    Scale: {_format_vector(half)}\n"
            f"}}"
        )
    return blocks


def _obj_export_path(scene):
    pack_path = bpy.path.abspath(getattr(scene, 'dynamx_pack_path', '')).strip()
    pack_name = getattr(scene, 'dynamx_pack_name', '').strip()
    block_name = getattr(scene, 'dynamx_block_name', '').strip()
    if not all([pack_path, pack_name, block_name]):
        return None, None

    block_name_safe = _safe_name(block_name)
    model_rel = str(getattr(scene, 'dynamx_block_model', '')).strip().replace('\\', '/')
    if not model_rel:
        model_rel = f"obj/{block_name_safe}/{block_name_safe}.obj"
    if not model_rel.lower().endswith('.obj'):
        model_rel += '.obj'

    assets_models_dir = os.path.join(pack_path, pack_name, 'assets', 'dynamxmod', 'models')
    if model_rel.lower().startswith('obj/'):
        rel_after_obj = model_rel[4:]
        rel_after_obj_norm = os.path.normpath(rel_after_obj).replace('\\', '/')
        if rel_after_obj_norm.startswith('..'):
            rel_after_obj_norm = f"{block_name_safe}/{block_name_safe}.obj"
        rel_dir = os.path.dirname(rel_after_obj_norm)
        filename = os.path.basename(rel_after_obj_norm)
        export_dir = os.path.join(assets_models_dir, 'obj', rel_dir) if rel_dir else os.path.join(assets_models_dir, 'obj')
    else:
        filename = os.path.basename(model_rel)
        export_dir = os.path.join(assets_models_dir, 'obj', block_name_safe)

    obj_filepath = os.path.join(export_dir, filename)
    return export_dir, obj_filepath


def _ensure_obj_mtllib(obj_filepath, mtl_filename):
    try:
        with open(obj_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return False

    mtllib_line = f"mtllib {mtl_filename}\n"
    updated = []
    replaced = False
    for line in lines:
        if line.lstrip().startswith('mtllib '):
            if not replaced:
                updated.append(mtllib_line)
                replaced = True
            continue
        updated.append(line)

    if not replaced:
        updated.insert(0, mtllib_line)

    try:
        with open(obj_filepath, 'w', encoding='utf-8') as f:
            f.writelines(updated)
    except Exception:
        return False
    return True


class DYNMX_OT_set_block(bpy.types.Operator):
    """Create or update the block_<name>.dynx file"""
    bl_idname = "dynamx.set_block"
    bl_label = "Set Block"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return (scene.dynamx_pack_path and scene.dynamx_pack_name and scene.dynamx_block_name and context.mode == 'OBJECT')

    def execute(self, context):
        scene = context.scene
        block_file = _block_dynx_path(scene)
        if not block_file:
            self.report({'ERROR'}, 'Pack path, pack name and block name are required')
            return {'CANCELLED'}

        block_name = scene.dynamx_block_name.strip()
        block_description = scene.dynamx_block_description.strip()
        block_model = scene.dynamx_block_model.strip()
        block_scale = tuple(scene.dynamx_block_scale)
        render_distance = int(scene.dynamx_block_render_distance_squared)
        creative_tab = scene.dynamx_block_creative_tab.strip()
        empty_mass = int(scene.dynamx_block_empty_mass)
        cog = tuple(scene.dynamx_block_cog_offset)
        friction = int(scene.dynamx_block_friction)

        block_name_safe = _safe_name(block_name)
        if not block_model:
            block_model = f"obj/{block_name_safe}/{block_name_safe}.obj"

        os.makedirs(os.path.dirname(block_file), exist_ok=True)

        hitboxes_col = bpy.data.collections.get('Hitboxes')
        shape_blocks = _build_shape_blocks(hitboxes_col)

        file_lines = [
            f"Name: {block_name}",
            f"Description: {block_description}",
            f"Model: {block_model}",
            f"Scale: {_format_vector(block_scale)}",
            f"RenderDistanceSquared: {render_distance}",
            "",
            f"CreativeTab: {creative_tab}",
            "",
        ]

        if shape_blocks:
            file_lines.append('// ------------- Hitbox -------------')
            file_lines.append('')
            file_lines.extend(shape_blocks)
            file_lines.append('')

        file_lines.extend([
            f"prop_{block_name_safe}{{",
            f"    EmptyMass: {empty_mass}",
            f"    CenterOfGravityOffset: {_format_vector(cog)}",
            f"    Friction: {friction}",
            f"}}",
            "",
        ])

        try:
            with open(block_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(file_lines))
        except Exception as e:
            self.report({'ERROR'}, f'Failed to write block file: {e}')
            return {'CANCELLED'}

        self.report({'INFO'}, f"Wrote block file: {os.path.basename(block_file)}")
        return {'FINISHED'}


class DYNMX_OT_export_block_obj(bpy.types.Operator):
    """Export the block model as OBJ/MTL with localized textures"""
    bl_idname = "dynamx.export_block_obj"
    bl_label = "Export Block OBJ"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return bool(getattr(scene, 'dynamx_pack_path', '').strip()) and bool(getattr(scene, 'dynamx_pack_name', '').strip()) and bool(getattr(scene, 'dynamx_block_name', '').strip()) and context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        export_dir, obj_filepath = _obj_export_path(scene)
        if not export_dir or not obj_filepath:
            self.report({'ERROR'}, 'Pack path, pack name and block name are required')
            return {'CANCELLED'}

        export_objs = []
        dynamx_col = bpy.data.collections.get('Dynamx')
        for obj in context.scene.objects:
            if dynamx_col and obj.name in dynamx_col.all_objects:
                continue
            if obj.type == 'LIGHT':
                continue
            export_objs.append(obj)

        if not export_objs:
            self.report({'ERROR'}, 'No objects to export')
            return {'CANCELLED'}

        os.makedirs(export_dir, exist_ok=True)
        mtl_filepath = obj_filepath.replace('.obj', '.mtl')

        try:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in export_objs:
                obj.select_set(True)
            context.view_layer.objects.active = export_objs[0]
            bpy.ops.wm.obj_export(filepath=obj_filepath, export_selected_objects=True, forward_axis='Y', up_axis='Z')
            bpy.ops.object.select_all(action='DESELECT')
        except Exception as e:
            self.report({'ERROR'}, f'OBJ export failed: {e}')
            return {'CANCELLED'}

        try:
            DYNMX_OT_export_obj._localize_export_textures(export_objs, mtl_filepath, export_dir)
        except Exception:
            pass

        _ensure_obj_mtllib(obj_filepath, os.path.basename(mtl_filepath))
        self.report({'INFO'}, f'Exported block OBJ: {obj_filepath}')
        return {'FINISHED'}


class DYNMX_OT_export_block(bpy.types.Operator):
    """Export the current block setup to block_<name>.dynx"""
    bl_idname = "dynamx.export_block"
    bl_label = "Export Block"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return DYNMX_OT_set_block.poll(context)

    def execute(self, context):
        return DYNMX_OT_set_block.execute(self, context)


classes = (DYNMX_OT_set_block, DYNMX_OT_export_block_obj, DYNMX_OT_export_block)


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