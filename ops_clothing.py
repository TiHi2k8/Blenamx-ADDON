"""Clothing-related operators"""
import os
import bpy
from .ops_vehicle import DYNMX_OT_export_obj


HEAD_MODEL = "headModel"
HEAD_MODEL_LEGACY = "headmodel"
BODY_MODEL = "bodyModel"
LEFT_ARM_MODEL = "leftArmModel"
RIGHT_ARM_MODEL = "rightArmModel"
LEFT_LEG_MODEL = "leftLegModel"
RIGHT_LEG_MODEL = "rightLegModel"


def _safe_name(value, fallback="clothing"):
    raw = str(value or "").strip().replace(" ", "_").lower()
    return raw if raw else fallback


def _pack_context(scene):
    pack_path = bpy.path.abspath(getattr(scene, 'dynamx_pack_path', '')).strip()
    pack_name = str(getattr(scene, 'dynamx_pack_name', '')).strip()
    if not pack_path or not pack_name:
        return None, None, None
    pack_name_safe = _safe_name(pack_name, fallback="pack")
    return pack_path, pack_name, pack_name_safe


def _clothing_context(scene):
    clothing_name = str(getattr(scene, 'dynamx_clothing_name', '')).strip()
    clothing_name_safe = _safe_name(clothing_name, fallback="clothing")
    return clothing_name, clothing_name_safe


def _model_relpath(scene, clothing_name_safe):
    raw = str(getattr(scene, 'dynamx_clothing_model', '')).strip().replace('\\', '/')
    if not raw:
        return f"obj/{clothing_name_safe}/{clothing_name_safe}.obj"
    if not raw.lower().endswith('.obj'):
        raw = f"{raw}.obj"
    return raw.lstrip('/')


def _armor_paths(scene):
    pack_path, _, pack_name_safe = _pack_context(scene)
    clothing_name, clothing_name_safe = _clothing_context(scene)
    if not pack_path or not pack_name_safe or not clothing_name:
        return None, None
    armor_dir = os.path.join(pack_path, pack_name_safe, "armors")
    armor_file = os.path.join(armor_dir, f"armor_{clothing_name_safe}.dynx")
    return armor_dir, armor_file


def _part_exists(part_name):
    if bpy.data.objects.get(part_name) is not None:
        return True
    if part_name == HEAD_MODEL and bpy.data.objects.get(HEAD_MODEL_LEGACY) is not None:
        return True
    return False


def _collect_material_variant_tokens(scene):
    variants = []
    for item in getattr(scene, 'dynamx_material_variants', []):
        raw = str(getattr(item, 'name', '')).strip()
        if not raw:
            continue
        variants.append("_".join(raw.split()))
    return variants


def _obj_export_path(scene):
    pack_path, _, pack_name_safe = _pack_context(scene)
    clothing_name, clothing_name_safe = _clothing_context(scene)
    if not pack_path or not pack_name_safe or not clothing_name:
        return None, None, None

    model_rel = _model_relpath(scene, clothing_name_safe)
    assets_models_dir = os.path.join(pack_path, pack_name_safe, "assets", "dynamxmod", "models")

    if model_rel.lower().startswith("obj/"):
        rel_after_obj = model_rel[4:]
        rel_after_obj_norm = os.path.normpath(rel_after_obj).replace('\\', '/')
        if rel_after_obj_norm.startswith(".."):
            rel_after_obj_norm = f"{clothing_name_safe}/{clothing_name_safe}.obj"
        rel_dir = os.path.dirname(rel_after_obj_norm)
        filename = os.path.basename(rel_after_obj_norm)
        export_dir = os.path.join(assets_models_dir, "obj", rel_dir) if rel_dir else os.path.join(assets_models_dir, "obj")
    else:
        filename = os.path.basename(model_rel)
        export_dir = os.path.join(assets_models_dir, "obj", clothing_name_safe)

    obj_filepath = os.path.join(export_dir, filename)
    return export_dir, obj_filepath, model_rel


