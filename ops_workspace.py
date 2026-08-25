"""Workspace-related operators"""
import bpy
import os
import tempfile


_SETUP_FLOW = (
    "Pack Settings",
    "Vehicle Settings",
    "Steering Wheel",
    "Seat",
    "Hitbox",
    "Wheels",
    "Basic Addon",
    "Lights",
    "OBJ Export",
)
_SETUP_MAX_STEP = len(_SETUP_FLOW) - 1


def _clamp_setup_step(value):
    try:
        step = int(value)
    except Exception:
        step = 0
    return max(0, min(_SETUP_MAX_STEP, step))


def _get_setup_step(scene):
    return _clamp_setup_step(getattr(scene, 'dynamx_setup_step', 0))


def _set_setup_step(scene, step):
    step = _clamp_setup_step(step)
    if hasattr(scene, 'dynamx_setup_step'):
        scene.dynamx_setup_step = step

    # Keep legacy flags in sync so older UI logic remains safe.
    if hasattr(scene, 'dynamx_setup_show_vehicle'):
        scene.dynamx_setup_show_vehicle = step >= 1
    if hasattr(scene, 'dynamx_setup_show_essentials'):
        scene.dynamx_setup_show_essentials = step >= 2
    return step


def _setup_step_label(step):
    return _SETUP_FLOW[_clamp_setup_step(step)]


def _ensure_dynamx_collection(scene):
    """Create Dynamx collection once and return it."""
    dynamx_col = bpy.data.collections.get("Dynamx")
    if dynamx_col is None:
        dynamx_col = bpy.data.collections.new("Dynamx")
        scene.collection.children.link(dynamx_col)
    return dynamx_col


def _ensure_child_collection(parent_col, child_name):
    child_col = bpy.data.collections.get(child_name)
    if child_col is None:
        child_col = bpy.data.collections.new(child_name)
    if child_col.name not in [c.name for c in parent_col.children]:
        parent_col.children.link(child_col)
    return child_col


def _link_object_exclusive(obj, target_col):
    if obj is None or target_col is None:
        return
    if target_col.name not in [c.name for c in obj.users_collection]:
        target_col.objects.link(obj)
    for col in list(obj.users_collection):
        if col.name != target_col.name:
            try:
                col.objects.unlink(obj)
            except Exception:
                pass


def _reset_setup_flags(scene):
    _set_setup_step(scene, 0)
    if hasattr(scene, 'dynamx_setup_show_vehicle'):
        scene.dynamx_setup_show_vehicle = False
    if hasattr(scene, 'dynamx_setup_show_essentials'):
        scene.dynamx_setup_show_essentials = False


