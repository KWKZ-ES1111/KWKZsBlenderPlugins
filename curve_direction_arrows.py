bl_info = {
    "name": "Curve Direction Arrows",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Item > Curve Direction Arrows",
    "description": "Generate arrow meshes along curve objects to visualize their direction.",
    "category": "Object",
}

import bisect
import math

import bpy
from mathutils import Matrix, Vector


ARROW_PROP = "curve_direction_arrows_target"
ARROW_MATERIAL = "Curve Direction Arrow"
MAX_ARROWS = 2000

STYLE_ITEMS = (
    ("SOLID", "Solid", "Cylinder shaft with a cone head"),
    ("FLAT", "Flat", "Thin extruded arrow silhouette"),
)

DISTRIBUTION_ITEMS = (
    ("COUNT", "Count", "Place a fixed number of arrows on each curve"),
    ("SPACING", "Spacing", "Place arrows at a fixed arc length interval"),
)

SIZE_MODE_ITEMS = (
    ("RELATIVE", "Relative", "Arrow length as a percentage of the curve length"),
    ("ABSOLUTE", "Absolute", "Arrow length in Blender units"),
)

UP_AXIS_ITEMS = (
    ("WORLD_Z", "World Z", "Use world +Z as the arrow up axis"),
    ("WORLD_Y", "World Y", "Use world +Y as the arrow up axis"),
    ("WORLD_X", "World X", "Use world +X as the arrow up axis"),
    ("CURVE_UP", "Curve Up", "Use the curve object's local +Z axis"),
)

UP_AXIS_VECTORS = {
    "WORLD_X": Vector((1.0, 0.0, 0.0)),
    "WORLD_Y": Vector((0.0, 1.0, 0.0)),
    "WORLD_Z": Vector((0.0, 0.0, 1.0)),
}


def _ring_vertices(x, radius, segments):
    return [
        (
            x,
            radius * math.cos(2.0 * math.pi * i / segments),
            radius * math.sin(2.0 * math.pi * i / segments),
        )
        for i in range(segments)
    ]


def build_solid_arrow_geometry(segments=12):
    """Build a unit length arrow pointing along local +X, centered on the origin."""
    tail = -0.5
    neck = 0.10
    tip = 0.5
    shaft_radius = 0.05
    head_radius = 0.16

    tail_ring = _ring_vertices(tail, shaft_radius, segments)
    neck_ring = _ring_vertices(neck, shaft_radius, segments)
    head_ring = _ring_vertices(neck, head_radius, segments)

    verts = []
    verts.extend(tail_ring)
    verts.extend(neck_ring)
    verts.extend(head_ring)
    apex = len(verts)
    verts.append((tip, 0.0, 0.0))

    tail_start = 0
    neck_start = segments
    head_start = segments * 2

    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((tail_start + i, tail_start + j, neck_start + j, neck_start + i))
        faces.append((head_start + i, head_start + j, apex))

    faces.append(tuple(tail_start + i for i in reversed(range(segments))))
    faces.append(tuple(head_start + i for i in reversed(range(segments))))

    return verts, faces


def build_flat_arrow_geometry():
    """Build a thin unit length arrow silhouette pointing along local +X."""
    half_thickness = 0.05
    tail = -0.5
    neck = 0.12
    tip = 0.5
    tail_half = 0.055
    head_half = 0.16

    outline = (
        (tail, -tail_half),
        (neck, -tail_half),
        (neck, -head_half),
        (tip, 0.0),
        (neck, head_half),
        (neck, tail_half),
        (tail, tail_half),
    )

    verts = [(x, y, half_thickness) for x, y in outline]
    verts.extend((x, y, -half_thickness) for x, y in outline)

    count = len(outline)
    faces = [
        tuple(range(count)),
        tuple(reversed(range(count, count * 2))),
    ]
    for i in range(count):
        j = (i + 1) % count
        faces.append((i, count + i, count + j, j))

    return verts, faces


