import bpy


def _find_steering_wheel_object():
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


def _draw_multitexture_section(layout, scene):
    multi_box = layout.box()
    multi_box.label(text="Multitexture", icon='MATERIAL')
    if hasattr(scene, 'dynamx_multitexture_material'):
        multi_box.prop_search(scene, 'dynamx_multitexture_material', bpy.data, 'materials', text='Material')

    add_row = multi_box.row(align=True)
    add_row.scale_y = 1.1
    add_row.operator("dynamx.add_material_variant", text="+", icon='ADD')

    variants = getattr(scene, 'dynamx_material_variants', None)
    if variants is None or len(variants) == 0:
        multi_box.label(text="No variants yet", icon='INFO')
    else:
        for idx, item in enumerate(variants):
            vrow = multi_box.row(align=True)
            vrow.prop(item, 'name', text='Name')
            vrow.prop(item, 'texture_path', text='Texture')
            rop = vrow.operator("dynamx.remove_material_variant", text="", icon='X')
            rop.index = idx


def _draw_export_section(layout, scene):
    export_box = layout.box()
    export_box.label(text="Export Settings:", icon='EXPORT')
    export_box.prop(scene, "dynamx_mtl_export_mode", text="MTL Export Mode")

    row = export_box.row()
    row.scale_y = 1.3
    row.operator("dynamx.export_obj", text="Export OBJ", icon='EXPORT')

    mtl_mode = getattr(scene, 'dynamx_mtl_export_mode', 'REPLACE')
    if mtl_mode in ('ADD', 'REPLACE'):
        row = export_box.row()
        row.scale_y = 1.2
        row.operator("dynamx.export_mtl_only", text="Export MTL Only", icon='EXPORT')


def _draw_light_material_settings(layout, scene):
    cfg = layout.box()
    cfg.label(text='Light Materials / Textures', icon='MATERIAL')
    if hasattr(scene, 'dynamx_use_basic_light_textures'):
        cfg.prop(scene, 'dynamx_use_basic_light_textures', text='Use basic Textures')

    combine = bool(getattr(scene, 'dynamx_combine_main_lights_materials', True))
    if hasattr(scene, 'dynamx_combine_main_lights_materials'):
        cfg.prop(scene, 'dynamx_combine_main_lights_materials', text='Combine Main Lights Materials')

    if combine:
        combined = cfg.box()
        combined.label(text='Main Lights (Combined)', icon='LIGHT')
        if hasattr(scene, 'dynamx_main_lights_material'):
            combined.prop_search(scene, 'dynamx_main_lights_material', bpy.data, 'materials', text='Material')
        if hasattr(scene, 'dynamx_main_lights_texture_off'):
            combined.prop(scene, 'dynamx_main_lights_texture_off', text='Off Texture')
        if hasattr(scene, 'dynamx_main_lights_texture_on'):
            combined.prop(scene, 'dynamx_main_lights_texture_on', text='On Texture')
        if hasattr(scene, 'dynamx_main_lights_glass_material'):
            combined.prop_search(scene, 'dynamx_main_lights_glass_material', bpy.data, 'materials', text='Glass Material')
    else:
        per_light = (
            ('HeadLight', 'dynamx_headlight_material', 'dynamx_headlight_texture_off', 'dynamx_headlight_texture_on'),
            ('BrakeLights', 'dynamx_brakelights_material', 'dynamx_brakelights_texture_off', 'dynamx_brakelights_texture_on'),
            ('ReverseLights', 'dynamx_reverselights_material', 'dynamx_reverselights_texture_off', 'dynamx_reverselights_texture_on'),
            ('Blinker Left', 'dynamx_blinker_left_material', 'dynamx_blinker_left_texture_off', 'dynamx_blinker_left_texture_on'),
            ('Blinker Right', 'dynamx_blinker_right_material', 'dynamx_blinker_right_texture_off', 'dynamx_blinker_right_texture_on'),
        )
        for title, mat_prop, off_prop, on_prop in per_light:
            pbox = cfg.box()
            pbox.label(text=title, icon='MATERIAL')
            if hasattr(scene, mat_prop):
                pbox.prop_search(scene, mat_prop, bpy.data, 'materials', text='Material')
            if hasattr(scene, off_prop):
                pbox.prop(scene, off_prop, text='Off Texture')
            if hasattr(scene, on_prop):
                pbox.prop(scene, on_prop, text='On Texture')

    siren_box = cfg.box()
    siren_box.label(text='Siren / RTK', icon='SOUND')
    if hasattr(scene, 'dynamx_sirenlight_material'):
        siren_box.prop_search(scene, 'dynamx_sirenlight_material', bpy.data, 'materials', text='Material')
    if hasattr(scene, 'dynamx_sirenlight_texture_off'):
        siren_box.prop(scene, 'dynamx_sirenlight_texture_off', text='Off Texture')
    if hasattr(scene, 'dynamx_sirenlight_texture_on'):
        siren_box.prop(scene, 'dynamx_sirenlight_texture_on', text='On Texture')
    if hasattr(scene, 'dynamx_sirenlight_on_token'):
        siren_box.prop(scene, 'dynamx_sirenlight_on_token', text='On Token')


def _draw_basicaddon_section(layout, scene, context, show_title=True):
    if show_title:
        layout.label(text="Basic Addon", icon='PLUGIN')

    if context.mode == 'OBJECT':
        box = layout.box()
        if hasattr(scene, 'dynamx_license_plate_text'):
            box.prop(scene, 'dynamx_license_plate_text', text='License Plate')
        row = box.row()
        row.scale_y = 1.4
        row.operator('dynamx.summon_license_plate', text='Summon License Plate', icon='FONT_DATA')

    sbox = layout.box()
    sbox.label(text='Storage Tools', icon='MESH_CUBE')
    if hasattr(scene, 'dynamx_storage_size'):
        sbox.prop(scene, 'dynamx_storage_size', text='Storage Size')
    srow = sbox.row()
    srow.scale_y = 1.2
    srow.operator('dynamx.summon_storage', text='Summon Storage', icon='MESH_CUBE')
    srow.operator('dynamx.set_storage', text='Set Storage', icon='SELECT_EXTEND')

    fbox = layout.box()
    fbox.label(text='Fuel Tank', icon='OUTLINER_OB_EMPTY')
    if hasattr(scene, 'dynamx_fueltank_size'):
        fbox.prop(scene, 'dynamx_fueltank_size', text='Fuel Tank Size')
    frow = fbox.row()
    frow.scale_y = 1.2
    frow.operator('dynamx.summon_fueltank', text='Summon Fuel Tank', icon='MESH_CUBE')
    frow.operator('dynamx.set_fueltank', text='Set Fuel Tank', icon='MOD_SOLIDIFY')

    layout.separator()
    erow = layout.row()
    erow.scale_y = 1.3
    erow.operator('dynamx.export_basics', text='Export Basic Addon', icon='EXPORT')

