import os

import bpy


def _parse_obj_index(token: str, vertex_count: int) -> int:
    """Parse OBJ v/vt/vn, v//vn, or plain v indices."""
    raw = token.split("/", 1)[0]
    index = int(raw)
    if index > 0:
        return index - 1
    # Negative OBJ indices are relative to the end of the vertex list.
    return vertex_count + index


def import_mesh(mesh_filepath: str) -> bpy.types.Mesh:
    if not os.path.isfile(mesh_filepath):
        raise FileNotFoundError(f"File does not exist at {mesh_filepath}")

    verts = []
    faces = []

    with open(mesh_filepath, "r", encoding="utf-8", errors="replace") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            tokens = line.split()
            element = tokens[0]

            if element == "v" and len(tokens) >= 4:
                verts.append(tuple(float(coord) for coord in tokens[1:4]))
            elif element == "f" and len(tokens) >= 4:
                faces.append(tuple(_parse_obj_index(token, len(verts)) for token in tokens[1:]))

    if not verts:
        raise ValueError(f"OBJ has no vertices: {mesh_filepath}")
    if not faces:
        raise ValueError(f"OBJ has no faces: {mesh_filepath}")

    new_mesh = bpy.data.meshes.new("QRemeshify Mesh")
    new_mesh.from_pydata(verts, [], faces)
    new_mesh.validate(verbose=False, clean_customdata=False)
    new_mesh.update(calc_edges=True)
    return new_mesh
