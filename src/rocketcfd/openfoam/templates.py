"""OpenFOAM dictionary/field-file text builders (pure strings, no disk I/O)."""
from __future__ import annotations

import numpy as np

from rocketcfd.gas import R_AIR, SUTHERLAND_MU_REF, SUTHERLAND_S, SUTHERLAND_T_REF
from rocketcfd.openfoam.settings import GroundPlane, MeshSettings, SymmetryPlane, validate_domain_planes

Bounds = tuple[float, float, float, float, float, float]  # xmin xmax ymin ymax zmin zmax


def _header(foam_class: str, obj: str) -> str:
    return (
        "FoamFile\n"
        "{\n"
        "    version     2.0;\n"
        "    format      ascii;\n"
        f"    class       {foam_class};\n"
        f"    object      {obj};\n"
        "}\n"
    )


def _vec(v: np.ndarray | tuple[float, float, float]) -> str:
    return f"({v[0]:.9g} {v[1]:.9g} {v[2]:.9g})"


SUPERSONIC_DOMAIN_MACH = 1.2
SUPERSONIC_DOWNSTREAM_GROWTH_PER_MACH = 0.75


def _downstream_mach_scale(mach: float) -> float:
    """Widens the downstream margin for supersonic runs: a trailing oblique shock/wake
    needs more room to leave the domain cleanly than the low-speed default provides, and
    that room grows with Mach number."""
    return 1.0 + max(0.0, mach - SUPERSONIC_DOMAIN_MACH) * SUPERSONIC_DOWNSTREAM_GROWTH_PER_MACH


def domain_bounds(
    body_bounds: Bounds,
    mesh_settings: MeshSettings,
    ground_plane: GroundPlane | None = None,
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
    mach: float = 0.0,
) -> Bounds:
    """Body-length-scaled far-field box, assuming the dominant flow direction is close to
    +x since the mesh is built once and reused across an alpha/beta sweep. Each symmetry
    plane clips its own axis to >= its offset (halving cell count, or quartering it with
    two planes on different axes); ground_plane replaces one domain face with a no-slip
    wall instead of far-field. mach is the highest Mach reached across the sweep (see
    _downstream_mach_scale)."""
    validate_domain_planes(ground_plane, symmetry_planes)
    xmin, xmax, ymin, ymax, zmin, zmax = body_bounds
    length = max(xmax - xmin, 1e-9)
    body_min = {"x": xmin, "y": ymin, "z": zmin}
    body_max = {"x": xmax, "y": ymax, "z": zmax}
    pad_lengths = {"x": mesh_settings.side_lengths, "y": mesh_settings.side_lengths, "z": mesh_settings.top_lengths}
    symmetry_by_axis = {plane.axis: plane for plane in symmetry_planes}
    downstream = mesh_settings.downstream_lengths * _downstream_mach_scale(mach) * length

    def axis_bounds(axis: str) -> tuple[float, float]:
        if axis == "x":
            lo, hi = xmin - mesh_settings.upstream_lengths * length, xmax + downstream
        else:
            lo, hi = body_min[axis] - pad_lengths[axis] * length, body_max[axis] + pad_lengths[axis] * length
        if ground_plane is not None and ground_plane.axis == axis:
            if ground_plane.side == "min":
                lo = body_min[axis]
            else:
                hi = body_max[axis]
        if axis in symmetry_by_axis:
            lo = symmetry_by_axis[axis].offset
        return lo, hi

    x_lo, x_hi = axis_bounds("x")
    y_lo, y_hi = axis_bounds("y")
    z_lo, z_hi = axis_bounds("z")
    return (x_lo, x_hi, y_lo, y_hi, z_lo, z_hi)


def background_cell_counts(domain: Bounds, body_bounds: Bounds, mesh_settings: MeshSettings) -> tuple[int, int, int]:
    body_length = max(body_bounds[1] - body_bounds[0], 1e-9)
    cell_size = body_length / max(mesh_settings.background_cell_count, 1)
    xmin, xmax, ymin, ymax, zmin, zmax = domain
    return (
        max(int(round((xmax - xmin) / cell_size)), 1),
        max(int(round((ymax - ymin) / cell_size)), 1),
        max(int(round((zmax - zmin) / cell_size)), 1),
    )


