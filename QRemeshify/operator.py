import math
import os

import bmesh
import bpy
import mathutils

from .lib import Quadwild, QWException
from .util import bisect, cleanup, exporter, importer


class QREMESH_OT_Remesh(bpy.types.Operator):
    """Remesh with QuadWild"""

    bl_idname = "qremeshify.remesh"
    bl_label = "Remesh"
    bl_options = {"REGISTER", "UNDO"}

    @staticmethod
    def _active_symmetry_axes(props):
        # Equal Left / Right is the requested one-click X symmetry. Keep the
        # original X/Y/Z properties for backwards compatibility and extra axes.
        return (
            bool(props.equalSides or props.symmetryX),
            bool(props.symmetryY),
            bool(props.symmetryZ),
        )

    @staticmethod
    def _scale_bmesh_to_world_size(bm, obj):
        """Bake world scale only, while keeping symmetry axes object-local.

        The old implementation baked rotation too, which changed the meaning of
        X/Y/Z symmetry on rotated objects. We preserve rotation for the output
        and only bake scale so remeshing still operates on the visible shape.
        """
        _location, _rotation, scale = obj.matrix_world.decompose()
        matrix = mathutils.Matrix.Diagonal((scale.x, scale.y, scale.z, 1.0))
        bmesh.ops.transform(bm, matrix=matrix, verts=bm.verts)
        bm.normal_update()

    @staticmethod
    def _output_world_matrix(obj):
        location, rotation, _scale = obj.matrix_world.decompose()
        return mathutils.Matrix.LocRotScale(location, rotation, mathutils.Vector((1.0, 1.0, 1.0)))

    def execute(self, ctx):
        props = ctx.scene.quadwild_props
        qr_props = ctx.scene.quadpatches_props
        selected_objs = list(ctx.selected_objects)

        if not selected_objs:
            self.report({"ERROR_INVALID_INPUT"}, "No selected objects")
            return {"CANCELLED"}

        obj = ctx.view_layer.objects.active
        if obj not in selected_objs:
            obj = selected_objs[0]

        if len(selected_objs) > 1:
            self.report({"INFO"}, "Multiple objects selected; remeshing the active object only")

        if obj is None or obj.type != "MESH":
            self.report({"ERROR_INVALID_INPUT"}, "Active object is not a mesh")
            return {"CANCELLED"}

        if len(obj.data.polygons) == 0:
            self.report({"ERROR_INVALID_INPUT"}, "Mesh has 0 faces")
            return {"CANCELLED"}

        symmetry_x, symmetry_y, symmetry_z = self._active_symmetry_axes(props)
        use_symmetry = symmetry_x or symmetry_y or symmetry_z

        mesh_filename = "".join(c if c not in "\\/:*?<>|" else "_" for c in obj.name).strip() or "QRemeshify"
        mesh_filepath = f"{os.path.join(bpy.app.tempdir, mesh_filename)}.obj"
        self.report({"DEBUG"}, f"Remeshing from {mesh_filepath}")

        qw = None
        evaluated_obj = None
        bm = None
        surface_bvh = None

        try:
            # Load native library after validating the input so missing platform
            # binaries produce a useful Blender report instead of a raw OSError.
            qw = Quadwild(mesh_filepath)

            # We need the evaluated source mesh for the normal pipeline, and also
            # for Straighten Flow reprojection when quadrangulation cache is used.
            if not props.useCache or props.enableFlowCleanup or props.enableTipCleanup:
                depsgraph = ctx.evaluated_depsgraph_get()
                evaluated_obj = obj.evaluated_get(depsgraph)
                evaluated_mesh = evaluated_obj.to_mesh()

                bm = bmesh.new()
                bm.from_mesh(evaluated_mesh)
                self._scale_bmesh_to_world_size(bm, obj)

                if props.enableFlowCleanup:
                    surface_bvh = cleanup.build_surface_bvh(bm)

            if not props.useCache:
                if bm is None:
                    raise QWException("Could not build evaluated mesh")

                # Prep an exact half/quarter/eighth for symmetry. The updated
                # bisector uses a scale-aware epsilon and exact center snapping.
                if use_symmetry:
                    bisect.bisect_on_axes(bm, symmetry_x, symmetry_y, symmetry_z)

                # Find edges to mark as sharp before triangulation.
                if props.enableSharp:
                    face_set_data_layer = bm.faces.layers.int.get(".sculpt_face_set")
                    bm.edges.ensure_lookup_table()
                    for edge in bm.edges:
                        face_angle = edge.calc_face_angle(0.0)
                        is_sharp = math.degrees(face_angle) > props.sharpAngle
                        is_material_boundary = (
                            len(edge.link_faces) > 1
                            and edge.link_faces[0].material_index != edge.link_faces[1].material_index
                        )
                        is_face_set_boundary = (
                            face_set_data_layer is not None
                            and len(edge.link_faces) > 1
                            and edge.link_faces[0][face_set_data_layer] != edge.link_faces[1][face_set_data_layer]
                        )

                        if is_sharp or edge.is_boundary or edge.seam or is_material_boundary or is_face_set_boundary:
                            edge.smooth = False

                # QuadWild consumes triangles. BEAUTY avoids a systematic
                # shortest-diagonal bias that can seed tilted field directions.
                bmesh.ops.triangulate(
                    bm,
                    faces=list(bm.faces),
                    quad_method="BEAUTY",
                    ngon_method="BEAUTY",
                )
                bm.normal_update()

                # Exporter now refreshes vertex/edge/face indices so .sharp face
                # IDs remain aligned with the exact OBJ face order.
                exporter.export_mesh(bm, mesh_filepath)

                if props.enableSharp:
                    num_sharp_features = exporter.export_sharp_features(bm, qw.sharp_path, props.sharpAngle)
                    self.report({"DEBUG"}, f"Found {num_sharp_features} sharp edges")

                qw.remeshAndField(
                    remesh=props.enableRemesh,
                    enableSharp=props.enableSharp,
                    sharpAngle=props.sharpAngle,
                )
                if props.debug:
                    new_mesh = importer.import_mesh(qw.remeshed_path)
                    new_obj = bpy.data.objects.new(f"{obj.name} remeshAndField", new_mesh)
                    ctx.collection.objects.link(new_obj)
                    new_obj.hide_set(True)

                qw.trace()
                if props.debug:
                    new_mesh = importer.import_mesh(qw.traced_path)
                    new_obj = bpy.data.objects.new(f"{obj.name} trace", new_mesh)
                    ctx.collection.objects.link(new_obj)
                    new_obj.hide_set(True)

            qw.quadrangulate(
                props.enableSmoothing,
                qr_props.scaleFact,
                qr_props.fixedChartClusters,
                qr_props.alpha,
                qr_props.ilpMethod,
                qr_props.timeLimit,
                qr_props.gapLimit,
                qr_props.minimumGap,
                qr_props.isometry,
                qr_props.regularityQuadrilaterals,
                qr_props.regularityNonQuadrilaterals,
                qr_props.regularityNonQuadrilateralsWeight,
                qr_props.alignSingularities,
                qr_props.alignSingularitiesWeight,
                qr_props.repeatLosingConstraintsIterations,
                qr_props.repeatLosingConstraintsQuads,
                qr_props.repeatLosingConstraintsNonQuads,
                qr_props.repeatLosingConstraintsAlign,
                qr_props.hardParityConstraint,
                qr_props.flowConfig,
                qr_props.satsumaConfig,
                qr_props.callbackTimeLimit,
                qr_props.callbackGapLimit,
            )

            if props.debug and props.enableSmoothing:
                debug_mesh = importer.import_mesh(qw.output_path)
                debug_obj = bpy.data.objects.new(f"{obj.name} quadrangulate", debug_mesh)
                ctx.collection.objects.link(debug_obj)
                debug_obj.hide_set(True)

            final_mesh_path = qw.output_smoothed_path if props.enableSmoothing else qw.output_path
            final_mesh = importer.import_mesh(final_mesh_path)

            if props.enableFlowCleanup:
                updates = cleanup.regularize_quad_flow(
                    final_mesh,
                    surface_bvh,
                    strength=props.flowCleanupStrength,
                    iterations=props.flowCleanupIterations,
                    sharp_angle=props.sharpAngle,
                )
                self.report({"DEBUG"}, f"Straighten Flow adjusted {updates} vertex steps")

            if props.enableTipCleanup:
                tips = cleanup.cleanup_pointed_tips(
                    final_mesh,
                    surface_bvh,
                    angle=props.tipCleanupAngle,
                )
                self.report({"DEBUG"}, f"Pointed Tip Cleanup converted {tips} terminal caps")

            final_obj = bpy.data.objects.new(f"{obj.name} Remeshed", final_mesh)
            ctx.collection.objects.link(final_obj)
            final_obj.matrix_world = self._output_world_matrix(obj)

            # Preserve material slots even though QuadWild does not preserve face
            # material assignment. This keeps the object ready for re-assignment.
            for material in obj.data.materials:
                final_mesh.materials.append(material)

            ctx.view_layer.objects.active = final_obj
            final_obj.select_set(True)

            if use_symmetry:
                mirror_modifier = final_obj.modifiers.new("QRemeshify Symmetry", "MIRROR")
                mirror_modifier.use_axis[0] = symmetry_x
                mirror_modifier.use_axis[1] = symmetry_y
                mirror_modifier.use_axis[2] = symmetry_z
                mirror_modifier.use_clip = True
                mirror_modifier.use_mirror_merge = True

                # The seam is snapped exactly to zero, so this threshold only has
                # to catch floating-point noise. Scale it to the resulting object.
                max_dimension = max(final_obj.dimensions) if max(final_obj.dimensions) > 0 else 1.0
                mirror_modifier.merge_threshold = max(max_dimension * 1.0e-7, 1.0e-6)

            obj.hide_set(True)
            return {"FINISHED"}

        except QWException as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, f"QRemeshify failed: {exc}")
            return {"CANCELLED"}
        finally:
            if bm is not None:
                bm.free()
            if evaluated_obj is not None:
                evaluated_obj.to_mesh_clear()
            if qw is not None:
                del qw
