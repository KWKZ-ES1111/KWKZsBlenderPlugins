bl_info = {
    "name": "Origin To Selected Edge",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Object Mode Context Menu > Set Origin > Selected Edge",
    "description": "Move the active object's origin to the selected edge midpoint and align local Z to that edge.",
    "category": "Object",
}

import bpy
from mathutils import Matrix, Vector


ORIGIN_MENU_NAMES = (
    "VIEW3D_MT_object_set_origin",
    "VIEW3D_MT_object_origin",
    "VIEW3D_MT_set_origin",
)
CONTEXT_MENU_NAMES = (
    "VIEW3D_MT_object_context_menu",
)
registered_menu_hooks = []


def selected_edges(mesh):
    return [edge for edge in mesh.edges if edge.select]


def transform_mesh_coordinates(mesh, local_transform):
    if mesh.shape_keys:
        for key_block in mesh.shape_keys.key_blocks:
            for point in key_block.data:
                point.co = local_transform @ point.co
    else:
        for vertex in mesh.vertices:
            vertex.co = local_transform @ vertex.co

    mesh.update()


def set_origin_to_edge(obj, edge):
    mesh = obj.data
    old_matrix = obj.matrix_world.copy()
    old_vertex_a = mesh.vertices[edge.vertices[0]].co.copy()
    old_vertex_b = mesh.vertices[edge.vertices[1]].co.copy()
    edge_midpoint_local = (old_vertex_a + old_vertex_b) * 0.5
    edge_midpoint_world = old_matrix @ edge_midpoint_local
    edge_direction_world = old_matrix.to_3x3() @ (old_vertex_b - old_vertex_a)

    if edge_direction_world.length == 0.0:
        raise ValueError("Selected edge has zero length.")

    edge_direction_world.normalize()
    _location, _rotation, scale = old_matrix.decompose()
    scale = Vector((abs(scale.x), abs(scale.y), abs(scale.z)))
    new_rotation = edge_direction_world.to_track_quat("Z", "Y")
    new_matrix = Matrix.LocRotScale(edge_midpoint_world, new_rotation, scale)
    local_transform = new_matrix.inverted() @ old_matrix
    child_world_matrices = {child: child.matrix_world.copy() for child in obj.children}

    transform_mesh_coordinates(mesh, local_transform)
    obj.matrix_world = new_matrix

    for child, child_matrix in child_world_matrices.items():
        child.matrix_world = child_matrix


class OBJECT_OT_origin_to_selected_edge(bpy.types.Operator):
    bl_idname = "object.origin_to_selected_edge"
    bl_label = "Selected Edge"
    bl_description = "Move origin to the selected edge midpoint and align local Z to the edge"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        active_object = context.view_layer.objects.active
        return context.mode == "OBJECT" and active_object is not None and active_object.type == "MESH"

    def execute(self, context):
        obj = context.view_layer.objects.active

        if obj.data.users > 1:
            obj.data = obj.data.copy()

        mesh = obj.data
        edges = selected_edges(mesh)

        if len(edges) != 1:
            self.report({"ERROR"}, "Select exactly one edge in Edit Mode, then return to Object Mode.")
            return {"CANCELLED"}

        try:
            set_origin_to_edge(obj, edges[0])
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, "Origin moved to selected edge and local Z aligned.")
        return {"FINISHED"}


def draw_origin_menu(self, _context):
    self.layout.operator(OBJECT_OT_origin_to_selected_edge.bl_idname, icon="EDGESEL")


def draw_context_menu(self, _context):
    self.layout.separator()
    self.layout.operator(
        OBJECT_OT_origin_to_selected_edge.bl_idname,
        text="Set Origin to Selected Edge",
        icon="EDGESEL",
    )


def append_menu(menu_name, draw_func):
    menu_type = getattr(bpy.types, menu_name, None)
    if menu_type is None:
        return

    menu_type.append(draw_func)
    registered_menu_hooks.append((menu_type, draw_func))


classes = (
    OBJECT_OT_origin_to_selected_edge,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    for menu_name in ORIGIN_MENU_NAMES:
        append_menu(menu_name, draw_origin_menu)

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
