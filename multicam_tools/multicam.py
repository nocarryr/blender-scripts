import bpy

class BlendObj(object):
    def __init__(self, **kwargs):
        self.context = kwargs.get('context')
        self.blend_obj = kwargs.get('blend_obj')
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
        prop = self.fcurve_property
        for fc in action.fcurves.values():
            if path not in fc.data_path:
                continue
            if fc.data_path.split('.')[-1] != prop:
                continue
            return fc
    
    
class MultiCam(BlendObj):
    fcurve_property = 'multicam_source'
    def __init__(self, **kwargs):
        super(MultiCam, self).__init__(**kwargs)
        self.cuts = {}
        self.strips = {}
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
        for frame in sorted(cuts.keys()):
            cut = cuts[frame]
            if cut == channel:
                d[frame] = True
                is_active = True
            elif is_active:
                d[frame] = False
                is_active = False
        return d
    def insert_keyframe(self, frame, value, **kwargs):
        if self.fcurve is None:
            self.blend_obj.keyframe_insert('blend_alpha', frame=frame)
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
    def build_keyframes(self):
        for frame, is_active in self.keyframe_data.items():
            if is_active:
                value = 1.
            else:
                value = 0.
            self.insert_keyframe(frame, value, interpolation='CONSTANT')
    
def test():
    mc = MultiCam(blend_obj=bpy.context.selected_sequences[0])
    mc.build_cuts()
    mc.build_strip_keyframes()
test()
