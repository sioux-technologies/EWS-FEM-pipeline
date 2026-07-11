# COMSOL versus FEBio model positioning

Date: 2026-06-01

This note positions the current COMSOL breast FEM pipeline against the older FEBio pipeline. The goal is not to prove that one model is perfect, but to explain what can and cannot be compared fairly.

## Practical conclusion

The FEBio model is best used as a historical and mechanical benchmark. It showed that geometry, support, glandular layout and material stiffness can strongly affect displacement and stress.

The COMSOL model is the active report pipeline. It has better reproducibility through TOMLs, clearer staged anatomy, better provenance, explicit surface-displacement exports, and the current Stage 6 tumor route.

The two models should not be treated as one-to-one solver validation because the dynamic loading, skin treatment, support geometry, material implementation and postprocessing outputs are different.

## Important skin-shell limitation

Most active COMSOL Stage 1-6 TOMLs currently use:

```toml
enable_skin_shell_physics = false
enable_skin_solid_coupling_scaffold = false
skin_shell_thickness_m = 0.0001
```

This means that the current report-oriented COMSOL dynamic runs do not yet include a separate mechanically active skin shell. The outer surface still exists geometrically and is used for selections and surface displacement postprocessing, but the stiff skin material is not acting as a separate shell layer unless `enable_skin_shell_physics = true`.

This was likely done for numerical robustness while the COMSOL geometry, glandular lobules, chestwall support, Cooper scaffold and tumor mask were being stabilized. It is defensible for early stage comparisons, but it should be documented as a model limitation.

For the final model, skin should not simply be ignored. A skin-on sensitivity should be added before making final claims about absolute displacement amplitudes, tumor detectability, or realistic breast motion. The current no-skin-shell results are still useful as a clean internal baseline, but they should not be presented as the final fully anatomical model.

Recommended next step:

1. Make a Stage 5 no-Cooper skin-on build-only case.
2. If it builds cleanly, run one dynamic skin-on scout against the existing no-skin 1.25g or 0.25g reference.
3. Only if the effect is small and stable, decide whether all final Stage 6 tumor runs need to be repeated with skin-on.

## Main result comparison

### COMSOL active summaries

The current Tier 1 COMSOL comparison reports:

| COMSOL case | Breast volume | Glandular fraction | Review avg displacement | Breast max VM |
|---|---:|---:|---:|---:|
| Stage 1 0.25g baseline | 718.7 ml | 11.9% | 17.76 mm | 10.73 kPa |
| Stage 2 xoffset055 chestwall | 585.1 ml | 9.2% | 3.03 mm | 1.35 kPa |
| Stage 3 realistic glandular | 585.1 ml | 24.3% | 3.00 mm | 1.67 kPa |
| Stage 4 realistic reference | 585.1 ml | 24.3% | 3.00 mm | 1.63 kPa |
| Stage 5 no-Cooper control | 585.1 ml | 24.3% | 3.00 mm | 1.61 kPa |

The Stage 5 dynamic amplitude scout shows:

| COMSOL case | Status | Peak max displacement | Peak avg displacement | Peak breast VM max |
|---|---|---:|---:|---:|
| No-Cooper 0.25g | successful | 7.37 mm | 3.91 mm | 2.11 kPa |
| No-Cooper 0.50g | successful | 9.08 mm | 4.76 mm | 2.55 kPa |
| No-Cooper 0.75g | failed/partial | not usable | not usable | not usable |
| No-Cooper 1.25g | solve-only successful | visually about 14 mm | not globally postprocessed yet | not globally postprocessed yet |

### FEBio benchmark summaries

Representative FEBio results show:

| FEBio set | Peak displacement | Peak VM max | Interpretation |
|---|---:|---:|---|
| Stage 1 baseline | 35.0 mm | 21.1 kPa | Older dynamic/material baseline |
| Stage 1 projected geometry | 40.4-43.0 mm | 29.2-36.1 kPa | Geometry increased response |
| Stage 2 refined/soft material | 40.3 mm | 29.1 kPa | More compliant response |
| Stage 2 intermediate material | 17.9 mm | 64.3 kPa | Stiffer, lower displacement |
| Stage 2 Chen-inspired material | 14.5 mm | 101.3 kPa | Strong stiffening, high stress |
| Stage 3 support sweep | 17.9-18.6 mm | 62.9-64.9 kPa | Support effect modest |
| Overnight lobule/asymmetry suite | 34.8-36.7 mm | 2.8-3.0 kPa | Useful qualitative benchmark, but not directly comparable |

