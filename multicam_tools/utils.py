import bpy

def get_full_data_path(bpy_obj):
    return repr(bpy_obj)
    
def get_bpy_obj_from_data_path(data_path):
    ## TODO: this is hackish and insecure
    return eval(data_path)
    
def get_active_strip(context=None):
    if context is None:
        context = bpy.context
    return context.scene.sequence_editor.active_strip
    
def get_fcurve(scene, data_path):
    action = scene.animation_data.action
    for fc in action.fcurves:
        if fc.data_path == data_path:
            return fc

def iter_keyframes(**kwargs):
    fcurves = kwargs.get('fcurves')
    if fcurves is None:
        scene = kwargs.get('scene')
        action = scene.animation_data.action
        fcurves = action.fcurves
    for fc in fcurves:
        for kf in fc.keyframe_points:
            yield kf, fc
        
def get_keyframe_dict(**kwargs):
    d = {}
    for kf, fc in iter_keyframes(**kwargs):
        frame = kf[0]
        if frame not in d:
            d[frame] = {}
        d[frame][fc.data_path] = {'keyframe':kf, 'fcurve':fc}
    return d
    
class MultiCamContext:
    @classmethod
    def poll(cls, context):
        if context.area.type != 'SEQUENCE_EDITOR':
            return 0
        active_strip = get_active_strip(context)
        if active_strip is None:
            return 0
        if active_strip.type != 'MULTICAM':
            return 0
        return 1
    def get_strip(self, context):
        return get_active_strip(context)
        
