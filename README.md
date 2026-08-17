# ReQRemeshify / QRemeshify 1.2.0

A Blender quad-remeshing add-on based on **QuadWild with Bi-MDF solver**, forked from QRemeshify and updated for cleaner topology flow and Blender 4.x.

Based on:
- https://github.com/ksami/QRemeshify
- https://github.com/cgg-bern/quadwild-bimdf
- https://github.com/nicopietroni/quadwild

## What changed in this fork

### Cleaner / less tilted edge flow

The fork fixes a feature-indexing bug in the old export pipeline: after BMesh triangulation, face indices could be stale while `.sharp` features were exported using those indices. That could attach a requested sharp feature to the wrong exported triangle and distort QuadWild's field direction.

It also adds **Straighten Flow**, a conservative post-process that:

- only relaxes regular valence-4 quad-grid vertices;
- keeps boundaries, singularities, non-quad regions and sharp regions fixed;
- moves vertices tangentially rather than doing ordinary shrink-heavy smoothing;
- reprojects the result to the original evaluated surface with a BVH.

Default settings are intentionally mild:

- Strength: `0.35`
- Passes: `4`

For hard-surface meshes, try `0.45-0.60` and `4-8` passes. For organic/high-detail surfaces, start around `0.20-0.35`.

### Equal Left / Right

There is now a prominent **Equal Left / Right** checkbox. It enables exact local-X bilateral symmetry with one click.

The symmetry pipeline was also changed to:

- use a scale-aware bisect tolerance instead of a fixed `0.0001`;
- snap the center seam exactly to `0`;
- keep symmetry axes object-local on rotated objects;
- enable Mirror clipping + merge with a very small scale-aware threshold.

The original X/Y/Z symmetry controls remain available for additional axes.

### Better remesh preprocessing

- BMesh vertex/edge/face indices are refreshed before OBJ and `.sharp` export.
- Sharp-edge face/edge references now follow exported face-loop order.
- Triangulation uses Blender's `BEAUTY` method instead of always preferring the shortest diagonal, reducing directional bias before field generation.

## Blender compatibility

- **Blender 4.0+**: supported by the Python add-on (`bl_info`). Install as a normal/legacy add-on on Blender 4.0 and 4.1.
- **Blender 4.2+**: can also be packaged/installed as a Blender Extension using the included `blender_manifest.toml`.

The Extension manifest remains `blender_version_min = "4.2.0"` because Blender's Extension format itself requires 4.2 or newer.

## Native QuadWild libraries

This repository/archive must contain the platform-native QuadWild binaries in `QRemeshify/lib/`:

- Windows: `lib_quadwild.dll`, `lib_quadpatches.dll`
- Linux: `liblib_quadwild.so`, `liblib_quadpatches.so`
- macOS: `liblib_quadwild.dylib`, `liblib_quadpatches.dylib`

The uploaded fork source did **not** contain these binaries, so this source ZIP cannot execute QuadWild until the corresponding compiled libraries are added. The add-on now reports this clearly instead of failing with a raw `ctypes` loader error.

## Installation

### Blender 4.0 / 4.1

Install the ZIP as a normal add-on from Blender Preferences, then enable **QRemeshify**.

### Blender 4.2+

You may install the add-on normally, or build/install it as a Blender Extension using the included manifest.

## Basic usage

1. Select one mesh object. If multiple objects are selected, the active object is used.
2. Open **3D View > N Panel > QRemeshify**.
3. Set **Density**.
4. Keep **Straighten Flow** enabled if you want cleaner, less wavy/tilted quad rows.
5. Enable **Equal Left / Right** for exact bilateral X symmetry.
6. Use **Extra Symmetry** if Y/Z symmetry is also needed.
7. Click **Remesh**.

## Main settings

| Setting | Purpose |
| --- | --- |
| Preprocess | QuadWild preprocessing before field tracing |
| Smoothing | QuadWild's final smoothing |
| Straighten Flow | Regularizes unnecessary skew after quadrangulation and reprojects to the source surface |
| Sharp Detect | Uses angle, marked sharp, seams, material boundaries and sculpt face-set boundaries as flow guides |
| Equal Left / Right | One-click exact local-X bilateral symmetry |
| Extra Symmetry X/Y/Z | Additional symmetry axes |
| Density | Quad size / detail control |

## Notes

- Save the `.blend` before a heavy remesh.
- Keep object origin centered on the intended symmetry plane.
- If Straighten Flow removes too much character from an organic surface, lower its Strength or Passes.
- Sharp/seam edges are still the best way to intentionally guide edge flow.
- `Use Cache` still assumes the source geometry and intermediate QuadWild files are unchanged.

See `CHANGELOG.md` for the 1.2.0 changes.