def _walk_path(path, remaining, adjacency):
    """Extend path along unused edges. Return True when the path closed on itself."""
    while True:
        current = path[-1]
        previous = path[-2]
        next_index = None

        for candidate in adjacency[current]:
            if candidate == previous:
                continue
            key = (min(current, candidate), max(current, candidate))
            if key in remaining:
                remaining.remove(key)
                next_index = candidate
                break

        if next_index is None:
            return False

        path.append(next_index)
        if next_index == path[0]:
            return True


def mesh_to_polylines(mesh):
    """Split a tessellated curve mesh into ordered vertex paths."""
    coords = [vertex.co.copy() for vertex in mesh.vertices]
    adjacency = [[] for _ in coords]
    remaining = set()

    for edge in mesh.edges:
        a, b = edge.vertices
        if a == b:
            continue
        adjacency[a].append(b)
        adjacency[b].append(a)
        remaining.add((min(a, b), max(a, b)))

    if not remaining:
        return [coords] if coords else []

    polylines = []
    while remaining:
        a, b = remaining.pop()
        path = [a, b]
        closed = _walk_path(path, remaining, adjacency)
        if not closed:
            path.reverse()
            _walk_path(path, remaining, adjacency)
        polylines.append([coords[index] for index in path])

    return polylines


def curve_polylines(curve_obj, context):
    """Return the curve centerline as world space polylines.

    A temporary copy without bevel/extrude is evaluated so the result is the
    curve path itself rather than its beveled surface geometry.
    """
    source = curve_obj.data
    temp_curve = source.copy()
    temp_curve.bevel_depth = 0.0
    temp_curve.bevel_resolution = 0
    temp_curve.extrude = 0.0
    temp_curve.offset = 0.0
    temp_curve.bevel_object = None
    temp_curve.taper_object = None
    temp_curve.fill_mode = "NONE"

    temp_obj = bpy.data.objects.new("_CurveDirectionSample", temp_curve)
    collection = context.collection or context.scene.collection
    collection.objects.link(temp_obj)

    try:
        context.view_layer.update()
        depsgraph = context.evaluated_depsgraph_get()
        evaluated = temp_obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            polylines = mesh_to_polylines(mesh)
        finally:
            evaluated.to_mesh_clear()
    finally:
        bpy.data.objects.remove(temp_obj, do_unlink=True)
        bpy.data.curves.remove(temp_curve)

    matrix = curve_obj.matrix_world
    return [[matrix @ co for co in polyline] for polyline in polylines]


def arrow_frame(tangent, up):
    """Return a rotation matrix mapping local +X to tangent and local +Z to up."""
    forward = tangent.normalized()

    projected_up = up - forward * forward.dot(up)
    if projected_up.length <= 1e-6:
        fallback = Vector((0.0, 1.0, 0.0))
        if abs(forward.dot(fallback)) > 0.99:
            fallback = Vector((1.0, 0.0, 0.0))
        projected_up = fallback - forward * forward.dot(fallback)

    local_up = projected_up.normalized()
    local_side = local_up.cross(forward)
    rotation = Matrix((forward, local_side, local_up)).transposed().to_4x4()
    return rotation, local_up


def sample_curve(polylines, scene):
    """Return (point, tangent) samples and the total centerline length."""
    segments = []
    total_length = 0.0

    for polyline in polylines:
        for start, end in zip(polyline, polyline[1:]):
            length = (end - start).length
            if length <= 1e-9:
                continue
            segments.append((total_length, total_length + length, start, end))
            total_length += length

    if not segments:
        return [], 0.0

    if scene.curve_direction_arrow_distribution == "COUNT":
        count = min(max(scene.curve_direction_arrow_count, 1), MAX_ARROWS)
        distances = [total_length * (i + 0.5) / count for i in range(count)]
    else:
        spacing = max(scene.curve_direction_arrow_spacing, 1e-5)
        distances = []
        distance = spacing * 0.5
        while distance < total_length and len(distances) < MAX_ARROWS:
            distances.append(distance)
            distance += spacing
        if not distances:
            distances = [total_length * 0.5]

    segment_starts = [segment[0] for segment in segments]
    samples = []

    for distance in distances:
        index = bisect.bisect_right(segment_starts, distance) - 1
        index = min(max(index, 0), len(segments) - 1)
        start_distance, end_distance, point_a, point_b = segments[index]
        span = end_distance - start_distance
        factor = 0.0 if span <= 0.0 else (distance - start_distance) / span
        factor = min(max(factor, 0.0), 1.0)
        point = point_a.lerp(point_b, factor)
        samples.append((point, (point_b - point_a).normalized()))

    return samples, total_length


