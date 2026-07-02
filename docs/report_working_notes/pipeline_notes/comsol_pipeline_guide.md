# COMSOL Pipeline Guide

## Purpose

This guide is the compact end-to-end explanation of how the COMSOL pipeline is currently used in this project.

Use it together with:

- [stages.md](C:\Users\20223231\ews_fem_clean\docs\report_notes\comsol_pipeline\stages.md)
- [full_update.md](C:\Users\20223231\ews_fem_clean\docs\report_notes\comsol_pipeline\full_update.md)

## What the COMSOL pipeline does

The COMSOL pipeline does not directly reuse the FEBio solver model.

Instead it:

1. starts from a TOML case definition
2. reuses the shared prepare pipeline where possible
3. exports a COMSOL build plan and helper artefacts
4. generates a COMSOL Java builder
5. builds an `.mph` model from that Java scaffold
6. optionally runs the COMSOL study
7. exports summary artefacts such as JSON, CSV, Markdown, and time-series files

## Main folders

Run definitions live in:

- [runs/comsol_runs](C:\Users\20223231\ews_fem_clean\runs\comsol_runs)

Current stage layout:

- `geometry_stage1`: trusted simple dynamic baselines
- `geometry_stage2`: chest/support realism
- `geometry_stage3`: material-alignment tests on light `v2` geometry
- `geometry_stage4`: richer glandular geometry
- `geometry_stage4a`: alternative gland representation
- `geometry_stage5`: Cooper's ligaments / fibrous support
- `geometry_stage6`: tumor/no-tumor comparisons
- `geometry_stage7`: final integrated model

## How a case is called

Each COMSOL case is defined by a TOML file.

Typical commands:

- `python -m ews_fem_pipeline_comsol build-only <case.toml>`
- `python -m ews_fem_pipeline_comsol run <case.toml>`
- `python -m ews_fem_pipeline_comsol compare-metrics <summary1.json> <summary2.json> --baseline <case_name>`

`build-only`:

- prepares the case
- generates COMSOL Java
- builds the `.mph`
- does not start the solve

`run`:

- prepares the case
- builds the `.mph` if needed
- runs the configured COMSOL study
- writes result artefacts to the case output folder

## Output structure

Each case writes to an output folder under its stage.

Typical subfolders:

- `prepare`
- `build`
- `solve`
- `logs`

Important files:

- `build/*generated*.mph`: built geometry/physics model for inspection
- `solve/*result.mph`: solved COMSOL model
- `solve/*summary.json`: high-level case summary
- `solve/*time_series.csv`: time history of the main metrics
- `logs/*comsol.log`: COMSOL solve log

## Current baseline behavior

The trusted working reference is still:

- [baseline_simple_gland_dynamic_solid_only.toml](C:\Users\20223231\ews_fem_clean\runs\comsol_runs\geometry_stage1\baseline_simple_gland_dynamic_solid_only.toml)

The stiffer shell/scaffold comparison case is:

- [full_baseline_reference_simple_gland_static_baseline.toml](C:\Users\20223231\ews_fem_clean\runs\comsol_runs\geometry_stage1\full_baseline_reference_simple_gland_static_baseline.toml)

These are the best starting points when checking whether geometry, support, motion, or later realism upgrades still behave plausibly.

## Current modeling assumptions

At the moment the COMSOL pipeline is strongest at:

- simple baseline geometry
- posterior attachment and dynamic jump loading
- slab/split support experiments
- shell/scaffold comparison

It is weaker or still evolving for:

- richer `v2` gland geometry robustness
- true 3D outer-shape asymmetry
- transverse chest-support realism
- Cooper's ligament implementation
- full final integrated realism

## About verification and metrics messages

The pipeline sometimes runs auxiliary Java checks after build or solve.

If those checks do not emit the expected JSON markers, the pipeline can still continue using fallback verification/reporting.

So:

- missing marker messages are usually not the main failure
- the important checks are still whether the `.mph`, summary files, and logs were created correctly

## Recommended reading order

1. read this guide first
2. read [stages.md](C:\Users\20223231\ews_fem_clean\docs\report_notes\comsol_pipeline\stages.md)
3. read [full_update.md](C:\Users\20223231\ews_fem_clean\docs\report_notes\comsol_pipeline\full_update.md)
4. then inspect the TOML of the stage you are actively working on