def _clamped_midpoint(body_lo: float, body_hi: float, domain_lo: float, domain_hi: float) -> float:
    """The snappyHexMesh seed point must land inside the meshed domain even when a
    symmetry/ground plane trims off the half of the body bounds it would otherwise sit
    in (e.g. a body centered below a symmetry offset)."""
    mid = 0.5 * (body_lo + body_hi)
    margin = 0.01 * max(domain_hi - domain_lo, 1e-9)
    return min(max(mid, domain_lo + margin), domain_hi - margin)


def location_in_mesh(domain: Bounds, body_bounds: Bounds, mesh_settings: MeshSettings) -> tuple[float, float, float]:
    body_length = max(body_bounds[1] - body_bounds[0], 1e-9)
    upstream = mesh_settings.upstream_lengths * body_length
    x = domain[0] + 0.5 * upstream
    y = _clamped_midpoint(body_bounds[2], body_bounds[3], domain[2], domain[3])
    z = _clamped_midpoint(body_bounds[4], body_bounds[5], domain[4], domain[5])
    return (x, y, z)


def block_mesh_dict(
    domain: Bounds,
    cell_counts: tuple[int, int, int],
    ground_plane: GroundPlane | None = None,
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
) -> str:
    validate_domain_planes(ground_plane, symmetry_planes)
    xmin, xmax, ymin, ymax, zmin, zmax = domain
    nx, ny, nz = cell_counts
    vertices = [
        (xmin, ymin, zmin),
        (xmax, ymin, zmin),
        (xmax, ymax, zmin),
        (xmin, ymax, zmin),
        (xmin, ymin, zmax),
        (xmax, ymin, zmax),
        (xmax, ymax, zmax),
        (xmin, ymax, zmax),
    ]
    vertices_str = "\n".join(f"    ({v[0]:.9g} {v[1]:.9g} {v[2]:.9g})" for v in vertices)

    faces = {
        "xmin": "(0 4 7 3)",
        "xmax": "(2 6 5 1)",
        "ymin": "(1 5 4 0)",
        "ymax": "(3 7 6 2)",
        "zmin": "(0 3 2 1)",
        "zmax": "(4 5 6 7)",
    }

    overrides: dict[str, tuple[str, str]] = {}
    if ground_plane is not None:
        overrides[f"{ground_plane.axis}{ground_plane.side}"] = ("ground", "wall")
    for plane in symmetry_planes:
        overrides[f"{plane.axis}min"] = (_symmetry_patch_name(plane.axis), "symmetryPlane")

    far_field_faces = [key for key in faces if key not in overrides]
    patches: list[tuple[str, str, list[str]]] = [
        (name, patch_type, [face_key]) for face_key, (name, patch_type) in overrides.items()
    ]
    patches.append(("farField", "patch", far_field_faces))

    boundary_blocks = []
    for name, patch_type, face_keys in patches:
        faces_str = "\n            ".join(faces[key] for key in face_keys)
        boundary_blocks.append(
            f"    {name}\n    {{\n        type {patch_type};\n        faces\n        (\n            {faces_str}\n        );\n    }}"
        )
    boundary = "\n".join(boundary_blocks)

    return f"""{_header("dictionary", "blockMeshDict")}
scale 1;

vertices
(
{vertices_str}
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
{boundary}
);

mergePatchPairs
(
);
"""


def surface_features_dict() -> str:
    return f"""{_header("dictionary", "surfaceFeaturesDict")}
surfaces ("body.stl");
includedAngle 150;
writeObj no;
"""


def _refinement_regions_block(feature_refinement: dict[str, tuple[int, int]] | None) -> str:
    if not feature_refinement:
        return ""
    region_lines = "\n".join(
        f"            {name} {{ level ({low} {high}); }}" for name, (low, high) in feature_refinement.items()
    )
    return f"\n        regions\n        {{\n{region_lines}\n        }}"


