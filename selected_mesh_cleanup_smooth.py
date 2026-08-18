bl_info = {
    "name": "Selected Mesh Cleanup Smooth",
    "author": "Cursor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Item > Mesh Cleanup Smooth",
    "description": "Merge vertices, clear custom normals, and add auto smooth shading for selected mesh objects.",
    "category": "Object",
}

import math

import bmesh
import bpy


def selected_mesh_objects(context):
    return [obj for obj in context.selected_objects if obj.type == "MESH"]


def merge_mesh_vertices(mesh, merge_distance):
    before_count = len(mesh.vertices)
    bm = bmesh.new()

    try:
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_distance)
        bm.to_mesh(mesh)
    finally:
        bm.free()

    mesh.update()
    return before_count - len(mesh.vertices)


def set_single_active_selection(context, obj):
    for scene_obj in context.view_layer.objects:
        scene_obj.select_set(False)

    obj.select_set(True)
    context.view_layer.objects.active = obj


def clear_custom_normals(context, obj):
    mesh = obj.data
    if not getattr(mesh, "has_custom_normals", False):
        return False

    set_single_active_selection(context, obj)

    try:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    except RuntimeError:
        return False

    mesh.update()
    return True


def shade_smooth_mesh(mesh):
    for polygon in mesh.polygons:
        polygon.use_smooth = True


def apply_legacy_auto_smooth(mesh, angle):
    if not hasattr(mesh, "use_auto_smooth"):
        return False

    mesh.use_auto_smooth = True
    mesh.auto_smooth_angle = angle
    return True


def apply_modifier_auto_smooth(context, objects, angle):
    if not objects:
        return False

    set_single_active_selection(context, objects[0])
    for obj in objects[1:]:
        obj.select_set(True)

    try:
        bpy.ops.object.shade_auto_smooth(angle=angle)
    except (AttributeError, RuntimeError):
        return False

    return True


def restore_selection(context, active_object, selected_objects):
    for obj in context.view_layer.objects:
        obj.select_set(False)

    for obj in selected_objects:
        try:
            obj.select_set(True)
        except ReferenceError:
            pass

    try:
        context.view_layer.objects.active = active_object
    except (ReferenceError, TypeError):
        context.view_layer.objects.active = None


class OBJECT_OT_cleanup_selected_meshes_smooth(bpy.types.Operator):
    bl_idname = "object.cleanup_selected_meshes_smooth"
    bl_label = "Cleanup And Auto Smooth"
    bl_description = "Merge vertices, clear custom normals, and add auto smooth shading for all selected mesh objects"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        mesh_objects = selected_mesh_objects(context)

        if not mesh_objects:
            self.report({"ERROR"}, "Select at least one mesh object.")
            return {"CANCELLED"}

        active_object = context.view_layer.objects.active
        selected_objects = list(context.selected_objects)
        previous_mode = active_object.mode if active_object else "OBJECT"

        if active_object and previous_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        merge_distance = context.scene.mesh_cleanup_smooth_merge_distance
        auto_smooth_angle = context.scene.mesh_cleanup_smooth_angle
        processed_meshes = set()
        total_merged = 0
        cleared_normals = 0
        legacy_auto_smooth_count = 0
        needs_modifier_auto_smooth = []

        try:
            for obj in mesh_objects:
                mesh_key = obj.data.as_pointer()
                if mesh_key not in processed_meshes:
                    total_merged += merge_mesh_vertices(obj.data, merge_distance)
                    cleared_normals += int(clear_custom_normals(context, obj))
                    shade_smooth_mesh(obj.data)

                    if apply_legacy_auto_smooth(obj.data, auto_smooth_angle):
                        legacy_auto_smooth_count += 1
                    else:
                        needs_modifier_auto_smooth.append(obj)

                    processed_meshes.add(mesh_key)
                elif not hasattr(obj.data, "use_auto_smooth"):
                    needs_modifier_auto_smooth.append(obj)

            modifier_auto_smooth_applied = apply_modifier_auto_smooth(
                context,
                needs_modifier_auto_smooth,
                auto_smooth_angle,
            )
        finally:
            restore_selection(context, active_object, selected_objects)
            if active_object and previous_mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode=previous_mode)
                except RuntimeError:
                    pass

        if needs_modifier_auto_smooth and not modifier_auto_smooth_applied:
            self.report(
                {"WARNING"},
                "Cleanup finished, but auto smooth modifier could not be added in this Blender version.",
            )
        else:
            self.report(
                {"INFO"},
                (
                    f"Processed {len(mesh_objects)} mesh object(s), "
                    f"merged {total_merged} vertex/vertices, "
                    f"cleared normals on {cleared_normals} mesh(es), "
                    f"auto smooth set on {legacy_auto_smooth_count + len(needs_modifier_auto_smooth)} mesh/object(s)."
                ),
            )

        return {"FINISHED"}


class VIEW3D_PT_selected_mesh_cleanup_smooth(bpy.types.Panel):
    bl_label = "Mesh Cleanup Smooth"
    bl_idname = "VIEW3D_PT_selected_mesh_cleanup_smooth"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Item"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mesh_count = len(selected_mesh_objects(context))

        layout.prop(scene, "mesh_cleanup_smooth_merge_distance")
        layout.prop(scene, "mesh_cleanup_smooth_angle")

        row = layout.row()
        row.enabled = mesh_count > 0
        row.operator("object.cleanup_selected_meshes_smooth", icon="MOD_SMOOTH")

        if mesh_count == 0:
            layout.label(text="Select one or more mesh objects.", icon="INFO")
        else:
            layout.label(text=f"Selected mesh objects: {mesh_count}", icon="MESH_DATA")


classes = (
    OBJECT_OT_cleanup_selected_meshes_smooth,
    VIEW3D_PT_selected_mesh_cleanup_smooth,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.mesh_cleanup_smooth_merge_distance = bpy.props.FloatProperty(
        name="Merge Distance",
        description="Distance used for merging duplicate or nearby vertices",
        default=0.0001,
        min=0.0,
        precision=6,
        subtype="DISTANCE",
    )
    bpy.types.Scene.mesh_cleanup_smooth_angle = bpy.props.FloatProperty(
        name="Auto Smooth Angle",
        description="Maximum angle used by auto smooth shading",
        default=math.radians(30.0),
        min=0.0,
        max=math.pi,
        subtype="ANGLE",
    )


def unregister():
    del bpy.types.Scene.mesh_cleanup_smooth_angle
    del bpy.types.Scene.mesh_cleanup_smooth_merge_distance

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
