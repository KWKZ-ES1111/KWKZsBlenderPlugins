bl_info = {
    "name": "Top Level Parent To Bone",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Object Mode Context Menu > Parent To Bone",
    "description": "Add a top-level object context menu entry for setting the selected objects' parent to the active bone.",
    "category": "Object",
}

import bpy


CONTEXT_MENU_NAMES = (
    "VIEW3D_MT_object_context_menu",
)
registered_menu_hooks = []


class OBJECT_OT_top_level_parent_to_bone(bpy.types.Operator):
    bl_idname = "object.top_level_parent_to_bone"
    bl_label = "Parent To Bone"
    bl_description = "Set the selected objects' parent to the active bone"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bpy.ops.object.parent_set.poll()

    def execute(self, context):
        return bpy.ops.object.parent_set(type="BONE")


def draw_context_menu(self, _context):
    self.layout.separator()
    self.layout.operator(
        OBJECT_OT_top_level_parent_to_bone.bl_idname,
        text="Parent To Bone",
        icon="BONE_DATA",
    )


def append_menu(menu_name, draw_func):
    menu_type = getattr(bpy.types, menu_name, None)
    if menu_type is None:
        return

    menu_type.append(draw_func)
    registered_menu_hooks.append((menu_type, draw_func))


classes = (
    OBJECT_OT_top_level_parent_to_bone,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    for menu_name in CONTEXT_MENU_NAMES:
        append_menu(menu_name, draw_context_menu)


def unregister():
    for menu_type, draw_func in reversed(registered_menu_hooks):
        try:
            menu_type.remove(draw_func)
        except ValueError:
            pass

    registered_menu_hooks.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