class DYNMX_PT_setup_main(bpy.types.Panel):
    """Dynamx Setup Panel"""
    bl_label = "Setup Dynamx"
    bl_idname = "DYNMX_PT_setup_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = -1
    
    @classmethod
    def poll(cls, context):
        try:
            # Show everywhere
            return True
        except Exception:
            return False
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        workspace_name = getattr(getattr(context, 'workspace', None), 'name', '')
        is_car = (workspace_name == "Dynamx - Car")

        if is_car:
            if hasattr(scene, 'dynamx_setup_step'):
                try:
                    step = int(scene.dynamx_setup_step)
                except Exception:
                    step = 0
            else:
                show_vehicle = bool(getattr(scene, 'dynamx_setup_show_vehicle', False))
                show_essentials = bool(getattr(scene, 'dynamx_setup_show_essentials', False))
                step = 2 if show_essentials else (1 if show_vehicle else 0)
            step = max(0, min(8, step))
        else:
            step = 0

        if not is_car or step == 0:
            if is_car:
                layout.label(text="Step 1/9: Pack", icon='INFO')

            box = layout.box()
            box.prop(scene, "dynamx_pack_path", text="Path")
            box.prop(scene, "dynamx_pack_name", text="Pack Name")
            box.prop(scene, "dynamx_pack_description", text="Description")
            box.prop(scene, "dynamx_pack_version", text="Pack Version")

            actions = layout.row(align=True)
            actions.scale_y = 1.2
            actions.operator("dynamx.create_pack", text="Set Pack", icon='FILE_FOLDER')
            actions.operator("dynamx.select_pack", text="Select Pack", icon='FILEBROWSER')

            if is_car:
                layout.separator()
                next_row = layout.row()
                next_row.scale_y = 1.2
                next_row.operator("dynamx.setup_dynamx", text="Next", icon='TRIA_RIGHT')

        elif step == 1:
            vehicle_box = layout.box()
            vehicle_box.label(text="Step 2/9: Vehicle", icon='AUTO')
            vehicle_box.label(text="Vehicle Settings", icon='AUTO')
            vehicle_box.prop(scene, "dynamx_vehicle_name", text="Vehicle Name")
            vehicle_box.prop(scene, "dynamx_vehicle_description", text="Description")
            vehicle_box.prop(scene, "dynamx_empty_mass", text="Empty Mass")
            if hasattr(scene, "dynamx_vehicle_scale"):
                vehicle_box.prop(scene, "dynamx_vehicle_scale", text="Vehicle Scale")
                update_row = vehicle_box.row(align=True)
                update_row.scale_y = 1.15
                update_row.operator("dynamx.update_scaled_parts", text="Update Scaled Parts", icon='MODIFIER')
            if hasattr(scene, "dynamx_cog_offset"):
                vehicle_box.prop(scene, "dynamx_cog_offset", text="Center Of Gravity Offset")
            if hasattr(scene, "dynamx_shape_y_offset"):
                vehicle_box.prop(scene, "dynamx_shape_y_offset", text="Shape Y Offset")
            vehicle_box.prop(scene, "dynamx_max_speed", text="Max Vehicle Speed")
            vehicle_box.prop(scene, "dynamx_drag_coefficient", text="Drag Coefficient")
            vehicle_box.prop(scene, "dynamx_zoom_level", text="Zoom Level")
            vehicle_box.prop(scene, "dynamx_model", text="Model")
            vehicle_box.prop(scene, "dynamx_default_engine", text="Default Engine")
            vehicle_box.prop(scene, "dynamx_default_sounds", text="Default Sounds")

            set_row = vehicle_box.row()
            set_row.scale_y = 1.2
            set_row.operator("dynamx.set_car", text="Set Car", icon='AUTO')

            import_row = vehicle_box.row()
            import_row.scale_y = 1.2
            import_row.operator("dynamx.select_vehicle", text="Import Vehicle", icon='IMPORT')

            chassis_row = vehicle_box.row()
            chassis_row.scale_y = 1.2
            chassis_row.operator("dynamx.set_chassis", text="Set Chassis", icon='MESH_CUBE')
            chassis_row.enabled = context.active_object is not None

            layout.separator()
            nav_row = layout.row(align=True)
            nav_row.scale_y = 1.2
            back_op = nav_row.operator("dynamx.setup_dynamx", text="Back", icon='TRIA_LEFT')
            back_op.go_back = True
            nav_row.operator("dynamx.setup_dynamx", text="Next", icon='TRIA_RIGHT')

        elif step == 2:
            steering_obj = _find_steering_wheel_object()

            essentials = layout.box()
            essentials.label(text="Step 3/9: Steering Wheel", icon='MODIFIER')

            sw_box = essentials.box()
            sw_box.label(text="Steering Wheel", icon='ORIENTATION_GIMBAL')
            if steering_obj is not None:
                sw_box.label(text=f"Current: {steering_obj.name}", icon='CHECKMARK')
            else:
                sw_box.label(text="Current: not set", icon='ERROR')

            set_sw_row = sw_box.row()
            set_sw_row.scale_y = 1.2
            set_sw_row.operator("dynamx.set_steering_wheel", text="Set Steering Wheel", icon='ORIENTATION_GIMBAL')
            set_sw_row.enabled = context.active_object is not None

            export_sw_row = sw_box.row()
            export_sw_row.scale_y = 1.2
            export_sw_row.operator("dynamx.export_steering_wheel", text="Export Steering Wheel", icon='EXPORT')
            export_sw_row.enabled = steering_obj is not None

            layout.separator()
            back_row = layout.row(align=True)
            back_row.scale_y = 1.2
            back_op = back_row.operator("dynamx.setup_dynamx", text="Back", icon='TRIA_LEFT')
            back_op.go_back = True
            back_row.operator("dynamx.setup_dynamx", text="Next", icon='TRIA_RIGHT')

        elif step == 3:
            layout.label(text="Step 4/9: Seat", icon='OUTLINER_COLLECTION')

            row = layout.row()
            row.scale_y = 1.3
            op = row.operator("dynamx.summon_seat", text="Summon Seat (Sitting)", icon='MESH_CUBE')
            op.is_standing = False

            row = layout.row()
            row.scale_y = 1.3
            op = row.operator("dynamx.summon_seat", text="Summon Seat (Standing)", icon='MESH_CUBE')
            op.is_standing = True

            row = layout.row(align=True)
            row.scale_y = 1.1
            row.operator("dynamx.duplicate_seat", text="Duplicate Seat", icon='DUPLICATE')
            row.operator("dynamx.delete_seat", text="Delete Seat", icon='TRASH')

            seat_box = layout.box()
            seat_box.prop(scene, "dynamx_replace_seats", text="Replace Seats")
            seat_export = seat_box.row()
            seat_export.scale_y = 1.2
            seat_export.operator("dynamx.export_seats", text="Export Seats", icon='EXPORT')

            layout.separator()
            nav_row = layout.row(align=True)
            nav_row.scale_y = 1.2
            back_op = nav_row.operator("dynamx.setup_dynamx", text="Back", icon='TRIA_LEFT')
            back_op.go_back = True
            nav_row.operator("dynamx.setup_dynamx", text="Next", icon='TRIA_RIGHT')

        elif step == 4:
            layout.label(text="Step 5/9: Hitbox", icon='MESH_CUBE')

            row = layout.row()
            row.scale_y = 1.3
            row.operator("dynamx.create_hitbox", text="Create Hitbox", icon='ADD')

            box = layout.box()
            box.label(text="Auto Generate", icon='AUTO')
            box.prop(scene, "dynamx_max_hitboxes", text="Max Hitboxes")
            arow = box.row()
            arow.scale_y = 1.2
            arow.operator("dynamx.auto_generate_hitboxes", text="Auto Generate Hitboxes", icon='MOD_SIMPLIFY')
            arow.enabled = len(context.selected_objects) > 0

            row = layout.row(align=True)
            row.scale_y = 1.1
            row.operator("dynamx.delete_hitbox", text="Delete Hitbox", icon='TRASH')
            row.operator("dynamx.export_hitboxes", text="Export Hitboxes", icon='EXPORT')

            layout.separator()
            nav_row = layout.row(align=True)
            nav_row.scale_y = 1.2
            back_op = nav_row.operator("dynamx.setup_dynamx", text="Back", icon='TRIA_LEFT')
            back_op.go_back = True
            nav_row.operator("dynamx.setup_dynamx", text="Next", icon='TRIA_RIGHT')

        elif step == 5:
            layout.label(text="Step 6/9: Wheels", icon='MOD_SOLIDIFY')

            box = layout.box()
            if hasattr(scene, 'dynamx_wheel_model'):
                box.prop(scene, 'dynamx_wheel_model', text='Model')
            if hasattr(scene, 'dynamx_wheel_friction'):
                box.prop(scene, 'dynamx_wheel_friction', text='Friction')
            if hasattr(scene, 'dynamx_wheel_brake_force'):
                box.prop(scene, 'dynamx_wheel_brake_force', text='Brake Force')
            if hasattr(scene, 'dynamx_wheel_roll_influence'):
                box.prop(scene, 'dynamx_wheel_roll_influence', text='RollIn Influence')
            if hasattr(scene, 'dynamx_wheel_suspension_rest_length'):
                box.prop(scene, 'dynamx_wheel_suspension_rest_length', text='Suspension Rest Length')
            if hasattr(scene, 'dynamx_wheel_suspension_stiffness'):
                box.prop(scene, 'dynamx_wheel_suspension_stiffness', text='Suspension Stiffness')
            if hasattr(scene, 'dynamx_wheel_suspension_max_force'):
                box.prop(scene, 'dynamx_wheel_suspension_max_force', text='Suspension Max Force')
            if hasattr(scene, 'dynamx_wheel_damping_relaxation'):
                box.prop(scene, 'dynamx_wheel_damping_relaxation', text='Wheel Damping Relaxation')
            if hasattr(scene, 'dynamx_wheels_damping_compression'):
                box.prop(scene, 'dynamx_wheels_damping_compression', text='Wheels Damping Compression')
            if hasattr(scene, 'dynamx_wheel_steerable'):
                box.prop(scene, 'dynamx_wheel_steerable', text='Wheel Is Steerable')

            row = box.row()
            row.scale_y = 1.2
            row.operator("dynamx.set_wheel", text="Set Wheel (1-2 objects)", icon='MESH_CYLINDER')
            row.enabled = len(context.selected_objects) > 0

            if hasattr(scene, 'dynamx_replace_wheels'):
                box.prop(scene, 'dynamx_replace_wheels', text='Replace Wheels')

            row = box.row(align=True)
            row.scale_y = 1.2
            row.operator("dynamx.save_wheel", text="Save Wheel", icon='EXPORT')
            row.operator('dynamx.export_wheels', text='Export Wheels', icon='EXPORT')

            row = layout.row(align=True)
            row.scale_y = 1.1
            row.operator('dynamx.duplicate_wheel', text='Duplicate Wheel', icon='DUPLICATE')
            row.operator('dynamx.delete_wheel', text='Delete Wheel', icon='TRASH')

            irow = layout.row()
            irow.scale_y = 1.1
            irow.operator('dynamx.import_wheel', text='Import Wheel (from pack)', icon='IMPORT')

            layout.separator()
            nav_row = layout.row(align=True)
            nav_row.scale_y = 1.2
            back_op = nav_row.operator("dynamx.setup_dynamx", text="Back", icon='TRIA_LEFT')
            back_op.go_back = True
            nav_row.operator("dynamx.setup_dynamx", text="Next", icon='TRIA_RIGHT')

        elif step == 6:
            layout.label(text="Step 7/9: Basic Addon", icon='PLUGIN')

            _draw_basicaddon_section(layout, scene, context, show_title=False)

            layout.separator()
            nav_row = layout.row(align=True)
            nav_row.scale_y = 1.2
            back_op = nav_row.operator("dynamx.setup_dynamx", text="Zuruck", icon='TRIA_LEFT')
            back_op.go_back = True
            nav_row.operator("dynamx.setup_dynamx", text="Weiter", icon='TRIA_RIGHT')

        elif step == 7:
            layout.label(text="Step 8/9: Lights", icon='LIGHT')

            if hasattr(scene, 'dynamx_way_sender'):
                layout.prop(scene, 'dynamx_way_sender', text='Way Sender')

            _draw_light_material_settings(layout, scene)

            blink_box = layout.box()
            blink_box.label(text='Blinkers', icon='ARROW_LEFTRIGHT')
            brow = blink_box.row()
            brow.scale_y = 1.1
            brow.operator('dynamx.set_blinker_left', text='Set Blinker Left')
            brow.operator('dynamx.set_blinker_right', text='Set Blinker Right')

            main_box = layout.box()
            main_box.label(text='Main Lights', icon='LIGHT')
            hrow = main_box.row()
            hrow.scale_y = 1.1
            hrow.operator('dynamx.set_headlight', text='Set HeadLight')
            hrow.operator('dynamx.set_brakelights', text='Set BrakeLights')
            rrow = main_box.row()
            rrow.scale_y = 1.1
            rrow.operator('dynamx.set_reverse', text='Set Reverse')

            siren_box = layout.box()
            siren_box.label(text='Siren / RTK', icon='SOUND')
            srow = siren_box.row()
            srow.scale_y = 1.1
            srow.operator('dynamx.set_sirenlight', text='Set SirenLight')
            sb = siren_box.row()
            sb.scale_y = 1.1
            sb.operator('dynamx.set_lightbar_blue_l', text='Lightbar Blue Left')
            sb.operator('dynamx.set_lightbar_blue_r', text='Lightbar Blue Right')
            sb2 = siren_box.row()
            sb2.scale_y = 1.1
            sb2.operator('dynamx.set_dot_blue_l', text='Dot Blue Left')
            sb2.operator('dynamx.set_dot_blue_r', text='Dot Blue Right')

            export_row = layout.row()
            export_row.scale_y = 1.2
            export_row.operator('dynamx.export_lights', text='Export Lights', icon='EXPORT')

            layout.separator()
            nav_row = layout.row(align=True)
            nav_row.scale_y = 1.2
            back_op = nav_row.operator("dynamx.setup_dynamx", text="Back", icon='TRIA_LEFT')
            back_op.go_back = True
            nav_row.operator("dynamx.setup_dynamx", text="Next", icon='TRIA_RIGHT')

        else:
            layout.label(text="Step 9/9: OBJ Export", icon='EXPORT')

            scale_box = layout.box()
            scale_box.label(text="Vehicle Scale", icon='TRANSFORM_ORIGINS')
            if hasattr(scene, "dynamx_vehicle_scale"):
                scale_box.prop(scene, "dynamx_vehicle_scale", text="Scale Factor")
                update_row = scale_box.row(align=True)
                update_row.scale_y = 1.15
                update_row.operator("dynamx.update_scaled_parts", text="Update Scaled Parts", icon='MODIFIER')
            scale_box.label(text="(affects hitboxes, wheels, storage, tank)", icon='INFO')

            _draw_multitexture_section(layout, scene)
            _draw_export_section(layout, scene)

            layout.separator()
            back_row = layout.row()
            back_row.scale_y = 1.2
            back_op = back_row.operator("dynamx.setup_dynamx", text="Back", icon='TRIA_LEFT')
            back_op.go_back = True


