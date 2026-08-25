"""
Main operators module - imports all operator modules
This file serves as a compatibility layer for the old structure
"""

import bpy
from bpy.props import StringProperty, FloatProperty, FloatVectorProperty, BoolProperty
from bpy.types import Scene

from . import ops_workspace
from . import ops_pack
from . import ops_vehicle
from . import ops_block
from . import ops_clothing
from . import ops_seat
from . import ops_hitbox
from . import ops_basic

from .ops_workspace import DYNMX_OT_create_workspace, DYNMX_OT_setup_dynamx, DYNMX_OT_create_clothing_workspace
from .ops_pack import DYNMX_OT_create_pack, DYNMX_OT_select_pack
from .ops_vehicle import DYNMX_OT_set_car, DYNMX_OT_set_steering_wheel, DYNMX_OT_apply_steering_wheel_rotation, DYNMX_OT_export_steering_wheel, DYNMX_OT_select_vehicle, DYNMX_OT_set_chassis, DYNMX_OT_save_wheel, DYNMX_OT_set_wheel, DYNMX_OT_export_wheels, DYNMX_OT_duplicate_wheel, DYNMX_OT_delete_wheel, DYNMX_OT_update_scaled_parts, DYNMX_OT_set_trailer, DYNMX_OT_select_trailer, DYNMX_OT_create_trailer_attach, DYNMX_OT_save_trailer_attach, DYNMX_OT_add_material_variant, DYNMX_OT_remove_material_variant, DYNMX_OT_export_material_variants, DYNMX_OT_generate_hitboxes, DYNMX_OT_export_obj, DYNMX_OT_export_mtl_only
from .ops_block import DYNMX_OT_set_block
from .ops_clothing import DYNMX_OT_set_clothing, DYNMX_OT_export_clothing_obj, DYNMX_OT_set_clothing_head, DYNMX_OT_set_clothing_body, DYNMX_OT_set_clothing_left_arm, DYNMX_OT_set_clothing_right_arm, DYNMX_OT_set_clothing_left_leg, DYNMX_OT_set_clothing_right_leg
from .ops_seat import DYNMX_OT_summon_seat, DYNMX_OT_duplicate_seat, DYNMX_OT_delete_seat, DYNMX_OT_export_seats
from .ops_hitbox import DYNMX_OT_create_hitbox, DYNMX_OT_auto_generate_hitboxes, DYNMX_OT_export_hitboxes, DYNMX_OT_delete_hitbox
from .ops_basic import DYNMX_OT_summon_license_plate, DYNMX_OT_summon_storage, DYNMX_OT_set_storage, DYNMX_OT_import_wheel

modules = (ops_workspace, ops_pack, ops_vehicle, ops_block, ops_clothing, ops_seat, ops_hitbox, ops_basic)


