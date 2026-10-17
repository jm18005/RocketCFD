# RocketCFD

> **Automated OpenFOAM CFD and aerodynamic analysis tool for launch vehicles and high-speed rocket aerodynamics.**

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CFD Backend](https://img.shields.io/badge/Backend-OpenFOAM-brightgreen.svg)](https://openfoam.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20PyVista-orange.svg)](https://www.pyvista.org/)

---

## Overview

`RocketCFD` is a specialized desktop and command-line application that automates the entire OpenFOAM computational fluid dynamics (CFD) workflow for launch vehicle aerodynamics. It bridges the gap between complex CFD configurations and aerospace engineering analysis by providing intelligent, rocket-sensible defaults for meshing, boundary conditions, turbulence models, and solver selection across subsonic, supersonic, and hypersonic regimes.

---

## Key Features

### 🚀 Automated OpenFOAM Workflow
* **Intelligent Solver Selection**: Automatically selects and sets up the appropriate solver based on Mach number ($0 < M < 8$):
  * **Subsonic/Incompressible**: `simpleFoam`
  * **Transonic/Supersonic**: `rhoSimpleFoam` / `rhoPimpleFoam`
  * **High-Speed Compressible & Shocks**: `rhoCentralFoam`
* **Automated Boundary Conditions**: Couples atmospheric parameters, vehicle velocity, angle of attack ($\alpha$), sideslip ($\beta$), and prevailing wind vectors directly into the solved boundary equations.
* **ISA Atmosphere Lookup**: Built-in International Standard Atmosphere model extending past 50,000 ft.

### 📐 Geometry & Watertight Validation
* **Multi-Format Support**: Imports raw **STL** geometry out of the box, with optional **STEP** and **IGES** CAD support via OpenCASCADE (`cadquery-ocp`).
* **Automated Watertight Repair**: Detects non-manifold edges, self-intersections, and open holes, automatically repairing meshes via `pymeshfix` and `trimesh`.
* **Domain Sizing**: Automatically sizes computational domain bounds based on vehicle body length and extends downstream boundaries dynamically based on Mach number.
* **Symmetry & Ground Effects**: Supports symmetry-plane half-body solves and ground-effect modeling.

### 🕸️ Automated Meshing (`snappyHexMesh`)
* **Density Presets**: Coarse, Medium, and Fine presets configure background mesh resolution, surface refinements, and feature edge snapping.
* **Boundary Layer & $y^+$ Sizing**: Automatically calculates and sizes first-layer prism cell thickness to target specified $y^+$ values based on flat-plate boundary layer theory.
* **Feature Refinement**: Targets fin edges, nosecone shoulders, boattails, and expected shock standoff zones.
* **Pre-Solve Mesh Previewer**: Inspect generated 3D surface mesh cells and aspect ratios in the interactive viewer before initiating runs.

### 📊 Real-Time Post-Processing & Analytics
* **Live In-App Residual Monitoring**: Real-time plots for continuity, momentum, and turbulence equation convergence during active solves.
* **3D Surface & Field Visualizations**: Interactive PyVista viewport displaying:
  * Surface pressure coefficient ($C_p$) contours
  * Wall shear stress ($\tau_w$) and skin friction ($C_f$)
  * Volumetric velocity slices and 3D streamlines
* **Parameter Sweeps**: Run single cases or parameter sweeps across Mach, altitude, AoA, and sideslip.
* **ANSYS Fluent Comparison**: Built-in parser to compare OpenFOAM force/moment polar results against exported ANSYS Fluent reports.

---

## Installation

### Prerequisites
* **Python 3.13+**
* [uv](https://docs.astral.sh/uv/) (recommended) or `pip`
* A working **OpenFOAM** installation (e.g. OpenFOAM v2012+ or OpenFOAM-10 via Linux or WSL)

### Setup with `uv`
```bash
# Clone the repository
git clone https://github.com/jm18005/RocketCFD.git
cd RocketCFD

# Install dependencies into a virtual environment
uv sync

# (Optional) Install CAD support for STEP/IGES files
uv sync --extra cad
```

---

## Quick Start

### Launch the GUI
```bash
uv run rocketcfd
```
1. **Load Geometry**: Import your rocket `.stl` file. The watertight checker verifies and fixes mesh integrity.
2. **Define Flight Profile**: Input Mach number, Altitude, Angle of Attack, and Sideslip.
3. **Configure Mesh**: Choose a mesh preset (Coarse / Medium / Fine) or customize $y^+$ targets.
4. **Solve & Monitor**: Click **Run Solve** and monitor real-time residuals and aerodynamic polars.

### Running Tests
The project features an automated test suite verifying geometry repair, atmospheric models, boundary layer sizing, solver selection, and GUI components:
```bash
uv run pytest
```

---

## Project Structure
```
RocketCFD/
├── src/
│   └── rocketcfd/
│       ├── atmosphere.py          # ISA standard atmosphere model
│       ├── geometry.py            # Mesh repair, watertight checks, STL handling
│       ├── brep_backend.py        # STEP/IGES CAD loader
│       ├── solver_selection.py    # Mach-dependent OpenFOAM solver selector
│       ├── sweep.py               # Multi-dimensional parameter sweep engine
│       ├── ansys_compare.py       # Benchmark comparison parser
│       ├── gui/                   # PySide6 & PyVista 3D desktop interface
│       ├── openfoam/              # snappyHexMesh, case builder, log parsers, runner
│       └── validation/            # Apollo CM validation benchmarks
├── tests/                         # Comprehensive pytest test suite
├── examples/                      # Sample geometry files
├── REQUIREMENTS_TRACEABILITY.md   # Feature verification and test traceability matrix
└── pyproject.toml                 # Package definition and dependencies
```

---

## Validation
RocketCFD has been benchmarked against wind tunnel and flight test reference data, including the classic **Apollo Command Module** supersonic and hypersonic blunt-body flowfields (see `src/rocketcfd/validation/` and [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md)).

---

## License
This project is licensed under the [MIT License](LICENSE).
