import os
import collections

DELIMS = [',', ';', ' ']
def split_line(line):
    for delim in DELIMS:
        line = line.replace(delim,'\t')
    return line.strip('\t').split('\t')

class IESBase(object):
    def __init__(self, **kwargs):
        kwargs = self.parse(**kwargs)
        self.name = kwargs.get('name')
        self.value = kwargs.get('value')
    def parse(self, **kwargs):
        return kwargs
    def __repr__(self):
        return '%s (%s)' % (self.__class__.__name__, self)
    def __str__(self):
        return '%s: %s' % (self.name, self.value)

class IESKeyword(IESBase):
    def parse(self, **kwargs):
        parse_str = kwargs.get('parse_str')
        if parse_str is None:
            return kwargs
        name = parse_str.split('[')[1].split(']')[0]
        value = parse_str.split(']')[1]
        return dict(name=name, value=value)

class IESField(IESBase):
    _field_map = [
        ['num_lamps', 'lumens_per_lamp', 'candela_multiplier',
         'num_vertical_angles', 'num_horizontal_angles',
         'photometric_type', 'units_type', 'width', 'length', 'height'],
        ['ballast_factor', '_future_use', 'input_watts'],
    ]
    @classmethod
    def parse_line(cls, **kwargs):
        parse_str = kwargs.get('parse_str')
        parse_index = kwargs.get('index')
        l = split_line(parse_str)
        d = {}
        for i, val in enumerate(l):
            name = cls._field_map[parse_index][i]
            if '.' in val:
                val = float(val)
            else:
                val = int(val)
            obj = cls(name=name, value=val)
            d[obj.name] = obj
        return d

class IESCandelaValue(IESBase):
    def parse(self, **kwargs):
        self.vertical = kwargs.get('vertical')
        self.horizontal = kwargs.get('horizontal')
        kwargs['name'] = (self.vertical, self.horizontal)
        return kwargs
    @classmethod
    def parse_line(cls, **kwargs):
        h_angle = kwargs.get('horizontal')
        v_angles = kwargs.get('vertial_angles')
        parse_str = kwargs.get('parse_str')
        l = split_line(parse_str)
        d = {}
        for val in l:
            v_angle = v_angles.popleft()
            obj = cls(vertical=v_angle, horizontal=h_angle, value=float(val))
            d[obj.name] = obj
        return v_angles, d


def do_parse(filename):
    if '~' in filename:
        filename = os.path.expanduser(filename)
    with open(filename, 'r') as f:
        s = f.read()
    keywords = {}
    fields = {}
    angles = {'vertical':[], 'horizontal':[]}
    angles_to_parse = {}
    candela_vals = {}
    tilt = None
    tilt_line = None
    for line_num, line in enumerate(s.splitlines()):
        if tilt is None:
            if line_num == 0 and line != 'IESNA:LM-63-2002':
                raise Exception('Not a valid file')
            if line.startswith('['):
                keyword = IESKeyword(parse_str=line)
                keywords[keyword.name] = keyword
            elif line.startswith('TILT='):
                tilt = line.split('=')[1]
                data_start = line_num + 1
                if tilt == 'INCLUDE':
                    data_start += 4
            continue
        if line_num in [data_start, data_start + 1]:
            fields.update(IESField.parse_line(
                parse_str=line,
                index=line_num-data_start,
            ))
        elif len(angles['vertical']) < fields['num_vertical_angles'].value:
            vals = [float(v) for v in split_line(line)]
            angles['vertical'].extend(vals)
        elif len(angles['horizontal']) < fields['num_horizontal_angles'].value:
            vals = [float(v) for v in split_line(line)]
            angles['horizontal'].extend(vals)
        else:
            for key in ['vertical', 'horizontal']:
                if angles_to_parse.get(key) is None:
                    angles_to_parse[key] = collections.deque(angles[key])
            h_angle = angles_to_parse['horizontal'][0]
            v_to_parse, vals = IESCandelaValue.parse_line(
                parse_str=line,
                vertial_angles=angles_to_parse['vertical'],
                horizontal=h_angle,
            )
            candela_vals.update(vals)
            if not len(v_to_parse):
                angles_to_parse['vertical'] = None
                angles_to_parse['horizontal'].popleft()
            else:
                angles_to_parse['vertical'] = v_to_parse
            if not len(angles_to_parse['horizontal']):
                break
    data = dict(
        keywords=keywords,
        fields=fields,
        angles=angles,
        candela_vals=candela_vals,
    )
    return data