def _layers_block(mesh_settings: MeshSettings, first_layer_thickness: float | None) -> str:
    if first_layer_thickness is not None:
        return f"""relativeSizes false;

    layers
    {{
        body
        {{
            nSurfaceLayers {mesh_settings.n_boundary_layers};
        }}
    }}

    firstLayerThickness     {first_layer_thickness:.6g};
    expansionRatio          {mesh_settings.boundary_layer_expansion_ratio};"""
    return f"""relativeSizes true;

    layers
    {{
        body
        {{
            nSurfaceLayers {mesh_settings.n_boundary_layers};
        }}
    }}

    expansionRatio          {mesh_settings.boundary_layer_expansion_ratio};
    finalLayerThickness     {mesh_settings.final_layer_thickness_ratio};"""


def snappy_hex_mesh_dict(
    mesh_settings: MeshSettings,
    location: tuple[float, float, float],
    first_layer_thickness: float | None = None,
    feature_refinement: dict[str, tuple[int, int]] | None = None,
) -> str:
    """first_layer_thickness, when given (from boundary_layer.first_layer_thickness), sizes
    the boundary layer to an absolute target-y+ thickness instead of a size relative to the
    local surface cell. feature_refinement maps a named surface region (see
    templates_geometry.assemble_rocket_labeled) to its own (min, max) refinement level,
    overriding the body-wide level for that region only."""
    return f"""{_header("dictionary", "snappyHexMeshDict")}
castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    body.stl
    {{
        type triSurfaceMesh;
        name body;
        file "body.stl";
    }}
}}

castellatedMeshControls
{{
    maxLocalCells           1000000;
    maxGlobalCells          4000000;
    minRefinementCells      10;
    maxLoadUnbalance        0.10;
    nCellsBetweenLevels     3;

    features
    (
        {{ file "body.eMesh"; level {mesh_settings.surface_refinement_max}; }}
    );

    refinementSurfaces
    {{
        body
        {{
            level ({mesh_settings.surface_refinement_min} {mesh_settings.surface_refinement_max});{_refinement_regions_block(feature_refinement)}
        }}
    }}

    resolveFeatureAngle     30;
    refinementRegions
    {{
    }}

    locationInMesh ({location[0]:.9g} {location[1]:.9g} {location[2]:.9g});
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch        3;
    tolerance           2.0;
    nSolveIter          30;
    nRelaxIter          5;
    nFeatureSnapIter    10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    {_layers_block(mesh_settings, first_layer_thickness)}
    minThickness            0.1;
    nGrow                   0;
    featureAngle            60;
    nRelaxIter              5;
    nSmoothSurfaceNormals   1;
    nSmoothNormals          3;
    nSmoothThickness        10;
    maxFaceThicknessRatio   0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle      90;
    nBufferCellsNoExtrude   0;
    nLayerIter              50;
}}

meshQualityControls
{{
    maxNonOrtho             {mesh_settings.max_non_orthogonality:.6g};
    maxBoundarySkewness     20;
    maxInternalSkewness     {mesh_settings.max_skewness:.6g};
    maxConcave              80;
    minVol                  1e-13;
    minTetQuality           1e-9;
    minArea                 -1;
    minTwist                0.02;
    minDeterminant          0.001;
    minFaceWeight           0.05;
    minVolRatio             0.01;
    minTriangleTwist        -1;
    nSmoothScale            4;
    errorReduction          0.75;
}}

mergeTolerance 1e-6;
"""


