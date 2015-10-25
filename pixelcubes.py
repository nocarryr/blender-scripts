#----------------------------------------------------------
# File photo.py - cubify a named image in project.
# @knowuh (Noah Paessel)  http://bit.ly/photoblend
# License: MIT ( http://opensource.org/licenses/MIT )
#----------------------------------------------------------

import bpy
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

class PixelImage(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.Image.pixel_image = PointerProperty(type=cls)
        cls.pixels = CollectionProperty(
            name='Pixels',
            type=Pixel,
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
        if image.size == self.original_size:
            image.scale(*[i // self.scale_factor for i in image.size])
        for pixel_ref in self.pixel_refs.values():
            pixel = pixel_ref.get_pixel(context, data)
            pixel.update_color(image=image)


class PixelGeneratorProps(bpy.types.PropertyGroup):
    @classmethod
    def register(cls):
        bpy.types.WindowManager.pixel_generator_props = PointerProperty(type=cls)
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
        props = context.window_manager.pixel_generator_props
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
                #image.pixel_image.pixels.add(obj.pixel_data)
    def execute(self, context):
        props = context.window_manager.pixel_generator_props
        image = context.area.spaces.active.image
        pixel_image = image.pixel_image
        if len(image.pixel_image.pixels):
            self.remove_old_pixels(pixel_image)
            image.reload()
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
        props = context.window_manager.pixel_generator_props
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

def register():
    bpy.utils.register_class(Pixel)
    bpy.utils.register_class(PixelImage)
    bpy.utils.register_class(PixelGeneratorProps)
    bpy.utils.register_class(PixelGenerator)
    bpy.utils.register_class(PixelGeneratorUi)

def unregister():
    bpy.utils.unregister_class(PixelGeneratorUi)
    bpy.utils.unregister_class(PixelGenerator)
    bpy.utils.unregister_class(PixelGeneratorProps)
    bpy.utils.unregister_class(PixelImage)
    bpy.utils.unregister_class(Pixel)

if __name__ == '__main__':
    register()
