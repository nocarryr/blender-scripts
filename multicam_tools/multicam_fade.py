import bpy
from bpy.app.handlers import persistent
from bpy.props import (IntProperty, 
                       FloatProperty, 
                       BoolProperty, 
                       StringProperty, 
                       PointerProperty, 
                       CollectionProperty)
from . import utils
from .utils import MultiCamContext
    
class MultiCamStrip(bpy.types.PropertyGroup):
    channel = IntProperty()
    strip_data_path = StringProperty()
    is_start_source = BoolProperty()
    is_next_source = BoolProperty()
    needs_blanking = BoolProperty()
    def get_parent_prop(self):
        data_path = '.'.join(self.path_from_id().split('.')[:-1])
        return self.id_data.path_resolve(data_path)
    def get_multicam_strip(self):
        return self.get_parent_prop.get_multicam_strip()
    def get_my_strip(self):
        scene = self.id_data
        if self.strip_data_path:
            try:
                strip = scene.path_resolve(self.strip_data_path)
            except ValueError:
                self.strip_data_path = ''
                strip = None
        else:
            strip = None
        if strip is not None:
            return strip
        for strip in scene.sequence_editor.sequences:
            if strip.channel == self.channel:
                data_path = strip.path_from_id()
                if self.strip_data_path != data_path:
                    self.strip_data_path = data_path
                return strip
    def get_fcurve(self):
        scene = self.id_data
        action = scene.animation_data.action
        if action is None:
            return None
        strip = self.get_my_strip()
        data_path = '.'.join([strip.path_from_id(), 'blend_alpha'])
        return utils.get_or_create_fcurve(scene, data_path)
    def get_keyframe(self, frame):
        fcurve = self.get_fcurve()
        for kf in fcurve.keyframe_points:
            if kf.co[0] == frame:
                return kf
        return None
    def remove_old_keyframes(self, start_frame, end_frame):
        fcurve = self.get_fcurve()
        to_remove = set()
        for kf in fcurve.keyframe_points:
            if kf.co[0] in [start_frame, end_frame]:
                to_remove.add(kf)
        for kf in to_remove:
            fcurve.keyframe_points.remove(kf)
        to_remove.clear()
    def add_keyframe(self, frame, value, interpolation=None):
        if interpolation is None:
            interpolation = 'CONSTANT'
        fcurve = self.get_fcurve()
        kf = fcurve.keyframe_points.insert(frame, value)
        kf.interpolation = interpolation
        return kf
    def update_flags(self):
        fade = self.get_parent_prop()
        d = {}
        d['is_start_source'] = fade.start_source == self.channel
        d['is_next_source'] = fade.next_source == self.channel
        if True in d.values():
            d['needs_blanking'] = False
        else:
            d['needs_blanking'] = self.channel > fade.start_source or self.channel > fade.next_source
        changed = False
        for key, val in d.items():
            if getattr(self, key) == val:
                continue
            setattr(self, key, val)
            changed = True
        if changed:
            self.update_keyframes()
    def ensure_start_keyframe(self):
        fade_props = self.get_parent_prop().get_parent_prop()
        keys = [float(key) for key in fade_props.fades.keys()]
        first_frame = min(keys)
        self.add_keyframe(first_frame - 1., 1.)
    def set_end_keyframe(self):
        fade = self.get_parent_prop()
        fade_props = fade.get_parent_prop()
        other_fade = fade_props.get_fade_in_range(fade.end_frame + 1.)
        if other_fade is not None:
            return
        self.add_keyframe(fade.end_frame + 1., 1.)
    def update_keyframes(self):
        self.ensure_start_keyframe()
        fade = self.get_parent_prop()
        kf_data = {fade.start_frame:{}, fade.end_frame:{}}
        if self.is_start_source:
            kf_data[fade.start_frame]['interpolation'] = 'BEZIER'
            if self.channel > fade.next_source:
                kf_data[fade.start_frame]['value'] = 1.
                kf_data[fade.end_frame]['value'] = 0.
            else:
                kf_data[fade.start_frame]['value'] = 1.
                kf_data[fade.end_frame]['value'] = 1.
        elif self.is_next_source:
            if self.channel > fade.start_source:
                kf_data[fade.start_frame]['value'] = 0.
                kf_data[fade.end_frame]['value'] = 1.
            else:
                kf_data[fade.start_frame]['value'] = 1.
                kf_data[fade.end_frame]['value'] = 1.
            kf_data[fade.start_frame]['interpolation'] = 'BEZIER'
            kf_data[fade.end_frame]['value'] = 1.
        elif self.needs_blanking:
            kf_data[fade.start_frame]['value'] = 0.
            kf_data[fade.end_frame]['value'] = 0.
            self.set_end_keyframe()
        else:
            return
        for frame, data in kf_data.items():
            self.add_keyframe(frame, data['value'], data.get('interpolation'))
        
