import bpy
from bpy.props import BoolProperty

class DYNMX_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = "dynamx_addon"

    create_on_enable: BoolProperty(
        name="Create Dynamx on enable",
        description="Automatically create the Dynamx workspace when the addon is enabled",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "create_on_enable")


classes = (DYNMX_AddonPreferences,)


def register():
    for c in classes:
        bpy.utils.register_class(c)

    prefs = bpy.context.preferences.addons.get("dynamx_addon")
    if prefs:
        try:
            if prefs.preferences.create_on_enable:
                bpy.ops.dynamx.create_workspace()
        except Exception:
            pass


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
