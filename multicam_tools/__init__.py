import bpy

bl_info = {
    "name": "Multicam Tools",
    "author": "Matt Reid",
    "version": (0, 0, 1),
    "blender": (2, 74, 0),
    "description": "", 
    "category":"Animation", 
    "warning": "",
}

def get_is_registered():
    module_obj = getattr(bpy.ops, 'multicam_tools', None)
    if module_obj is None:
        return False
    if not len(dir(module_obj)):
        return False
    return True

def register():
    from multicam_tools import multicam, multicam_ui
    bpy.utils.register_module(__name__)
    #multicam.register()
    #multicam_ui.register()
    
def unregister():
    from multicam_tools import multicam, multicam_ui
    #multicam_ui.unregister()
    #multicam.unregister()
    bpy.utils.unregister_module(__name__)
    
