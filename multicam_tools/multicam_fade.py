import bpy
from bpy.props import (IntProperty, 
                       FloatProperty, 
                       StringProperty, 
                       CollectionProperty)

def get_active_strip(context=None):
    if context is None:
        context = bpy.context
    return context.scene.sequence_editor.active_strip
    
class MultiCamFaderProperties(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Scene.multicam_fader_properties = CollectionProperty(type=cls)
        cls.multicam_strip_path = StringProperty(name='Multicam Strip Data Path')
        cls.next_source = IntProperty(name='Next Source')
        #cls.frame_duration = FloatProperty(name='Frame Duration', default=20.)
        cls.fade_position = FloatProperty(name='Fade Position', min=0., max=1.)
    @classmethod
    def unregister(cls):
        del bpy.types.Scene.multicam_fader_properties
    @classmethod
    def get_for_data_path(cls, data_path, context=None):
        if context is None:
            context = bpy.context
        for prop in context.scene.multicam_fader_properties:
            if prop.multicam_strip_path == data_path:
                return prop
    @classmethod
    def get_for_strip(cls, mc_strip, context=None):
        data_path = mc_strip.path_from_id()
        return cls.get_for_data_path(data_path, context)
    @classmethod
    def get_or_create(cls, **kwargs):
        context = kwargs.get('context')
        data_path = kwargs.get('data_path')
        if data_path is not None:
            prop = cls.get_for_data_path(data_path, context)
        else:
            mc_strip = kwargs.get('mc_strip')
            prop = cls.get_for_strip(mc_strip)
        created = prop is None
        if created:
            if data_path is None:
                data_path = mc_strip.path_from_id()
            prop = context.scene.multicam_fader_properties.add()
            prop.multicam_strip_path = data_path
        return prop, created
    
class MultiCamFaderCreateProps(bpy.types.Operator):
    bl_idname = 'sequencer.multicam_create_props'
    bl_label = 'Multicam Fader Create Props'
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
    def execute(self, context):
        mc_strip = get_active_strip()
        MultiCamFaderProperties.get_or_create(context=context, mc_strip=mc_strip)
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(MultiCamFaderProperties)
    bpy.utils.register_class(MultiCamFaderCreateProps)
    
def unregister():
    bpy.utils.unregister_class(MultiCamFaderCreateProps)
    bpy.utils.unregister_class(MultiCamFaderProperties)