The key lesson is that the old FEBio model could reach larger displacements, but this was highly dependent on material stiffness and loading route. The stiffer FEBio material cases moved toward the same displacement order as the newer COMSOL high-amplitude scouts.

## Material implementation in FEBio

The old FEBio pipeline wrote material definitions directly to `.feb` XML. Skin, adipose, glandular and pectoralis were represented as Mooney-Rivlin materials. The source code used:

```text
skin:       density 1100 kg/m3, K 8.33 MPa, c1 41667 Pa, c2 41667 Pa
adipose:    density 950 kg/m3,  K 425 kPa,  c1 310 Pa,   c2 300 Pa
glandular: density 1070 kg/m3, K 425 kPa,  c1 833 Pa,   c2 834 Pa
pectoralis: density 1050 kg/m3, K 425 kPa, c1 950 Pa,   c2 717 Pa
```

Some FEBio Stage 2 calibration cases deliberately used softer/intermediate material values:

```text
stage2 intermediate skin:       c1 20833 Pa, c2 20833 Pa
stage2 intermediate adipose:    c1 250 Pa,   c2 240 Pa
stage2 intermediate glandular:  c1 600 Pa,   c2 500 Pa
```

FEBio also supported analytic spatial material expressions. Heterogeneous glandular patterns and tumor overlays could be written as coordinate-based math expressions in density, `c1`, and `c2`. Tumor was not a separate explicit domain in that route; it modified material properties inside a spherical mask.

Approximate small-strain stiffnesses:

| FEBio material setting | Approx. E |
|---|---:|
| Default skin | 497 kPa |
| Stage 2 intermediate skin | 249 kPa |
| Default adipose | 3.7 kPa |
| Stage 2 intermediate adipose | 2.9 kPa |
| Default glandular | 10.0 kPa |
| Stage 2 intermediate glandular | 6.6 kPa |
| Default pectoralis | 10.0 kPa |

## Material implementation in COMSOL

The COMSOL pipeline now carries the source-case material settings into the COMSOL builder. The active Stage 5/6 reference TOMLs use essentially the fixed/default material set:

```text
skin:       density 1100 kg/m3, K 8.33 MPa, c1 41667 Pa, c2 41667 Pa
adipose:    density 950 kg/m3,  K 425 kPa,  c1 310 Pa,   c2 300 Pa
glandular: density 1070 kg/m3, K 425 kPa,  c1 833 Pa,   c2 833 Pa
chest wall: density 1050 kg/m3, E 10 kPa, nu 0.49
```

The COMSOL builder attempts to create Mooney-Rivlin hyperelastic features for adipose and glandular tissue, and uses Rayleigh mass damping with the configured `dynamic_mass_damping_alpha_s_inv`. The helper `material_mapping.py` also computes a linear elastic approximation from the same Mooney-Rivlin parameters:

```text
G ~= 2 * (c1 + c2)
E = 9*K*G / (3*K + G)
nu = (3*K - 2*G) / (2*(3*K + G))
```

So the current COMSOL material input is not completely different from FEBio. The larger difference is that the active COMSOL dynamic runs currently leave the skin shell physics disabled, and use a fixed-support acceleration pulse instead of the older FEBio prescribed displacement/jump route.

Approximate COMSOL active stiffnesses:

| COMSOL active material | Approx. E | Active in current dynamic runs? |
|---|---:|---|
| Skin shell source value | 497 kPa | No, shell disabled in active Stage 1-6 runs |
| Adipose | 3.7 kPa | Yes |
| Glandular | 10.0 kPa | Yes |
| Chest wall surrogate | 10.0 kPa | Yes |

## Why COMSOL moves less than some FEBio cases

The lower COMSOL displacement is probably not caused by one single parameter. The most likely contributors are:

1. Different loading: COMSOL uses a fixed-support acceleration pulse; FEBio cases used displacement/jump-style boundary motion.
2. Different geometry: COMSOL Stage 2-5 uses the xoffset055 chestwall and smaller approximately 585 ml volume, while COMSOL Stage 1 and some FEBio cases used different/simpler shapes.
3. Different material state: COMSOL active tissue values are closer to the stiffer/default material set than to the softer FEBio baseline.
4. Different skin/support status: COMSOL currently has no active skin shell, while FEBio represented skin as a shell domain in the source model.
5. Different evaluation metric: COMSOL report tables emphasize review-time average/surface metrics, while FEBio summaries often report peak maximum displacement.

