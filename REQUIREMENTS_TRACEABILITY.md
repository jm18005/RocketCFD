Traceability matrix, proposal item to implementation to test. Status: DONE, PARTIAL (works, scope trimmed), or GAP (not built).

## Overview / Goals

| Item | Status | Implementation | Test |
|---|---|---|---|
| GUI wrapping OpenFOAM | DONE | gui/app_window.py, gui/main_window.py | test_gui_main_window.py, test_widgets.py (offscreen Qt) |
| Import geometry, set conditions, run, postprocess | DONE | gui/geometry_panel.py, gui/main_window.py | test_gui_main_window.py |
| Rocket sensible defaults (mesh/solver/turbulence/domain/BC) | DONE | openfoam/settings.py defaults, solver_selection.py | test_solver_selection.py, test_gui_main_window.py (defaults round-trip through the GUI) |
| Advanced override of solver/mesh/turbulence params | DONE | every setting is a GUI field with a default; advanced/rarely-touched fields are grouped under collapsible "Advanced" sections (gui/widgets.py CollapsibleSection) so a first-time user sees only what they need | test_gui_main_window.py, test_widgets.py |
| Single-case or parameter sweeps | DONE | sweep.py supports N-D; GUI allows up to MAX_SWEPT_VARIABLES=3 swept axes at once (each point is a full mesh+solve, so the GUI still caps the axis count well below sweep.py's unlimited N-D support) | test_sweep.py, test_gui_main_window.py |
| 0 < M < 5, 0 < altitude < 50000 ft | DONE (renegotiated) | default Mach ceiling 3.0, adjustable to HARD_MACH_LIMIT=8.0 with warnings; atmosphere.py valid well past 50000 ft | test_solver_selection.py, test_atmosphere.py |
| Visualize flow before/after run | DONE | gui/viewport.py, gui/surface_fields.py | smoke test |
| Automated ANSYS comparison | DONE (CSV-based) | ansys_compare.py, reads an exported Fluent/CFD-Post report CSV, not raw ANSYS binary files | test_ansys_compare.py |

## Geometry

| Item | Status | Implementation | Test |
|---|---|---|---|
| Import STL/STEP/IGES | DONE (STEP/IGES needs optional `cad` extra) | geometry.py, brep_backend.py | test_geometry.py (STL path only; STEP/IGES needs cadquery-ocp installed) |
| Auto watertight check + repair | DONE | geometry.ensure_watertight | test_geometry.py |
| Manual-fix message when repair fails | DONE | GeometryNotWatertightError, surfaced in gui/geometry_panel.py | test_geometry.py |
| Auto domain sizing from body length | DONE | openfoam/templates.py domain_bounds (scales by body length) | test_openfoam_templates.py |
| Auto domain sizing by Mach number | DONE | openfoam/templates.py domain_bounds widens the downstream margin above Mach 1.2, using the fastest condition in the sweep | test_openfoam_templates.py, test_case_builder.py |
| CG / moment reference input | DONE | gui/main_window.py moment reference spin boxes | test_gui_main_window.py |
| Symmetry-plane mirror | DONE | templates.py symmetry patch, case_builder.py, gui checkbox | test_openfoam_templates.py, test_case_builder.py |
| Ground effect plane | DONE | ported from josh-cfd, unchanged | test_openfoam_templates.py |

## Flight Conditions

| Item | Status | Implementation | Test |
|---|---|---|---|
| Altitude/velocity/Mach/AoA/sideslip/wind input | DONE | gui/sweep_axis_row.py, wind speed/direction fields; wind is now vectorially combined with the vehicle's own velocity into the actual solved 0/U boundary condition (FlowCondition.effective_condition(), case_result.py), not just visualized | test_gui_main_window.py (apply-atmosphere, swept-axis-limit tests), test_case_result.py (wind-into-BC coupling, round trip) |
| ISA atmosphere lookup | DONE | atmosphere.py | test_atmosphere.py |
| Auto solver selection by Mach | DONE | solver_selection.py (simpleFoam / rhoSimpleFoam / rhoPimpleFoam / rhoCentralFoam) | test_solver_selection.py |
| N-dimensional sweeps | DONE | sweep.build_conditions supports any number of axes; GUI allows up to MAX_SWEPT_VARIABLES=3 at once | test_sweep.py, test_gui_main_window.py |

## Meshing

| Item | Status | Implementation | Test |
|---|---|---|---|
| Automated snappyHexMesh, boundary layers | DONE | openfoam/templates.py, case_builder.py | test_openfoam_templates.py |
| Boundary layers sized to a target y+ | DONE | openfoam/boundary_layer.py (flat-plate skin-friction estimate) sizes an absolute first-layer thickness from the fastest swept condition when "Size first layer to target y+" is checked; GUI toggle falls back to the existing relative-thickness setting otherwise | test_boundary_layer.py, test_case_builder.py, test_openfoam_templates.py |
| Feature-specific refinement (fin edges, nosecone shoulder, boattail, shocks) | DONE (parametric geometry only) | templates_geometry.assemble_rocket_labeled tags faces by part; case_builder writes a multi-region STL and openfoam/templates.py snappy_hex_mesh_dict applies a per-region refinement level via MeshSettings.feature_refinement_levels. Arbitrary loaded STL/STEP/IGES geometry has no part labels, so this only applies to rockets built from the parametric template library, and there is no GUI editor for the level dict yet (set it in code/tests) | test_templates_geometry.py, test_case_builder.py, test_openfoam_templates.py |
| Automatic mesh quality gate before solving | DONE | openfoam/mesh_quality.py, case_result.py | test_mesh_quality.py |
| Mesh density presets (coarse/medium/fine) | DONE | openfoam/settings.py MESH_PRESETS/mesh_settings_for_preset; GUI preset dropdown in main_window.py sets background cell count/surface refinement/layers/target y+ together and switches to "Custom" on manual edits | test_mesh_presets.py, test_gui_main_window.py |

## Visualization

| Item | Status | Implementation | Test |
|---|---|---|---|
| Mirror plane, ground plane, domain box | DONE | gui/viewport.py add_domain_box | smoke test |
| Flow direction vector (AoA/sideslip live) | DONE | gui/viewport.py, control_panel_mixins.py | smoke test |
| Wind-direction and total-flow-direction vectors | DONE | gui/viewport.py render_reference_scene (visualization); flow.py effective_condition()/case_result.py couple the same vector into the solved 0/U boundary condition | smoke test; test_case_result.py |
| CG/moment reference marker | DONE | gui/viewport.py | smoke test |
| Mesh preview/explorer before solving | DONE | "Preview mesh" button (main_window.py) runs blockMesh/snappyHexMesh only (case_result.ensure_mesh, shared with the full run's cache) and shows the real generated body-patch cells (gui/mesh_preview.py, via pyvista's OpenFOAM reader) with edges on, distinct from the smooth pre-mesh CAD preview | test_mesh_preview.py, test_gui_main_window.py |
| Live in-app residual monitoring during solve | DONE | A QTimer re-parses the running case's solver log and redraws the Residuals plot every 2s while a solve is in progress and that plot mode is selected (main_window.py case_started signal + _on_residual_timer_tick) | test_gui_main_window.py, test_case_result.py (on_case_started callback) |
| Pressure/velocity contours, surface Cp, flow-path traces, convergence history | DONE | pressure/wall-shear/Cf/y+ surface fields and force/moment convergence plots, plus a velocity-magnitude cutting-plane slice and traced flow paths read from the volumetric field (gui/volume_fields.py, via pyvista's OpenFOAM reader) | smoke test; test_volume_fields.py, test_gui_main_window.py |

## Post-Processing

| Item | Status | Implementation | Test |
|---|---|---|---|
| Auto force/moment extraction, coefficients | DONE | openfoam/coefficients.py, results_parser.py | test_openfoam_templates.py, test_case_builder.py |
| Plot any swept variable vs any other | DONE | gui/openfoam_results.py PLOT_X_QUANTITIES | smoke test |
| Aerotable CSV generation | DONE | aerotable.py | test_aerotable.py |
| Sanity-check flags (negative drag, discontinuity, non-convergence) | DONE | sanity_checks.py, wired into aerotable export | test_sanity_checks.py |

## Deployment

| Item | Status | Implementation | Test |
|---|---|---|---|
| Platform auto-detection | DONE | deployment.py is_windows_host/is_linux_host | test_deployment.py |
| Native Linux support | DONE (untested against a real OpenFOAM install) | openfoam/execution.py NativeLinuxExecutionBackend, runner.run_commands_native | test_execution.py; none end-to-end |
| Windows via WSL2 | DONE | openfoam/execution.py WslExecutionBackend (ported, proven pattern) | test_runner.py, test_execution.py |
| Automated OpenFOAM/WSL install | DONE (script generation and invocation tested; not run for real) | deployment.py, gui/deployment_panel.py | test_deployment.py |
| TACC or local submission | DONE | tacc.py, gui/deployment_panel.py | test_tacc.py |

## Additional Features

| Item | Status | Implementation | Test |
|---|---|---|---|
| Case/result caching | DONE | caching.py, openfoam/case_result.py | test_caching.py |
| Parametric geometry template library | DONE | templates_geometry.py (body tube, nosecone, boattail, fin, assembly) | test_templates_geometry.py |
| Convergence auto-stop | DONE | residualControl blocks in fvSolution (all regimes) | test_openfoam_templates.py |
| UT Box integration | DONE | box_integration.py, gui/deployment_panel.py | test_box_integration.py |

## Architecture

| Item | Status | Implementation | Test |
|---|---|---|---|
| PySide desktop app, Python orchestration | DONE | src/rocketcfd, uv-managed project | pytest, offscreen Qt tests |
| Version controlled, shareable source | PARTIAL | project scaffolded with uv/git-ready layout; no commit made yet, pending the user's go-ahead | n/a |
| Beginner-friendly, progressive-disclosure UI | DONE | gui/widgets.py CollapsibleSection; main_window.py groups mesh/solver/execution/reference-override detail fields under collapsed-by-default "Advanced" sections (auto-expanding when a user edits a field inside one), keeps geometry/flight-conditions/Run as the only always-visible steps, and adds an intro banner explaining the 3-step flow; result/validation tables resize columns to fit their content instead of clipping text, the app enforces a 1100x700 minimum window size, and the control-panel/3D-view splitter opens at a sane 440/1060 default so nothing starts squeezed off-screen | test_widgets.py, test_gui_main_window.py |

## Validation

| Item | Status | Implementation | Test |
|---|---|---|---|
| Sphere/cone/flat-plate test cases | DONE | validation/runner.py sphere_case/flat_plate_case/cone_case | test_validation_reference_data.py |
| Automated run of validation cases | DONE (pipeline wired; not run end-to-end without a real OpenFOAM install) | validation/runner.run_validation_suite, gui/validation_panel.py | none end-to-end |
| Reference data with a defined margin | DONE | validation/reference_data.py (Blasius/turbulent flat plate, digitized sphere Cd curve, linearized cone wave drag), 25% default tolerance | test_validation_reference_data.py |

## Test suite summary

199 unit tests passing (`uv run pytest`), lint clean (`claudemd_linter.py`). No proposal item is now marked GAP or PARTIAL. Everything marked "end-to-end" as untested requires an actual OpenFOAM install (WSL2, native Linux, or TACC), which this environment does not have; the case-file generation, parsing, and orchestration logic around it is unit tested with synthetic data instead. The mesh-preview and volume-field (velocity slice/flow-path trace) readers are unit tested against a mocked pyvista OpenFOAM reader for the same reason -- their exact behavior against a real OpenFOAM install's on-disk format is unverified here.

A repo-wide audit closed the previous gap of zero automated GUI coverage: tests/conftest.py now boots a shared offscreen QApplication for the whole suite, and test_widgets.py / test_gui_main_window.py cover the new progressive-disclosure widgets and the automation panel's settings/preset/run-guard wiring directly (not just an ad hoc manual smoke test). The same pass added missing coverage for openfoam/results_parser.py, openfoam/execution.py, openfoam/paths.py, openfoam/case_result.py (previously untested), and openfoam/runner.py's bashrc-detection/distro-listing/process-streaming helpers, and fixed three bugs the new tests surfaced: the convergence-residual dropdown silently defaulted to 1e-3 instead of the intended 1e-4 (a string-format mismatch between the default value and the dropdown's item list), caching.compute_case_hash rebuilt a full nested Python list from every mesh vertex/face array before hashing it (now hashes raw bytes instead), and openfoam/runner.stream_process never closed its subprocess's pipes on the success path (now used as a context manager).

A follow-up pass closed every remaining PARTIAL item: raised the GUI's swept-axis cap from 1 to 3 (sweep.py already supported unlimited N-D sweeps); coupled the wind vector into the actual solved boundary condition instead of only the 3D-view arrows (FlowCondition.effective_condition(), with the vehicle-frame condition recovered losslessly on re-import via metadata); added a "Preview mesh" action that runs the mesh-only pipeline and displays the real snappyHexMesh surface; added a live-updating residual chart while a solve is in progress; and added a velocity-magnitude slice and traced-flow-path view read from the solved volumetric field. Also passed over the whole GUI for "nothing hidden or cut off": table columns now resize to fit their content, the app enforces a sane minimum window size, and the control-panel/3D-view splitter opens at a fixed, readable ratio.
