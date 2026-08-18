bl_info = {
    "name": "Bone Axis Reference",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Item > Bone Axis Reference",
    "description": "Create vertices along the selected object's local +/-XYZ axes for checking bone orientation.",
    "category": "Object",
}

import re

import bpy
from mathutils import Matrix, Vector


AXIS_REFERENCE_PROP = "bone_axis_reference_target"


def parse_distances(raw_value):
    """Return sorted positive distances from a comma/space separated string."""
    tokens = re.split(r"[,;\s]+", raw_value.strip())
    distances = []
    seen = set()

    for token in tokens:
        if not token:
            continue

        try:
            distance = float(token)
        except ValueError as exc:
            raise ValueError(f"Invalid distance value: {token}") from exc

        if distance <= 0:
            raise ValueError("Distances must be greater than 0.")

        key = round(distance, 6)
        if key not in seen:
            seen.add(key)
            distances.append(distance)

    if not distances:
        raise ValueError("Enter at least one positive distance.")

    return sorted(distances)


def build_axis_reference_mesh(distances):
    verts = [(0.0, 0.0, 0.0)]
    edges = []
    axis_point_indices = {"x": [], "y": [], "z": []}

    for axis_index, axis_name in enumerate(("x", "y", "z")):
        for sign in (-1.0, 1.0):
            for distance in distances:
                coord = [0.0, 0.0, 0.0]
                coord[axis_index] = sign * distance
                axis_point_indices[axis_name].append((sign * distance, len(verts)))
                verts.append(tuple(coord))

    for axis_points in axis_point_indices.values():
        negative_points = sorted(
            ((value, index) for value, index in axis_points if value < 0.0),
            key=lambda item: item[0],
        )
        positive_points = sorted(
            ((value, index) for value, index in axis_points if value > 0.0),
            key=lambda item: item[0],
        )
        ordered_indices = [index for _, index in negative_points] + [0] + [
            index for _, index in positive_points
        ]

        for start, end in zip(ordered_indices, ordered_indices[1:]):
            edges.append((start, end))

    mesh = bpy.data.meshes.new("Bone Axis Reference Mesh")
    mesh.from_pydata(verts, edges, [])
    mesh.update()
    return mesh


def find_existing_reference(context, target):
    if not context.scene.bone_axis_reference_replace_existing:
        return None

    for obj in context.scene.objects:
        if obj.get(AXIS_REFERENCE_PROP) == target.name:
            return obj

    return None


def create_axis_reference(context, target, distances):
    mesh = build_axis_reference_mesh(distances)
    reference = find_existing_reference(context, target)

    if reference:
        old_mesh = reference.data
        reference.data = mesh
        if old_mesh and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
    else:
        reference = bpy.data.objects.new(f"{target.name}_AxisReference", mesh)
        context.collection.objects.link(reference)

    location, rotation, _scale = target.matrix_world.decompose()
    reference.matrix_world = Matrix.LocRotScale(location, rotation, Vector((1.0, 1.0, 1.0)))
    reference.show_in_front = context.scene.bone_axis_reference_show_in_front
    reference.display_type = "WIRE"
    reference[AXIS_REFERENCE_PROP] = target.name

    reference.select_set(True)
    target.select_set(True)
    context.view_layer.objects.active = target
    return reference


class OBJECT_OT_create_bone_axis_reference(bpy.types.Operator):
    bl_idname = "object.create_bone_axis_reference"
    bl_label = "Create Axis Reference"
    bl_description = "Create reference vertices along the active object's local +/-XYZ axes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        target = context.view_layer.objects.active

        if target is None:
            self.report({"ERROR"}, "Select an object first.")
            return {"CANCELLED"}

        if target.get(AXIS_REFERENCE_PROP):
            self.report({"ERROR"}, "Select the object you want to inspect, not an axis reference object.")
            return {"CANCELLED"}

        try:
            distances = parse_distances(context.scene.bone_axis_reference_distances)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        reference = create_axis_reference(context, target, distances)
        self.report({"INFO"}, f"Created axis reference: {reference.name}")
        return {"FINISHED"}


class VIEW3D_PT_bone_axis_reference(bpy.types.Panel):
    bl_label = "Bone Axis Reference"
    bl_idname = "VIEW3D_PT_bone_axis_reference"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        active_object = context.view_layer.objects.active

        layout.prop(scene, "bone_axis_reference_distances")
        layout.prop(scene, "bone_axis_reference_replace_existing")
        layout.prop(scene, "bone_axis_reference_show_in_front")

        row = layout.row()
        row.enabled = active_object is not None
        row.operator("object.create_bone_axis_reference", icon="EMPTY_AXIS")

        if active_object is None:
            layout.label(text="Select an object to use its origin and local axes.", icon="INFO")
        else:
            layout.label(text=f"Target: {active_object.name}", icon="OBJECT_DATA")

        layout.separator()
        layout.label(text="Example: 0.5, 1, 2")


classes = (
    OBJECT_OT_create_bone_axis_reference,
    VIEW3D_PT_bone_axis_reference,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.bone_axis_reference_distances = bpy.props.StringProperty(
        name="Distances",
        description="Positive distances from the origin; separate multiple values with commas, semicolons, or spaces",
        default="1",
    )
    bpy.types.Scene.bone_axis_reference_replace_existing = bpy.props.BoolProperty(
        name="Update Existing",
        description="Replace the previous reference generated for the same target object",
        default=True,
    )
    bpy.types.Scene.bone_axis_reference_show_in_front = bpy.props.BoolProperty(
        name="Show In Front",
        description="Draw the reference object in front of other geometry",
        default=True,
    )


def unregister():
    del bpy.types.Scene.bone_axis_reference_show_in_front
    del bpy.types.Scene.bone_axis_reference_replace_existing
    del bpy.types.Scene.bone_axis_reference_distances

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