class DYNMX_PT_general_panel(bpy.types.Panel):
    """Dynamx General Settings Panel"""
    bl_label = "Dynamx - General"
    bl_idname = "DYNMX_PT_general_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 0
    
    @classmethod
    def poll(cls, context):
        try:
            return context.workspace.name in ("Dynamx - Car", "Dynamx - Trailer", "Dynamx - Block")
        except Exception:
            return False
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.label(text="Pack Settings", icon='PACKAGE')
        
        box = layout.box()
        box.prop(scene, "dynamx_pack_name", text="Pack Name")
        box.prop(scene, "dynamx_pack_description", text="Description")
        box.prop(scene, "dynamx_pack_version", text="Pack Version")
        box.prop(scene, "dynamx_pack_path", text="Path")
        
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.create_pack", text="Set Pack", icon='FILE_FOLDER')
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.select_pack", text="Select Pack", icon='FILEBROWSER')


class DYNMX_PT_car_panel(bpy.types.Panel):
    """Dynamx Car Settings Panel"""
    bl_label = "Dynamx - Car"
    bl_idname = "DYNMX_PT_car_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 1
    
    @classmethod
    def poll(cls, context):
        try:
            wn = getattr(context.workspace, 'name', '')
            return wn == "Dynamx - Car"
        except Exception:
            return False
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        layout.label(text="Vehicle Settings", icon='AUTO')
        
        box = layout.box()
        box.prop(scene, "dynamx_vehicle_name", text="Vehicle Name")
        box.prop(scene, "dynamx_vehicle_description", text="Description")
        box.prop(scene, "dynamx_empty_mass", text="Empty Mass")
        if hasattr(scene, "dynamx_cog_offset"):
            box.prop(scene, "dynamx_cog_offset", text="Center Of Gravity Offset")
        if hasattr(scene, "dynamx_shape_y_offset"):
            box.prop(scene, "dynamx_shape_y_offset", text="Shape Y Offset")
        box.prop(scene, "dynamx_max_speed", text="Max Vehicle Speed")
        box.prop(scene, "dynamx_drag_coefficient", text="Drag Coefficient")
        box.prop(scene, "dynamx_zoom_level", text="Zoom Level")
        box.prop(scene, "dynamx_model", text="Model")
        box.prop(scene, "dynamx_default_engine", text="Default Engine")
        box.prop(scene, "dynamx_default_sounds", text="Default Sounds")
        
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.set_car", text="Set Car", icon='AUTO')
        
        layout.separator()

        multi_box = layout.box()
        multi_box.label(text="Multitexture", icon='MATERIAL')
        if hasattr(scene, 'dynamx_multitexture_material'):
            multi_box.prop_search(scene, 'dynamx_multitexture_material', bpy.data, 'materials', text='Material')

        add_row = multi_box.row(align=True)
        add_row.scale_y = 1.1
        add_row.operator("dynamx.add_material_variant", text="+", icon='ADD')

        variants = getattr(scene, 'dynamx_material_variants', None)
        if variants is None or len(variants) == 0:
            multi_box.label(text="No variants yet", icon='INFO')
        else:
            for idx, item in enumerate(variants):
                vrow = multi_box.row(align=True)
                vrow.prop(item, 'name', text='Name')
                vrow.prop(item, 'texture_path', text='Texture')
                rop = vrow.operator("dynamx.remove_material_variant", text="", icon='X')
                rop.index = idx

        layout.separator()
        
        export_box = layout.box()
        export_box.label(text="Export Settings:", icon='EXPORT')
        export_box.prop(scene, "dynamx_mtl_export_mode", text="MTL Export Mode")
        row = export_box.row()
        row.scale_y = 1.5
        row.operator("dynamx.export_obj", text="Export OBJ", icon='EXPORT')
        
        # Export MTL Only button (only show if ADD or REPLACE)
        mtl_mode = getattr(scene, 'dynamx_mtl_export_mode', 'REPLACE')
        if mtl_mode in ('ADD', 'REPLACE'):
            row = export_box.row()
            row.scale_y = 1.5
            row.operator("dynamx.export_mtl_only", text="Export MTL Only", icon='EXPORT')
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.select_vehicle", text="Select Vehicle", icon='FILEBROWSER')
        
        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.set_chassis", text="Set Chassis", icon='MESH_CUBE')
        row.enabled = context.active_object is not None

        layout.separator()

        essentials = layout.box()
        essentials.label(text="Essentials", icon='MODIFIER')
        steering_obj = _find_steering_wheel_object()

        sw_box = essentials.box()
        sw_box.label(text="Steering Wheel", icon='ORIENTATION_GIMBAL')
        if steering_obj is not None:
            sw_box.label(text=f"Current: {steering_obj.name}", icon='CHECKMARK')
        else:
            sw_box.label(text="Current: not set", icon='ERROR')

        row = sw_box.row()
        row.scale_y = 1.2
        row.operator("dynamx.set_steering_wheel", text="Set Steering Wheel", icon='ORIENTATION_GIMBAL')
        row.enabled = context.active_object is not None
        
        row = sw_box.row()
        row.scale_y = 1.2
        row.operator("dynamx.export_steering_wheel", text="Export Steering Wheel", icon='EXPORT')
        row.enabled = steering_obj is not None