def up_vector(scene, curve_obj):
    axis = scene.curve_direction_arrow_up_axis
    if axis == "CURVE_UP":
        return (
            curve_obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, 1.0))
        ).normalized()
    return UP_AXIS_VECTORS.get(axis, UP_AXIS_VECTORS["WORLD_Z"]).copy()


def arrow_material(color):
    material = bpy.data.materials.get(ARROW_MATERIAL)
    if material is None:
        material = bpy.data.materials.new(ARROW_MATERIAL)
        material.use_nodes = True

    rgba = (color[0], color[1], color[2], 1.0)
    material.diffuse_color = rgba

    if material.use_nodes and material.node_tree:
        for node in material.node_tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            base_color = node.inputs.get("Base Color")
            if base_color is not None:
                base_color.default_value = rgba
            roughness = node.inputs.get("Roughness")
            if roughness is not None:
                roughness.default_value = 0.45
            emission = node.inputs.get("Emission Color")
            if emission is None:
                emission = node.inputs.get("Emission")
            if emission is not None:
                emission.default_value = rgba
            emission_strength = node.inputs.get("Emission Strength")
            if emission_strength is not None:
                emission_strength.default_value = 0.15

    return material


def find_arrow_object(scene, curve_obj):
    for obj in scene.objects:
        if obj.get(ARROW_PROP) == curve_obj.name:
            return obj
    return None


def create_arrow_object(context, curve_obj, mesh):
    scene = context.scene
    arrow = None
    if scene.curve_direction_arrow_replace_existing:
        arrow = find_arrow_object(scene, curve_obj)

    if arrow is not None:
        old_mesh = arrow.data
        arrow.data = mesh
        if old_mesh is not None and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
    else:
        arrow = bpy.data.objects.new(f"{curve_obj.name}_DirectionArrows", mesh)
        collection = context.collection or context.scene.collection
        collection.objects.link(arrow)
        arrow[ARROW_PROP] = curve_obj.name

    arrow.show_in_front = scene.curve_direction_arrow_show_in_front

    if scene.curve_direction_arrow_parent_to_curve:
        arrow.parent = curve_obj
        arrow.matrix_parent_inverse = curve_obj.matrix_world.inverted()
    else:
        arrow.parent = None
        arrow.matrix_parent_inverse = Matrix.Identity(4)

    arrow.matrix_basis = Matrix.Identity(4)
    return arrow


