#----------------------------------------------------------
# File photo.py - cubify a named image in project.
# @knowuh (Noah Paessel)  http://bit.ly/photoblend
# License: MIT ( http://opensource.org/licenses/MIT )
#----------------------------------------------------------

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    IntProperty,
    StringProperty,
    FloatProperty,
    CollectionProperty,
    IntVectorProperty,
    FloatVectorProperty,
    EnumProperty,
    PointerProperty
)
import mathutils
from random import uniform


def make_material(color):
    alpha = 1.0
    red, green, blue, alpha = color
    color_name = '%(red)03d_%(green)03d_%(blue)03d' % {"red": red, "green": green, "blue": blue}
    color = bpy.data.materials.new(color_name)
    color.use_nodes = True
    Diffuse_BSDF = color.node_tree.nodes['Diffuse BSDF']
    Diffuse_BSDF.inputs[0].default_value = [red, green, blue, alpha]
    return color


def draw_pix(x, y, col):
    material = make_material(col)
    r, g, b, a = col
    size = 16 - ((r + g + b) * 4)
    z = size
    bpy.ops.mesh.primitive_cube_add(location=(x, y, z))
    bpy.ops.transform.resize(value=(0.9,0.9,size))
    new_obj = bpy.context.active_object
    new_obj.data.materials.append(material)

class Pixel(bpy.types.PropertyGroup):
    def get_x(self):
        return self.position[0]
    def set_x(self, value):
        self.position[0] = value
    x = FloatProperty(name='x', get=get_x, set=set_x)
    def get_y(self):
        return self.position[1]
    def set_y(self, value):
        self.position[1] = value
    y = FloatProperty(name='y', get=get_y, set=set_y)
    def set_material_color(self, context=None):
        if not self.material_name:
            return
        material = self.id_data.data.materials[self.material_name]
        if material.use_nodes:
            bsdf = material.node_tree.nodes['Diffuse BSDF']
            bsdf.inputs[0].default_value = self.color
        else:
            material.diffuse_color = self.color[:3]
            material.alpha = self.color[3]
    color = FloatVectorProperty(
        name='color',
        default=[0., 0., 0., 0.],
        size=4,
        subtype='COLOR',
        update=set_material_color,
    )
    @classmethod
    def register(cls):
        bpy.types.Object.pixel_data = PointerProperty(type=cls)
        cls.is_first_obj = BoolProperty(default=False)
        cls.pixel_image_name = StringProperty()
        cls.material_name = StringProperty()
        cls.position = FloatVectorProperty(size=2)
        cls.pixel_start_index = IntProperty()
        cls.z_scale_color_modifier = StringProperty()
        cls.z_scale_modifier_amount = FloatProperty()
    @classmethod
    def on_frame_change(cls, scene):
        frame = scene.frame_current
        print(frame)
        imgs_anim = {}
        imgs_static = {}
        to_update = []
        frame = scene.frame_current
        for obj in scene.objects.values():
            img_name = obj.pixel_data.pixel_image_name
            if img_name is None:
                continue
            if img_name in imgs_static:
                continue
            img = imgs_anim.get(img_name)
            if img is None:
                img = bpy.data.images.get(img_name)
                material = obj.active_material
                if material is None:
                    continue
                i = material.texture_slots.find(img_name)
                tex = obj.active_material.texture_slots[i].texture
                img = tex.image
                if img is None:
                    continue
                if not tex.image_user.frame_duration:
                    imgs_static[img_name] = img
                    continue
                if frame < tex.image_user.frame_start:
                    imgs_static[img_name] = img
                    continue
                if frame > tex.image_user.frame_duration - tex.image_user.frame_start:
                    imgs_static[img_name] = img
                    continue
                imgs_anim[img_name] = img
                tex.image_user.frame_current = frame
                img.update_tag()
                tex.update_tag()
                scene.update()
                img.pixel_image.check_scale()
            to_update.append(obj)
        scene.update()
        for obj in to_update:
            obj.pixel_data.update_color(image=img)
            obj.data.update_tag()
            obj.active_material.update_tag()
            obj.update_tag()
        print(imgs_anim)
        scene.update()
    def make_material(self, context, image):
        data = bpy.data
        self.material_name = '%s-%dx%d' % (self.pixel_image_name, self.x, self.y)
        if self.material_name in data.materials:
            material = data.materials[self.material_name]
        else:
            material = data.materials.new(self.material_name)
        if context.scene.render.engine == 'CYCLES':
            material.use_nodes = True
            bsdf = material.node_tree.nodes['Diffuse BSDF']
            bsdf.inputs[0].default_value = self.color
        else:
            tex = data.textures.get(image.name)
            if tex is None:
                tex = data.textures.new(image.name, type='IMAGE')
                tex.image = image
                tex.image_user.frame_start = image.frame_start
                tex.image_user.frame_duration = image.frame_duration
                tex.image_user.use_auto_refresh = True
            slot_index = material.texture_slots.find(tex.name)
            if slot_index == -1:
                slot = material.texture_slots.add()
                slot.texture = tex
            else:
                slot = material.texture_slots[slot_index]
            slot.use_map_color_diffuse = False
            material.diffuse_color = self.color[:3]
            material.alpha = self.color[3]
            material.use_transparency = True

        self.id_data.active_material = material
    def update_color(self, context=None, image=None):
        if image is None:
            if context is not None:
                data = context.blend_data
            else:
                image = self.id_data.active_material.active_texture.image
                #data = bpy.data
                #image = data.images[self.pixel_image_name]
        i = self.pixel_start_index
        self.color = image.pixels[i:i+4]
        z_mod_amt = self.z_scale_modifier_amount
        if z_mod_amt == 0:
            return
        z_mod_attr = self.z_scale_color_modifier
        if z_mod_attr == 'a':
            val = self.color[3]
        else:
            color = mathutils.Color(self.color[:3])
            val = getattr(color, z_mod_attr)
        z = val * z_mod_amt
        self.id_data.scale[2] = z