Therefore, it is safer to write that COMSOL currently gives a stiffer/quieter response under the selected diagnostic excitation, not that the model is wrong.

## Higher acceleration versus softer materials

It is useful to test higher `g` values, but higher acceleration should not be the only calibration knob. If the goal is to produce breast motion closer to reported human motion amplitudes, there are two legitimate sensitivity axes:

### Dynamic excitation sensitivity

Increasing the acceleration amplitude tests whether the EWS-style surface response becomes measurable under stronger but still controlled excitation. This is useful for device-sensitivity reasoning.

However, a high acceleration should be labelled as diagnostic acceleration excitation unless the input is tied carefully to measured torso/platform acceleration.

### Material sensitivity

Testing softer adipose/glandular settings is also useful. The FEBio Stage 2 material ladder already showed that softer materials can produce much larger displacement. This is scientifically valuable because real breast tissue stiffness varies strongly between subjects, loading conditions and measurement protocols.

A good report interpretation would be:

> The model response depends on both excitation amplitude and tissue stiffness. Higher acceleration explores measurement sensitivity under stronger motion, while softer material variants explore patient/material uncertainty. Both are valid sensitivity studies, but neither should be tuned alone to force a target displacement.

Recommended COMSOL material sensitivity:

| Variant | Purpose |
|---|---|
| Current fixed/default material | Main reproducible reference |
| FEBio intermediate-like material | Softer comparison; checks whether COMSOL can reproduce older displacement order |
| Chen/stiffer material | Upper stiffness diagnostic; likely lower displacement and higher stress |
| Skin-on material/reference | Checks whether active skin shell changes surface motion enough to require reruns |

## What should be rerun?

Do not rerun everything immediately. The efficient order is:

1. Build-only skin-on Stage 5 no-Cooper reference.
2. One dynamic skin-on scout for Stage 5 no-Cooper at the chosen excitation.
3. One softer-material COMSOL scout, preferably no-Cooper and no-tumor first.
4. Only after those scouts decide whether final tumor cases need skin-on and/or softer-material variants.

If skin-on changes displacement or surface patterns substantially, final Stage 6 tumor conclusions should be based on skin-on runs. If it fails or is too unstable, keep the no-skin-shell model as the main stable baseline and report skin as an important limitation/future improvement.

## Report wording suggestion

Suggested wording:

> The previous FEBio model is used as a historical benchmark rather than direct validation. It demonstrated that material stiffness and geometry strongly affect breast displacement and stress. The current COMSOL model uses a more explicit staged anatomy, xoffset055 chestwall geometry, realistic glandular lobule placement, and surface-oriented postprocessing for the EWS use case. Active COMSOL Stage 1-6 dynamic runs currently omit a mechanically active skin shell for robustness, so skin remains a required sensitivity step before final absolute displacement claims. The material parameters are conceptually inherited from the same Mooney-Rivlin source-case framework, but the COMSOL runs use a different dynamic input and currently emphasize diagnostic surface response rather than exact reproduction of the older FEBio jump response.

## Sources in this repository

- `analysis_output/comsol_pipeline/tier1_comparison/tables/summary_results.csv`
- `analysis_output/comsol_pipeline/stage5_dynamic_amplitude_scout/tables/review_metrics.csv`
- `analysis_output/figures_Febio_pipeline/comparison_all_models/compare_summary.csv`
- `analysis_output/figures_Febio_pipeline/comparison_stage2_material_ladder/compare_summary.csv`
- `analysis_output/figures_Febio_pipeline/comparison_stage3_support_sweep/compare_summary.csv`
- `runs/comsol_runs/geometry_stage5/stage5_reference_no_cooper_xoffset055_025g_preview.toml`
- `runs/febio_runs/geometry_stage2/stage2_reference_intermediate_materials/stage2_reference_intermediate_materials.toml`
- `src/ews_fem_pipeline_clean/prepare_simulation/simulation_settings.py`
- `src/ews_fem_pipeline_comsol/script_builder.py`
- `src/ews_fem_pipeline_comsol/material_mapping.py`
