import bmesh


def _adaptive_epsilon(bm: bmesh.types.BMesh) -> float:
    """Scale-aware tolerance for symmetry cuts.

    The old fixed 0.0001 value was too large for tiny meshes and too small for
    very large meshes. This keeps the tolerance proportional to the object.
    """
    if not bm.verts:
        return 1.0e-7

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    diagonal = ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2) ** 0.5
    return max(diagonal * 1.0e-7, 1.0e-8)


def _all_geom(bm: bmesh.types.BMesh):
    return list(bm.verts) + list(bm.edges) + list(bm.faces)


def _snap_axis(bm: bmesh.types.BMesh, axis: int, epsilon: float) -> None:
    """Snap seam vertices to the symmetry plane exactly."""
    threshold = epsilon * 4.0
    for vert in bm.verts:
        if abs(vert.co[axis]) <= threshold:
            vert.co[axis] = 0.0


def bisect_on_axes(
    bm: bmesh.types.BMesh,
    xaxis: bool,
    yaxis: bool,
    zaxis: bool,
    epsilon: float | None = None,
):
    """Bisect once for each requested axis and keep the positive side.

    Seam vertices are snapped exactly to zero so the final Mirror modifier can
    merge them without tiny cracks or a visibly crooked center line.
    """
    epsilon = _adaptive_epsilon(bm) if epsilon is None else max(float(epsilon), 1.0e-12)

    axes = (
        (xaxis, (1.0, 0.0, 0.0), 0),
        (yaxis, (0.0, 1.0, 0.0), 1),
        (zaxis, (0.0, 0.0, 1.0), 2),
    )

    for enabled, plane_normal, axis_index in axes:
        if not enabled:
            continue

        bmesh.ops.bisect_plane(
            bm,
            geom=_all_geom(bm),
            dist=epsilon,
            plane_co=(0.0, 0.0, 0.0),
            plane_no=plane_normal,
            use_snap_center=True,
            clear_outer=False,
            clear_inner=True,
        )
        _snap_axis(bm, axis_index, epsilon)
        bm.normal_update()
