bl_info = {
    "name": "Circle Through Three Verts",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Edit Mode Context Menu / Sidebar > Item",
    "description": "Create a separate circle mesh through three selected vertices to reveal the circumcenter.",
    "category": "Mesh",
}

import math

import bmesh
import bpy
from mathutils import Matrix, Vector


CIRCLE_REFERENCE_PROP = "circle_through_three_verts_source"
CONTEXT_MENU_NAMES = (
    "VIEW3D_MT_edit_mesh_context_menu",
)
registered_menu_hooks = []


def selected_mesh_vertices(bm):
    return [vert for vert in bm.verts if vert.select]


def circumcircle_from_points(point_a, point_b, point_c, epsilon=1e-8):
    ab = point_b - point_a
    ac = point_c - point_a
    normal = ab.cross(ac)
    normal_length_squared = normal.length_squared

    if normal_length_squared < epsilon * epsilon:
        raise ValueError("Selected vertices are collinear; cannot build a circle.")

    ab_length_squared = ab.length_squared
    ac_length_squared = ac.length_squared
    center = point_a + (
        ac_length_squared * normal.cross(ab) + ab_length_squared * ac.cross(normal)
    ) / (2.0 * normal_length_squared)
    radius = (center - point_a).length

    if radius < epsilon:
        raise ValueError("Computed circle radius is too small.")

    normal.normalize()
    return center, radius, normal


def build_oriented_basis(normal, preferred_x=None, epsilon=1e-8):
    if preferred_x is not None and preferred_x.length > epsilon:
        x_axis = preferred_x - preferred_x.dot(normal) * normal
        if x_axis.length > epsilon:
            x_axis.normalize()
            y_axis = normal.cross(x_axis).normalized()
            return x_axis, y_axis

    helper = Vector((1.0, 0.0, 0.0))
    if abs(normal.dot(helper)) > 0.9:
        helper = Vector((0.0, 1.0, 0.0))

    x_axis = normal.cross(helper).normalized()
    y_axis = normal.cross(x_axis).normalized()
    return x_axis, y_axis


