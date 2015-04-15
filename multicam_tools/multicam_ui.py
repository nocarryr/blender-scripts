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
        ops_props = context.scene.multicam_fader_ops_properties
        row = layout.row()
        if fade_props is None:
            row.operator('sequencer.multicam_create_props', text='Create Props')
        else:
            ## XXX can't set these properties within the context
            #ops_props.update_props(context)
            ## TODO: find a way to remove this handler when inactive
            #bpy.app.handlers.frame_change_pre.append(ops_props.on_frame_change)
            box = row.box()
            box.prop(ops_props, 'destination_source')
            box.prop(ops_props, 'end_frame')
            box.prop(ops_props, 'frame_duration')
            box.operator('scene.multicam_fader')
        row = layout.row()
        row.operator('sequencer.bake_multicam_strips', text='Bake Strips')
        row = layout.row()
        row.operator('sequencer.import_multicam', text='Import')
        row.operator('sequencer.export_multicam', text='Export')
    
def register():
    bpy.utils.register_class(MultiCamPanel)
    
def unregister():
    bpy.utils.unregister_class(MultiCamPanel)
