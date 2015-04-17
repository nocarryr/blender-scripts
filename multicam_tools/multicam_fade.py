import bpy
from bpy.app.handlers import persistent
from bpy.props import (IntProperty, 
                       FloatProperty, 
                       PointerProperty, 
                       CollectionProperty)
from . import utils
from .utils import MultiCamContext
from .multicam import MultiCam
    
class MultiCamFaderFade(bpy.types.PropertyGroup):
    start_frame = FloatProperty()
    end_frame = FloatProperty()
    start_source = IntProperty(name='Start Source')
    next_source = IntProperty(name='Next Source')
    def update_values(self, **kwargs):
        start_frame = kwargs.get('start_frame')
        if start_frame is not None:
            start_frame = float(start_frame)
            if start_frame != self.start_frame:
                self.name = str(start_frame)
        for key, val in kwargs.items():
            setattr(self, key, val)
    
class MultiCamFaderProperties(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Scene.multicam_fader_properties = CollectionProperty(type=cls)
        cls.start_source = IntProperty(name='Start Source')
        cls.next_source = IntProperty(name='Next Source')
        cls.fade_position = FloatProperty(name='Fade Position', min=0., max=1.)
        cls.fades = CollectionProperty(type=MultiCamFaderFade)
    @classmethod
    def unregister(cls):
        del bpy.types.Scene.multicam_fader_properties
    @classmethod
    def _handle_get_kwargs(cls, **kwargs):
        if kwargs.get('handled'):
            return kwargs
        mc_strip = kwargs.get('mc_strip')
        data_path = kwargs.get('data_path')
        context = kwargs.get('context')
        scene = kwargs.get('scene')
        if mc_strip is not None:
            kwargs['data_path'] = mc_strip.path_from_id()
            kwargs['scene'] = mc_strip.id_data
        elif data_path is not None:
            if data_path.startswith('bpy.data'):
                kwargs['mc_strip'] = utils.get_bpy_obj_from_data_path(data_path)
                kwargs['scene'] = kwargs['mc_strip'].id_data
                kwargs['data_path'] = kwargs['mc_strip'].path_from_id()
            else:
                if scene is None:
                    if context is None:
                        context = bpy.context
                        kwargs['context'] = context
                    scene = context.scene
                    kwargs['scene'] = scene
                kwargs['mc_strip'] = scene.path_resolve(data_path)
        kwargs['handled'] = True
        return kwargs
    @classmethod
    def get_props(cls, **kwargs):
        kwargs = cls._handle_get_kwargs(**kwargs)
        scene = kwargs.get('scene')
        data_path = kwargs.get('data_path')
        return scene.multicam_fader_properties.get(data_path)
    @classmethod
    def get_for_strip(cls, mc_strip):
        data_path = mc_strip.path_from_id()
        scene = mc_strip.id_data
        return cls.get_props(data_path=data_path, scene=scene)
    @classmethod
    def get_or_create(cls, **kwargs):
        kwargs = cls._handle_get_kwargs(**kwargs)
        prop = cls.get_props(**kwargs)
        created = prop is None
        if created:
            data_path = kwargs.get('data_path')
            scene = kwargs.get('scene')
            prop = scene.multicam_fader_properties.add()
            prop.name = data_path
        return prop, created
    def set_keyframes_from_fade(self, fade):
        self.start_source = fade.start_source
        self.next_source = fade.next_source
        self.fade_position = 0.
        data_path = self.path_from_id()
        scene = self.id_data
        mc_strip = scene.path_resolve(self.name)
        attrs = ['start_source', 'next_source', 'fade_position']
        for attr in attrs:
            scene.keyframe_insert(data_path='.'.join([data_path, attr]), 
                                  frame=fade.start_frame, 
                                  group='Multicam Fader (%s)' % (mc_strip.name))
        self.fade_position = 1.
        for attr in attrs:
            scene.keyframe_insert(data_path='.'.join([data_path, attr]), 
                                  frame=fade.end_frame, 
                                  group='Multicam Fader (%s)' % (mc_strip.name))
    def add_fade(self, **kwargs):
        start_frame = kwargs.get('start_frame')
        end_frame = kwargs.get('end_frame')
        start_source = kwargs.get('start_source')
        next_source = kwargs.get('next_source')
        name = str(start_frame)
        fade = self.fades.get(name)
        if fade is not None:
            return False
        fade = self.fades.add()
        fade.name = name
        fade.start_frame = start_frame
        fade.end_frame = end_frame
        fade.start_source = start_source
        fade.next_source = next_source
        self.set_keyframes_from_fade(fade)
        return fade
    def get_fade(self, start_frame):
        start_frame = float(start_frame)
        name = str(start_frame)
        return self.fades.get(name)
    def get_fade_in_range(self, frame):
        if not len(self.fades):
            return None
        keys = [key for key in self.fades.keys() if frame >= float(key)]
        if not len(keys):
            return None
        float_keys = [float(key) for key in keys]
        for key, float_key in zip(keys, float_keys):
            fade = self.fades.get(key)
            if frame <= fade.end_frame:
                return fade
        return None
    def update_fade(self, fade, **kwargs):
        fade.update_values(**kwargs)
        
    
class MultiCamFaderCreateProps(bpy.types.Operator, MultiCamContext):
    bl_idname = 'sequencer.multicam_create_props'
    bl_label = 'Multicam Fader Create Props'
    def execute(self, context):
        mc_strip = self.get_strip(context)
        MultiCamFaderProperties.get_or_create(mc_strip=mc_strip)
        return {'FINISHED'}
    
class DummyContext(object):
    def __init__(self, scene):
        self.scene = scene

class MultiCamFaderOpsProperties(bpy.types.PropertyGroup):
    def on_end_frame_update(self, context):
        start = self.get_start_frame(context)
        duration = self.end_frame - start
        if duration == self.frame_duration:
            return
        self.frame_duration = duration
    def on_frame_duration_update(self, context):
        start = self.get_start_frame(context)
        end = start + self.frame_duration
        if end == self.end_frame:
            return
        self.end_frame = end
    def get_start_frame(self, context=None):
        if context is None:
            context = bpy.context
        if isinstance(context, bpy.types.Scene):
            scene = context
        else:
            scene = context.scene
        return scene.frame_current_final
    @classmethod
    def register(cls):
        bpy.types.Scene.multicam_fader_ops_properties = PointerProperty(type=cls)
        cls.start_source = IntProperty(
            name='Start Source', 
            description='The source to transition from (also the current multicam source)', 
        )
        cls.destination_source = IntProperty(
            name='Destination Source', 
            description='The source to transition to', 
        )
        cls.end_frame = FloatProperty(
            name='End Frame', 
            description='Ending frame for transition (relative to current)', 
            update=cls.on_end_frame_update, 
        )
        cls.frame_duration = FloatProperty(
            name='Frame Duration', 
            description='Duration of the transition', 
            default=20., 
            update=cls.on_frame_duration_update, 
        )
    @classmethod
    def unregister(cls):
        del bpy.types.Scene.multicam_fader_ops_properties
    def update_props(self, context=None):
        if context is None:
            context = bpy.context
        self.on_frame_duration_update(context)
    @staticmethod
    def on_frame_change(scene):
        if bpy.context.screen.is_animation_playing:
            return
        prop = scene.multicam_fader_ops_properties
        prop.on_frame_duration_update(scene)
#    def get_fade_props_action_group(self, mc_strip):
#        scene = mc_strip.id_data
#        action = scene.animation_data.action
#        group_name = 'Multicam Fader (%s)' % (mc_strip.name)
#        return action.groups.get(group_name)
#    def get_fade_props_fcurves(self, **kwargs):
#        action_group = kwargs.get('action_group')
#        if action_group is None:
#            mc_strip = kwargs.get('mc_strip')
#            action_group = self.get_fade_props_action_group(mc_strip)
#        fcurves = {}
#        for fc in action_group.channels:
#            key = fc.data_path.split('.')[-1]
#            fcurves[key] = fc
#        return fcurves
#    def get_fade_props_keyframes(self, **kwargs):
#        fcurves = kwargs.get('fcurves')
#        if fcurves is None:
#            fcurves = self.get_fade_props_fcurves(**kwargs)
#        return utils.get_keyframe_dict(fcurves=fcurves)
    
class MultiCamFader(bpy.types.Operator, MultiCamContext):
    bl_idname = 'scene.multicam_fader'
    bl_label = 'Multicam Fader'
    def get_start_frame(self, context=None):
        if context is None:
            context = bpy.context
        return context.scene.frame_current_final
    def execute(self, context):
        mc_strip = self.get_strip(context)
        fade_props, created = MultiCamFaderProperties.get_or_create(mc_strip=mc_strip)
        ops_props = context.scene.multicam_fader_ops_properties
        start_frame = self.get_start_frame(context)
        fade = fade_props.add_fade(start_frame=start_frame, 
                                   end_frame=ops_props.end_frame, 
                                   start_source=mc_strip.multicam_source, 
                                   next_source=ops_props.destination_source)
#        fade_props.start_source = mc_strip.multicam_source
#        fade_props.next_source = ops_props.destination_source
#        fade_props.fade_position = 0.
#        data_path = fade_props.path_from_id()
#        attrs = ['start_source', 'next_source', 'fade_position']
#        for attr in attrs:
#            context.scene.keyframe_insert(data_path='.'.join([data_path, attr]), 
#                                          frame=start_frame, 
#                                          group='Multicam Fader (%s)' % (mc_strip.name))
#        fade_props.fade_position = 1.
#        for attr in attrs:
#            context.scene.keyframe_insert(data_path='.'.join([data_path, attr]), 
#                                          frame=ops_props.end_frame, 
#                                          group='Multicam Fader (%s)' % (mc_strip.name))
        multicam = MultiCam(blend_obj=mc_strip, context=context)
        multicam.insert_keyframe(start_frame, mc_strip.channel - 1, interpolation='CONSTANT')
        multicam.insert_keyframe(fade.end_frame, fade.next_source, interpolation='CONSTANT')
        multicam.build_fade(fade=None, frame=start_frame)
        return {'FINISHED'}
        
    
def register():
    bpy.utils.register_class(MultiCamFaderFade)
    bpy.utils.register_class(MultiCamFaderProperties)
    bpy.utils.register_class(MultiCamFaderCreateProps)
    bpy.utils.register_class(MultiCamFaderOpsProperties)
    bpy.utils.register_class(MultiCamFader)
    
    @persistent
    def on_frame_change(scene):
        MultiCamFaderOpsProperties.on_frame_change(scene)
    bpy.app.handlers.frame_change_pre.append(on_frame_change)
    
def unregister():
    bpy.utils.unregister_class(MultiCamFader)
    bpy.utils.unregister_class(MultiCamFaderOpsProperties)
    bpy.utils.unregister_class(MultiCamFaderCreateProps)
    bpy.utils.unregister_class(MultiCamFaderProperties)
    bpy.utils.unregister_class(MultiCamFaderFade)
