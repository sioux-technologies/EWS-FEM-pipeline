# COMSOL analysis output

This folder contains cleaned figures and tables generated from the current COMSOL
pipeline post-processing outputs.

Most subfolders follow the same structure:

- `figures/`: generated PNG/SVG plots for visual comparison.
- `tables/`: CSV/Markdown summary tables used to create the figures.

The most report-relevant folders are:

- `report_fixed_material_suite/`: material and volumetric-skin sensitivity
  comparisons used in the Results section.
- `stage5_cooper/`: Cooper-like support comparison figures and tables.
- `stage5_dynamic_amplitude_scout/`: dynamic loading amplitude scout outputs.
- `stage6_fast_tumor_screening/` and `stage6_tumor_preview/`: tumor placement
  and lightweight tumor-output checks.
- `tier1_comparison/` and `tier1_comparison_without_stage1/`: broader overview
  comparisons across the main model-development stages.
- `manual_postprocess/`: manually collected/exported post-processing summaries
  and comparison figures.

