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



def _face_neighbor_faces(face: bmesh.types.BMFace) -> list[bmesh.types.BMFace]:
    neighbours = []
    seen = set()
    for edge in face.edges:
        for linked in edge.link_faces:
            if linked is face:
                continue
            key = id(linked)
            if key not in seen:
                seen.add(key)
                neighbours.append(linked)
    return neighbours


def _tip_cap_score(face: bmesh.types.BMFace, angle_radians: float) -> float | None:
    """Return a conservative score for a small terminal cap face.

    A good cap is surrounded on most/all sides by faces that turn sharply away
    from it, while the neighbouring face centroids sit behind the cap along the
    cap normal. This is intentionally strict: a missed fingertip is preferable
    to collapsing an ordinary patch on the cheek, torso, etc.
    """
    if len(face.verts) not in (3, 4):
        return None
    if any(edge.is_boundary or edge.is_wire or len(edge.link_faces) != 2 for edge in face.edges):
        return None

    neighbours = _face_neighbor_faces(face)
    if len(neighbours) < len(face.edges):
        return None

    center = face.calc_center_median()
    normal = face.normal.normalized() if face.normal.length_squared > 1.0e-20 else None
    if normal is None:
        return None

    neighbour_centers = [other.calc_center_median() for other in neighbours]
    neighbour_center = sum(neighbour_centers, Vector()) / len(neighbour_centers)
    outward = center - neighbour_center
    if outward.length_squared <= 1.0e-20:
        return None
    outward.normalize()

    # Normals can be flipped on imported geometry, so use absolute alignment.
    axial_alignment = abs(normal.dot(outward))
    if axial_alignment < 0.55:
        return None

    angles = []
    for other in neighbours:
        if other.normal.length_squared <= 1.0e-20:
            continue
        dot = max(-1.0, min(1.0, normal.dot(other.normal.normalized())))
        angles.append(math.acos(dot))
    if len(angles) < 3:
        return None

    turned = [a for a in angles if a >= angle_radians]
    # Require most side faces to bend away strongly. This avoids ordinary
    # curved quad patches where all neighbouring normals are nearly parallel.
    required = 3 if len(face.verts) == 4 else 2
    if len(turned) < required:
        return None

    edge_lengths = [edge.calc_length() for edge in face.edges]
    mean_edge = sum(edge_lengths) / len(edge_lengths)
    if mean_edge <= 1.0e-12:
        return None

    # Extremely stretched faces are flow artifacts, not a clean cap candidate.
    if max(edge_lengths) / max(min(edge_lengths), 1.0e-12) > 2.35:
        return None

    axial_depth = abs((center - neighbour_center).dot(normal)) / mean_edge
    if axial_depth < 0.12:
        return None

    mean_turn = sum(angles) / len(angles)
    return axial_alignment * 1.5 + mean_turn + min(axial_depth, 2.0) * 0.35


def _candidate_faces_conflict(a: bmesh.types.BMFace, b: bmesh.types.BMFace) -> bool:
    """Keep cap collapses separated by at least one face ring."""
    a_verts = set(a.verts)
    if any(v in a_verts for v in b.verts):
        return True
    a_neighbours = set(_face_neighbor_faces(a))
    return b in a_neighbours


def cleanup_pointed_tips(
    mesh,
    surface_bvh: BVHTree | None,
    angle: float = 48.0,
    max_tips: int = 32,
) -> int:
    """Turn pinched terminal caps into a single center pole with a radial ring.

    Quad remeshers often finish a fingertip/horn/spike with several skewed quads
    fighting for space. For a strongly convex terminal cap, collapse only the
    cap face to one pole. Its outer edge loop remains intact, naturally making
    a triangle fan / radial first ring around the pole.

    The detector is deliberately conservative and only accepts closed 3/4-sided
    caps whose surrounding faces turn sharply away from the cap.
    """
    max_tips = max(0, int(max_tips))
    if max_tips == 0:
        return 0

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.normal_update()

    angle_radians = math.radians(max(15.0, min(float(angle), 85.0)))
    collapsed = 0

    try:
        scored = []
        for face in bm.faces:
            score = _tip_cap_score(face, angle_radians)
            if score is not None:
                scored.append((score, face))
        scored.sort(key=lambda item: item[0], reverse=True)

        selected: list[bmesh.types.BMFace] = []
        for _score, face in scored:
            if not face.is_valid:
                continue
            if any(_candidate_faces_conflict(face, other) for other in selected if other.is_valid):
                continue
            selected.append(face)
            if len(selected) >= max_tips:
                break

        for face in selected:
            if not face.is_valid or len(face.verts) not in (3, 4):
                continue

            center = face.calc_center_median()
            if surface_bvh is not None:
                nearest = surface_bvh.find_nearest(center)
                if nearest is not None and nearest[0] is not None:
                    center = nearest[0]

            verts = list(face.verts)
            if len(verts) < 3:
                continue

            # Merge exactly the terminal cap into one vertex. The neighbouring
            # ring is untouched, producing the requested single center point
            # with faces radiating around it instead of a pinched quad patch.
            bmesh.ops.pointmerge(bm, verts=verts, merge_co=center)
            collapsed += 1
            bm.normal_update()

        if collapsed:
            # Remove any zero-area leftovers produced by pathological inputs.
            degenerate = [edge for edge in bm.edges if edge.is_valid and edge.calc_length() <= 1.0e-10]
            if degenerate:
                bmesh.ops.dissolve_degenerate(bm, dist=1.0e-10, edges=degenerate)
            bm.normal_update()
            bm.to_mesh(mesh)
            mesh.update()
    finally:
        bm.free()

    return collapsed
