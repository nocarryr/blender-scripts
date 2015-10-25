#----------------------------------------------------------
# File photo.py - cubify a named image in project.
# @knowuh (Noah Paessel)  http://bit.ly/photoblend
# License: MIT ( http://opensource.org/licenses/MIT )
#----------------------------------------------------------

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    StringProperty,
    FloatProperty,
    CollectionProperty,
    IntVectorProperty,
    FloatVectorProperty,
    PointerProperty
)
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
        cls.pixel_image_name = StringProperty()
        cls.material_name = StringProperty()
        cls.position = FloatVectorProperty(size=2)
    def make_material(self, context):
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
            material.diffuse_color = self.color[:3]
            material.alpha = self.color[3]
            material.use_transparency = True

        self.id_data.active_material = material
    def update_color(self, context=None, image=None):
        if image is None:
            if context is not None:
                data = context.blend_data
            else:
                data = bpy.data
                image = data.images[self.pixel_image_name]
        i = int(self.x * self.y * 4)
        self.color = image.pixels[i:i+4]

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
    def update_pixels(self, context=None, data=None):
        image = self.id_data
        if list(image.size) == list(self.original_size):
            image.scale(*[i // self.scale_factor for i in image.size])
        for pixel_ref in self.pixel_refs.values():
            pixel = pixel_ref.get_pixel(context, data)
            pixel.update_color(image=image)

class PixelImageReference(bpy.types.PropertyGroup):
    name = StringProperty()
    @classmethod
    def on_frame_change(cls, scene):
        frame = scene.frame_current
        for img_ref in scene.pixel_generator_props.pixel_image_refs.values():
            pixel_image = img_ref.get_pixel_image()
            img = pixel_image.id_data
            fr_dur = img.frame_duration
            if not fr_dur:
                continue
            if frame < img.frame_start:
                continue
            if frame > fr_dur - img.frame_start:
                continue
            pixel_image.update_pixels(data=scene)
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

class PixelGenerator(bpy.types.Operator):
    bl_idname = 'image.pixel_generator'
    bl_label = 'Pixel Generator'
    def remove_old_pixels(self, pixel_image):
        return
        for pixel in pixel_image.pixels:
            ## TODO: figure out how to get the object
            #obj = ????
            bpy.ops.object.delete(obj)
        pixel_image.pixels.clear()
    def generate_pixels(self, context, image):
        props = context.scene.pixel_generator_props
        if props.use_active_object:
            obj = context.active_object
        else:
            bpy.ops.mesh.primitive_cube_add(location=(0., 0., 0.))
            obj = context.active_object
        image_size = image.size
        #pixel_scale = [1, 1]#self.pixel_image_scale
        #pixel_size = [i // px_scale for i, px_scale in zip(image_size, pixel_scale)]
        is_first_obj = True
        for x in range(image_size[0]):
            for y in range(image_size[1]):
                if is_first_obj:
                    is_first_obj = False
                else:
                    objdata = obj.data.copy()
                    bpy.ops.object.duplicate()
                    obj = bpy.context.active_object
                    obj.data = objdata
                #image_pos = [px * im for px, im in zip(px_pos, image_size)]
                obj.scale = props.pixel_object_scale
                obj.location = [x, y, 0]
                obj.pixel_data.position = [x, y]
                obj.pixel_data.pixel_image_name = image.name
                material = obj.pixel_data.make_material(context)
                #obj.data.materials.append(material)
                obj.pixel_data.update_color(context, image)
                pixel_ref = image.pixel_image.pixel_refs.add()
                pixel_ref.name = obj.name
    def execute(self, context):
        props = context.scene.pixel_generator_props
        image = context.area.spaces.active.image
        pixel_image = image.pixel_image
        if image.name in props.pixel_image_refs:
            self.remove_old_data(context.active_object, props.pixel_image_refs[image.name])
        img_ref = props.pixel_image_refs.add()
        img_ref.name = image.name
        #if len(image.pixel_image.pixels):
        #    self.remove_old_pixels(pixel_image)
        #    image.reload()
        pixel_image.scale_factor = props.scale_factor
        pixel_image.original_size = image.size
        new_size = [i // props.scale_factor for i in image.size]
        image.scale(*new_size)
        self.generate_pixels(context, image)
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
    PixelImageReference.on_frame_change(scene)

def remove_old_handler():
    for f in bpy.app.handlers.frame_change_pre[:]:
        if f.__name__ == pixel_cubes_on_frame_change.__name__:
            bpy.app.handlers.frame_change_pre.remove(f)

def add_handler():
    remove_old_handler()
    bpy.app.handlers.frame_change_pre.append(pixel_cubes_on_frame_change)

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
