import bpy

def get_active_strip(context=None):
    if context is None:
        context = bpy.context
    return context.scene.sequence_editor.active_strip
    
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
        
