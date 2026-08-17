# Changelog

## 1.2.1 - Pointed tip topology

- Updated Blender add-on/extension metadata and support links to the TamKungZ_ fork repository.
- Added **Pointed Tip Cleanup** for fingertips, horns, spikes, and other strongly tapered ends.
- Strongly convex terminal 3/4-sided caps are converted into **one center pole** with the surrounding ring left intact, producing a radial fan instead of several pinched/skewed quads fighting at the tip.
- Tip detection is intentionally conservative and requires a strong bend around the cap to avoid collapsing ordinary curved surfaces.
- Added an advanced **Tip Detection Angle** control (default 48 degrees).
- Tip center is reprojected to the original evaluated source surface when available, preserving the original silhouette better.

## 1.2.0 - ReQRemeshify fork

- Added **Straighten Flow** post-process to reduce unnecessary tilted/wavy quad rows while reprojecting to the source surface.
- Added a prominent **Equal Left / Right** checkbox for one-click bilateral X symmetry.
- Symmetry cuts now use scale-aware tolerances and snap seam vertices exactly to the center plane.
- Fixed stale BMesh face indices after triangulation so `.sharp` feature references match exported OBJ faces.
- Switched triangulation to `BEAUTY` to reduce diagonal-direction bias before QuadWild field generation.
- Symmetry axes now remain object-local on rotated objects instead of effectively becoming world axes.
- Preserves material slots on the remeshed object.
- More robust registration/unregistration and native-library error reporting.
- Python add-on compatibility target changed to Blender 4.0+; extension-manifest package remains 4.2+ as required by Blender's extension format.