class DYNMX_PT_block_panel(bpy.types.Panel):
    """Dynamx Block Settings Panel"""
    bl_label = "Dynamx - Block"
    bl_idname = "DYNMX_PT_block_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        try:
            return getattr(context.workspace, 'name', '') == "Dynamx - Block"
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Block Settings", icon='MESH_CUBE')

        box = layout.box()
        box.prop(scene, "dynamx_block_name", text="Block Name")
        box.prop(scene, "dynamx_block_description", text="Description")
        box.prop(scene, "dynamx_block_model", text="Model")
        box.prop(scene, "dynamx_block_scale", text="Scale")
        box.prop(scene, "dynamx_block_render_distance_squared", text="Render Distance Squared")
        box.prop(scene, "dynamx_block_creative_tab", text="Creative Tab")

        layout.separator()

        row = layout.row()
        row.scale_y = 1.3
        row.operator("dynamx.export_block_obj", text="Export OBJ", icon='EXPORT')

        layout.separator()

        prop_box = layout.box()
        prop_box.label(text="Prop", icon='OUTLINER_OB_EMPTY')
        prop_box.prop(scene, "dynamx_block_empty_mass", text="Empty Mass")
        prop_box.prop(scene, "dynamx_block_cog_offset", text="Center Of Gravity Offset")
        prop_box.prop(scene, "dynamx_block_friction", text="Friction")

        row = prop_box.row()
        row.scale_y = 1.3
        row.operator("dynamx.export_block", text="Export Block", icon='EXPORT')