def _ensure_orientation_helpers(context, scene):
    dynamx_col = _ensure_dynamx_collection(scene)
    orientations_col = _ensure_child_collection(dynamx_col, "Orientations")

    steve_obj = bpy.data.objects.get("orientation_standing_steve")
    if steve_obj is None:
        obj_content = ""
        try:
            from . import ops_seat as _ops_seat
            obj_content = getattr(_ops_seat, 'SEAT_STANDING_OBJ_CONTENT', "")
        except Exception:
            obj_content = ""

        imported = False
        new_objs = []
        if obj_content:
            tmpdir = bpy.app.tempdir or tempfile.gettempdir()
            obj_path = os.path.join(tmpdir, "orientation_standing_steve.obj")
            mtl_path = os.path.join(tmpdir, "steve-model-sitting.mtl")
            try:
                with open(obj_path, 'w', encoding='utf-8') as f:
                    f.write(obj_content)
                if not os.path.exists(mtl_path):
                    with open(mtl_path, 'w', encoding='utf-8') as f:
                        f.write("newmtl default\nKd 0.8 0.8 0.8\n")

                pre_names = set(o.name for o in bpy.data.objects)
                try:
                    res = bpy.ops.wm.obj_import(filepath=obj_path)
                    imported = (res == {'FINISHED'})
                except Exception:
                    imported = False
                if not imported:
                    try:
                        res = bpy.ops.import_scene.obj(filepath=obj_path)
                        imported = (res == {'FINISHED'})
                    except Exception:
                        imported = False

                if imported:
                    post_names = set(o.name for o in bpy.data.objects)
                    new_names = list(post_names - pre_names)
                    new_objs = [bpy.data.objects[n] for n in new_names if n in bpy.data.objects]
            except Exception:
                imported = False

        if imported and new_objs:
            steve_obj = new_objs[0]
            steve_obj.name = "orientation_standing_steve"
            steve_obj.location = (1.5, 0.0, 0.0)
            steve_obj.rotation_mode = 'XYZ'
            steve_obj.rotation_euler = (0.0, 0.0, 0.0)
            _link_object_exclusive(steve_obj, orientations_col)
            for ob in new_objs[1:]:
                try:
                    bpy.data.objects.remove(ob, do_unlink=True)
                except Exception:
                    pass
        else:
            bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0.0, 0.0, 0.25))
            steve_obj = context.active_object
            if steve_obj is not None:
                steve_obj.name = "orientation_standing_steve"
                _link_object_exclusive(steve_obj, orientations_col)

    if steve_obj is not None:
        steve_obj.location = (1.5, 0.0, 0.0)
        steve_obj.rotation_mode = 'XYZ'
        steve_obj.rotation_euler = (0.0, 0.0, 0.0)
        _link_object_exclusive(steve_obj, orientations_col)

    cube_obj = bpy.data.objects.get("orientation_reference_cube")
    if cube_obj is None:
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(2.5, 0.0, 0.5))
        cube_obj = context.active_object
        if cube_obj is not None:
            cube_obj.name = "orientation_reference_cube"
    if cube_obj is not None:
        cube_obj.location = (2.5, 0.0, 0.5)
        cube_obj.scale = (2.0, 2.0, 2.0)
        _link_object_exclusive(cube_obj, orientations_col)

    arrow_obj = bpy.data.objects.get("orientation_front_arrow")
    if arrow_obj is None:
        bpy.ops.object.empty_add(type='SINGLE_ARROW', location=(0.0, -2.5, 0.25))
        arrow_obj = context.active_object
        if arrow_obj is not None:
            arrow_obj.name = "orientation_front_arrow"
    if arrow_obj is not None:
        arrow_obj.location = (0.0, -2.5, 0.25)
        arrow_obj.rotation_mode = 'XYZ'
        arrow_obj.rotation_euler = (1.57079632679, 0.0, 0.0)
        arrow_obj.scale = (2.0, 2.0, 2.0)
        _link_object_exclusive(arrow_obj, orientations_col)