def control_dict(
    application: str,
    end_time: float,
    write_interval: float,
    forces_patches: list[str] | None = None,
    rho_inf: float | None = None,
    cofr: np.ndarray | None = None,
    compressible: bool = False,
    transient: bool = False,
    max_courant: float = 0.5,
    initial_delta_t: float = 1e-6,
) -> str:
    functions = ""
    if forces_patches is not None:
        patches_str = " ".join(forces_patches)
        rho_line = "rho             rho;" if compressible else f"rho             rhoInf;\n        rhoInf          {rho_inf:.9g};"
        functions = f"""
functions
{{
    forces1
    {{
        type            forces;
        libs            ("libforces.so");
        patches         ({patches_str});
        {rho_line}
        CofR            {_vec(cofr)};
        writeControl    timeStep;
        writeInterval   1;
    }}
    wallShearStress1
    {{
        type            wallShearStress;
        libs            ("libfieldFunctionObjects.so");
        patches         (body);
        executeControl  writeTime;
        writeControl    writeTime;
    }}
    yPlus1
    {{
        type            yPlus;
        libs            ("libfieldFunctionObjects.so");
        executeControl  writeTime;
        writeControl    writeTime;
    }}
    surfaceSample
    {{
        type            surfaces;
        libs            ("libsampling.so");
        writeControl    writeTime;
        surfaceFormat   vtk;
        interpolate     false;
        interpolationScheme cellPoint;
        fields          (p wallShearStress yPlus);
        surfaces
        (
            body
            {{
                type        patch;
                patches     (body);
                triangulate false;
            }}
        );
    }}
}}
"""
    if transient:
        time_control = f"""deltaT          {initial_delta_t:.3g};
adjustTimeStep  yes;
maxCo           {max_courant:.3g};
maxDeltaT       1;"""
    else:
        time_control = "deltaT          1;"

    return f"""{_header("dictionary", "controlDict")}
application     {application};
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time:.9g};
{time_control}
writeControl    timeStep;
writeInterval   {write_interval:.9g};
purgeWrite      2;
writeFormat     ascii;
writePrecision  7;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
{functions}"""


def fv_schemes_incompressible() -> str:
    return f"""{_header("dictionary", "fvSchemes")}
ddtSchemes
{{
    default steadyState;
}}

gradSchemes
{{
    default Gauss linear;
}}

divSchemes
{{
    default                        none;
    div(phi,U)                     bounded Gauss linearUpwind grad(U);
    div(phi,k)                     bounded Gauss upwind;
    div(phi,omega)                 bounded Gauss upwind;
    div(phi,nuTilda)               bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}}

laplacianSchemes
{{
    default Gauss linear corrected;
}}

interpolationSchemes
{{
    default linear;
}}

snGradSchemes
{{
    default corrected;
}}

wallDist
{{
    method meshWave;
}}
"""


def fv_schemes_compressible(steady: bool) -> str:
    ddt = "steadyState" if steady else "Euler"
    return f"""{_header("dictionary", "fvSchemes")}
ddtSchemes
{{
    default {ddt};
}}

gradSchemes
{{
    default Gauss linear;
}}

divSchemes
{{
    default                          none;
    div(phi,U)                       bounded Gauss upwind;
    div(phi,e)                       bounded Gauss upwind;
    div(phi,K)                       bounded Gauss upwind;
    div(phi,Ekp)                     bounded Gauss upwind;
    div(phi,k)                       bounded Gauss upwind;
    div(phi,omega)                   bounded Gauss upwind;
    div(phi,nuTilda)                 bounded Gauss upwind;
    div(((rho*nuEff)*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default Gauss linear corrected;
}}

interpolationSchemes
{{
    default linear;
}}

snGradSchemes
{{
    default corrected;
}}

wallDist
{{
    method meshWave;
}}
"""


def fv_schemes_rho_central() -> str:
    return f"""{_header("dictionary", "fvSchemes")}
ddtSchemes
{{
    default Euler;
}}

gradSchemes
{{
    default Gauss linear;
}}

divSchemes
{{
    default             none;
}}

laplacianSchemes
{{
    default Gauss linear corrected;
}}

interpolationSchemes
{{
    default             linear;
    reconstruct(rho)    vanLeer;
    reconstruct(U)      vanLeerV;
    reconstruct(T)      vanLeer;
}}

snGradSchemes
{{
    default corrected;
}}
"""


def fv_solution_incompressible(convergence_residual: float) -> str:
    return f"""{_header("dictionary", "fvSolution")}
solvers
{{
    p
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-7;
        relTol          0.1;
    }}

    "(U|k|omega|nuTilda)"
    {{
        solver          smoothSolver;
        smoother        GaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
    }}
}}

SIMPLE
{{
    nNonOrthogonalCorrectors 1;
    consistent      yes;

    residualControl
    {{
        p               {convergence_residual:.3g};
        U               {convergence_residual:.3g};
        "(k|omega|nuTilda)" {convergence_residual:.3g};
    }}
}}

relaxationFactors
{{
    equations
    {{
        U               0.7;
        k               0.7;
        omega           0.7;
        nuTilda         0.7;
    }}
}}
"""


