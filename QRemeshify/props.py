from bpy.types import PropertyGroup
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty


class QWPropertyGroup(PropertyGroup):
    debug: BoolProperty(
        name="Debug Mode",
        description="Show meshes from intermediate steps",
        default=False,
    )
    useCache: BoolProperty(
        name="Use Cache",
        description=(
            "Reuses previously calculated features and only runs quadrangulate step. "
            "Must run all steps at least once before enabling this.\n"
            "May be out of sync if the mesh has been modified"
        ),
        default=False,
    )
    enableRemesh: BoolProperty(
        name="Preprocess",
        description="Decimates, triangulates, and tries to fix common geometry issues",
        default=True,
    )
    enableSmoothing: BoolProperty(
        name="Smoothing",
        description="Performs QuadWild smoothing after quadrangulation",
        default=True,
    )
    enableFlowCleanup: BoolProperty(
        name="Straighten Flow",
        description=(
            "Relax regular quad-grid vertices tangentially and project them back to the source surface. "
            "Helps reduce unnecessary tilted or wavy edge flow"
        ),
        default=True,
    )
    flowCleanupStrength: FloatProperty(
        name="Straighten Strength",
        description="How strongly to regularize skewed quad flow",
        min=0.0,
        max=1.0,
        default=0.35,
        precision=2,
        subtype="FACTOR",
    )
    flowCleanupIterations: IntProperty(
        name="Straighten Passes",
        description="Number of topology regularization passes",
        min=1,
        max=20,
        default=4,
    )
    enableTipCleanup: BoolProperty(
        name="Pointed Tip Cleanup",
        description=(
            "Replace strongly pinched terminal caps such as fingertips, horns and spikes "
            "with one center pole and a clean radial first ring"
        ),
        default=True,
    )
    tipCleanupAngle: FloatProperty(
        name="Tip Detection Angle",
        description="Minimum bend around a terminal cap before it is converted to a center pole",
        min=15.0,
        max=85.0,
        default=48.0,
        precision=1,
    )
    enableSharp: BoolProperty(
        name="Sharp Detection",
        description="Detect sharp features from marked sharp edges, seams, material boundaries, face sets, and angle threshold",
        default=True,
    )
    sharpAngle: FloatProperty(
        name="Angle Threshold",
        description="Angle threshold for sharp edges",
        min=0,
        soft_min=0.1,
        max=180,
        soft_max=179.9,
        default=35,
        precision=1,
        step=10,
        subtype="UNSIGNED",
    )
    equalSides: BoolProperty(
        name="Equal Left / Right",
        description="Force exact bilateral topology by processing one side and mirroring it across local X",
        default=False,
    )
    symmetryX: BoolProperty(name="X", description="Enable symmetry in local X-axis", default=False)
    symmetryY: BoolProperty(name="Y", description="Enable symmetry in local Y-axis", default=False)
    symmetryZ: BoolProperty(name="Z", description="Enable symmetry in local Z-axis", default=False)


class QRPropertyGroup(PropertyGroup):
    scaleFact: FloatProperty(
        name="Scale Factor",
        description="Values > 1 for larger quads, < 1 to preserve more detail",
        min=0.01,
        max=10,
        default=1,
        subtype="FACTOR",
    )

    fixedChartClusters: IntProperty(
        name="Fixed Chart Clusters",
        description="Fixed chart clusters",
        min=0,
        default=0,
    )

    alpha: FloatProperty(
        name="Alpha",
        description="Blends between isometry (alpha) and regularity (1-alpha)",
        default=0.005,
        min=0.0,
        max=0.999,
        precision=3,
        step=0.5,
        subtype="FACTOR",
    )

    ilpMethod: EnumProperty(
        name="ILP Method",
        description="ILP method for solving the ILP problem",
        items=[
            ("LEASTSQUARES", "Least Squares", "Use least squares ILP method", 1),
            ("ABS", "Absolute", "Use absolute ILP method", 2),
        ],
        default="LEASTSQUARES",
    )

    timeLimit: IntProperty(
        name="Time Limit",
        description="Time limit for optimization in seconds",
        default=200,
        min=1,
    )

    gapLimit: FloatProperty(
        name="Gap Limit",
        description="Optimization stops when gap value reaches this limit",
        default=0.0,
        min=0.0,
    )

    minimumGap: FloatProperty(
        name="Minimum Gap",
        description="Optimization must reach at least this gap value",
        default=0.4,
        min=0.0,
    )

    isometry: BoolProperty(name="Isometry", description="Enable isometry", default=True)
    regularityQuadrilaterals: BoolProperty(
        name="Regularity Quadrilaterals",
        description="Enable regularity for quadrilaterals",
        default=True,
    )
    regularityNonQuadrilaterals: BoolProperty(
        name="Regularity Non-Quadrilaterals",
        description="Enable regularity for non-quadrilaterals",
        default=True,
    )
    regularityNonQuadrilateralsWeight: FloatProperty(
        name="Regularity Non-Quadrilaterals Weight",
        description="Weight for regularity of non-quadrilaterals",
        default=0.9,
        min=0.0,
        max=1.0,
    )
    alignSingularities: BoolProperty(
        name="Align Singularities",
        description="Enable singularity alignment",
        default=True,
    )
    alignSingularitiesWeight: FloatProperty(
        name="Singularity Alignment Weight",
        description="Weight for singularity alignment",
        default=0.1,
        min=0.0,
        max=1.0,
    )
    repeatLosingConstraintsIterations: BoolProperty(
        name="Repeat Losing Constraints Iterations",
        description="Repeat losing constraints for iterations",
        default=True,
    )
    repeatLosingConstraintsQuads: BoolProperty(
        name="Repeat Losing Constraints Quadrilaterals",
        description="Repeat losing constraints for quadrilaterals",
        default=False,
    )
    repeatLosingConstraintsNonQuads: BoolProperty(
        name="Repeat Losing Constraints Non-Quadrilaterals",
        description="Repeat losing constraints for non-quadrilaterals",
        default=False,
    )
    repeatLosingConstraintsAlign: BoolProperty(
        name="Repeat Losing Constraints Alignment",
        description="Repeat losing constraints for alignment",
        default=True,
    )
    hardParityConstraint: BoolProperty(
        name="Hard Parity Constraint",
        description="Use hard parity constraint",
        default=True,
    )
    flowConfig: EnumProperty(
        name="Flow Config",
        description="Flow config to use",
        items=[
            ("SIMPLE", "Simple", "", 1),
            ("HALF", "Half", "", 2),
        ],
        default="SIMPLE",
    )
    satsumaConfig: EnumProperty(
        name="Satsuma Config",
        description="Satsuma config to use",
        items=[
            ("DEFAULT", "Default", "", 1),
            ("MST", "Approx-MST", "", 2),
            ("ROUND2EVEN", "Approx-Round2Even", "", 3),
            ("SYMMDC", "Approx-Symmdc", "", 4),
            ("EDGETHRU", "Edgethru", "", 5),
            ("LEMON", "Lemon", "", 6),
            ("NODETHRU", "Nodethru", "", 7),
        ],
        default="DEFAULT",
    )
    callbackTimeLimit: FloatVectorProperty(
        name="Callback Time Limit",
        description="Callback time limit",
        size=8,
        default=[3.00, 5.000, 10.0, 20.0, 30.0, 60.0, 90.0, 120.0],
    )
    callbackGapLimit: FloatVectorProperty(
        name="Callback Gap Limit",
        description="Callback gap limit",
        size=8,
        precision=3,
        default=[0.005, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.3],
    )
