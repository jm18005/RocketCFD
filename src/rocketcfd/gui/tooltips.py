"""Master list of GUI tooltip strings, kept out of widget-construction code."""
from __future__ import annotations

MESH_SCALE_TOOLTIP = (
    "Uniform multiplier applied on top of the file-unit conversion above, "
    "for meshes that are exported at a nonstandard scale (e.g. a CAD export scaled 1.2x)."
)

LOAD_MODEL_TOOLTIP = (
    "Load a 3D model of the rocket to analyze: triangulated mesh (.stl/.obj/.ply) or "
    "CAD BREP (.step/.stp/.iges/.igs, requires the optional CAD backend)."
)

ROTATE_X_TOOLTIP = "Rotate the loaded model about the X axis (degrees), applied to both the 3D view and the CFD solve."
ROTATE_Y_TOOLTIP = "Rotate the loaded model about the Y axis (degrees), applied to both the 3D view and the CFD solve."
ROTATE_Z_TOOLTIP = "Rotate the loaded model about the Z axis (degrees), applied to both the 3D view and the CFD solve."
BBOX_LABEL_TOOLTIP = "Bounding-box size of the model in its current (rotated/scaled) orientation."

APPLY_ATMOSPHERE_TOOLTIP = (
    "Look up US Standard Atmosphere density and temperature at the altitude entered above "
    "and fill in the density/temperature fields with those values."
)

EXPORT_CSV_TOOLTIP = "Save every case in the results table below to an aerotable CSV file."

IMPORT_RESULTS_TOOLTIP = (
    "Load results from a previous run without re-solving: pick a case root (containing "
    "run_0xx folders) or a single run folder, and matching force/moment data is found and "
    "loaded automatically."
)

RUN_OPENFOAM_TOOLTIP = (
    "Build the OpenFOAM case(s) and run them: mesh once (blockMesh, surfaceFeatures, "
    "snappyHexMesh, checkMesh), then solve each swept condition with the solver auto-picked "
    "from its Mach number. This can take from minutes to hours depending on mesh size and "
    "iteration count -- check the Log tab for progress."
)

CASE_ROOT_BROWSE_TOOLTIP = "Choose the folder where generated OpenFOAM case files will be written."

SHOW_GEOMETRY_BBOX_TOOLTIP = "Draw a wireframe box around the loaded geometry, labeled with its length/width/height."

SHOW_DOMAIN_BOX_TOOLTIP = (
    "Preview the far-field volume-mesh domain that blockMesh will build (before snappyHexMesh "
    "carves the body out of it) using the upstream/downstream/side/top distances below, plus "
    "the snappyHexMesh seed point, the ground patch, and the symmetry plane (if modeled). "
    "Updates live as those settings change, so you can sanity-check them before running a case."
)

PREVIEW_MESH_TOOLTIP = (
    "Runs blockMesh + snappyHexMesh only (no solving) and shows the real generated surface "
    "cells in the 3D view, so you can check mesh quality/density before committing to a full "
    "run. Reuses the same cache as Run, so this mesh is reused instead of rebuilt if you run "
    "afterward with unchanged settings."
)

SHOW_COORDS_TOOLTIP = "Draw the X/Y/Z coordinate axes anchored at the moment reference point."

SHOW_FLOW_TOOLTIP = "Draw an arrow showing the vehicle's own flow direction at the current AoA/sideslip, anchored at the moment reference point."

SHOW_WIND_TOOLTIP = (
    "Draw the ambient wind-direction arrow and the total (vehicle + wind) relative-flow "
    "arrow, anchored at the moment reference point."
)

GROUND_EFFECT_TOOLTIP = (
    "Add an explicit no-slip wall patch at one face of the mesh domain instead of treating "
    "it as far-field, approximating a stationary ground (e.g. for pad transients). Axis/side "
    "below pick which domain face."
)
GROUND_AXIS_TOOLTIP = "Which world axis is \"down\": the ground patch replaces this axis's min or max domain face."
GROUND_SIDE_TOOLTIP = "Which face of the domain (on the ground axis) becomes the ground patch."

SYMMETRY_PLANE_TOOLTIP = (
    "If the geometry (and beta/sideslip) is symmetric about a plane, mesh only the >= offset "
    "half along the chosen axis and mirror it with a symmetryPlane patch, roughly halving cell "
    "count. Enable both symmetry planes (on two different axes) for a quarter-body mesh."
)
SYMMETRY_AXIS_TOOLTIP = "World axis this symmetry plane cuts along; only the >= offset half is meshed."
SYMMETRY_OFFSET_TOOLTIP = (
    "World coordinate along the chosen axis where the cut is made -- e.g. the geometric "
    "centerline, if you loaded the full (not pre-halved) CAD geometry."
)