class MultiCamFaderFade(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        cls.strips = CollectionProperty(type=MultiCamStrip)
        cls.start_frame = FloatProperty()
        cls.end_frame = FloatProperty()
        cls.start_source = IntProperty(name='Start Source')
        cls.next_source = IntProperty(name='Next Source')
    def get_parent_prop(self):
        data_path = '.'.join(self.path_from_id().split('.')[:-1])
        return self.id_data.path_resolve(data_path)
    def get_multicam_strip(self):
        return self.get_parent_prop().get_multicam_strip()
    def update_values(self, **kwargs):
        start_frame = kwargs.get('start_frame')
        if start_frame is not None:
            start_frame = float(start_frame)
            if start_frame != self.start_frame:
                self.name = str(start_frame)
        for key, val in kwargs.items():
            setattr(self, key, val)
        self.update_strips()
    def update_strips(self):
        mc_strip = self.get_multicam_strip()
        for channel in range(1, mc_strip.channel):
            key = str(channel)
            fade_strip = self.strips.get(key)
            if fade_strip is None:
                fade_strip = self.strips.add()
                fade_strip.name = key
                fade_strip.channel = channel
            fade_strip.update_flags()
        
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
    def get_multicam_strip(self):
        return self.id_data.path_resolve(self.name)
    def set_keyframes_from_fade(self, fade):
        self.start_source = fade.start_source
        self.next_source = fade.next_source
        self.fade_position = 0.
        data_path = self.path_from_id()
        scene = self.id_data
        mc_strip = self.get_multicam_strip()
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
        fade.update_strips()
        self.set_keyframes_from_fade(fade)
        return fade
    def get_fade(self, start_frame):
        start_frame = float(start_frame)
        name = str(start_frame)
        return self.fades.get(name)
    def get_fade_in_range(self, frame):
        if not len(self.fades):
            return None
        if isinstance(frame, bpy.types.Scene):
            frame = frame.frame_current_final
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

class MultiCamFaderOpsProperties(bpy.types.PropertyGroup):
    def on_end_frame_update(self, context):
        fade = self.get_fade_in_range(context.scene)
        if fade is not None:
            start = fade.start_frame
        else:
            start = self.get_start_frame(context)
        duration = self.end_frame - start
        if duration == self.frame_duration:
            return
        self.frame_duration = duration
    def on_frame_duration_update(self, context):
        if isinstance(context, bpy.types.Scene):
            scene = context
        else:
            scene = context.scene
        fade = self.get_fade_in_range(scene)
        if fade is not None:
            return
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
        r = prop.update_from_fader_props(scene)
        if not r:
            prop._start_frame = None
            prop.on_frame_duration_update(scene)
    def get_fade_in_range(self, scene):
        strip = scene.sequence_editor.active_strip
        if strip is None:
            return
        if strip.type != 'MULTICAM':
            return
        self.start_source = strip.multicam_source
        prop = MultiCamFaderProperties.get_for_strip(strip)
        if prop is None:
            return
        return prop.get_fade_in_range(scene.frame_current_final)
    def update_from_fader_props(self, scene):
        fade = self.get_fade_in_range(scene)
        if fade is None:
            return False
        self.destination_source = fade.next_source
        self.end_frame = fade.end_frame
        return True
    
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
        fade_kwargs = dict(start_frame=start_frame, 
                           end_frame=ops_props.end_frame, 
                           start_source=mc_strip.multicam_source, 
                           next_source=ops_props.destination_source)
        fade = fade_props.get_fade_in_range(context.scene)
        if fade is not None:
            fade_props.update_fade(fade, **fade_kwargs)
        else:
            fade = fade_props.add_fade(**fade_kwargs)
        return {'FINISHED'}
        
    
def register():
    bpy.utils.register_class(MultiCamStrip)
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
    bpy.utils.unregister_class(MultiCamStrip)
