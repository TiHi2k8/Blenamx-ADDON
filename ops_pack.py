"""Pack-related operators"""
import bpy
import os
import re


class DYNMX_OT_create_pack(bpy.types.Operator):
    """Create a pack folder at the specified path"""
    bl_idname = "dynamx.create_pack"
    bl_label = "Create Pack"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        pack_name = scene.dynamx_pack_name.strip()
        pack_path = bpy.path.abspath(scene.dynamx_pack_path)
        pack_description = scene.dynamx_pack_description.strip()
        pack_version = scene.dynamx_pack_version
        
        if not pack_name:
            self.report({'ERROR'}, "Pack name cannot be empty")
            return {'CANCELLED'}
        
        if not pack_path:
            self.report({'ERROR'}, "Pack path cannot be empty")
            return {'CANCELLED'}
        
        pack_name_safe = pack_name.replace(" ", "_").lower()
        
        full_path = os.path.join(pack_path, pack_name_safe)
        
        try:
            os.makedirs(full_path, exist_ok=True)
            
            assets_path = os.path.join(full_path, "assets")
            dynamxmod_path = os.path.join(assets_path, "dynamxmod")
            models_path = os.path.join(dynamxmod_path, "models")
            obj_path = os.path.join(models_path, "obj")
            lang_path = os.path.join(dynamxmod_path, "lang")
            
            os.makedirs(obj_path, exist_ok=True)
            os.makedirs(lang_path, exist_ok=True)
            
            mcmeta_content = '''{
    "pack": {
        "pack_format": 3,
        "description": "''' + pack_description + '''"
    }
}'''
            mcmeta_path = os.path.join(full_path, "pack.mcmeta")
            with open(mcmeta_path, 'w', encoding='utf-8') as f:
                f.write(mcmeta_content)
            
            dynx_content = f'''PackName: {pack_name}
CompatibleWithLoaderVersions: [1.0,1.1)
PackVersion: {pack_version}
DcFileVersion: 12.5.0
'''
            dynx_path = os.path.join(full_path, "pack_info.dynx")
            with open(dynx_path, 'w', encoding='utf-8') as f:
                f.write(dynx_content)
            
            if os.path.exists(full_path):
                self.report({'INFO'}, f"Pack folder created/updated: {full_path} | Pack version: {pack_version}")
            else:
                self.report({'INFO'}, f"Pack folder created: {full_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create folder: {str(e)}")
            return {'CANCELLED'}


class DYNMX_OT_select_pack(bpy.types.Operator):
    """Select an existing pack and load its info"""
    bl_idname = "dynamx.select_pack"
    bl_label = "Select Pack"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.dynx", options={'HIDDEN'})
    
    filename_ext = ".dynx"

    def execute(self, context):
        scene = context.scene
        
        if not self.filepath or not os.path.exists(self.filepath):
            self.report({'ERROR'}, "Invalid file path")
            return {'CANCELLED'}
        
        filename = os.path.basename(self.filepath)
        if filename != "pack_info.dynx":
            self.report({'ERROR'}, "Please select pack_info.dynx file")
            return {'CANCELLED'}
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            match = re.search(r'^PackName:\s*(.+)$', content, re.MULTILINE)
            if match:
                scene.dynamx_pack_name = match.group(1).strip()
            
            match = re.search(r'^PackVersion:\s*(.+)$', content, re.MULTILINE)
            if match:
                scene.dynamx_pack_version = match.group(1).strip()
            
            pack_dir = os.path.dirname(self.filepath)
            parent_dir = os.path.dirname(pack_dir)
            
            scene.dynamx_pack_path = parent_dir
            
            mcmeta_path = os.path.join(pack_dir, "pack.mcmeta")
            if os.path.exists(mcmeta_path):
                try:
                    import json
                    with open(mcmeta_path, 'r', encoding='utf-8') as f:
                        mcmeta = json.load(f)
                    desc = mcmeta.get('pack', {}).get('description', '')
                    if desc:
                        scene.dynamx_pack_description = desc
                except Exception:
                    pass
            
            self.report({'INFO'}, f"Loaded pack: {scene.dynamx_pack_name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load pack info: {str(e)}")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


classes = (DYNMX_OT_create_pack, DYNMX_OT_select_pack)


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