UPSTREAM_DISTANCE_TOOLTIP = (
    "How far the mesh domain extends ahead of the body, in multiples of the body's length "
    "(along X). Too small starves the flow of room to develop before reaching the body; "
    "check the mesh domain preview in the 3D view to see the effect."
)

DOWNSTREAM_DISTANCE_TOOLTIP = (
    "How far the mesh domain extends behind the body, in multiples of the body's length. "
    "Usually larger than the upstream distance so the wake has room to develop and decay "
    "before hitting the domain boundary."
)

SIDE_DISTANCE_TOOLTIP = (
    "How far the mesh domain extends to each side of the body (+/-Y, or +Y only if the "
    "symmetry plane is enabled), in multiples of the body's length."
)

TOP_DISTANCE_TOOLTIP = (
    "How far the mesh domain extends above the body (and below it too, unless ground effect "
    "is modeled), in multiples of the body's length."
)

BACKGROUND_CELL_COUNT_TOOLTIP = (
    "Number of background blockMesh cells spanning the body's length, before snappyHexMesh "
    "refines near the surface. Keep this small (a coarse background block) -- the actual "
    "near-surface cell size comes from the surface refinement levels below, not from this."
)

SURFACE_REFINEMENT_MIN_TOOLTIP = (
    "Minimum snappyHexMesh octree refinement level applied near the body surface. Each level "
    "halves the local cell size, so higher = finer."
)

SURFACE_REFINEMENT_MAX_TOOLTIP = (
    "Maximum snappyHexMesh octree refinement level applied right at the body surface (and "
    "along detected feature edges, e.g. fin leading/trailing edges and the nosecone "
    "shoulder). Each level halves the local cell size relative to the background mesh."
)

BOUNDARY_LAYERS_TOOLTIP = "Number of prismatic boundary-layer cells snappyHexMesh grows off the body surface."

LAYER_EXPANSION_TOOLTIP = "Growth ratio between successive boundary-layer cells, moving away from the surface."

FINAL_LAYER_THICKNESS_TOOLTIP = (
    "Thickness of the outermost (largest) boundary-layer cell, as a fraction of the local "
    "background/refined cell size."
)

MESH_QUALITY_GATE_TOOLTIP = (
    "Run checkMesh after meshing and refuse to solve if non-orthogonality/skewness exceed "
    "the limits below. Disable only if you understand the mesh warnings and want to solve "
    "anyway."
)

MAX_NON_ORTHOGONALITY_TOOLTIP = "checkMesh max non-orthogonality (degrees) allowed before the mesh quality gate blocks solving."

MAX_SKEWNESS_TOOLTIP = "checkMesh max internal skewness allowed before the mesh quality gate blocks solving."

MACH_CEILING_TOOLTIP = (
    "Highest Mach number this run is allowed to reach. Below 0.3 uses incompressible "
    "simpleFoam; 0.3-0.8 uses compressible rhoSimpleFoam; 0.8-1.2 (transonic) uses transient "
    "rhoPimpleFoam; above 1.2 (supersonic) uses shock-capturing rhoCentralFoam. Raise this "
    "above the default of 3 only if you understand that automation confidence drops as Mach "
    "increases, and that the tool refuses to run above a hard limit regardless of this setting."
)

TURBULENCE_MODEL_TOOLTIP = "RAS turbulence model the solver uses."

TURBULENCE_INTENSITY_TOOLTIP = (
    "Assumed freestream turbulence intensity (as a fraction, e.g. 0.05 = 5%), used only to "
    "set the initial k/omega/nuTilda field values -- it is not enforced as a boundary condition."
)

MAX_ITERATIONS_TOOLTIP = "Maximum solver iterations (or transient timesteps) per case, regardless of whether the residuals below are met."

RESIDUAL_TOOLTIP = "Solver stops early once all residuals drop below this value."

N_PROCESSORS_TOOLTIP = (
    "Number of MPI processes to decompose each case across. 1 runs the solver directly; "
    ">1 uses decomposePar/mpirun/reconstructPar."
)

USE_CACHE_TOOLTIP = (
    "Skip re-meshing/re-solving a condition that was already run with the same geometry, "
    "mesh, and solver settings; reuses its cached results instead."
)

EXECUTION_MODE_TOOLTIP = "Where OpenFOAM commands actually run: inside a WSL2 distro (Windows), directly on this Linux host, or submitted to TACC."

DISTRO_TOOLTIP = "WSL distro to run OpenFOAM commands in. Leave blank to use your default WSL distro."

BASHRC_TOOLTIP = (
    "Path (inside WSL, or on this host for native Linux) to the OpenFOAM installation's "
    "etc/bashrc, sourced before every command so its environment variables are set. Leave "
    "blank to auto-detect at run time, or click Auto-detect to fill it in now."
)

AUTO_DETECT_BASHRC_TOOLTIP = "Search common OpenFOAM install locations and fill in the bashrc path above with what it finds."

