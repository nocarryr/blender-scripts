import bpy

def get_active_strip(context=None):
    if context is None:
        context = bpy.context
    return context.scene.sequence_editor.active_strip
    
class MultiCamPanel(bpy.types.Panel):
    bl_label = 'Multicam Tools'
    bl_idname = 'multicam_tools.panel'
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
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
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator('multicam_tools.import', text='Import')
        row.operator('multicam_tools.export', text='Export')
    
def _register():
    bpy.utils.register_class(MultiCamPanel)
    
def _unregister():
    bpy.utils.unregister_class(MultiCamPanel)
