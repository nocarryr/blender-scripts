import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

import json

from .utils import MultiCamContext

class MultiCamFadeError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)
        
class BlendObj(object):
    def __init__(self, **kwargs):
        self.context = kwargs.get('context')
        self.blend_obj = kwargs.get('blend_obj')
        if hasattr(self.__class__, 'fcurve_property'):
            self.fcurve_property = self.__class__.fcurve_property
        if not hasattr(self, 'fcurve_property'):
            self.fcurve_property = kwargs.get('fcurve_property')
    @property
    def blend_obj(self):
        return getattr(self, '_blend_obj', None)
    @blend_obj.setter
    def blend_obj(self, value):
        old = self.blend_obj
        if value == old:
            return
        self._blend_obj = value
        self.on_blend_obj_set(value, old)
    def on_blend_obj_set(self, new, old):
        self._fcurve = None
    @property
    def context(self):
        context = getattr(self, '_context', None)
        if context is None:
            context = bpy.context
        return context
    @context.setter
    def context(self, value):
        old = getattr(self, '_context', None)
        if old == value:
            return
        self._context = value
        self.on_context_set(value, old)
    def on_context_set(self, new, old):
        self._fcurve = None
    @property
    def fcurve(self):
        fc = getattr(self, '_fcurve', None)
        if fc is None:
            fc = self._fcurve = self.get_fcurve()
        return fc
    def get_fcurve(self):
        path = self.blend_obj.path_from_id()
        action = self.context.scene.animation_data.action
        if action is None:
            return None
        prop = self.fcurve_property
        for fc in action.fcurves.values():
            if path not in fc.data_path:
                continue
            if fc.data_path.split('.')[-1] != prop:
                continue
            return fc
    def remove_fcurve(self):
        if self.fcurve is None:
            return
        action = self.context.scene.animation_data.action
        action.fcurves.remove(self.fcurve)
        self._fcurve = None
    def iter_keyframes(self):
        for kf in self.fcurve.keyframe_points.values():
            yield kf.co
    def insert_keyframe(self, frame, value, prop=None, **kwargs):
        if prop is None:
            prop = self.fcurve_property
        if self.fcurve is None:
            self.blend_obj.keyframe_insert(prop, frame=frame)
            kf = self.get_keyframe(frame)
            kf.co[1] = value
        else:
            kf = self.fcurve.keyframe_points.insert(frame, value)
        for key, val in kwargs.items():
            setattr(kf, key, val)
        return kf
    def get_keyframe(self, frame):
        for kf in self.fcurve.keyframe_points.values():
            if kf.co[0] == frame:
                return kf
    
    
class MultiCam(BlendObj):
    fcurve_property = 'multicam_source'
    def __init__(self, **kwargs):
        super(MultiCam, self).__init__(**kwargs)
        self.cuts = {}
        self.strips = {}
    def bake_strips(self):
        if not len(self.cuts):
            self.build_cuts()
        self.build_strip_keyframes()
        self.blend_obj.mute = True
    def build_cuts(self):
        for frame, channel in self.iter_keyframes():
            self.cuts[frame] = channel
            if channel not in self.strips:
                self.get_strip_from_channel(channel)
    def build_strip_keyframes(self):
        for strip in self.strips.values():
            strip.build_keyframes()
    def get_strip_from_channel(self, channel):
        for s in self.context.scene.sequence_editor.sequences:
            if s.channel == channel:
                source = MulticamSource(context=self.context, blend_obj=s, multicam=self)
                self.strips[channel] = source
                return source
                
class MultiCamFade(BlendObj):
    def __init__(self, **kwargs):
        self.multicam = kwargs.get('multicam')
        self.fade_props = {}
        self.fades = {}
        kwargs.setdefault('context', self.multicam.context)
        super(MultiCamFade, self).__init__(**kwargs)
        if self.blend_obj is None:
            self.blend_obj = self.get_fade_prop_group()
    def on_blend_obj_set(self, new, old):
        self.fade_props.clear()
        self.fades.clear()
        if new is None:
            return
        self.get_fade_props()
    def get_fade_prop_group(self):
        mc_data_path = self.multicam.blend_obj.path_from_id()
        return self.context.scene.multicam_fader_properties.get(mc_data_path)
    def get_fade_props(self):
        action = self.context.scene.animation_data.action
        group_name = 'Multicam Fader (%s)' % (self.multicam.blend_obj.name)
        group = action.groups.get(group_name)
        for fc in group.channels:
            key = fc.data_path.split('.')[-1]
            fade_prop = MultiCamFadeProp(multicam_fade=self, fcurve_property=key)
            self.fade_props[key] = fade_prop
    def build_fades(self):
        prop_iters = {}
        for key, prop in self.fade_props.items():
            prop_iters[key] = prop.iter_keyframes()
        def find_next_fade(frame=None):
            prop_vals = {'start':{}, 'end':{}}
            start_frame = None
            try:
                for key, prop in prop_iters.items():
                    frame, value = next(prop)
                    if start_frame is None:
                        start_frame = frame
                    elif frame != start_frame:
                        raise MultiCamFadeError('keyframes are not aligned: %s' % ({'frame':frame, 'prop_vals':prop_vals}))
                    prop_vals['start'][key] = value
            except StopIteration:
                return None, None, None
            end_frame = None
            for key, prop in prop_iters.items():
                frame, value = next(prop)
                if end_frame is None:
                    end_frame = frame
                elif frame != end_frame:
                    raise MultiCamFadeError('keyframes are not aligned: %s' % ({'frame':frame, 'prop_vals':prop_vals}))
                prop_vals['end'][key] = value
            return start_frame, end_frame, prop_vals
        while True:
            start_frame, end_frame, prop_vals = find_next_fade()
            if start_frame is None:
                break
            self.fades[start_frame] = {
                'start_frame':start_frame, 
                'end_frame':end_frame, 
                'prop_vals':prop_vals, 
            }
            
