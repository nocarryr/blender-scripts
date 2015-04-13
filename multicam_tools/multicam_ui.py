import bpy

def get_active_strip(context=None):
    if context is None:
        context = bpy.context
    return context.scene.sequence_editor.active_strip
    
class SEQUENCER_PT_multicam_tools(bpy.types.Panel):
    bl_label = 'Multicam Tools'
    bl_idname = 'SEQUENCER_PT_multicam_tools'
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
        if not hasattr(active_strip, 'fade_to_source'):
            print('poll: strip property not active')
            return 0
        return 1
    def draw(self, context):
        layout = self.layout
        mc_strip = get_active_strip(context)
        if hasattr(mc_strip, 'fade_to_source'):
            row = layout.row()
            row.prop(mc_strip, 'fade_to_source', text='')
        else:
            print('draw: strip property not active')
        row = layout.row()
        row.operator('sequencer.bake_multicam_strips', text='Bake Strips')
        row = layout.row()
        row.operator('sequencer.import_multicam', text='Import')
        row.operator('sequencer.export_multicam', text='Export')
    
def register():
    bpy.utils.register_class(SEQUENCER_PT_multicam_tools)
    
def unregister():
    bpy.utils.unregister_class(SEQUENCER_PT_multicam_tools)