def create_arrows_for_curve(context, curve_obj):
    scene = context.scene

    polylines = curve_polylines(curve_obj, context)
    samples, total_length = sample_curve(polylines, scene)
    if not samples:
        return None, 0

    if scene.curve_direction_arrow_size_mode == "RELATIVE":
        arrow_size = total_length * scene.curve_direction_arrow_size_percent * 0.01
    else:
        arrow_size = scene.curve_direction_arrow_size
    arrow_size = max(arrow_size, 1e-5)

    if scene.curve_direction_arrow_style == "FLAT":
        base_verts, base_faces = build_flat_arrow_geometry()
    else:
        base_verts, base_faces = build_solid_arrow_geometry()

    up = up_vector(scene, curve_obj)
    offset = scene.curve_direction_arrow_offset

    verts = []
    faces = []
    for point, tangent in samples:
        rotation, local_up = arrow_frame(tangent, up)
        origin = point + local_up * offset
        matrix = Matrix.Translation(origin) @ rotation @ Matrix.Scale(arrow_size, 4)

        start = len(verts)
        verts.extend(tuple(matrix @ Vector(vertex)) for vertex in base_verts)
        faces.extend(tuple(start + index for index in face) for face in base_faces)

    mesh = bpy.data.meshes.new(f"{curve_obj.name}_DirectionArrowsMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    mesh.update()
    mesh.materials.append(arrow_material(scene.curve_direction_arrow_color))

    arrow = create_arrow_object(context, curve_obj, mesh)
    return arrow, len(samples)


class OBJECT_OT_create_curve_direction_arrows(bpy.types.Operator):
    bl_idname = "object.create_curve_direction_arrows"
    bl_label = "Create Direction Arrows"
    bl_description = "Generate arrow meshes along the selected curves, pointing in the curve direction"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and any(
            obj.type == "CURVE" for obj in context.selected_objects
        )

    def execute(self, context):
        curves = [obj for obj in context.selected_objects if obj.type == "CURVE"]
        if not curves:
            self.report({"ERROR"}, "Select one or more curve objects first.")
            return {"CANCELLED"}

        created = 0
        total_arrows = 0
        failed = []

        for curve_obj in curves:
            try:
                arrow, count = create_arrows_for_curve(context, curve_obj)
            except Exception as exc:
                failed.append(f"{curve_obj.name}: {exc}")
                continue

            if arrow is None:
                failed.append(f"{curve_obj.name}: no usable curve length")
            else:
                created += 1
                total_arrows += count

        if created:
            self.report(
                {"INFO"},
                f"Created {total_arrows} arrow(s) on {created} curve(s).",
            )

        if failed:
            self.report({"WARNING"}, "Skipped: " + "; ".join(failed))
            return {"FINISHED"} if created else {"CANCELLED"}

        return {"FINISHED"}


class OBJECT_OT_clear_curve_direction_arrows(bpy.types.Operator):
    bl_idname = "object.clear_curve_direction_arrows"
    bl_label = "Clear Direction Arrows"
    bl_description = "Delete generated arrow objects for the selected curves, or for all curves when nothing is selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        selected_names = {
            obj.name for obj in context.selected_objects if obj.type == "CURVE"
        }

        removed = 0
        for obj in list(scene.objects):
            if ARROW_PROP not in obj:
                continue
            if selected_names and obj.get(ARROW_PROP) not in selected_names:
                continue

            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            removed += 1

        if removed:
            self.report({"INFO"}, f"Removed {removed} arrow object(s).")
        else:
            self.report({"INFO"}, "No generated arrow objects found.")

        return {"FINISHED"}


class VIEW3D_PT_curve_direction_arrows(bpy.types.Panel):
    bl_label = "Curve Direction Arrows"
    bl_idname = "VIEW3D_PT_curve_direction_arrows"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "curve_direction_arrow_style")
        layout.prop(scene, "curve_direction_arrow_distribution")

        if scene.curve_direction_arrow_distribution == "COUNT":
            layout.prop(scene, "curve_direction_arrow_count")
        else:
            layout.prop(scene, "curve_direction_arrow_spacing")

        layout.prop(scene, "curve_direction_arrow_size_mode")
        if scene.curve_direction_arrow_size_mode == "RELATIVE":
            layout.prop(scene, "curve_direction_arrow_size_percent")
        else:
            layout.prop(scene, "curve_direction_arrow_size")

        layout.prop(scene, "curve_direction_arrow_offset")
        layout.prop(scene, "curve_direction_arrow_up_axis")
        layout.prop(scene, "curve_direction_arrow_color")

        layout.separator()
        layout.prop(scene, "curve_direction_arrow_show_in_front")
        layout.prop(scene, "curve_direction_arrow_parent_to_curve")
        layout.prop(scene, "curve_direction_arrow_replace_existing")

        layout.separator()
        row = layout.row()
        row.scale_y = 1.2
        row.operator("object.create_curve_direction_arrows", icon="CURVE_DATA")

        curve_count = sum(1 for obj in context.selected_objects if obj.type == "CURVE")
        if curve_count:
            layout.label(text=f"Selected curves: {curve_count}", icon="CURVE_BEZCURVE")
        else:
            layout.label(text="Select one or more curves first.", icon="INFO")

        layout.operator("object.clear_curve_direction_arrows", icon="X")