def _parse_mtl_materials(mtl_filepath):
    materials = {}
    header = ""
    try:
        with open(mtl_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = content.split('newmtl ')
        header = blocks[0]
        for block in blocks[1:]:
            lines = block.split('\n')
            if not lines or not lines[0]:
                continue
            mat_name = lines[0].strip()
            mat_content = 'newmtl ' + block.rstrip() + '\n'
            materials[mat_name] = mat_content
    except Exception:
        pass
    return materials, header


def _merge_mtl_files(old_mtl_path, new_mtl_path):
    try:
        old_materials, _old_header = _parse_mtl_materials(old_mtl_path)
        new_materials, new_header = _parse_mtl_materials(new_mtl_path)

        merged = dict(old_materials)
        for mat_name, mat_content in new_materials.items():
            if mat_name not in merged:
                merged[mat_name] = mat_content

        with open(new_mtl_path, 'w', encoding='utf-8') as f:
            if new_header:
                f.write(new_header)
            mat_values = list(merged.values())
            for idx, mat_content in enumerate(mat_values):
                f.write(mat_content)
                if idx < len(mat_values) - 1:
                    f.write('\n')
    except Exception:
        pass


def _remove_obj_mtllib(obj_filepath):
    try:
        with open(obj_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        with open(obj_filepath, 'w', encoding='utf-8') as f:
            for line in lines:
                if not line.startswith('mtllib'):
                    f.write(line)
    except Exception:
        pass


def _ensure_obj_mtllib(obj_filepath, mtl_filename):
    try:
        with open(obj_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return False

    mtllib_line = f"mtllib {mtl_filename}\n"
    updated = []
    replaced = False
    inserted = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('mtllib '):
            if not replaced:
                updated.append(mtllib_line)
                replaced = True
            continue
        updated.append(line)

    if not replaced:
        updated.insert(0, mtllib_line)
        inserted = True

    try:
        with open(obj_filepath, 'w', encoding='utf-8') as f:
            f.writelines(updated)
    except Exception:
        return False

    return replaced or inserted


def _set_origin_to_world_zero(context, obj):
    scene = context.scene
    view_layer = context.view_layer
    cursor = scene.cursor
    prev_cursor_location = cursor.location.copy()
    prev_active = view_layer.objects.active
    prev_selected = list(context.selected_objects)

    try:
        try:
            bpy.ops.object.select_all(action='DESELECT')
        except Exception:
            pass
        try:
            obj.select_set(True)
            view_layer.objects.active = obj
        except Exception:
            pass

        cursor.location = (0.0, 0.0, 0.0)
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    except Exception:
        return False
    finally:
        try:
            cursor.location = prev_cursor_location
        except Exception:
            pass
        try:
            bpy.ops.object.select_all(action='DESELECT')
            for selected_obj in prev_selected:
                if selected_obj and selected_obj.name in bpy.data.objects:
                    selected_obj.select_set(True)
            if prev_active and prev_active.name in bpy.data.objects:
                view_layer.objects.active = prev_active
        except Exception:
            pass

    return True


def _set_part_object(context, target_name):
    obj = context.active_object
    if obj is None:
        return False, "No active object selected"

    existing = bpy.data.objects.get(target_name)
    if existing is not None and existing != obj:
        try:
            existing.name = f"{target_name}_old"
            if getattr(existing, 'data', None):
                existing.data.name = existing.name
        except Exception:
            pass

    obj.name = target_name
    if getattr(obj, 'data', None):
        obj.data.name = target_name
    try:
        obj['dynamx_clothing_part'] = target_name
    except Exception:
        pass

    if not _set_origin_to_world_zero(context, obj):
        return False, "Could not set object origin to (0, 0, 0)"

    return True, f"Set part: {target_name}"


class DYNMX_OT_set_clothing_head(bpy.types.Operator):
    """Set active object as clothing head model"""
    bl_idname = "dynamx.set_clothing_head"
    bl_label = "Set Head"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        ok, msg = _set_part_object(context, HEAD_MODEL)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_set_clothing_body(bpy.types.Operator):
    """Set active object as clothing body model"""
    bl_idname = "dynamx.set_clothing_body"
    bl_label = "Set Body"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        ok, msg = _set_part_object(context, BODY_MODEL)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_set_clothing_left_arm(bpy.types.Operator):
    """Set active object as clothing left arm model"""
    bl_idname = "dynamx.set_clothing_left_arm"
    bl_label = "Set Left Arm"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        ok, msg = _set_part_object(context, LEFT_ARM_MODEL)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_set_clothing_right_arm(bpy.types.Operator):
    """Set active object as clothing right arm model"""
    bl_idname = "dynamx.set_clothing_right_arm"
    bl_label = "Set Right Arm"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        ok, msg = _set_part_object(context, RIGHT_ARM_MODEL)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_set_clothing_left_leg(bpy.types.Operator):
    """Set active object as clothing left leg model"""
    bl_idname = "dynamx.set_clothing_left_leg"
    bl_label = "Set Left Leg"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        ok, msg = _set_part_object(context, LEFT_LEG_MODEL)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_set_clothing_right_leg(bpy.types.Operator):
    """Set active object as clothing right leg model"""
    bl_idname = "dynamx.set_clothing_right_leg"
    bl_label = "Set Right Leg"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None

    def execute(self, context):
        ok, msg = _set_part_object(context, RIGHT_LEG_MODEL)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class DYNMX_OT_set_clothing(bpy.types.Operator):
    """Create armor dynx file for clothing"""
    bl_idname = "dynamx.set_clothing"
    bl_label = "Set Clothing"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        clothing_name = str(getattr(scene, 'dynamx_clothing_name', '')).strip()
        return bool(getattr(scene, 'dynamx_pack_path', '').strip()) and bool(getattr(scene, 'dynamx_pack_name', '').strip()) and bool(clothing_name)

    def execute(self, context):
        scene = context.scene
        armor_dir, armor_file = _armor_paths(scene)
        if not armor_dir or not armor_file:
            self.report({'ERROR'}, "Pack path, pack name and clothing name are required")
            return {'CANCELLED'}

        clothing_name, clothing_name_safe = _clothing_context(scene)
        description = str(getattr(scene, 'dynamx_clothing_description', '')).strip()
        model_rel = _model_relpath(scene, clothing_name_safe)

        lines = [
            f"Name: {clothing_name}",
            f"Description: {description}",
            f"Model: {model_rel}",
        ]

        if _part_exists(HEAD_MODEL):
            lines.append(f"ArmorHead: {HEAD_MODEL}")
        if _part_exists(BODY_MODEL):
            lines.append(f"ArmorBody: {BODY_MODEL}")

        arms = [name for name in (LEFT_ARM_MODEL, RIGHT_ARM_MODEL) if _part_exists(name)]
        if arms:
            lines.append(f"ArmorArms: {' '.join(arms)}")

        legs = [name for name in (LEFT_LEG_MODEL, RIGHT_LEG_MODEL) if _part_exists(name)]
        if legs:
            lines.append(f"ArmorLegs: {' '.join(legs)}")

        variants = _collect_material_variant_tokens(scene)
        if variants:
            lines.append("")
            lines.append("MaterialVariants{")
            lines.append(f"    Variants: {' '.join(variants)}")
            lines.append("}")

        content = "\n".join(lines) + "\n"

        try:
            os.makedirs(armor_dir, exist_ok=True)
            with open(armor_file, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write armor file: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Created armor file: {armor_file}")
        return {'FINISHED'}


class DYNMX_OT_export_clothing_obj(bpy.types.Operator):
    """Export clothing model as OBJ"""
    bl_idname = "dynamx.export_clothing_obj"
    bl_label = "Export Clothing OBJ"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        clothing_name = str(getattr(scene, 'dynamx_clothing_name', '')).strip()
        return context.mode == 'OBJECT' and bool(getattr(scene, 'dynamx_pack_path', '').strip()) and bool(getattr(scene, 'dynamx_pack_name', '').strip()) and bool(clothing_name)

    def execute(self, context):
        scene = context.scene

        export_objs = []
        dynamx_col = bpy.data.collections.get("Dynamx")
        for obj in context.scene.objects:
            if dynamx_col and obj.name in dynamx_col.all_objects:
                continue
            if obj.type == 'LIGHT':
                continue
            export_objs.append(obj)

        if not export_objs:
            self.report({'ERROR'}, "No objects to export")
            return {'CANCELLED'}

        export_dir, obj_filepath, _model_rel = _obj_export_path(scene)
        if not export_dir or not obj_filepath:
            self.report({'ERROR'}, "Pack path, pack name and clothing name are required")
            return {'CANCELLED'}

        mtl_filepath = obj_filepath.replace('.obj', '.mtl')
        mtl_mode = getattr(scene, 'dynamx_mtl_export_mode', 'REPLACE')
        old_mtl_backup = None
        if os.path.exists(mtl_filepath):
            old_mtl_backup = mtl_filepath + '.backup'
            try:
                import shutil
                shutil.copy2(mtl_filepath, old_mtl_backup)
            except Exception:
                old_mtl_backup = None

        try:
            os.makedirs(export_dir, exist_ok=True)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create export directory: {e}")
            return {'CANCELLED'}

        try:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in export_objs:
                obj.select_set(True)
            context.view_layer.objects.active = export_objs[0]
            bpy.ops.wm.obj_export(filepath=obj_filepath, export_selected_objects=True, forward_axis='Y', up_axis='Z')
            bpy.ops.object.select_all(action='DESELECT')
        except Exception as e:
            self.report({'ERROR'}, f"OBJ export failed: {e}")
            return {'CANCELLED'}

        if mtl_mode in ('ADD', 'REPLACE'):
            try:
                DYNMX_OT_export_obj._localize_export_textures(export_objs, mtl_filepath, export_dir)
            except Exception:
                pass
            _ensure_obj_mtllib(obj_filepath, os.path.basename(mtl_filepath))

        if mtl_mode == 'NONE':
            if old_mtl_backup and os.path.exists(old_mtl_backup):
                try:
                    import shutil
                    shutil.copy2(old_mtl_backup, mtl_filepath)
                    os.remove(old_mtl_backup)
                except Exception:
                    pass
            else:
                try:
                    if os.path.exists(mtl_filepath):
                        os.remove(mtl_filepath)
                except Exception:
                    pass
            _remove_obj_mtllib(obj_filepath)

        elif mtl_mode == 'ADD':
            if old_mtl_backup and os.path.exists(old_mtl_backup):
                _merge_mtl_files(old_mtl_backup, mtl_filepath)
                try:
                    os.remove(old_mtl_backup)
                except Exception:
                    pass

        elif mtl_mode == 'REPLACE':
            if old_mtl_backup and os.path.exists(old_mtl_backup):
                try:
                    os.remove(old_mtl_backup)
                except Exception:
                    pass

        self.report({'INFO'}, f"Exported clothing OBJ: {obj_filepath}")
        return {'FINISHED'}


classes = (
    DYNMX_OT_set_clothing_head,
    DYNMX_OT_set_clothing_body,
    DYNMX_OT_set_clothing_left_arm,
    DYNMX_OT_set_clothing_right_arm,
    DYNMX_OT_set_clothing_left_leg,
    DYNMX_OT_set_clothing_right_leg,
    DYNMX_OT_set_clothing,
    DYNMX_OT_export_clothing_obj,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
