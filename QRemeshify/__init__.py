bl_info = {
    "name": "QRemeshify",
    "description": "Quad remesher with symmetry and flow cleanup",
    "author": "ksami; ReQRemeshify fork improvements",
    "version": (1, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > QRemeshify",
    "category": "Mesh",
}

import bpy

from .operator import QREMESH_OT_Remesh
from .props import QRPropertyGroup, QWPropertyGroup
from .ui import QREMESH_PT_UIAdvancedPanel, QREMESH_PT_UICallbackPanel, QREMESH_PT_UIPanel


classes = (
    QWPropertyGroup,
    QRPropertyGroup,
    QREMESH_OT_Remesh,
    QREMESH_PT_UIPanel,
    QREMESH_PT_UIAdvancedPanel,
    QREMESH_PT_UICallbackPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.quadwild_props = bpy.props.PointerProperty(type=QWPropertyGroup)
    bpy.types.Scene.quadpatches_props = bpy.props.PointerProperty(type=QRPropertyGroup)


def unregister():
    # Delete Scene properties before unregistering their PropertyGroup classes.
    if hasattr(bpy.types.Scene, "quadpatches_props"):
        del bpy.types.Scene.quadpatches_props
    if hasattr(bpy.types.Scene, "quadwild_props"):
        del bpy.types.Scene.quadwild_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