def _ensure_clothing_reference(context, scene):
    dynamx_col = _ensure_dynamx_collection(scene)
    clothing_col = _ensure_child_collection(dynamx_col, "Clothing")

    steve_obj = bpy.data.objects.get("clothing_reference_steve")
    expected_vertex_count = 48
    if steve_obj is not None:
        is_valid = (
            steve_obj.type == 'MESH'
            and getattr(steve_obj, 'data', None) is not None
            and len(getattr(steve_obj.data, 'vertices', [])) == expected_vertex_count
        )
        if not is_valid:
            try:
                bpy.data.objects.remove(steve_obj, do_unlink=True)
            except Exception:
                pass
            steve_obj = None

    if steve_obj is None:
        imported = False
        new_objs = []
        addon_dir = os.path.dirname(__file__)
        obj_path = os.path.join(addon_dir, "models", "clothing_reference_steve.obj")
        if os.path.exists(obj_path):
            try:
                pre_names = set(o.name for o in bpy.data.objects)
                try:
                    res = bpy.ops.wm.obj_import(filepath=obj_path)
                    imported = (res == {'FINISHED'})
                except Exception:
                    imported = False
                if not imported:
                    try:
                        res = bpy.ops.import_scene.obj(filepath=obj_path)
                        imported = (res == {'FINISHED'})
                    except Exception:
                        imported = False

                if imported:
                    post_names = set(o.name for o in bpy.data.objects)
                    new_names = list(post_names - pre_names)
                    new_objs = [bpy.data.objects[n] for n in new_names if n in bpy.data.objects]
            except Exception:
                imported = False
        else:
            imported = False

        if imported and new_objs:
            steve_obj = new_objs[0]
            steve_obj.name = "clothing_reference_steve"
            for ob in new_objs[1:]:
                try:
                    bpy.data.objects.remove(ob, do_unlink=True)
                except Exception:
                    pass

    if steve_obj is not None:
        steve_obj.location = (0.0, 0.0, -1.5)
        steve_obj.rotation_mode = 'XYZ'
        steve_obj.rotation_euler = (0.0, 0.0, 0.0)
        _link_object_exclusive(steve_obj, clothing_col)

    arrow_obj = bpy.data.objects.get("clothing_reference_front_arrow")
    if arrow_obj is None:
        bpy.ops.object.empty_add(type='SINGLE_ARROW', location=(0.0, -0.8, -1.5))
        arrow_obj = context.active_object
        if arrow_obj is not None:
            arrow_obj.name = "clothing_reference_front_arrow"
    if arrow_obj is not None:
        arrow_obj.location = (0.0, -0.8, -1.5)
        arrow_obj.rotation_mode = 'XYZ'
        arrow_obj.rotation_euler = (1.57079632679, 0.0, 0.0)
        arrow_obj.scale = (1.2, 1.2, 1.2)
        _link_object_exclusive(arrow_obj, clothing_col)


class DYNMX_OT_create_workspace(bpy.types.Operator):
    """Create a Workspace named Dynamx - Car"""
    bl_idname = "dynamx.create_workspace"
    bl_label = "Create Dynamx Workspace"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = "Dynamx - Car"
        for ws in bpy.data.workspaces:
            if ws.name == name:
                self.report({'INFO'}, f"Workspace '{name}' already exists")
                context.window.workspace = ws
                try:
                    _ensure_orientation_helpers(context, context.scene)
                    _reset_setup_flags(context.scene)
                except Exception:
                    pass
                return {'FINISHED'}

        original_ws = context.workspace
        original_name = original_ws.name
        
        try:
            bpy.ops.workspace.duplicate()
            
            new_ws = context.workspace
            
            new_ws.name = name
            
            for ws in bpy.data.workspaces:
                if ws != new_ws and ".001" in ws.name:
                    ws.name = ws.name.replace(".001", "")
                    break
            
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.show_region_ui = True

            _ensure_orientation_helpers(context, context.scene)
            _reset_setup_flags(context.scene)
            
            self.report({'INFO'}, f"Workspace '{name}' created successfully")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create workspace: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_setup_dynamx(bpy.types.Operator):
    """Setup Dynamx navigation between Pack, Vehicle, Steering, Hitbox, Seat, Wheels, Basic Addon, Lights and OBJ export"""
    bl_idname = "dynamx.setup_dynamx"
    bl_label = "Setup Dynamx"
    bl_options = {'REGISTER', 'UNDO'}

    go_back: bpy.props.BoolProperty(
        name="Go Back",
        description="Switch from vehicle settings back to pack settings",
        default=False,
        options={'SKIP_SAVE'}
    )

    go_essentials: bpy.props.BoolProperty(
        name="Go Essentials",
        description="Jump to steering wheel setup step",
        default=False,
        options={'SKIP_SAVE'}
    )
    
    def execute(self, context):
        scene = context.scene

        workspace_name = getattr(getattr(context, 'workspace', None), 'name', '')
        if workspace_name != "Dynamx - Car":
            _reset_setup_flags(scene)
            self.report({'WARNING'}, "Weiter ist nur im Workspace 'Dynamx - Car' verfugbar")
            return {'CANCELLED'}

        step = _get_setup_step(scene)

        if self.go_back:
            new_step = _set_setup_step(scene, step - 1)
            self.report({'INFO'}, f"Zuruck zu {_setup_step_label(new_step)}")
            return {'FINISHED'}

        if self.go_essentials:
            new_step = _set_setup_step(scene, 2)
            self.report({'INFO'}, f"{_setup_step_label(new_step)} freigeschaltet")
            return {'FINISHED'}

        new_step = _set_setup_step(scene, step + 1)
        if new_step == step:
            self.report({'INFO'}, f"Bereits bei {_setup_step_label(new_step)}")
        else:
            self.report({'INFO'}, f"{_setup_step_label(new_step)} freigeschaltet")
        return {'FINISHED'}


