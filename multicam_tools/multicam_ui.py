import bpy
from .utils import MultiCamContext
from .multicam_fade import MultiCamFaderProperties

    
class MultiCamPanel(bpy.types.Panel, MultiCamContext):
    bl_label = 'Multicam Tools'
    bl_idname = 'SEQUENCER_PT_multicam_tools'
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    def draw(self, context):
        layout = self.layout
        mc_strip = self.get_strip(context)
        fade_props = MultiCamFaderProperties.get_for_strip(mc_strip, context)
        row = layout.row()
        if fade_props is None:
            row.operator('sequencer.multicam_create_props', text='Create Props')
        else:
            row.prop(fade_props, 'next_source')
            row.prop(fade_props, 'fade_position')
        row = layout.row()
        row.operator('sequencer.bake_multicam_strips', text='Bake Strips')
        row = layout.row()
        row.operator('sequencer.import_multicam', text='Import')
        row.operator('sequencer.export_multicam', text='Export')
    
def register():
    bpy.utils.register_class(MultiCamPanel)
    
def unregister():
    bpy.utils.unregister_class(MultiCamPanel)