class DYNMX_PT_extras(bpy.types.Panel):
    """Extras for Car workspace (no addon)"""
    bl_label = "Dynamx - Extras (No Addon)"
    bl_idname = "DYNMX_PT_extras"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 9

    @classmethod
    def poll(cls, context):
        try:
            return context.workspace.name == "Dynamx - Car"
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Trailer Extras (No Addon)")

        row = layout.row()
        row.scale_y = 1.4
        row.operator('dynamx.create_trailer_attach', text='Create Trailer Attach', icon='EMPTY_DATA')
        row = layout.row()
        row.scale_y = 1.3
        row.operator('dynamx.save_trailer_attach', text='Save Attach Point', icon='EXPORT')
        
        # Attach strength & save controls moved to Trailer workspace panel


class DYNMX_PT_trailer_panel(bpy.types.Panel):
    """Dynamx Trailer Settings Panel"""
    bl_label = "Dynamx - Trailer"
    bl_idname = "DYNMX_PT_trailer_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        try:
            return (context.workspace.name == "Dynamx - Trailer" and context.mode == 'OBJECT')
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Trailer Settings", icon='EMPTY_DATA')

        box = layout.box()
        box.prop(scene, "dynamx_vehicle_name", text="Trailer Name")
        box.prop(scene, "dynamx_vehicle_description", text="Description")
        box.prop(scene, "dynamx_empty_mass", text="Empty Mass")
        if hasattr(scene, "dynamx_cog_offset"):
            box.prop(scene, "dynamx_cog_offset", text="Center Of Gravity Offset")
        if hasattr(scene, "dynamx_shape_y_offset"):
            box.prop(scene, "dynamx_shape_y_offset", text="Shape Y Offset")
        box.prop(scene, "dynamx_drag_coefficient", text="Drag Coefficient")
        box.prop(scene, "dynamx_zoom_level", text="Zoom Level")
        box.prop(scene, "dynamx_model", text="Model")

        layout.separator()

        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.set_trailer", text="Set Trailer", icon='EMPTY_DATA')

        layout.separator()

        export_box = layout.box()
        export_box.label(text="Export Settings:", icon='EXPORT')
        export_box.prop(scene, "dynamx_mtl_export_mode", text="MTL Export Mode")
        row = export_box.row()
        row.scale_y = 1.5
        row.operator("dynamx.export_obj", text="Export OBJ", icon='EXPORT')
        
        # Export MTL Only button (only show if ADD or REPLACE)
        mtl_mode = getattr(scene, 'dynamx_mtl_export_mode', 'REPLACE')
        if mtl_mode in ('ADD', 'REPLACE'):
            row = export_box.row()
            row.scale_y = 1.5
            row.operator("dynamx.export_mtl_only", text="Export MTL Only", icon='EXPORT')

        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.select_trailer", text="Select Trailer", icon='FILEBROWSER')

        row = layout.row()
        row.scale_y = 1.5
        row.operator("dynamx.set_chassis", text="Set Chassis", icon='MESH_CUBE')
        row.enabled = context.active_object is not None

        layout.separator()
        row = layout.row()
        row.scale_y = 1.4
        row.operator('dynamx.create_trailer_attach', text='Create Trailer Attach', icon='EMPTY_DATA')

        box = layout.box()
        if hasattr(scene, 'dynamx_attach_strength'):
            box.prop(scene, 'dynamx_attach_strength', text='Attach Strength')
        brow = box.row()
        brow.scale_y = 1.3
        brow.operator('dynamx.save_trailer_attach', text='Save Attach Point', icon='EXPORT')


