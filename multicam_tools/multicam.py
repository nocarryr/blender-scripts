import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

import json

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
    def iter_keyframes(self):
        for kf in self.fcurve.keyframe_points.values():
            yield kf.co
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
            
class MultiCamBakeStrips(bpy.types.Operator):
    '''Bakes the mulicam source into the affected strips using opacity'''
    bl_idname = 'multicam_tools.bake_strips'
    bl_label = 'Bake Multicam Strips'
    def execute(self, context):
        mc = MultiCam(blend_obj=context.scene.sequence_editor.active_strip, 
                      context=context)
        mc.bake_strips()
        return {'FINISHED'}
        
class MultiCamExport(bpy.types.Operator, ExportHelper):
    bl_idname = 'multicam_tools.export'
    bl_label = 'Export Multicam'
    filename_ext = '.json'
    def execute(self, context):
        mc = MultiCam(blend_obj=context.scene.sequence_editor.active_strip, 
                      context=context)
        data = {}
        for frame, value in mc.iter_keyframes():
            data[frame] = value
        keys = sorted(data.keys())
        out_data = [(key, data[key]) for key in keys]
        with open(self.filepath, 'w') as f:
            f.write(json.dumps(out_data, indent=2))
        return {'FINISHED'}
        
class MultiCamImport(bpy.types.Operator, ImportHelper):
    bl_idname = 'multicam_tools.import'
    bl_label = 'Import Multicam'
    filename_ext = '.json'
    def execute(self, context):
        with open(self.filepath, 'r') as f:
            data = json.loads(f.read())
        mc = MultiCam(blend_obj=context.scene.sequence_editor.active_strip, 
                      context=context)
        mc.remove_fcurve()
        for frame, value in data:
            mc.insert_keyframe(frame, value, interpolation='CONSTANT')
        return {'FINISHED'}
    
def _register():
    bpy.utils.register_class(MultiCamBakeStrips)
    bpy.utils.register_class(MultiCamExport)
    bpy.utils.register_class(MultiCamImport)
def _unregister():
    bpy.utils.unregister_class(MultiCamBakeStrips)
    bpy.utils.unregister_class(MultiCamExport)
    bpy.utils.unregister_class(MultiCamImport)