def build_circle_mesh(radius, segments, include_center):
    verts = []
    edges = []

    for index in range(segments):
        angle = (2.0 * math.pi * index) / segments
        verts.append((math.cos(angle) * radius, math.sin(angle) * radius, 0.0))

    for index in range(segments):
        edges.append((index, (index + 1) % segments))

    if include_center:
        verts.append((0.0, 0.0, 0.0))

    mesh = bpy.data.meshes.new("Circle Through Three Verts Mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    return mesh


def create_circle_object(context, source_object, center, radius, normal, point_a):
    scene = context.scene
    segments = scene.circle_through_three_verts_segments
    include_center = scene.circle_through_three_verts_include_center
    show_in_front = scene.circle_through_three_verts_show_in_front

    x_axis, y_axis = build_oriented_basis(normal, preferred_x=point_a - center)
    rotation = Matrix((x_axis, y_axis, normal)).transposed().to_quaternion()
    mesh = build_circle_mesh(radius, segments, include_center)
    circle_object = bpy.data.objects.new(f"{source_object.name}_CircumCircle", mesh)
    context.collection.objects.link(circle_object)

    circle_object.matrix_world = Matrix.LocRotScale(center, rotation, Vector((1.0, 1.0, 1.0)))
    circle_object.show_in_front = show_in_front
    circle_object.display_type = "WIRE"
    circle_object[CIRCLE_REFERENCE_PROP] = source_object.name

    if scene.circle_through_three_verts_set_cursor:
        context.scene.cursor.location = center

    return circle_object


class MESH_OT_circle_through_three_verts(bpy.types.Operator):
    bl_idname = "mesh.circle_through_three_verts"
    bl_label = "Circle Through Three Verts"
    bl_description = "Create a separate circle through three selected vertices; object origin is the center"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        active_object = context.view_layer.objects.active
        return (
            context.mode == "EDIT_MESH"
            and active_object is not None
            and active_object.type == "MESH"
        )

    def execute(self, context):
        obj = context.view_layer.objects.active
        bm = bmesh.from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        selected = selected_mesh_vertices(bm)

        if len(selected) != 3:
            self.report({"ERROR"}, "Select exactly three vertices.")
            return {"CANCELLED"}

        point_a = obj.matrix_world @ selected[0].co
        point_b = obj.matrix_world @ selected[1].co
        point_c = obj.matrix_world @ selected[2].co

        try:
            center, radius, normal = circumcircle_from_points(point_a, point_b, point_c)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        previous_mode = obj.mode
        bpy.ops.object.mode_set(mode="OBJECT")

        try:
            circle_object = create_circle_object(
                context,
                obj,
                center,
                radius,
                normal,
                point_a,
            )
        finally:
            for scene_obj in context.view_layer.objects:
                scene_obj.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            try:
                bpy.ops.object.mode_set(mode=previous_mode)
            except RuntimeError:
                pass

        self.report(
            {"INFO"},
            f"Created circle '{circle_object.name}' (radius {radius:.6g}). Origin is the center.",
        )
        return {"FINISHED"}


class VIEW3D_PT_circle_through_three_verts(bpy.types.Panel):
    bl_label = "Circle Through Three Verts"
    bl_idname = "VIEW3D_PT_circle_through_three_verts"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "circle_through_three_verts_segments")
        layout.prop(scene, "circle_through_three_verts_include_center")
        layout.prop(scene, "circle_through_three_verts_show_in_front")
        layout.prop(scene, "circle_through_three_verts_set_cursor")

        row = layout.row()
        row.enabled = MESH_OT_circle_through_three_verts.poll(context)
        row.operator(MESH_OT_circle_through_three_verts.bl_idname, icon="MESH_CIRCLE")

        if context.mode != "EDIT_MESH":
            layout.label(text="Enter Edit Mode and select three vertices.", icon="INFO")
        else:
            layout.label(text="Select exactly three vertices, then create.", icon="INFO")


def draw_context_menu(self, context):
    if context.mode != "EDIT_MESH":
        return

    self.layout.separator()
    self.layout.operator(
        MESH_OT_circle_through_three_verts.bl_idname,
        text="Circle Through Three Verts",
        icon="MESH_CIRCLE",
    )


def append_menu(menu_name, draw_func):
    menu_type = getattr(bpy.types, menu_name, None)
    if menu_type is None:
        return

    menu_type.append(draw_func)
    registered_menu_hooks.append((menu_type, draw_func))


classes = (
    MESH_OT_circle_through_three_verts,
    VIEW3D_PT_circle_through_three_verts,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.circle_through_three_verts_segments = bpy.props.IntProperty(
        name="Segments",
        description="Number of vertices used to approximate the circle",
        default=32,
        min=3,
        max=512,
    )
    bpy.types.Scene.circle_through_three_verts_include_center = bpy.props.BoolProperty(
        name="Include Center Vertex",
        description="Add an unconnected center vertex inside the circle mesh",
        default=True,
    )
    bpy.types.Scene.circle_through_three_verts_show_in_front = bpy.props.BoolProperty(
        name="Show In Front",
        description="Display the generated circle in front of other geometry",
        default=True,
    )
    bpy.types.Scene.circle_through_three_verts_set_cursor = bpy.props.BoolProperty(
        name="Move 3D Cursor To Center",
        description="Place the 3D cursor at the computed circle center",
        default=True,
    )

    for menu_name in CONTEXT_MENU_NAMES:
        append_menu(menu_name, draw_context_menu)


def unregister():
    for menu_type, draw_func in reversed(registered_menu_hooks):
        try:
            menu_type.remove(draw_func)
        except ValueError:
            pass

    registered_menu_hooks.clear()

    del bpy.types.Scene.circle_through_three_verts_set_cursor
    del bpy.types.Scene.circle_through_three_verts_show_in_front
    del bpy.types.Scene.circle_through_three_verts_include_center
    del bpy.types.Scene.circle_through_three_verts_segments

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
