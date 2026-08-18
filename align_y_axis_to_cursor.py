bl_info = {
    "name": "Align Y Axis To 3D Cursor",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Object Mode Context Menu > Align Y Axis To 3D Cursor",
    "description": "Rotate around local Z and slide along local Z so local Y points to the 3D cursor as closely as possible.",
    "category": "Object",
}

import bpy
from mathutils import Matrix, Vector


CONTEXT_MENU_NAMES = (
    "VIEW3D_MT_object_context_menu",
)
registered_menu_hooks = []


def transform_mesh_coordinates(mesh, local_transform):
    if mesh.shape_keys:
        for key_block in mesh.shape_keys.key_blocks:
            for point in key_block.data:
                point.co = local_transform @ point.co
    else:
        for vertex in mesh.vertices:
            vertex.co = local_transform @ vertex.co

    mesh.update()


def normalized_axis(matrix, axis):
    direction = matrix.to_3x3() @ axis
    if direction.length == 0.0:
        raise ValueError("Object has a zero-length transform axis.")

    direction.normalize()
    return direction


def build_rotation_from_yz(y_axis, z_axis):
    x_axis = y_axis.cross(z_axis)
    if x_axis.length == 0.0:
        raise ValueError("Cannot build a stable rotation from the current axes.")

    x_axis.normalize()
    y_axis = z_axis.cross(x_axis)
    y_axis.normalize()

    return Matrix(
        (
            (x_axis.x, y_axis.x, z_axis.x),
            (x_axis.y, y_axis.y, z_axis.y),
            (x_axis.z, y_axis.z, z_axis.z),
        )
    ).to_quaternion()


def align_y_axis_to_cursor(obj, cursor_location):
    old_matrix = obj.matrix_world.copy()
    origin = old_matrix.translation
    z_axis = normalized_axis(old_matrix, Vector((0.0, 0.0, 1.0)))
    current_y_axis = normalized_axis(old_matrix, Vector((0.0, 1.0, 0.0)))

    z_offset = (cursor_location - origin).dot(z_axis)
    new_origin = origin + z_axis * z_offset
    target_vector = cursor_location - new_origin

    if target_vector.length > 1e-8:
        y_axis = target_vector.normalized()
    else:
        # The cursor lies on the locked Z axis; keep the current twist because all
        # possible Y directions are equally close.
        y_axis = current_y_axis - z_axis * current_y_axis.dot(z_axis)
        if y_axis.length == 0.0:
            y_axis = z_axis.orthogonal()
        y_axis.normalize()

    _location, _rotation, scale = old_matrix.decompose()
    scale = Vector((abs(scale.x), abs(scale.y), abs(scale.z)))
    new_rotation = build_rotation_from_yz(y_axis, z_axis)
    new_matrix = Matrix.LocRotScale(new_origin, new_rotation, scale)
    local_transform = new_matrix.inverted() @ old_matrix
    child_world_matrices = {child: child.matrix_world.copy() for child in obj.children}

    transform_mesh_coordinates(obj.data, local_transform)
    obj.matrix_world = new_matrix

    for child, child_matrix in child_world_matrices.items():
        child.matrix_world = child_matrix

    return (cursor_location - new_origin).length


class OBJECT_OT_align_y_axis_to_cursor(bpy.types.Operator):
    bl_idname = "object.align_y_axis_to_cursor"
    bl_label = "Align Y Axis To 3D Cursor"
    bl_description = "Keep local Z fixed, slide along Z, and rotate around Z so local Y points to the 3D cursor"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        active_object = context.view_layer.objects.active
        return context.mode == "OBJECT" and active_object is not None and active_object.type == "MESH"

    def execute(self, context):
        obj = context.view_layer.objects.active

        if obj.data.users > 1:
            obj.data = obj.data.copy()

        cursor_location = context.scene.cursor.location.copy()

        try:
            distance = align_y_axis_to_cursor(obj, cursor_location)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        if distance <= 1e-8:
            self.report(
                {"INFO"},
                "Cursor is on the locked Z axis; origin moved to cursor and current Y twist was preserved.",
            )
        else:
            self.report({"INFO"}, "Local Y aligned to the 3D cursor without changing local Z direction.")

        return {"FINISHED"}


def draw_context_menu(self, _context):
    self.layout.separator()
    self.layout.operator(
        OBJECT_OT_align_y_axis_to_cursor.bl_idname,
        icon="EMPTY_AXIS",
    )


def append_menu(menu_name, draw_func):
    menu_type = getattr(bpy.types, menu_name, None)
    if menu_type is None:
        return

    menu_type.append(draw_func)
    registered_menu_hooks.append((menu_type, draw_func))


classes = (
    OBJECT_OT_align_y_axis_to_cursor,
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