class MultiCamFadeProp(BlendObj):
    def __init__(self, **kwargs):
        self.multicam_fade = kwargs.get('multicam_fade')
        kwargs.setdefault('context', self.multicam_fade.context)
        kwargs.setdefault('blend_obj', self.multicam_fade.blend_obj)
        super(MultiCamFadeProp, self).__init__(**kwargs)
        
class MulticamSource(BlendObj):
    fcurve_property = 'blend_alpha'
    def __init__(self, **kwargs):
        super(MulticamSource, self).__init__(**kwargs)
        self.multicam = kwargs.get('multicam')
        self._keyframe_data = None
    @property
    def keyframe_data(self):
        d = self._keyframe_data
        if d is None:
            d = self._keyframe_data = self.build_keyframe_data()
        return d
    def build_keyframe_data(self):
        d = {}
        cuts = self.multicam.cuts
        channel = self.blend_obj.channel
        is_active = False
        is_first_keyframe = True
        for frame in sorted(cuts.keys()):
            cut = cuts[frame]
            if cut == channel:
                d[frame] = True
                is_active = True
            elif is_active:
                d[frame] = False
                is_active = False
            elif is_first_keyframe:
                d[frame] = False
            is_first_keyframe = False
        return d
    def build_keyframes(self):
        self.remove_fcurve()
        for frame, is_active in self.keyframe_data.items():
            if is_active:
                value = 1.
            else:
                value = 0.
            self.insert_keyframe(frame, value, interpolation='CONSTANT')
    
class MultiCamBakeStrips(bpy.types.Operator, MultiCamContext):
    '''Bakes the mulicam source into the affected strips using opacity'''
    bl_idname = 'sequencer.bake_multicam_strips'
    bl_label = 'Bake Multicam Strips'
    def execute(self, context):
        mc = MultiCam(blend_obj=self.get_strip(context), 
                      context=context)
        mc.bake_strips()
        return {'FINISHED'}
        
class MultiCamExport(bpy.types.Operator, ExportHelper, MultiCamContext):
    bl_idname = 'sequencer.export_multicam'
    bl_label = 'Export Multicam'
    filename_ext = '.json'
    def execute(self, context):
        mc = MultiCam(blend_obj=self.get_strip(context), 
                      context=context)
        mc_fader = MultiCamFade(multicam=mc)
        mc_fader.build_fades()
        data = {'cuts':{}}
        for frame, value in mc.iter_keyframes():
            data['cuts'][frame] = value
        data['fades'] = mc_fader.fades
        with open(self.filepath, 'w') as f:
            f.write(json.dumps(data, indent=2))
        return {'FINISHED'}
        
class MultiCamImport(bpy.types.Operator, ImportHelper, MultiCamContext):
    bl_idname = 'sequencer.import_multicam'
    bl_label = 'Import Multicam'
    filename_ext = '.json'
    def execute(self, context):
        with open(self.filepath, 'r') as f:
            data = json.loads(f.read())
        mc = MultiCam(blend_obj=self.get_strip(context), 
                      context=context)
        mc.remove_fcurve()
        for frame, value in data['cuts'].items():
            mc.insert_keyframe(float(frame), value, interpolation='CONSTANT')
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(MultiCamBakeStrips)
    bpy.utils.register_class(MultiCamExport)
    bpy.utils.register_class(MultiCamImport)
    
    
def unregister():
    bpy.utils.unregister_class(MultiCamBakeStrips)
    bpy.utils.unregister_class(MultiCamExport)
    bpy.utils.unregister_class(MultiCamImport)

