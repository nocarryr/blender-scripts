import bpy

class MultiCam(object):
    def __init__(self, mc):
        self.mc = mc
        self.cuts = {}
        self.strips = {}
    @property
    def fcurve(self):
        fc = getattr(self, '_fcurve', None)
        if fc is None:
            fc = self._fcurve = self.get_fcurve()
        return fc
    def get_fcurve(self):
        mc_path = self.mc.path_from_id()
        action = bpy.context.scene.animation_data.action
        for fc in action.fcurves.values():
            if mc_path not in fc.data_path:
                continue
            if 'multicam_source' not in fc.data_path:
                continue
            return fc
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
        for s in bpy.context.scene.sequence_editor.sequences:
            if s.channel == channel:
                source = MulticamSource(self, s)
                self.strips[channel] = source
                return source
                
class MulticamSource(object):
    def __init__(self, multicam, strip):
        self.multicam = multicam
        self.strip = strip
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
        channel = self.strip.channel
        is_active = False
        for frame in sorted(cuts.keys()):
            cut = cuts[frame]
            if cut == channel:
                d[frame] = True
                is_active = True
            elif is_active:
                d[frame] = False
        return d
    def build_keyframes(self):
        for frame, is_active in self.keyframe_data.items():
            if is_active:
                value = 1.
            else:
                value = 0.
            self.strip.keyframe_insert('blend_alpha', frame=frame)
            ## then set the keyframe's value
    
def test():
    mc = MultiCam(bpy.context.selected_sequences[0])
    mc.build_cuts()
    mc.build_strip_keyframes()
test()
