# COMSOL Testcase Templates

This folder contains small reference TOML files for inspecting the COMSOL pipeline settings.

## Files

- `all_settings.toml`
  - Annotated settings overview with the main editable `[pipeline]`, `[comsol]`, `[source]`, and embedded `[source_case]` blocks.
  - Best starting point when someone wants to understand which settings can be changed.
  - Copy this file before using it as a real case.

- `all_default_settings.toml`
  - Full default settings template written from `ews_fem_pipeline_comsol.settings`.
  - Useful for checking the raw loader defaults.
  - Less readable than `all_settings.toml` because it is a generated default dump.

For runnable examples, use the curated cases in `runs/comsol_runs/geometry_stage*`.
