bl_info = {
    "name": "Weight Gradient Bridge",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Item > Weight Gradient Bridge",
    "description": (
        "Fill two anchor vertex groups with complementary smooth weight gradients "
        "interpolated by distance to the anchors across the whole mesh "
        "(rubber boots / flexible sleeves fixed at both ends)."
    ),
    "category": "Mesh",
}

import bpy
from mathutils.kdtree import KDTree


ANCHOR_WEIGHT_EPS = 1e-3


def clamp01(value):
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def find_group(obj, name):
    if not name:
        return None
    return obj.vertex_groups.get(name)


def anchor_positions(mesh_vertices, group):
    """Coordinates of vertices that already carry weight in the anchor group."""
    positions = []
    for vert in mesh_vertices:
        if group.weight(vert.index) > ANCHOR_WEIGHT_EPS:
            positions.append(vert.co.copy())
    return positions


def build_kdtree(positions):
    tree = KDTree(len(positions))
    for index, co in enumerate(positions):
        tree.insert(co, index)
    tree.balance()
    return tree


def distance_to_anchor(tree, co):
    return tree.find_n(co, 1)[0][2]


class OBJECT_OT_weight_gradient_bridge(bpy.types.Operator):
    bl_idname = "object.weight_gradient_bridge"
    bl_label = "Apply Gradient"
    bl_description = (
        "Write weights into the two anchor groups: group A gets weight_a at its anchor "
        "and weight_b at the other anchor, interpolated by vertex distance; "
        "group B receives the complementary gradient"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        scene = context.scene
        obj = context.view_layer.objects.active

        if context.mode != "OBJECT":
            self.report({"ERROR"}, "Run in Object Mode.")
            return {"CANCELLED"}

        group_a = find_group(obj, scene.weight_gradient_bridge_group_a)
        group_b = find_group(obj, scene.weight_gradient_bridge_group_b)

        if group_a is None or group_b is None:
            self.report({"ERROR"}, "Pick two vertex groups (Group A and Group B).")
            return {"CANCELLED"}

        if group_a.name == group_b.name:
            self.report({"ERROR"}, "Group A and Group B must be different groups.")
            return {"CANCELLED"}

        weight_a = clamp01(scene.weight_gradient_bridge_weight_a)
        weight_b = clamp01(scene.weight_gradient_bridge_weight_b)

        mesh_vertices = obj.data.vertices
        positions_a = anchor_positions(mesh_vertices, group_a)
        positions_b = anchor_positions(mesh_vertices, group_b)

        if not positions_a or not positions_b:
            self.report(
                {"ERROR"},
                "Assign at least one vertex with weight > 0 to each anchor group first.",
            )
            return {"CANCELLED"}

        tree_a = build_kdtree(positions_a)
        tree_b = build_kdtree(positions_b)

        vertex_count = len(mesh_vertices)
        values_a = [0.0] * vertex_count
        min_p = 1.0
        max_p = 0.0

        for index, vert in enumerate(mesh_vertices):
            dist_a = distance_to_anchor(tree_a, vert.co)
            dist_b = distance_to_anchor(tree_b, vert.co)
            total = dist_a + dist_b

            # p = A-anchor proximity: ~1 next to group A, ~0 next to group B.
            p = 0.5 if total < 1e-9 else dist_b / total
            if p < min_p:
                min_p = p
            if p > max_p:
                max_p = p

            values_a[index] = clamp01(weight_a * p + weight_b * (1.0 - p))

        if max_p - min_p < 1e-6:
            self.report(
                {"WARNING"},
                "Gradient is flat: the two anchor groups seem to overlap or cover every vertex.",
            )
            return {"CANCELLED"}

        index_list = list(range(vertex_count))
        group_a.add(index_list, values_a, "REPLACE")

        if scene.weight_gradient_bridge_complement:
            values_b = [
                clamp01(weight_a + weight_b - value_a) for value_a in values_a
            ]
            group_b.add(index_list, values_b, "REPLACE")

        self.report(
            {"INFO"},
            f"Gradient written to '{group_a.name}'"
            + (" and complement to '{}'.".format(group_b.name)
               if scene.weight_gradient_bridge_complement
               else "."),
        )
        return {"FINISHED"}


class VIEW3D_PT_weight_gradient_bridge(bpy.types.Panel):
    bl_label = "Weight Gradient Bridge"
    bl_idname = "VIEW3D_PT_weight_gradient_bridge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.view_layer.objects.active

        if obj is None or obj.type != "MESH":
            layout.label(text="Select a mesh object.", icon="INFO")
            return

        layout.label(text=f"Object: {obj.name}", icon="OBJECT_DATA")

        layout.prop_search(
            scene,
            "weight_gradient_bridge_group_a",
            obj,
            "vertex_groups",
            text="Group A",
        )
        layout.prop_search(
            scene,
            "weight_gradient_bridge_group_b",
            obj,
            "vertex_groups",
            text="Group B",
        )

        layout.separator()
        layout.prop(scene, "weight_gradient_bridge_weight_a")
        layout.prop(scene, "weight_gradient_bridge_weight_b")
        layout.prop(scene, "weight_gradient_bridge_complement")

        layout.separator()
        row = layout.row()
        row.enabled = context.mode == "OBJECT"
        row.operator(OBJECT_OT_weight_gradient_bridge.bl_idname, icon="GROUP_VERTEX")

        if context.mode != "OBJECT":
            layout.label(text="Run in Object Mode.", icon="ERROR")
        else:
            layout.label(text="Anchors: weight > 0 assigned to each group.", icon="INFO")


classes = (
    OBJECT_OT_weight_gradient_bridge,
    VIEW3D_PT_weight_gradient_bridge,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.weight_gradient_bridge_group_a = bpy.props.StringProperty(
        name="Group A",
        description="Anchor group at the first end; its vertices receive weight_a",
        default="",
    )
    bpy.types.Scene.weight_gradient_bridge_group_b = bpy.props.StringProperty(
        name="Group B",
        description="Anchor group at the second end; its vertices receive weight_b",
        default="",
    )
    bpy.types.Scene.weight_gradient_bridge_weight_a = bpy.props.FloatProperty(
        name="Max Weight (A End)",
        description="Weight written next to the Group A anchor",
        default=1.0,
        min=0.0,
        max=1.0,
    )
    bpy.types.Scene.weight_gradient_bridge_weight_b = bpy.props.FloatProperty(
        name="Min Weight (B End)",
        description="Weight written next to the Group B anchor",
        default=0.0,
        min=0.0,
        max=1.0,
    )
    bpy.types.Scene.weight_gradient_bridge_complement = bpy.props.BoolProperty(
        name="Write Complement To Group B",
        description="Also fill group B with (weight_a + weight_b - value) so both groups add up smoothly",
        default=True,
    )


def unregister():
    del bpy.types.Scene.weight_gradient_bridge_complement
    del bpy.types.Scene.weight_gradient_bridge_weight_b
    del bpy.types.Scene.weight_gradient_bridge_weight_a
    del bpy.types.Scene.weight_gradient_bridge_group_b
    del bpy.types.Scene.weight_gradient_bridge_group_a

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