def register():
    for m in modules:
        if hasattr(m, 'register'):
            m.register()
    
    Scene.dynamx_pack_name = StringProperty(
        name="Pack Name",
        description="Name of the pack folder to create",
        default="MyPack"
    )
    Scene.dynamx_pack_description = StringProperty(
        name="Description",
        description="Pack description",
        default="A Dynamx content pack"
    )
    Scene.dynamx_pack_version = StringProperty(
        name="Pack Version",
        description="Version of the pack",
        default="1.0"
    )
    Scene.dynamx_pack_path = StringProperty(
        name="Pack Path",
        description="Directory where the pack folder will be created",
        default="",
        subtype='DIR_PATH'
    )
    
    Scene.dynamx_vehicle_name = StringProperty(
        name="Vehicle Name",
        description="Name of the vehicle",
        default="MyCar"
    )
    Scene.dynamx_vehicle_description = StringProperty(
        name="Description",
        description="Vehicle description",
        default="A custom vehicle"
    )
    Scene.dynamx_empty_mass = FloatProperty(
        name="Empty Mass",
        description="Empty mass of the vehicle in kg",
        default=5000.0,
        min=0.0,
        step=100,
        precision=0
    )
    Scene.dynamx_max_speed = FloatProperty(
        name="Max Vehicle Speed",
        description="Maximum vehicle speed",
        default=120.0,
        min=0.0,
        step=10,
        precision=0
    )
    Scene.dynamx_drag_coefficient = FloatProperty(
        name="Drag Coefficient",
        description="Drag coefficient of the vehicle",
        default=0.7,
        min=0.0,
        max=2.0,
        step=1,
        precision=2
    )
    Scene.dynamx_zoom_level = FloatProperty(
        name="Zoom Level",
        description="Camera zoom level",
        default=5.0,
        min=1.0,
        step=1,
        precision=0
    )
    Scene.dynamx_cog_offset = FloatVectorProperty(
        name="Center Of Gravity Offset",
        description="Center of gravity offset (X, Y, Z)",
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=2
    )
    Scene.dynamx_shape_y_offset = FloatProperty(
        name="Shape Y Offset",
        description="Shape Y offset for vehicle collision",
        default=0.0,
        step=1,
        precision=2
    )
    Scene.dynamx_model = StringProperty(
        name="Model",
        description="Name of the 3D model file (without .obj extension)",
        default=""
    )
    Scene.dynamx_vehicle_scale = FloatProperty(
        name="Vehicle Scale",
        description="Scale multiplier applied to export-relevant runtime parts (hitboxes, wheel size, storage, fuel tank), while leaving seats and orientation helpers unchanged.",
        default=1.0,
        min=0.01,
        max=10.0,
        step=10,
        precision=3
    )
    Scene.dynamx_default_engine = StringProperty(
        name="Default Engine",
        description="Name of the default engine configuration",
        default=""
    )
    Scene.dynamx_default_sounds = StringProperty(
        name="Default Sounds",
        description="Name of the default sounds configuration",
        default=""
    )
    Scene.dynamx_clothing_name = StringProperty(
        name="Clothing Name",
        description="Name of the clothing/armor",
        default="MyClothing"
    )
    Scene.dynamx_clothing_description = StringProperty(
        name="Clothing Description",
        description="Description of the clothing/armor",
        default="A custom clothing"
    )
    Scene.dynamx_clothing_model = StringProperty(
        name="Clothing Model",
        description="Relative model path, e.g. obj/baujacke/baujacke.obj",
        default=""
    )
    Scene.dynamx_block_name = StringProperty(
        name="Block Name",
        description="Name of the block",
        default="Blue Table"
    )
    Scene.dynamx_block_description = StringProperty(
        name="Block Description",
        description="Description of the block",
        default=""
    )
    Scene.dynamx_block_model = StringProperty(
        name="Block Model",
        description="Relative model path for the block",
        default=""
    )
    Scene.dynamx_block_scale = FloatVectorProperty(
        name="Block Scale",
        description="Scale of the block in X, Y, Z",
        size=3,
        default=(1.0, 1.0, 1.0),
        precision=3
    )
    Scene.dynamx_block_render_distance_squared = bpy.props.IntProperty(
        name="Render Distance Squared",
        description="Render distance squared for the block",
        default=2500,
        min=0
    )
    Scene.dynamx_block_creative_tab = StringProperty(
        name="Creative Tab",
        description="Creative tab name",
        default=""
    )
    Scene.dynamx_block_empty_mass = bpy.props.IntProperty(
        name="Empty Mass",
        description="Empty mass of the prop block",
        default=300,
        min=0
    )
    Scene.dynamx_block_cog_offset = FloatVectorProperty(
        name="Center Of Gravity Offset",
        description="Center of gravity offset (X, Y, Z)",
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=3
    )
    Scene.dynamx_block_friction = bpy.props.IntProperty(
        name="Friction",
        description="Friction value of the prop block",
        default=2,
        min=0
    )
    Scene.dynamx_mtl_export_mode = bpy.props.EnumProperty(
        name="MTL Export Mode",
        description="How to handle material exports",
        items=[
            ('NONE', "No MTL", "Don't export MTL files"),
            ('ADD', "Add to MTL", "Add materials to existing MTL"),
            ('REPLACE', "Replace MTL", "Replace existing MTL file")
        ],
        default='REPLACE'
    )
    Scene.dynamx_max_hitboxes = bpy.props.IntProperty(
        name="Max Hitboxes",
        description="Maximum number of hitboxes to generate automatically",
        default=10,
        min=1,
        max=50
    )
    Scene.dynamx_replace_seats = BoolProperty(
        name="Replace Seats",
        description="When exporting seats, replace existing seats with matching names. If false, only add missing seats.",
        default=False
    )
    Scene.dynamx_replace_wheels = BoolProperty(
        name="Replace Wheels",
        description="When exporting wheels, replace existing wheel objects in the 'wheels' collection.",
        default=False
    )
    Scene.dynamx_wheel_model = StringProperty(
        name="Wheel Model",
        description="Name of the wheel model",
        default=""
    )
    Scene.dynamx_wheel_friction = FloatProperty(
        name="Friction",
        description="Wheel friction value",
        default=1.0,
        min=0.0
    )
    Scene.dynamx_wheel_brake_force = FloatProperty(
        name="Brake Force",
        description="Brake force",
        default=100.0,
        min=0.0
    )
    Scene.dynamx_wheel_roll_influence = FloatProperty(
        name="RollInInfluence",
        description="Roll influence value",
        default=1.0,
        min=0.0
    )
    Scene.dynamx_wheel_suspension_rest_length = FloatProperty(
        name="Suspension Rest Length",
        description="Suspension rest length",
        default=0.13,
        min=0.0
    )
    Scene.dynamx_wheel_suspension_stiffness = FloatProperty(
        name="Suspension Stiffness",
        description="Suspension stiffness",
        default=20.0,
        min=0.0
    )
    Scene.dynamx_wheel_suspension_max_force = FloatProperty(
        name="Suspension Max Force",
        description="Max suspension force",
        default=1000000.0, 
        min=0.0
    )
    Scene.dynamx_wheel_damping_relaxation = FloatProperty(
        name="Damping Relaxation",
        description="Wheel damping relaxation",
        default=0.45,
        min=0.0
    )
    Scene.dynamx_wheels_damping_compression = FloatProperty(
        name="Damping Compression",
        description="Wheels damping compression",
        default=0.2,
        min=0.0
    )
    Scene.dynamx_wheel_steerable = BoolProperty(
        name="Wheel Is Steerable",
        description="Default steerable flag to apply when creating or duplicating wheels",
        default=False
    )
    Scene.dynamx_steering_rotation_deg = FloatVectorProperty(
        name="Steering Rotation (deg)",
        description="Steering wheel rotation in degrees (X, Y, Z). Export uses quaternion from this value.",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype='XYZ',
        precision=3
    )
    Scene.dynamx_material_variants = bpy.props.CollectionProperty(
        type=ops_vehicle.DYNMX_PG_material_variant
    )
    Scene.dynamx_material_variants_index = bpy.props.IntProperty(
        name="Material Variant Index",
        default=0,
        min=0
    )
    Scene.dynamx_multitexture_material = StringProperty(
        name="Multitexture Material",
        description="Material name whose MTL block receives color map_Kd variant lines",
        default=""
    )
    Scene.dynamx_setup_show_vehicle = BoolProperty(
        name="Setup Show Vehicle",
        description="Internal setup step flag",
        default=False
    )
    Scene.dynamx_setup_show_essentials = BoolProperty(
        name="Setup Show Essentials",
        description="Internal setup essentials step flag",
        default=False
    )
    Scene.dynamx_setup_step = bpy.props.IntProperty(
        name="Setup Step",
        description="Internal setup step index",
        default=0,
        min=0,
        max=8,
        options={'SKIP_SAVE'}
    )

    Scene.dynamx_license_plate_text = StringProperty(
        name="License Plate",
        description="Text to place on summoned license plate",
        default="YC @@ %%%%"
    )
    def _storage_size_update(self, context):
        try:
            val = int(self.dynamx_storage_size)
            if val <= 0:
                val = 9
            new = max(9, int(round(val / 9.0) * 9))
            if new != val:
                try:
                    self.dynamx_storage_size = new
                except Exception:
                    pass
        except Exception:
            try:
                self.dynamx_storage_size = 9
            except Exception:
                pass

    Scene.dynamx_storage_size = bpy.props.IntProperty(
        name="Storage Size",
        description="Inventory size (must be divisible by 9)",
        default=9,
        min=9,
        update=_storage_size_update,
    )

    Scene.dynamx_fueltank_size = bpy.props.IntProperty(
        name="Fuel Tank Size",
        description="Fuel tank capacity (invspace) - independent from storage size",
        default=200,
        min=1,
    )

    Scene.dynamx_way_sender = BoolProperty(
        name="Way Sender",
        description="Enable way sender indicator (used for additional blinker exports)",
        default=False
    )

    Scene.dynamx_use_basic_light_textures = BoolProperty(
        name="Use basic textures",
        description="Automatically create and assign the default Lights / Lights_Glass materials and off/on textures for new light objects",
        default=True,
    )
    Scene.dynamx_combine_main_lights_materials = BoolProperty(
        name="Combine Main Lights Materials",
        description="Use one shared main light material and one shared on/off texture pair",
        default=True,
    )
    Scene.dynamx_main_lights_material = StringProperty(
        name="Main Lights Material",
        description="Material name used for combined main lights",
        default="main_light",
    )
    Scene.dynamx_main_lights_texture_off = StringProperty(
        name="Main Lights Off Texture",
        description="Texture used when main lights are off",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_main_lights_texture_on = StringProperty(
        name="Main Lights On Texture",
        description="Texture used when main lights are on",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_main_lights_glass_material = StringProperty(
        name="Main Lights Glass Material",
        description="Additional glass material used for the light object",
        default="lights_glass",
    )

    Scene.dynamx_headlight_material = StringProperty(
        name="Headlight Material",
        description="Material name for headlight",
        default="headlight",
    )
    Scene.dynamx_headlight_texture_off = StringProperty(
        name="Headlight Off Texture",
        description="Headlight off texture",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_headlight_texture_on = StringProperty(
        name="Headlight On Texture",
        description="Headlight on texture",
        default="",
        subtype='FILE_PATH',
    )

    Scene.dynamx_brakelights_material = StringProperty(
        name="BrakeLights Material",
        description="Material name for brakelights",
        default="brakelights",
    )
    Scene.dynamx_brakelights_texture_off = StringProperty(
        name="BrakeLights Off Texture",
        description="BrakeLights off texture",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_brakelights_texture_on = StringProperty(
        name="BrakeLights On Texture",
        description="BrakeLights on texture",
        default="",
        subtype='FILE_PATH',
    )

    Scene.dynamx_reverselights_material = StringProperty(
        name="ReverseLights Material",
        description="Material name for reverselights",
        default="reverselights",
    )
    Scene.dynamx_reverselights_texture_off = StringProperty(
        name="ReverseLights Off Texture",
        description="ReverseLights off texture",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_reverselights_texture_on = StringProperty(
        name="ReverseLights On Texture",
        description="ReverseLights on texture",
        default="",
        subtype='FILE_PATH',
    )

    Scene.dynamx_blinker_left_material = StringProperty(
        name="Blinker Left Material",
        description="Material name for left blinker",
        default="blinker_left",
    )
    Scene.dynamx_blinker_left_texture_off = StringProperty(
        name="Blinker Left Off Texture",
        description="Blinker left off texture",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_blinker_left_texture_on = StringProperty(
        name="Blinker Left On Texture",
        description="Blinker left on texture",
        default="",
        subtype='FILE_PATH',
    )

    Scene.dynamx_blinker_right_material = StringProperty(
        name="Blinker Right Material",
        description="Material name for right blinker",
        default="blinker_right",
    )
    Scene.dynamx_blinker_right_texture_off = StringProperty(
        name="Blinker Right Off Texture",
        description="Blinker right off texture",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_blinker_right_texture_on = StringProperty(
        name="Blinker Right On Texture",
        description="Blinker right on texture",
        default="",
        subtype='FILE_PATH',
    )

    Scene.dynamx_sirenlight_material = StringProperty(
        name="Siren / RTK Material",
        description="Material name for siren/RTK light textures",
        default="lightbar_light",
    )
    Scene.dynamx_sirenlight_texture_off = StringProperty(
        name="Siren / RTK Off Texture",
        description="Siren/RTK off texture",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_sirenlight_texture_on = StringProperty(
        name="Siren / RTK On Texture",
        description="Siren/RTK on texture",
        default="",
        subtype='FILE_PATH',
    )
    Scene.dynamx_sirenlight_on_token = StringProperty(
        name="Siren / RTK On Token",
        description="Token appended to map_Kd for siren/RTK on texture",
        default="lightbar_on",
    )

    Scene.dynamx_attach_strength = FloatProperty(
        name="Attach Strength",
        description="Strength used when saving trailer attach points",
        default=100000.0,
        min=0.0,
    )

    Scene.dynamx_door_name = bpy.props.StringProperty(
        name="Door Name",
        description="Name to assign to the door",
        default="door"
    )
    Scene.dynamx_door_open_angle = bpy.props.FloatProperty(
        name="Open Angle",
        description="Open angle in radians",
        default=1.0,
        
    )
    Scene.dynamx_door_axis = bpy.props.EnumProperty(
        name="Axis",
        description="Axis to rotate the door around",
        items=[('X_ROT', 'X_ROT', 'Rotate around X'), ('Y_ROT', 'Y_ROT', 'Rotate around Y'), ('Z_ROT', 'Z_ROT', 'Rotate around Z')],
        default='Z_ROT'
    )

    Scene.dynamx_hide_part_name = bpy.props.StringProperty(
        name="Part Name",
        description="Name of the hideable part group",
        default="part"
    )
    Scene.dynamx_hide_default_state = bpy.props.BoolProperty(
        name="Default State",
        description="Default visible state for the hideable part",
        default=True
    )


def unregister():
    def _safe_del(attr):
        try:
            delattr(Scene, attr)
        except Exception:
            pass

    _safe_del('dynamx_pack_name')
    _safe_del('dynamx_pack_description')
    _safe_del('dynamx_pack_version')
    _safe_del('dynamx_pack_path')
    _safe_del('dynamx_vehicle_name')
    _safe_del('dynamx_vehicle_description')
    _safe_del('dynamx_empty_mass')
    _safe_del('dynamx_max_speed')
    _safe_del('dynamx_drag_coefficient')
    _safe_del('dynamx_zoom_level')
    _safe_del('dynamx_cog_offset')
    _safe_del('dynamx_shape_y_offset')
    _safe_del('dynamx_model')
    _safe_del('dynamx_default_engine')
    _safe_del('dynamx_default_sounds')
    _safe_del('dynamx_clothing_name')
    _safe_del('dynamx_clothing_description')
    _safe_del('dynamx_clothing_model')
    _safe_del('dynamx_block_name')
    _safe_del('dynamx_block_description')
    _safe_del('dynamx_block_model')
    _safe_del('dynamx_block_scale')
    _safe_del('dynamx_block_render_distance_squared')
    _safe_del('dynamx_block_creative_tab')
    _safe_del('dynamx_block_empty_mass')
    _safe_del('dynamx_block_cog_offset')
    _safe_del('dynamx_block_friction')
    _safe_del('dynamx_mtl_export_mode')
    _safe_del('dynamx_max_hitboxes')
    _safe_del('dynamx_replace_seats')
    try:
        del Scene.dynamx_replace_wheels
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_model
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_friction
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_brake_force
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_roll_influence
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_suspension_rest_length
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_suspension_stiffness
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_suspension_max_force
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_damping_relaxation
    except Exception:
        pass
    try:
        del Scene.dynamx_wheels_damping_compression
    except Exception:
        pass
    try:
        del Scene.dynamx_wheel_steerable
    except Exception:
        pass
    try:
        del Scene.dynamx_steering_rotation_deg
    except Exception:
        pass
    try:
        del Scene.dynamx_material_variants
    except Exception:
        pass
    try:
        del Scene.dynamx_material_variants_index
    except Exception:
        pass
    _safe_del('dynamx_multitexture_material')
    try:
        del Scene.dynamx_setup_show_vehicle
    except Exception:
        pass
    try:
        del Scene.dynamx_setup_show_essentials
    except Exception:
        pass
    try:
        del Scene.dynamx_setup_step
    except Exception:
        pass
    try:
        del Scene.dynamx_license_plate_text
    except Exception:
        pass
    try:
        del Scene.dynamx_storage_size
    except Exception:
        pass
    try:
        del Scene.dynamx_fueltank_size
    except Exception:
        pass
    try:
        del Scene.dynamx_way_sender
    except Exception:
        pass
    _safe_del('dynamx_use_basic_light_textures')
    _safe_del('dynamx_combine_main_lights_materials')
    _safe_del('dynamx_main_lights_material')
    _safe_del('dynamx_main_lights_texture_off')
    _safe_del('dynamx_main_lights_texture_on')
    _safe_del('dynamx_headlight_material')
    _safe_del('dynamx_headlight_texture_off')
    _safe_del('dynamx_headlight_texture_on')
    _safe_del('dynamx_brakelights_material')
    _safe_del('dynamx_brakelights_texture_off')
    _safe_del('dynamx_brakelights_texture_on')
    _safe_del('dynamx_reverselights_material')
    _safe_del('dynamx_reverselights_texture_off')
    _safe_del('dynamx_reverselights_texture_on')
    _safe_del('dynamx_blinker_left_material')
    _safe_del('dynamx_blinker_left_texture_off')
    _safe_del('dynamx_blinker_left_texture_on')
    _safe_del('dynamx_blinker_right_material')
    _safe_del('dynamx_blinker_right_texture_off')
    _safe_del('dynamx_blinker_right_texture_on')
    _safe_del('dynamx_sirenlight_material')
    _safe_del('dynamx_sirenlight_texture_off')
    _safe_del('dynamx_sirenlight_texture_on')
    _safe_del('dynamx_sirenlight_on_token')
    try:
        del Scene.dynamx_attach_strength
    except Exception:
        pass
    
    # Unregister modules in reverse order
    for m in reversed(modules):
        if hasattr(m, 'unregister'):
            m.unregister()
