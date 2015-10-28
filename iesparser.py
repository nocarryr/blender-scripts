import os
import collections
import json
import numbers

DELIMS = [',', ';', ' ']
def split_line(line):
    for delim in DELIMS:
        line = line.replace(delim,'\t')
    return line.strip('\t').split('\t')

class IESJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (IESData, IESBase)):
            d = {'_IES_CLS_':o.__class__.__name__}
            if isinstance(o, IESData):
                attrs = ['filename', 'keywords', 'fields', 'candela_values']
                d.update({k: getattr(o, k) for k in attrs})
            else:
                d.update({'name':o.name, 'value':o.value})
            if isinstance(o, IESCandelaValue):
                d.update({k: getattr(o, k) for k in ['vertical', 'horizontal']})
            return d
        elif isinstance(o, dict):
            numkeys = [k for k in o.keys() if isinstance(k, numbers.Number)]
            for k in numkeys:
                v = o.pop(k)
                o[str(k)] = v
        return super(IESJSONEncoder, self).default(o)

def ies_json_object_hook(d):
    if '_IES_CLS_' in d.keys():
        if d['_IES_CLS_'] == 'IESData':
            cls = IESData
        else:
            cls = IESBase.find_subclass(d['_IES_CLS_'])
        #for key, val in d.items():
        #    if isinstance(val, dict):
        #        d[key] = ies_json_object_hook(val)
        return cls(**d)
    return d

class IESJSONDecoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        kwargs.setdefault('object_hook', ies_json_object_hook)
        super(IESJSONDecoder, self).__init__(**kwargs)

class IESBase(object):
    def __init__(self, **kwargs):
        kwargs = self.parse(**kwargs)
        self.parent = kwargs.get('parent')
        self.name = kwargs.get('name')
        self.value = kwargs.get('value')
    @classmethod
    def find_subclass(cls, cls_name):
        if cls_name == cls.__name__:
            return cls
        for _cls in cls.__subclasses__():
            r = _cls.find_subclass(cls_name)
            if r is not None:
                return r
        return None
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
    def get_computed_value(self, candela_multiplier=None, ballast_factor=None):
        p = self.parent
        if candela_multiplier is None:
            candela_multiplier = p.candela_multiplier.value
        if ballast_factor is None:
            ballast_factor = p.ballast_factor.value
        return self.value * candela_multiplier * ballast_factor

class IESData(object):
    def __init__(self, **kwargs):
        self._keywords = {}
        self._fields = {}
        self.filename = kwargs.get('filename')
        self.keywords = kwargs.get('keywords', {})
        self.fields = kwargs.get('fields', {})
        self.candela_values = {}
        candela_vals = kwargs.get('candela_values', {})
        if isinstance(candela_vals, dict):
            candela_vals = candela_vals.values()
        for c in candela_vals:
            if isinstance(c, dict) and 'name' not in c:
                for _c in c.values():
                    self.add_candela_value(_c)
            else:
                self.add_candela_value(c)
    @classmethod
    def from_file(cls, filename):
        data = do_parse(filename)
        data['filename'] = filename
        return cls(**data)
    @property
    def keywords(self):
        return self._keywords
    @keywords.setter
    def keywords(self, value):
        if isinstance(value, dict):
            for key, val in value.items():
                if isinstance(val, IESKeyword):
                    self.add_keyword(val)
                else:
                    self.add_keyword(name=key, value=val)
        elif isinstance(value, IESKeyword):
            value = [value]
        if isinstance(value, collections.Sequence):
            for obj in value:
                self.add_keyword(obj)
    @property
    def fields(self):
        return self._fields
    @fields.setter
    def fields(self, value):
        if isinstance(value, dict):
            for key, val in value.items():
                if isinstance(val, IESField):
                    self.add_field(val)
                else:
                    self.add_field(name=key, value=val)
        elif isinstance(value, IESField):
            value = [value]
        if isinstance(value, collections.Sequence):
            for obj in value:
                self.add_field(obj)
    def _add_ies_obj(self, cls, obj=None, dict_attr=None, **kwargs):
        if obj is None:
            obj = cls(**kwargs)
        elif isinstance(obj, dict):
            obj = cls(**obj)
        if dict_attr is not None:
            d = getattr(self, dict_attr)
            if obj.name in d:
                d[obj.name].value = obj.value
                obj = d[obj.name]
            else:
                d[obj.name] = obj
        obj.parent = self
        return obj
    def add_keyword(self, obj=None, **kwargs):
        return self._add_ies_obj(
            cls=IESKeyword, obj=obj, dict_attr='keywords', **kwargs)
    def add_field(self, obj=None, **kwargs):
        return self._add_ies_obj(
            cls=IESField, obj=obj, dict_attr='fields', **kwargs)
    def add_candela_value(self, obj=None, **kwargs):
        obj = self._add_ies_obj(cls=IESCandelaValue, obj=obj, **kwargs)
        if obj.vertical not in self.candela_values:
            self.candela_values[obj.vertical] = {}
        self.candela_values[obj.vertical][obj.horizontal] = obj
        return obj
    def __getattr__(self, attr):
        if hasattr(self, '_fields') and attr in self._fields:
            return self._fields[attr]
        if hasattr(self, '_keywords'):
            _attr = attr
            if _attr not in keywords:
                _attr = _attr.upper()
            if _attr in self._keywords:
                return self._keywords[_attr]
        raise AttributeError('%r object has no attribute %r' %
                             (self.__class__, attr))
    def iter_candela(self):
        cvals = self.candela_values
        for v in sorted(cvals.keys()):
            d = cvals[v]
            for h in sorted(d.keys()):
                cobj = d[h]
                yield v, h, cobj
    def iter_candela_computed(self):
        for v, h, cobj in self.iter_candela():
            yield v, h, cobj.get_computed_value()

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
        candela_values=candela_vals,
    )
    return data
