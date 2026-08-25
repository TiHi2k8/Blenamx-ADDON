bl_info = {
    "name": "Blenamx ADDON",
    "author": "TiHi2k8 / KI",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "Topbar > Window",
    "description": "A Blender addon for creating and managing DynamX assets more easily.",
    "warning": "Experimental",
    "wiki_url": "",
    "category": "Workspace",
}

from . import operators, panels, preferences
import bpy

modules = (operators, panels, preferences)
_is_registered = False


def _unregister_all_by_prefix():
    """Unregister all Dynamx classes by prefix."""
    to_unregister = []
    for name in dir(bpy.types):
        if name.startswith('DYNMX_'):
            try:
                cls = getattr(bpy.types, name)
                to_unregister.append(cls)
            except Exception:
                pass
    
    for cls in reversed(to_unregister):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


@bpy.app.handlers.persistent
def workspace_change_handler(dummy):
    """Auto-open sidebar when switching to Dynamx workspaces"""
    try:
        workspace = bpy.context.workspace
        if workspace and workspace.name in ("Dynamx - Car", "Dynamx - Trailer", "Dynamx - Block"):
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                space.show_region_ui = True
    except Exception:
        pass


def register():
    global _is_registered
    if _is_registered:
        try:
            unregister()
        except Exception:
            pass
    
    try:
        # Clear all stale DYNMX registrations first
        _unregister_all_by_prefix()
        
        # Now register fresh
        for m in modules:
            if hasattr(m, 'register'):
                try:
                    m.register()
                except RuntimeError as e:
                    if "already registered" in str(e):
                        # Re-unregister and try again
                        _unregister_all_by_prefix()
                        try:
                            m.register()
                        except Exception:
                            pass
                    else:
                        raise
                except Exception:
                    pass
        
        if workspace_change_handler not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(workspace_change_handler)
        
        try:
            addon_prefs = bpy.context.preferences.addons.get("dynamx_addon")
            if addon_prefs and getattr(addon_prefs.preferences, 'create_on_enable', False):
                bpy.ops.dynamx.create_workspace()
        except Exception:
            pass
        
        _is_registered = True
    except Exception as e:
        if workspace_change_handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(workspace_change_handler)
        _is_registered = False
        raise


def unregister():
    global _is_registered
    try:
        if workspace_change_handler in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.remove(workspace_change_handler)
    except Exception:
        pass
    
    # Unregister modules
    for m in reversed(modules):
        if hasattr(m, 'unregister'):
            try:
                m.unregister()
            except Exception:
                pass
    
    # Clear any stale registrations
    _unregister_all_by_prefix()
    
    _is_registered = False