class DYNMX_PT_vehicle_seat(bpy.types.Panel):
    """Seat tools"""
    bl_label = "Dynamx - Seat"
    bl_idname = "DYNMX_PT_vehicle_seat"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 2

    @classmethod
    def poll(cls, context):
        try:
            wn = getattr(context.workspace, 'name', '')
            return (wn.startswith("Dynamx") and context.mode == 'OBJECT')
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Seats Tools", icon='OUTLINER_COLLECTION')
        
        row = layout.row()
        row.scale_y = 1.4
        op = row.operator("dynamx.summon_seat", text="Summon Seat (Sitting)", icon='MESH_CUBE')
        op.is_standing = False
        
        row = layout.row()
        row.scale_y = 1.4
        op = row.operator("dynamx.summon_seat", text="Summon Seat (Standing)", icon='MESH_CUBE')
        op.is_standing = True
        
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.2
        row.operator("dynamx.duplicate_seat", text="Duplicate Seat", icon='DUPLICATE')
        row = layout.row()
        row.scale_y = 1.2
        row.operator("dynamx.delete_seat", text="Delete Seat", icon='TRASH')
        
        layout.separator()
        
        box = layout.box()
        box.prop(scene, "dynamx_replace_seats", text="Replace Seats")
        row = box.row()
        row.scale_y = 1.5
        row.operator("dynamx.export_seats", text="Export Seats", icon='EXPORT')

        seats_col = bpy.data.collections.get("Seats")
        obj = context.active_object
        if seats_col and obj and obj.name in seats_col.objects and hasattr(obj, 'dynamx_is_standing'):
            layout.separator()
            box = layout.box()
            box.label(text="Selected Seat", icon='OBJECT_DATA')
            box.prop(obj, 'dynamx_is_standing', text='Standing Seat')


class DYNMX_PT_hitbox_panel(bpy.types.Panel):
    """Hitbox tools"""
    bl_label = "Dynamx - Hitbox"
    bl_idname = "DYNMX_PT_hitbox_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 3

    @classmethod
    def poll(cls, context):
        try:
            return (context.workspace.name in ("Dynamx - Car", "Dynamx - Trailer", "Dynamx - Block") and context.mode == 'OBJECT')
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Hitbox Tools", icon='MESH_CUBE')
        
        row = layout.row()
        row.scale_y = 1.4
        row.operator("dynamx.create_hitbox", text="Create Hitbox", icon='ADD')
        
        layout.separator()
        
        box = layout.box()
        box.label(text="Auto Generate", icon='AUTO')
        box.prop(scene, "dynamx_max_hitboxes", text="Max Hitboxes")
        row = box.row()
        row.scale_y = 1.3
        row.operator("dynamx.auto_generate_hitboxes", text="Auto Generate Hitboxes", icon='MOD_SIMPLIFY')
        row.enabled = len(context.selected_objects) > 0
        
        layout.separator()
        
        row = layout.row()
        row.scale_y = 1.2
        row.operator("dynamx.delete_hitbox", text="Delete Hitbox", icon='TRASH')
        
        row = layout.row()
        row.scale_y = 1.2
        row.operator("dynamx.export_hitboxes", text="Export Hitboxes", icon='EXPORT')


class DYNMX_PT_wheels_panel(bpy.types.Panel):
    """Wheels tools"""
    bl_label = "Dynamx - Wheels"
    bl_idname = "DYNMX_PT_wheels_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 4

    @classmethod
    def poll(cls, context):
        try:
            return (context.workspace.name in ("Dynamx - Car", "Dynamx - Trailer") and context.mode == 'OBJECT')
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Wheels Tools", icon='MOD_SOLIDIFY')

        box = layout.box()
        box.label(text="Wheel Parameters", icon='MESH_CYLINDER')
        if hasattr(scene, 'dynamx_wheel_model'):
            box.prop(scene, 'dynamx_wheel_model', text='Model')
        if hasattr(scene, 'dynamx_wheel_friction'):
            box.prop(scene, 'dynamx_wheel_friction', text='Friction')
        if hasattr(scene, 'dynamx_wheel_brake_force'):
            box.prop(scene, 'dynamx_wheel_brake_force', text='Brake Force')
        if hasattr(scene, 'dynamx_wheel_roll_influence'):
            box.prop(scene, 'dynamx_wheel_roll_influence', text='RollIn Influence')
        if hasattr(scene, 'dynamx_wheel_suspension_rest_length'):
            box.prop(scene, 'dynamx_wheel_suspension_rest_length', text='Suspension Rest Length')
        if hasattr(scene, 'dynamx_wheel_suspension_stiffness'):
            box.prop(scene, 'dynamx_wheel_suspension_stiffness', text='Suspension Stiffness')
        if hasattr(scene, 'dynamx_wheel_suspension_max_force'):
            box.prop(scene, 'dynamx_wheel_suspension_max_force', text='Suspension Max Force')
        if hasattr(scene, 'dynamx_wheel_damping_relaxation'):
            box.prop(scene, 'dynamx_wheel_damping_relaxation', text='Wheel Damping Relaxation')
        if hasattr(scene, 'dynamx_wheels_damping_compression'):
            box.prop(scene, 'dynamx_wheels_damping_compression', text='Wheels Damping Compression')

        if hasattr(scene, 'dynamx_wheel_steerable'):
            box.prop(scene, 'dynamx_wheel_steerable', text='Wheel Is Steerable')

        row = box.row()
        row.scale_y = 1.3
        row.operator("dynamx.set_wheel", text="Set Wheel (1-2 objects)", icon='MESH_CYLINDER')
        row.enabled = len(context.selected_objects) > 0

        box.prop(scene, 'dynamx_replace_wheels', text='Replace Wheels')
        
        row = box.row()
        row.scale_y = 1.4
        row.operator("dynamx.save_wheel", text="Save Wheel", icon='EXPORT')
        
        row = box.row()
        row.scale_y = 1.3
        row.operator('dynamx.export_wheels', text='Export Wheels', icon='EXPORT')

        row = layout.row()
        row.scale_y = 1.2
        row.operator('dynamx.duplicate_wheel', text='Duplicate Wheel', icon='DUPLICATE')
        row.operator('dynamx.delete_wheel', text='Delete Wheel', icon='TRASH')

        irow = layout.row()
        irow.scale_y = 1.2
        irow.operator('dynamx.import_wheel', text='Import Wheel (from pack)', icon='IMPORT')