def fv_solution_compressible(convergence_residual: float, steady: bool) -> str:
    algorithm = "SIMPLE" if steady else "PIMPLE"
    consistent_line = "    consistent      yes;\n" if steady else ""
    residual_block = f"""
    residualControl
    {{
        p               {convergence_residual:.3g};
        U               {convergence_residual:.3g};
        e               {convergence_residual:.3g};
        "(k|omega|nuTilda)" {convergence_residual:.3g};
    }}"""
    pimple_extra = "" if steady else "\n    nOuterCorrectors 2;\n    nCorrectors      1;\n    nNonOrthogonalCorrectors 1;"
    return f"""{_header("dictionary", "fvSolution")}
solvers
{{
    "(p|rho)"
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-7;
        relTol          0.1;
    }}

    "(U|e|k|omega|nuTilda)"
    {{
        solver          smoothSolver;
        smoother        GaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
    }}
}}

{algorithm}
{{
    nNonOrthogonalCorrectors 1;
{consistent_line}{pimple_extra}{residual_block}
}}

relaxationFactors
{{
    equations
    {{
        U               0.7;
        e               0.7;
        k               0.7;
        omega           0.7;
        nuTilda         0.7;
    }}
}}
"""


def fv_solution_rho_central() -> str:
    return f"""{_header("dictionary", "fvSolution")}
solvers
{{
    "(k|omega|nuTilda)"
    {{
        solver          smoothSolver;
        smoother        GaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
    }}
}}
"""


def decompose_par_dict(n_processors: int) -> str:
    return f"""{_header("dictionary", "decomposeParDict")}
numberOfSubdomains {n_processors};
method          scotch;
"""


def transport_properties(kinematic_viscosity: float) -> str:
    return f"""{_header("dictionary", "transportProperties")}
transportModel  Newtonian;
nu              [0 2 -1 0 0 0 0] {kinematic_viscosity:.6e};
"""


def thermophysical_properties() -> str:
    """Calorically-perfect air: hConst thermo + Sutherland transport, valid up to the
    tool's supersonic Mach ceiling but not for hypersonic real-gas/dissociation effects."""
    return f"""{_header("dictionary", "thermophysicalProperties")}
thermoType
{{
    type            hePsiThermo;
    mixture         pureMixture;
    transport       sutherland;
    thermo          hConst;
    equationOfState perfectGas;
    specie          specie;
    energy          sensibleInternalEnergy;
}}

mixture
{{
    specie
    {{
        molWeight   28.9;
    }}
    thermodynamics
    {{
        Cp          1005;
        Hf          0;
    }}
    transport
    {{
        As          {SUTHERLAND_MU_REF * (SUTHERLAND_T_REF + SUTHERLAND_S) / SUTHERLAND_T_REF**1.5:.6e};
        Ts          {SUTHERLAND_S:.6g};
    }}
}}
"""


def turbulence_properties(turbulence_model: str) -> str:
    ras_model = "kOmegaSST" if turbulence_model == "kOmegaSST" else "SpalartAllmaras"
    return f"""{_header("dictionary", "turbulenceProperties")}
simulationType RAS;

RAS
{{
    RASModel        {ras_model};
    turbulence      on;
    printCoeffs     on;
}}
"""


def _wall_patches_block(wall_patches: list[str], type_line: str, value_line: str) -> str:
    lines = f"        {type_line}" + (f"\n        {value_line}" if value_line else "")
    return "\n".join(f"    {patch}\n    {{\n{lines}\n    }}" for patch in wall_patches)


def _symmetry_patch_name(axis: str) -> str:
    return f"symmetry_{axis}"


def _symmetry_block(symmetry_planes: tuple[SymmetryPlane, ...]) -> str:
    return "".join(
        f"    {_symmetry_patch_name(plane.axis)}\n    {{\n        type symmetryPlane;\n    }}\n" for plane in symmetry_planes
    )