classes = (DYNMX_OT_create_workspace, DYNMX_OT_setup_dynamx)


class DYNMX_OT_create_trailer_workspace(bpy.types.Operator):
    """Create a Workspace named Dynamx - Trailer"""
    bl_idname = "dynamx.create_trailer_workspace"
    bl_label = "Create Dynamx Trailer Workspace"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = "Dynamx - Trailer"
        for ws in bpy.data.workspaces:
            if ws.name == name:
                self.report({'INFO'}, f"Workspace '{name}' already exists")
                context.window.workspace = ws
                try:
                    _ensure_dynamx_collection(context.scene)
                    _reset_setup_flags(context.scene)
                except Exception:
                    pass
                return {'FINISHED'}

        try:
            bpy.ops.workspace.duplicate()
            new_ws = context.workspace
            new_ws.name = name

            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.show_region_ui = True

            _ensure_dynamx_collection(context.scene)
            _reset_setup_flags(context.scene)

            self.report({'INFO'}, f"Workspace '{name}' created successfully")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create workspace: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_create_clothing_workspace(bpy.types.Operator):
    """Create a Workspace named Clothing - Dynamx"""
    bl_idname = "dynamx.create_clothing_workspace"
    bl_label = "Create Dynamx Clothing Workspace"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = "Clothing - Dynamx"
        for ws in bpy.data.workspaces:
            if ws.name == name:
                self.report({'INFO'}, f"Workspace '{name}' already exists")
                context.window.workspace = ws
                try:
                    _ensure_dynamx_collection(context.scene)
                    _ensure_clothing_reference(context, context.scene)
                    _reset_setup_flags(context.scene)
                except Exception:
                    pass
                return {'FINISHED'}

        try:
            bpy.ops.workspace.duplicate()
            new_ws = context.workspace
            new_ws.name = name

            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.show_region_ui = True

            _ensure_dynamx_collection(context.scene)
            _ensure_clothing_reference(context, context.scene)
            _reset_setup_flags(context.scene)

            self.report({'INFO'}, f"Workspace '{name}' created successfully")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create workspace: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_create_block_workspace(bpy.types.Operator):
    """Create a Workspace named Dynamx - Block"""
    bl_idname = "dynamx.create_block_workspace"
    bl_label = "Create Dynamx Block Workspace"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = "Dynamx - Block"
        for ws in bpy.data.workspaces:
            if ws.name == name:
                self.report({'INFO'}, f"Workspace '{name}' already exists")
                context.window.workspace = ws
                try:
                    _ensure_orientation_helpers(context, context.scene)
                    _reset_setup_flags(context.scene)
                except Exception:
                    pass
                return {'FINISHED'}

        try:
            bpy.ops.workspace.duplicate()
            new_ws = context.workspace
            new_ws.name = name

            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.show_region_ui = True

            _ensure_orientation_helpers(context, context.scene)
            _reset_setup_flags(context.scene)

            self.report({'INFO'}, f"Workspace '{name}' created successfully")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create workspace: {str(e)}")
            return {'CANCELLED'}


classes = classes + (DYNMX_OT_create_block_workspace,)


def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except Exception:
            pass
    try:
        bpy.utils.register_class(DYNMX_OT_create_trailer_workspace)
    except Exception:
        pass
    try:
        bpy.utils.register_class(DYNMX_OT_create_clothing_workspace)
    except Exception:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(DYNMX_OT_create_clothing_workspace)
    except Exception:
        pass
    try:
        bpy.utils.unregister_class(DYNMX_OT_create_trailer_workspace)
    except Exception:
        pass
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
