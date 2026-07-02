# Parameter Overview

This file gives a compact TOML-style overview of the main settings used in the COMSOL EWS breast FEM project. It is intended as a quick handover reference, not as a replacement for the actual case `.toml` files.

For complete defaults, see `runs/comsol_testcases/all_default_settings.toml`. For actual solved cases, always check the relevant case file in `runs/comsol_runs/`.

## Pipeline

| Setting | Typical value | Meaning |
|---|---:|---|
| `pipeline.model_name` | `breast_model_comsol` | COMSOL model route name. |
| `pipeline.output_subdir` | `output` / `outputs/output_<case>` | Output location is resolved per case. |

## Source Case

| Setting | Typical value | Meaning |
|---|---:|---|
| `source.base_case_toml` | case-dependent | Optional source-case TOML used to build geometry/material inputs. |
| `source.reuse_source_prepare` | `true` | Reuse prepared mesh/lobule/build-plan artefacts when possible. |
| `source.export_mesh_npz` | `true` | Export compact mesh data for COMSOL builder input. |
| `source.export_mesh_csv` | `true` | Export node/element CSV helper files. |
| `source.export_lobules_json` | `true` | Export glandular-lobule metadata. |

## Anatomical Geometry

| Parameter group | Main settings | Current project interpretation |
|---|---|---|
| Breast volume | reference around `585 mL` | Selected reference volume for the report route. |
| Chestwall curvature | transverse curved posterior support, selected offset `0.055 m` | Used to represent a curved posterior support rather than a full anatomical thorax. |
| Glandular distribution | realistic reference lobule spread, glandular fraction about `24.3%` | Fibroglandular-rich reference case for EWS-oriented development. |
| Outer-shape variation | `outer_shape_scale_x/y/z`, inferior/lateral fullness options | Implemented for geometry sensitivity and asymmetry scouts. |
| Nipple position | `nipple_geometry_x_offset_m`, `nipple_geometry_z_offset_m` | Implemented for nipple-position variation examples. |

## Material Parameters

Small-strain stiffness scale for the current two-coefficient Mooney-Rivlin route:

```text
E ~= 6 * (C10 + C01)
```

for nearly incompressible materials.

| Component | Density | Main parameters | Approx. stiffness scale |
|---|---:|---|---:|
| Adipose | `950 kg/m3` | `K=425 kPa`, `C10=310 Pa`, `C01=300 Pa` | `E ~= 3.66 kPa` |
| Fibroglandular | `1070 kg/m3` | `K=425 kPa`, `C10=833 Pa`, `C01=833 Pa` | `E ~= 10.0 kPa` |
| Skin, reference stiff route | `1100 kg/m3` | `K=8.33 MPa`, `C10=41667 Pa`, `C01=41667 Pa` | `E ~= 500 kPa` |
| Tumor hard contrast route | case-dependent | `C10=8333 Pa`, `C01=8333 Pa` | `E ~= 100 kPa` |
| Posterior support | `1050 kg/m3` | `E=10 kPa`, `nu=0.49` | linear elastic surrogate |

The lower/intermediate/stiff material variants are sensitivity settings. They should not be interpreted as patient-specific tissue measurements.

## Volumetric Skin

| Setting | Typical value | Meaning |
|---|---:|---|
| `enable_volumetric_skin_layer` | case-dependent | Enables a solid skin layer instead of only a surface. |
| `volumetric_skin_thickness_m` | `0.0015 m` | Main report skin thickness. |
| alternative thickness | `0.0001 m` | Thin-skin sensitivity route. |

Skin stiffness and thickness had a strong effect on simulated displacement, so skin settings should be kept explicit in any future comparison.

## Cooper-Like Support

| Setting | Typical value | Meaning |
|---|---:|---|
| `enable_cooper_ligament_scaffold` | case-dependent | Enables simplified Cooper-like support, not anatomical ligament reconstruction. |
| `cooper_ligament_variant` | `none`, `nipple_to_chestwall`, `glandular_to_skin`, `dense_network` | Implemented support-selection routes. |
| `cooper_ligament_effective_modulus_pa` | `5.8 MPa` | Ligament stiffness scale used to derive restoring support. |
| `cooper_ligament_area_fraction` | around `0.06-0.12` in tested variants | Active support area fraction. |
| `cooper_ligament_reference_length_m` | about `0.04-0.07 m` | Reference length for traction scale. |
| `cooper_ligament_tangential_scale` | `0.35` | Tangential-to-normal support scaling. |

The current Cooper route is a support-strength sensitivity model. It is not a reconstructed ligament network.

## Dynamic Loading

| Setting | Main report/scout value | Meaning |
|---|---:|---|
| `dynamic_motion_mode` | `fixed_support_acceleration_pulse` or `prescribed_support_displacement` | Two available dynamic excitation routes. |
| `dynamic_acceleration_amplitude_g` | commonly `0.25 g` or `1.25 g` scouts | Body acceleration amplitude relative to gravity. |
| `dynamic_acceleration_duration_s` | `0.60 s` in main mild pulse descriptions | Pulse duration. |
| `dynamic_mass_damping_alpha_s_inv` | `60 s^-1` in main damped route | Rayleigh mass-proportional damping coefficient. |
| `dynamic_support_displacement_amplitude_m` | `0.02-0.06 m` in support-motion scouts | Prescribed support displacement amplitude. |
| `dynamic_support_displacement_duration_s` | `0.60 s` in support-motion scouts | Support-motion duration. |

Dynamic loading is a controlled excitation for model comparison. It is not yet calibrated to measured EWS motion data.

## Post-Processing

| Mode | Main outputs | Use |
|---|---|---|
| `global` | lightweight summary/time-series | Quick check that solve and displacement response are available. |
| `ews_surface` | surface metrics, landmarks, time series, stress fields where available | Main EWS-oriented surface evaluation route. |
| `internal_tumor` | tumor-mask volume, displacement and stress metrics | Local tumor-overlay evaluation. |

Main metrics:

- displacement magnitude;
- signed vertical displacement;
- surface/landmark displacement;
- von Mises stress;
- tumor-mask displacement/stress when tumor overlay is enabled.