class DYNMX_PT_clothing_panel(bpy.types.Panel):
    """Clothing tools"""
    bl_label = "Dynamx - Clothing"
    bl_idname = "DYNMX_PT_clothing_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        try:
            return context.workspace.name == "Clothing - Dynamx"
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Clothing Settings", icon='MOD_CLOTH')

        box = layout.box()
        box.prop(scene, "dynamx_clothing_name", text="Name")
        box.prop(scene, "dynamx_clothing_description", text="Description")
        box.prop(scene, "dynamx_clothing_model", text="Model")
        if hasattr(scene, 'dynamx_mtl_export_mode'):
            box.prop(scene, 'dynamx_mtl_export_mode', text='MTL Export Mode')

        row = box.row()
        row.scale_y = 1.2
        row.operator("dynamx.set_clothing", text="Set Clothing", icon='CHECKMARK')

        row = box.row()
        row.scale_y = 1.2
        row.operator("dynamx.export_clothing_obj", text="Export OBJ", icon='EXPORT')

        parts = layout.box()
        parts.label(text="Armor Parts", icon='OUTLINER_OB_MESH')

        head_row = parts.row()
        head_row.scale_y = 1.1
        head_row.operator("dynamx.set_clothing_head", text="Set Head (headModel)", icon='MESH_UVSPHERE')
        head_row.enabled = context.active_object is not None

        body_row = parts.row()
        body_row.scale_y = 1.1
        body_row.operator("dynamx.set_clothing_body", text="Set Body (bodyModel)", icon='MESH_CUBE')
        body_row.enabled = context.active_object is not None

        arm_row = parts.row(align=True)
        arm_row.scale_y = 1.1
        arm_row.operator("dynamx.set_clothing_left_arm", text="Left Arm", icon='TRIA_LEFT')
        arm_row.operator("dynamx.set_clothing_right_arm", text="Right Arm", icon='TRIA_RIGHT')
        arm_row.enabled = context.active_object is not None

        leg_row = parts.row(align=True)
        leg_row.scale_y = 1.1
        leg_row.operator("dynamx.set_clothing_left_leg", text="Left Leg", icon='TRIA_LEFT')
        leg_row.operator("dynamx.set_clothing_right_leg", text="Right Leg", icon='TRIA_RIGHT')
        leg_row.enabled = context.active_object is not None

        variants_box = layout.box()
        variants_box.label(text="Material Variants", icon='MATERIAL')

        add_row = variants_box.row(align=True)
        add_row.scale_y = 1.1
        add_row.operator("dynamx.add_material_variant", text="+", icon='ADD')

        variants = getattr(scene, 'dynamx_material_variants', None)
        if variants is None or len(variants) == 0:
            variants_box.label(text="No variants yet", icon='INFO')
        else:
            for idx, item in enumerate(variants):
                vrow = variants_box.row(align=True)
                vrow.prop(item, 'name', text=f"Variant {idx + 1}")
                rop = vrow.operator("dynamx.remove_material_variant", text="", icon='X')
                rop.index = idx

        variants_box.label(text="Will be written into armor.dynx when using Set Clothing", icon='INFO')

        parts.separator()
        part_names = ("headModel", "bodyModel", "leftArmModel", "rightArmModel", "leftLegModel", "rightLegModel")
        for part_name in part_names:
            exists = bpy.data.objects.get(part_name) is not None
            if not exists and part_name == "headModel":
                exists = bpy.data.objects.get("headmodel") is not None
            icon = 'CHECKMARK' if exists else 'ERROR'
            parts.label(text=part_name, icon=icon)


class DYNMX_MT_workspace_menu(bpy.types.Menu):
    bl_label = "Dynamx"
    bl_idname = "DYNMX_MT_workspace_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("dynamx.create_workspace", icon='WORKSPACE')
        layout.operator("dynamx.create_trailer_workspace", icon='WORKSPACE')
        layout.operator("dynamx.create_block_workspace", icon='WORKSPACE')
        layout.operator("dynamx.create_clothing_workspace", icon='WORKSPACE')


def menu_func(self, context):
    self.layout.menu(DYNMX_MT_workspace_menu.bl_idname)


classes = (DYNMX_PT_setup_main, DYNMX_PT_general_panel, DYNMX_PT_car_panel, DYNMX_PT_block_panel, DYNMX_PT_clothing_panel, DYNMX_PT_extras, DYNMX_PT_trailer_panel, DYNMX_PT_vehicle_seat, DYNMX_PT_hitbox_panel, DYNMX_PT_wheels_panel, DYNMX_MT_workspace_menu)


class DYNMX_PT_basic_panel(bpy.types.Panel):
    """Basic addon panel (License Plate)"""
    bl_label = "Dynamx - BasicAddon"
    bl_idname = "DYNMX_PT_basic_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 5

    @classmethod
    def poll(cls, context):
        try:
            ws = getattr(context, 'workspace', None)
            wn = getattr(ws, 'name', '') if ws else ''
            return wn in ("Dynamx - Car", "Dynamx - Trailer")
        except Exception:
            return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        _draw_basicaddon_section(layout, scene, context, show_title=True)

classes = (DYNMX_PT_setup_main, DYNMX_PT_general_panel, DYNMX_PT_car_panel, DYNMX_PT_block_panel, DYNMX_PT_clothing_panel, DYNMX_PT_extras, DYNMX_PT_trailer_panel, DYNMX_PT_vehicle_seat, DYNMX_PT_hitbox_panel, DYNMX_PT_wheels_panel, DYNMX_MT_workspace_menu, DYNMX_PT_basic_panel)


