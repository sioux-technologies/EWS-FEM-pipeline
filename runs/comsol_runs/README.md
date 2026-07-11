# COMSOL run configurations

This folder contains the active TOML case definitions and local generated output
for the COMSOL breast-model pipeline. The TOML files are project provenance and
should remain versioned. Large generated COMSOL artefacts should stay local and
outside GitHub.

## Main staged route

- `geometry_stage1`: early motion and loading sanity checks.
- `geometry_stage2_chestwall`: posterior support and chestwall-curvature cases.
- `geometry_stage3`: glandular distribution and anatomical reference cases.
- `geometry_stage4`: outer-shape and nipple/asymmetry sensitivity cases.
- `geometry_stage5`: skin, material and Cooper-like support cases.
- `geometry_stage5_1_motion_scout`: prescribed-support motion scout cases.
- `geometry_stage6`: tumor-overlay placement and selected tumor-output cases.

These stage folders contain the main history of the COMSOL model-development
route. For report use, prefer the latest verified TOMLs and summary outputs over
older scout cases.

## Review and support folders

- `report_fixed_material_suite`: report-oriented material and skin sensitivity
  case set.
- `material_parameter_sensitivity`: broader material-parameter sensitivity
  cases.
- `dynamic_realism_branch`: exploratory dynamic-loading and motion realism
  cases.
- `sandbox_testcases`: small scratch cases for quick build or pipeline checks.

## GitHub notes

Track in GitHub:

- active `.toml` case definitions;
- small summary tables and report-ready outputs when useful;
- documentation that explains how to reproduce a case.

Avoid tracking:

- `.mph`, `.recovery`, `.status`;
- COMSOL cache/configuration folders;
- generated `output*`, `build`, `solve`, and `prepare` folders;
- large mesh exports or full generated run folders.