classes = (
    OBJECT_OT_create_curve_direction_arrows,
    OBJECT_OT_clear_curve_direction_arrows,
    VIEW3D_PT_curve_direction_arrows,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    scene = bpy.types.Scene
    scene.curve_direction_arrow_style = bpy.props.EnumProperty(
        name="Style",
        description="How each arrow is built",
        items=STYLE_ITEMS,
        default="SOLID",
    )
    scene.curve_direction_arrow_distribution = bpy.props.EnumProperty(
        name="Distribution",
        description="How arrow positions are chosen along each curve",
        items=DISTRIBUTION_ITEMS,
        default="COUNT",
    )
    scene.curve_direction_arrow_count = bpy.props.IntProperty(
        name="Count",
        description="Number of arrows per curve object",
        default=8,
        min=1,
        max=MAX_ARROWS,
    )
    scene.curve_direction_arrow_spacing = bpy.props.FloatProperty(
        name="Spacing",
        description="Arc length between arrows",
        default=0.5,
        min=1e-5,
        soft_max=100.0,
        unit="LENGTH",
    )
    scene.curve_direction_arrow_size_mode = bpy.props.EnumProperty(
        name="Size Mode",
        description="Whether arrow length is absolute or relative to the curve length",
        items=SIZE_MODE_ITEMS,
        default="RELATIVE",
    )
    scene.curve_direction_arrow_size_percent = bpy.props.FloatProperty(
        name="Size (%)",
        description="Arrow length as a percentage of the curve length",
        default=3.0,
        min=0.01,
        max=100.0,
    )
    scene.curve_direction_arrow_size = bpy.props.FloatProperty(
        name="Size",
        description="Arrow length in Blender units",
        default=0.2,
        min=1e-5,
        soft_max=10.0,
        unit="LENGTH",
    )
    scene.curve_direction_arrow_offset = bpy.props.FloatProperty(
        name="Offset",
        description="Distance to lift arrows along the up axis, useful to keep them off the curve surface",
        default=0.0,
        soft_min=-10.0,
        soft_max=10.0,
        unit="LENGTH",
    )
    scene.curve_direction_arrow_up_axis = bpy.props.EnumProperty(
        name="Up Axis",
        description="Axis used to orient the arrow's up direction",
        items=UP_AXIS_ITEMS,
        default="WORLD_Z",
    )
    scene.curve_direction_arrow_color = bpy.props.FloatVectorProperty(
        name="Color",
        description="Viewport and render color of the generated arrows",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 0.45, 0.05),
    )
    scene.curve_direction_arrow_show_in_front = bpy.props.BoolProperty(
        name="Show In Front",
        description="Draw generated arrows in front of other geometry",
        default=True,
    )
    scene.curve_direction_arrow_parent_to_curve = bpy.props.BoolProperty(
        name="Follow Curve",
        description="Parent generated arrows to their curve so they move together",
        default=True,
    )
    scene.curve_direction_arrow_replace_existing = bpy.props.BoolProperty(
        name="Update Existing",
        description="Replace the previous arrow object generated for the same curve",
        default=True,
    )


def unregister():
    scene = bpy.types.Scene
    del scene.curve_direction_arrow_replace_existing
    del scene.curve_direction_arrow_parent_to_curve
    del scene.curve_direction_arrow_show_in_front
    del scene.curve_direction_arrow_color
    del scene.curve_direction_arrow_up_axis
    del scene.curve_direction_arrow_offset
    del scene.curve_direction_arrow_size
    del scene.curve_direction_arrow_size_percent
    del scene.curve_direction_arrow_size_mode
    del scene.curve_direction_arrow_spacing
    del scene.curve_direction_arrow_count
    del scene.curve_direction_arrow_distribution
    del scene.curve_direction_arrow_style

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
