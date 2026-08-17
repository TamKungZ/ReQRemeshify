import math

import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def build_surface_bvh(bm: bmesh.types.BMesh) -> BVHTree:
    """Build a projection surface before the remesh pipeline modifies the mesh."""
    bm.normal_update()
    return BVHTree.FromBMesh(bm)


def _is_locked_vertex(vert: bmesh.types.BMVert, sharp_angle_radians: float) -> bool:
    # Preserve open borders, singular/problem regions, non-quad neighborhoods,
    # and obvious hard-surface features. Cleanup is meant to regularize a grid,
    # not erase intentional topology changes.
    if len(vert.link_edges) != 4 or not vert.link_faces:
        return True
    if any(edge.is_boundary or edge.is_wire for edge in vert.link_edges):
        return True
    if any(len(face.verts) != 4 for face in vert.link_faces):
        return True

    for edge in vert.link_edges:
        if len(edge.link_faces) != 2:
            return True
        if edge.calc_face_angle(0.0) >= sharp_angle_radians:
            return True

    return False


def _average_edge_length(vert: bmesh.types.BMVert) -> float:
    if not vert.link_edges:
        return 0.0
    return sum(edge.calc_length() for edge in vert.link_edges) / len(vert.link_edges)


def regularize_quad_flow(
    mesh,
    surface_bvh: BVHTree | None,
    strength: float = 0.35,
    iterations: int = 4,
    sharp_angle: float = 35.0,
) -> int:
    """Reduce unnecessary quad skew while keeping the result on the source surface.

    Only regular valence-4 quad-grid vertices are relaxed. Movement is tangent
    to the current surface first, then reprojected to the original evaluated
    surface using a BVH. Boundaries, singularities and sharp regions are kept.

    Returns the number of vertex updates performed across all iterations.
    """
    strength = max(0.0, min(float(strength), 1.0))
    iterations = max(0, int(iterations))
    if strength <= 0.0 or iterations <= 0:
        return 0

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.normal_update()

    sharp_angle_radians = math.radians(max(0.0, min(float(sharp_angle), 180.0)))
    total_updates = 0

    try:
        for _ in range(iterations):
            bm.verts.index_update()
            bm.verts.ensure_lookup_table()
            bm.normal_update()

            targets: dict[int, Vector] = {}
            for vert in bm.verts:
                if _is_locked_vertex(vert, sharp_angle_radians):
                    continue

                neighbours = [edge.other_vert(vert) for edge in vert.link_edges]
                if len(neighbours) != 4:
                    continue

                centroid = sum((other.co for other in neighbours), Vector()) / 4.0
                normal = vert.normal.normalized() if vert.normal.length_squared > 1.0e-20 else Vector((0.0, 0.0, 1.0))
                delta = centroid - vert.co

                # Tangential relaxation regularizes the quad grid with far less
                # shrinkage than ordinary Laplacian smoothing.
                tangent_delta = delta - normal * delta.dot(normal)
                if tangent_delta.length_squared <= 1.0e-20:
                    continue

                target = vert.co + tangent_delta * strength

                if surface_bvh is not None:
                    nearest = surface_bvh.find_nearest(target)
                    if nearest is not None:
                        location, _normal, _face_index, distance = nearest
                        if location is None or distance is None:
                            continue
                        # Avoid jumping across a thin shell or to another nearby
                        # disconnected surface. Normal remesh drift is much less
                        # than one local edge length.
                        local_scale = _average_edge_length(vert)
                        if local_scale <= 1.0e-12 or distance <= local_scale:
                            target = location

                targets[vert.index] = target.copy()

            if not targets:
                break

            for index, target in targets.items():
                bm.verts[index].co = target
            total_updates += len(targets)

        bm.normal_update()
        bm.to_mesh(mesh)
        mesh.update()
    finally:
        bm.free()

    return total_updates
