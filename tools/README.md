# Tools

This folder contains helper scripts for post-processing, report figures, and manual COMSOL export checks.

The core COMSOL pipeline is implemented in `src/ews_fem_pipeline_comsol`. The scripts in this folder are optional utilities and should be run from the repository root.

## Main Utilities

- `make_comsol_evaluation_plots.py`  
  Generates comparison plots and tables from existing COMSOL post-processing outputs.

- `update_manual_postprocess_summary.py`  
  Rebuilds compact summary tables and plots from manually exported COMSOL CSV files.

- `compare_manual_surface_exports.py`  
  Compares two manual COMSOL outer-surface CSV exports and writes diagnostic difference plots.

## Report-Figure Helpers

- `make_chestwall_curvature_schematic.py`  
  Generates the schematic chestwall-curvature figure.

- `make_single_comsol_case_plot.py`  
  Creates a clean single-case displacement plot from existing postprocess CSV output.

- `make_report_contact_sheets.py`  
  Creates contact sheets from existing COMSOL plot screenshots and metrics files.

- `make_model_option_tree_preview.py`  
  Generates a model-option overview figure from existing screenshots.

- `make_stage6_tumor_fast_evaluation.py`  
  Legacy helper for summarising selected Stage 6 tumor-screening outputs.

## Vendor Files

- `_vendor/` contains local copies of small Python dependencies used by selected plotting tools.