class DYNMX_PT_lights_panel(bpy.types.Panel):
    """Lights tools"""
    bl_label = "Dynamx - Lights"
    bl_idname = "DYNMX_PT_lights_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 6

    @classmethod
    def poll(cls, context):
        try:
            ws = context.workspace
            if ws and getattr(ws, 'name', None):
                return ws.name in ("Dynamx - Car", "Dynamx - Trailer")
        except Exception:
            pass
        return False

    def draw(self, context):
        try:
            layout = self.layout
            scene = context.scene
            if hasattr(scene, 'dynamx_way_sender'):
                layout.prop(scene, 'dynamx_way_sender', text='Way Sender')

            _draw_light_material_settings(layout, scene)

            blink_box = layout.box()
            blink_box.label(text='Blinkers', icon='ARROW_LEFTRIGHT')
            brow = blink_box.row()
            brow.scale_y = 1.2
            brow.operator('dynamx.set_blinker_left', text='Set Blinker Left')
            brow.operator('dynamx.set_blinker_right', text='Set Blinker Right')

            main_box = layout.box()
            main_box.label(text='Main Lights', icon='LIGHT')
            hrow = main_box.row()
            hrow.scale_y = 1.2
            hrow.operator('dynamx.set_headlight', text='Set HeadLight')
            hrow.operator('dynamx.set_brakelights', text='Set BrakeLights')
            rrow = main_box.row()
            rrow.scale_y = 1.2
            rrow.operator('dynamx.set_reverse', text='Set Reverse')

            siren_box = layout.box()
            siren_box.label(text='Siren', icon='SOUND')
            srow = siren_box.row()
            srow.scale_y = 1.2
            srow.operator('dynamx.set_sirenlight', text='Set SirenLight')

            layout.separator()
            sbox = layout.box()
            sbox.label(text='Siren / RTK', icon='SOUND')
            sb = sbox.row()
            sb.scale_y = 1.1
            sb.operator('dynamx.set_lightbar_blue_l', text='Lightbar Blue Left')
            sb.operator('dynamx.set_lightbar_blue_r', text='Lightbar Blue Right')
            sb2 = sbox.row()
            sb2.scale_y = 1.1
            sb2.operator('dynamx.set_dot_blue_l', text='Dot Blue Left')
            sb2.operator('dynamx.set_dot_blue_r', text='Dot Blue Right')

            layout.separator()
            lrow = layout.row()
            lrow.scale_y = 1.3
            lrow.operator('dynamx.export_lights', text='Export Lights', icon='EXPORT')
        except Exception as _e:
            try:
                layout = self.layout
                layout.label(text=f"Lights panel error: {_e}", icon='ERROR')
            except Exception:
                pass

classes = classes + (DYNMX_PT_lights_panel,)


class DYNMX_PT_doors_panel(bpy.types.Panel):
    """Door tools"""
    bl_label = "Dynamx - Door"
    bl_idname = "DYNMX_PT_doors_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 7

    @classmethod
    def poll(cls, context):
        try:
            ws = context.workspace
            if ws and getattr(ws, 'name', None):
                return ws.name in ("Dynamx - Car", "Dynamx - Trailer")
        except Exception:
            pass
        return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        box = layout.box()
        box.label(text='Doors', icon='MESH_CUBE')
        if hasattr(scene, 'dynamx_door_name'):
            box.prop(scene, 'dynamx_door_name', text='Door Name')
        if hasattr(scene, 'dynamx_door_open_angle'):
            box.prop(scene, 'dynamx_door_open_angle', text='Open Angle')
        if hasattr(scene, 'dynamx_door_axis'):
            box.prop(scene, 'dynamx_door_axis', text='Axis')

        brow = box.row()
        brow.scale_y = 1.2
        brow.operator('dynamx.set_door', text='Set Door', icon='OUTLINER_OB_MESH')
        brow.operator('dynamx.export_doors', text='Export Doors', icon='EXPORT')


class DYNMX_PT_hide_parts_panel(bpy.types.Panel):
    """Hideable parts tools"""
    bl_label = "Dynamx - Hide Parts"
    bl_idname = "DYNMX_PT_hide_parts_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Dynamx'
    bl_order = 8

    @classmethod
    def poll(cls, context):
        try:
            ws = context.workspace
            if ws and getattr(ws, 'name', None):
                return ws.name in ("Dynamx - Car", "Dynamx - Trailer")
        except Exception:
            pass
        return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        box = layout.box()
        box.label(text='Hideable Parts', icon='HIDE_OFF')
        if hasattr(scene, 'dynamx_hide_part_name'):
            box.prop(scene, 'dynamx_hide_part_name', text='Part Name')
        if hasattr(scene, 'dynamx_hide_default_state'):
            box.prop(scene, 'dynamx_hide_default_state', text='Default State')

        brow = box.row()
        brow.scale_y = 1.2
        brow.operator('dynamx.set_hide_parts', text='Set Parts', icon='RESTRICT_VIEW_OFF')

        try:
            groups = {}
            for o in bpy.data.objects:
                part = o.get('dynamx_hide_part')
                if part:
                    groups.setdefault(part, []).append(o.name)
            if groups:
                box.separator()
                box.label(text='Existing Hideable Parts:')
                for part, objs in groups.items():
                    row = box.row()
                    row.label(text=f"{part} ({len(objs)})")
                    col = box.column()
                    for name in objs:
                        col.label(text=f"  {name}")
        except Exception:
            pass

classes = classes + (DYNMX_PT_doors_panel, DYNMX_PT_hide_parts_panel)


def _unregister_by_name(class_name):
    existing = getattr(bpy.types, class_name, None)
    if existing is None:
        return False
    try:
        bpy.utils.unregister_class(existing)
        return True
    except Exception:
        return False


def register():
    for c in classes:
        _unregister_by_name(c.__name__)
        try:
            bpy.utils.register_class(c)
        except Exception as e:
            if "already registered as a subclass" in str(e):
                _unregister_by_name(c.__name__)
                try:
                    bpy.utils.unregister_class(c)
                except Exception:
                    pass
                try:
                    bpy.utils.register_class(c)
                except Exception as e2:
                    if "already registered as a subclass" in str(e2):
                        # Keep going if Blender still keeps a stale registration record.
                        continue
                    raise
            else:
                raise
    try:
        bpy.types.TOPBAR_MT_window.remove(menu_func)
    except Exception:
        pass
    bpy.types.TOPBAR_MT_window.append(menu_func)


def unregister():
    try:
        bpy.types.TOPBAR_MT_window.remove(menu_func)
    except Exception:
        pass
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            _unregister_by_name(c.__name__)
