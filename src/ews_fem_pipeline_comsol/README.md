# COMSOL Pipeline Code Guide

This package contains the active COMSOL FEM pipeline for the EWS breast-model project.

Use this file as a reading guide for the code. The root `README.md` explains the project; this file explains how the package itself is organized.

## Normal Case Flow

The normal command:

```powershell
python -m ews_fem_pipeline_comsol run <case.toml>
```

follows this path:

1. `cli/__init__.py`
   - parses the command-line arguments
   - dispatches to `pipeline.py`

2. `pipeline.py`
   - loads the COMSOL TOML from `settings.py`
   - resolves output folders through `paths.py`
   - calls `prepare_source_case.py`
   - calls `script_builder.py`
   - writes the generated COMSOL input JSON and manifest
   - hands the generated JSON to `run_simulation/comsol_runner.py`

3. `prepare_source_case.py`
   - resolves either `[source].base_case_toml` or embedded `[source_case]`
   - writes resolved/source-case snapshots
   - exports optional mesh, lobule, and build-plan artefacts

4. `script_builder.py`
   - generates COMSOL Java source files
   - writes selection hints
   - creates the builder Java, postprocess Java, and verification Java

5. `run_simulation/comsol_runner.py`
   - runs COMSOL batch commands
   - builds the MPH from generated Java
   - optionally solves the configured study
   - optionally runs postprocess/verification Java
   - removes duplicate large MPH artefacts when configured

6. `reporting.py`
   - converts postprocess metrics JSON into lightweight summary files
   - writes summary CSV/Markdown and optional time-series CSVs

## Main Entry Points

- `python -m ews_fem_pipeline_comsol generate <case.toml>`
  - generate JSON/Java/build artefacts only

- `python -m ews_fem_pipeline_comsol build-only <case.toml>`
  - generate and build an MPH without solving

- `python -m ews_fem_pipeline_comsol run <case.toml>`
  - generate, build, solve, and postprocess according to TOML settings

- `python -m ews_fem_pipeline_comsol postprocess-only --mode global <case.toml>`
  - regenerate postprocess Java and evaluate an existing solved result MPH

- `python -m ews_fem_pipeline_comsol license-check <case.toml>`
  - check whether COMSOL batch can reach a license

## Module Overview

- `cli/__init__.py`
  - CLI parser and command dispatch.

- `settings.py`
  - COMSOL pipeline dataclasses.
  - Loads TOMLs and merges them with defaults.

- `paths.py`
  - Central output-folder layout.
  - Defines `prepare`, `build`, `solve`, and `logs` folders.

- `pipeline.py`
  - High-level orchestration.
  - Keeps command flow readable and delegates heavy work to other modules.

- `prepare_source_case.py`
  - Converts source-case anatomy/material settings into COMSOL build inputs.
  - Writes source snapshots, build plans, lobules, and optional mesh artefacts.

- `script_builder.py`
  - Main COMSOL Java generator.
  - This is currently the largest and most important implementation file.
  - Contains geometry, selection, material, dynamics, tumor, Cooper, plotting, postprocess, and verification Java generation.

- `java_utils.py`
  - Small Python helpers used by Java generation, such as safe Java class names and list chunking.

- `material_mapping.py`
  - Material conversion helpers, including the current Mooney-Rivlin to linear-elastic approximation.

- `run_simulation/comsol_runner.py`
  - Runs COMSOL batch and auxiliary Java classes.
  - Handles build, solve, postprocess, progress logging, timeouts, license errors, and duplicate MPH cleanup.

- `reporting.py`
  - Converts raw COMSOL metrics JSON into smaller report-friendly outputs.

- `metrics_compare.py`
  - Lightweight comparison helper for COMSOL metrics and older FEBio-style summaries.

## Source-Case Subpackage

The `source_case/` folder contains the source anatomy/material schema and helper generation code:

- `source_case_settings.py`
  - source-case anatomy, material, load, output, and legacy XML schema

- `geometry_settings.py`
  - analytical breast profile and mesh/tissue-part settings

- `lobule_generation.py`
  - deterministic glandular lobule templates

- `mesh_generation.py`
  - gmsh source-case mesh generation and mesh export support

- `toml_io.py`
  - source-case TOML read/write helpers

## Important Design Notes

- The active package is `ews_fem_pipeline_comsol`.
- TOMLs are the main reproducibility layer. Generated `.mph`, build, solve, and cache artefacts are intentionally not tracked by Git.
- Tumor/lesion modelling currently uses an analytical `tumor_mask` material overlay plus a separate preview sphere for visual inspection.
- Cooper ligaments are currently implemented as mechanical support sensitivity scaffolds, not as fully validated anatomical ligament reconstruction.
- Stage 1 is a motion sanity baseline; later stages are the anatomical comparison route.

## Current Refactor Priorities

These are documentation/maintenance priorities, not requirements before running cases:

1. Split `script_builder.py` into smaller generators when the model behavior is stable.
2. Split `comsol_runner.py` into command execution, build/solve, and postprocess helpers.
3. Group `ComsolSettings` into clearer nested setting classes after existing TOMLs are stable.
4. Replace user-facing `assert` checks with explicit `ValueError` or CLI errors.