class PixelReference(bpy.types.PropertyGroup):
    name = StringProperty()
    def get_object(self, context=None, data=None):
        if data is None:
            if context is not None:
                data = context.data
            else:
                data = bpy.data
        return data.objects[self.name]
    def get_pixel(self, context=None, data=None):
        obj = self.get_object(context, data)
        return obj.pixel_data

class PixelImage(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Image.pixel_image = PointerProperty(type=cls)
        cls.pixel_refs = CollectionProperty(
            name='pixel_refs',
            type=PixelReference,
        )
        cls.original_size = IntVectorProperty(
            name='OriginalSize',
            size=2,
        )
        cls.scale_factor = FloatProperty(name='ScaleFactor')
        cls.pixel_scale = FloatVectorProperty(
            name='Pixel Scale',
            size=2,
        )
    def check_scale(self):
        image = self.id_data
        if list(image.size) == list(self.original_size):
            image.scale(*[i // self.scale_factor for i in image.size])

class PixelImageReference(bpy.types.PropertyGroup):
    name = StringProperty()
    def get_pixel_image(self, context=None, data=None):
        if data is None:
            if context is not None:
                data = context.data
            else:
                data = bpy.data
        image = data.images[self.name]
        return image.pixel_image

class PixelGeneratorProps(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Scene.pixel_generator_props = PointerProperty(type=cls)
        cls.pixel_image_refs = CollectionProperty(
            type=PixelImageReference,
            name='pixel_image_refs',
        )
        cls.scale_factor = FloatProperty(
            default=64.,
            name='Scale Factor',
        )
        cls.pixel_object_scale = FloatVectorProperty(
            default=[1., 1., 1.],
            size=3,
            name='Pixel Object Scale',
        )
        cls.use_active_object = BoolProperty(
            default=True,
            name='Use Active Object',
        )
        cls.z_scale_color_modifier = EnumProperty(
            items=[
                ('r', 'red', 'Red'),
                ('g', 'green', 'Green'),
                ('b', 'blue', 'Blue'),
                ('h', 'hue', 'Hue'),
                ('s', 'sat', 'Saturation'),
                ('v', 'value', 'Value'),
                ('a', 'alpha', 'Alpha'),
            ],
            default='v',
        )
        cls.z_scale_modifier_amount = FloatProperty(default=0.)

def delete_object(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select = True
    bpy.ops.object.delete()

def set_object_parent(scene, obj, parent):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select = True
    parent.select = True
    scene.objects.active = parent
    bpy.ops.object.parent_set()

class PixelGenerator(bpy.types.Operator):
    bl_idname = 'image.pixel_generator'
    bl_label = 'Pixel Generator'
    def remove_old_data(self, pixel_image_ref):
        pixel_image = pixel_image_ref.get_pixel_image()
        scene = pixel_image_ref.id_data
        first_obj = None
        empty_obj = None
        for pixel_ref in pixel_image.pixel_refs.values():
            try:
                obj = pixel_ref.get_object(data=scene)
            except KeyError:
                obj = None
            if obj is not None:
                if empty_obj is None and obj.parent is not None:
                    empty_obj = obj.parent
                else:
                    obj.parent = None
                if obj.pixel_data.is_first_obj:
                    first_obj = obj
                    continue
                delete_object(obj)
        if empty_obj is not None:
            delete_object(empty_obj)
        pixel_image.pixel_refs.clear()
        i = scene.pixel_generator_props.pixel_image_refs.find(pixel_image_ref.name)
        scene.pixel_generator_props.pixel_image_refs.remove(i)
        return first_obj
    def generate_pixels(self, context, image, first_obj):
        props = context.scene.pixel_generator_props
        active_obj = context.active_object
        if props.use_active_object:
            if active_obj is not None:
                obj = active_obj
                if first_obj is not None and first_obj != obj:
                    delete_object(first_obj)
            elif first_obj is not None:
                obj = first_obj
                obj.select = True
            else:
                obj = None
        if obj is None:
            bpy.ops.mesh.primitive_cube_add(location=(0., 0., 0.))
            obj = context.active_object
        objdata = obj.data
        image_size = image.size

        bpy.ops.object.add()
        empty_obj = context.active_object
        empty_obj.name = '-'.join(['Empty', image.name])
        empty_obj.location = [image_size[0]/2., image_size[1]/2., -10.]
        empty_obj.select = False

        z_mod_attr = props.z_scale_color_modifier
        z_mod_amt = props.z_scale_modifier_amount
        obj.select = True
        #pixel_scale = [1, 1]#self.pixel_image_scale
        #pixel_size = [i // px_scale for i, px_scale in zip(image_size, pixel_scale)]
        is_first_obj = True
        for x in range(image_size[0]):
            for y in range(image_size[1]):
                if is_first_obj:
                    is_first_obj = False
                else:
                    #bpy.ops.object.select_all(action='DESELECT')
                    obj = obj.copy()
                    obj.data = objdata.copy()
                    context.scene.objects.link(obj)
                #image_pos = [px * im for px, im in zip(px_pos, image_size)]
                obj.scale = props.pixel_object_scale
                obj.location = [x, y, 0]
                set_object_parent(context.scene, obj, empty_obj)
                obj.pixel_data.is_first_obj = is_first_obj
                obj.pixel_data.position = [x, y]
                obj.pixel_data.pixel_image_name = image.name
                obj.pixel_data.z_scale_color_modifier = z_mod_attr
                obj.pixel_data.z_scale_modifier_amount = z_mod_amt
                block_number = (y * image_size[0]) + x
                obj.pixel_data.pixel_start_index = int(block_number * 4)
                material = obj.pixel_data.make_material(context, image)
                #obj.data.materials.append(material)
                obj.pixel_data.update_color(context, image)
                pixel_ref = image.pixel_image.pixel_refs.add()
                pixel_ref.name = obj.name

    def execute(self, context):
        props = context.scene.pixel_generator_props
        image = context.area.spaces.active.image
        pixel_image = image.pixel_image
        if image.name in props.pixel_image_refs:
            first_obj = self.remove_old_data(props.pixel_image_refs[image.name])
        else:
            first_obj = None
        image.reload()
        img_ref = props.pixel_image_refs.add()
        img_ref.name = image.name
        #if len(image.pixel_image.pixels):
        #    self.remove_old_pixels(pixel_image)
        #    image.reload()
        pixel_image.scale_factor = props.scale_factor
        pixel_image.original_size = image.size
        new_size = [i // props.scale_factor for i in image.size]
        image.scale(*new_size)
        self.generate_pixels(context, image, first_obj)
        return {'FINISHED'}

class PixelGeneratorUi(bpy.types.Panel):
    bl_label = 'Pixel Generator'
    bl_idname = 'IMAGE_PT_pixel_generator'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'
    def draw(self, context):
        props = context.scene.pixel_generator_props
        layout = self.layout
        row = layout.row()
        row.prop(props, 'scale_factor')
        row = layout.row()
        row.prop(props, 'pixel_object_scale')
        row = layout.row()
        row.prop(props, 'use_active_object')
        row = layout.row()
        row.prop(props, 'z_scale_color_modifier')
        row = layout.row()
        row.prop(props, 'z_scale_modifier_amount')
        row = layout.row()
        row.operator('image.pixel_generator')


def generate_cubes(image_name, scale_factor=16):
    orig_img = bpy.data.images[image_name]
    img = orig_img.copy()
    img.scale(img.size[0] // 16, img.size[1] // 16)
    width, height = myImage.size
    for y in range(0, height):
        for x in range(0, width):
            block_number = (y * width) + x
            color = []
            for color_index in range(0, 4):
                index = (block_number * 4) + color_index
                color.append(myImage.pixels[index])
            draw_pix(x * 2, y * 2, color)
        print ("y: %(y)04d / %(height)04d" % {"y": y, "height": height})

#cubify('sprite.png')

#@persistent
def pixel_cubes_on_frame_change(scene):
    Pixel.on_frame_change(scene)

def remove_old_handler():
    for f in bpy.app.handlers.frame_change_post[:]:
        if f.__name__ == pixel_cubes_on_frame_change.__name__:
            bpy.app.handlers.frame_change_post.remove(f)

def add_handler():
    remove_old_handler()
    bpy.app.handlers.frame_change_post.append(pixel_cubes_on_frame_change)

def register():
    bpy.utils.register_class(PixelReference)
    bpy.utils.register_class(PixelImageReference)
    bpy.utils.register_class(Pixel)
    bpy.utils.register_class(PixelImage)
    bpy.utils.register_class(PixelGeneratorProps)
    bpy.utils.register_class(PixelGenerator)
    bpy.utils.register_class(PixelGeneratorUi)
    add_handler()

def unregister():
    remove_old_handler()
    bpy.utils.unregister_class(PixelGeneratorUi)
    bpy.utils.unregister_class(PixelGenerator)
    bpy.utils.unregister_class(PixelGeneratorProps)
    bpy.utils.unregister_class(PixelImage)
    bpy.utils.unregister_class(Pixel)
    bpy.utils.unregister_class(PixelImageReference)
    bpy.utils.unregister_class(PixelReference)

if __name__ == '__main__':
    register()
