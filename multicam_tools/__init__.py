from multicam_tools import multicam, multicam_ui

bl_info = {
    "name": "Multicam Tools",
    "author": "Matt Reid",
    "version": (0, 0, 1),
    "blender": (2, 74, 0),
    "description": "", 
    "warning": "",
}

def register():
    multicam._register()
    multicam_ui._register()
    
def unregister():
    multicam._unregister()
    multicam_ui._unregister()

if __name__ == '__main__':
    register()