INSTALL_OPENFOAM_TOOLTIP = "Automatically install WSL2/OpenFOAM (Windows) or OpenFOAM (native Linux) if it is not already present."

CASE_ROOT_TOOLTIP = "Folder where generated OpenFOAM case files will be written."

REF_DIMS_OVERRIDE_TOOLTIP = (
    "By default, reference area/length are recomputed from the geometry's frontal area at "
    "the current alpha/beta. Check this to enter fixed values instead (e.g. to match a "
    "published reference area)."
)

MOMENT_REF_X_TOOLTIP = "X coordinate of the point moments (and the flow-direction/coordinate-system overlay) are computed about."
MOMENT_REF_Y_TOOLTIP = "Y coordinate of the point moments (and the flow-direction/coordinate-system overlay) are computed about."
MOMENT_REF_Z_TOOLTIP = "Z coordinate of the point moments (and the flow-direction/coordinate-system overlay) are computed about."
REF_AREA_TOOLTIP = "Reference area for nondimensionalizing force coefficients (Cd, Cl, Cs)."
REF_LENGTH_TOOLTIP = "Reference length for nondimensionalizing moment coefficients (Cm)."

WIND_SPEED_TOOLTIP = "Ambient wind speed, vectorially combined with the vehicle's own velocity into the actual solved boundary condition (and drawn in the 3D view as the wind-direction and total-flow-direction vectors)."
WIND_DIRECTION_TOOLTIP = "Compass-style direction (azimuth) the wind blows toward, measured from +X toward +Y."
WIND_ELEVATION_TOOLTIP = "Elevation the wind blows toward, measured up from horizontal (+X/+Y plane) toward +Z. 0 = purely horizontal wind."

MACH_INPUT_TOOLTIP = "Enter the Mach number field's values as Mach instead of m/s; converted to true velocity per-case using that case's temperature."

ENABLE_ROTATION_TOOLTIP = "Show the manual Rotate X/Y/Z controls below (hidden by default since most models don't need them)."

MOMENT_REF_CENTROID_TOOLTIP = "Lock the moment reference point to the loaded model's centroid, recomputed automatically whenever the geometry changes. Uncheck to enter a custom point."

ALTITUDE_TOOLTIP = "Sets the density and temperature fields below from the US Standard Atmosphere at this altitude; leave blank to set density/temperature directly instead."
MOMENT_REF_BOX_TOOLTIP = "Auto-filled from your model's centroid when a model is loaded. Edit to move the point moments (and the coordinate-system/flow overlays) are computed about."
REF_DIMS_BOX_TOOLTIP = "Used for nondimensionalizing Cd/Cl/Cs/Cm."

ANSYS_IMPORT_TOOLTIP = (
    "Load an ANSYS-exported results CSV (Fluent/CFD-Post report table with mach/alpha/"
    "cd/cl/cm columns) and compare it against the OpenFOAM results currently in the table."
)

BOX_UPLOAD_TOOLTIP = "Upload the aerotable CSV and case logs in the case directory to a UT Box folder, using a Box access token."

VALIDATION_RUN_TOOLTIP = "Run the built-in validation suite (sphere, flat plate, slender cone) through this same OpenFOAM pipeline and compare against reference data."

MESH_PRESET_TOOLTIP = (
    "Coarse/Medium/Fine set the background cell count, surface refinement levels, boundary "
    "layer count, and target y+ together. Choose Custom (set automatically once you edit "
    "any individual value below) to tune them independently."
)

USE_TARGET_Y_PLUS_TOOLTIP = (
    "Size the first boundary-layer cell to hit the target y+ below, estimated from a "
    "flat-plate turbulent skin-friction correlation at the fastest condition in this run "
    "(a conservative single sizing shared by the whole sweep, since the mesh is built once). "
    "Uncheck to size the last layer as a fraction of the local cell size instead (below)."
)

TARGET_Y_PLUS_TOOLTIP = "Target dimensionless wall distance (y+) for the first boundary-layer cell center. ~1 resolves the viscous sublayer; ~30-300 relies on wall functions."

CASE_SELECT_TOOLTIP = "Which solved case's geometry/surface field and convergence history to display."
VIEW_SCALAR_TOOLTIP = "Choose which sampled surface field (or plain geometry) colors the 3D view for the selected case."
PLOT_MODE_TOOLTIP = "Sweep: quantity vs the swept flow variable. Convergence: quantity vs iteration for the selected case. Residuals: solver residual history for the selected case."
PLOT_X_AXIS_TOOLTIP = "Quantity plotted on the X axis (Sweep mode only)."
PLOT_QUANTITY_TOOLTIP = "Quantity plotted on the Y axis."
RESIDUAL_FIELD_TOOLTIP = "Which solver field's residual history to plot (Residuals mode only)."

COLLAPSIBLE_SECTION_TOGGLE_TOOLTIP = "Click to show or hide these optional advanced settings."