def u_field(velocity: np.ndarray, wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()) -> str:
    walls = _wall_patches_block(wall_patches, "type noSlip;", "")
    return f"""{_header("volVectorField", "U")}
dimensions [0 1 -1 0 0 0 0];
internalField uniform {_vec(velocity)};

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestreamVelocity;
        freestreamValue uniform {_vec(velocity)};
    }}
}}
"""


def p_field(wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()) -> str:
    """Incompressible simpleFoam solves for kinematic pressure (p/rho), referenced to 0."""
    walls = _wall_patches_block(wall_patches, "type zeroGradient;", "")
    return f"""{_header("volScalarField", "p")}
dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestreamPressure;
        freestreamValue uniform 0;
    }}
}}
"""


def p_field_compressible(
    static_pressure: float, wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()
) -> str:
    walls = _wall_patches_block(wall_patches, "type zeroGradient;", "")
    return f"""{_header("volScalarField", "p")}
dimensions [1 -1 -2 0 0 0 0];
internalField uniform {static_pressure:.6g};

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestreamPressure;
        freestreamValue uniform {static_pressure:.6g};
    }}
}}
"""


def t_field(
    temperature: float,
    wall_patches: list[str],
    adiabatic_wall: bool,
    wall_temperature: float,
    symmetry_planes: tuple[SymmetryPlane, ...] = (),
) -> str:
    if adiabatic_wall:
        walls = _wall_patches_block(wall_patches, "type zeroGradient;", "")
    else:
        walls = _wall_patches_block(wall_patches, "type fixedValue;", f"value uniform {wall_temperature:.6g};")
    return f"""{_header("volScalarField", "T")}
dimensions [0 0 0 1 0 0 0];
internalField uniform {temperature:.6g};

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestream;
        freestreamValue uniform {temperature:.6g};
    }}
}}
"""


def k_field(k0: float, wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()) -> str:
    walls = _wall_patches_block(wall_patches, "type kqRWallFunction;", f"value uniform {k0:.6g};")
    return f"""{_header("volScalarField", "k")}
dimensions [0 2 -2 0 0 0 0];
internalField uniform {k0:.6g};

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestream;
        freestreamValue uniform {k0:.6g};
    }}
}}
"""


def omega_field(omega0: float, wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()) -> str:
    walls = _wall_patches_block(wall_patches, "type omegaWallFunction;", f"value uniform {omega0:.6g};")
    return f"""{_header("volScalarField", "omega")}
dimensions [0 0 -1 0 0 0 0];
internalField uniform {omega0:.6g};

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestream;
        freestreamValue uniform {omega0:.6g};
    }}
}}
"""


def nut_field_komega(wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()) -> str:
    walls = _wall_patches_block(wall_patches, "type nutkWallFunction;", "value uniform 0;")
    return f"""{_header("volScalarField", "nut")}
dimensions [0 2 -1 0 0 0 0];
internalField uniform 0;

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestream;
        freestreamValue uniform 0;
    }}
}}
"""


def nu_tilda_field(nu_tilda0: float, wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()) -> str:
    walls = _wall_patches_block(wall_patches, "type fixedValue;", "value uniform 0;")
    return f"""{_header("volScalarField", "nuTilda")}
dimensions [0 2 -1 0 0 0 0];
internalField uniform {nu_tilda0:.6g};

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestream;
        freestreamValue uniform {nu_tilda0:.6g};
    }}
}}
"""


def nut_field_sa(wall_patches: list[str], symmetry_planes: tuple[SymmetryPlane, ...] = ()) -> str:
    walls = _wall_patches_block(wall_patches, "type nutUSpaldingWallFunction;", "value uniform 0;")
    return f"""{_header("volScalarField", "nut")}
dimensions [0 2 -1 0 0 0 0];
internalField uniform 0;

boundaryField
{{
{walls}
{_symmetry_block(symmetry_planes)}    farField
    {{
        type freestream;
        freestreamValue uniform 0;
    }}
}}
"""
