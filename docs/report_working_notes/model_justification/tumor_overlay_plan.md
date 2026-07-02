# Stage 6 Tumor/Lesion Plan

Date: 2026-05-26

## Purpose

Stage 6 adds a first controlled tumor/lesion sensitivity layer on top of the current best anatomical COMSOL route:

- Stage 2 selected xoffset055 transverse chestwall, volume-preserving and auto-aligned.
- Stage 3 realistic reference glandular lobule spread.
- Stage 4/5 no-asymmetry and no-Cooper control geometry.
- Stage 1 0.25g fixed-support acceleration pulse.

The first Stage 6 route is deliberately conservative. Tumor cases should be generated and build-only checked first. Full dynamic solves should only be run after placement, geometry, selections, and planned metrics have been inspected.

## Current Implementation

The current COMSOL tumor path is an analytic spherical material overlay:

- `tumor_mask = 1` inside a sphere and `0` elsewhere.
- The mask modifies density and Mooney-Rivlin coefficients inside existing adipose/glandular domains.
- It does not create a separate Boolean tumor domain.
- It does not create a separate COMSOL tumor selection.
- Tumor-local metrics are computed by integrating `tumor_mask * expression` over `geom1_breast_union_dom`.

This is appropriate for first-order stiffness/location sensitivity. It should not be described as a segmented anatomical tumor domain.

## Build-Only Cases

Report/control:

- `stage6_tumor_control_xoffset055_025g_preview.toml`: same reference geometry, tumor disabled.

Size sweep:

- `stage6_tumor_small_central_xoffset055_025g_preview.toml`: 6 mm diameter central lesion.
- `stage6_tumor_medium_central_xoffset055_025g_preview.toml`: 12 mm diameter central lesion.
- `stage6_tumor_large_central_xoffset055_025g_preview.toml`: 20 mm diameter central lesion; use as upper-end diagnostic sensitivity, not as the first routine solve.

Location sweep:

- `stage6_tumor_small_central_xoffset055_025g_preview.toml`: central glandular-region probe.
- `stage6_tumor_small_upper_outer_xoffset055_025g_preview.toml`: superior-lateral/upper-outer style probe.
- `stage6_tumor_small_upper_outer_surface_proximal_xoffset055_025g_preview.toml`: 6 mm superior-lateral/upper-outer probe moved anteriorly toward the inner breast surface; candidate position `[0.025, 0.060, 0.018] m`.
- `stage6_tumor_small_upper_outer_superior_xoffset055_025g_preview.toml`: 6 mm superior-lateral/upper-outer probe moved superiorly; candidate position `[0.025, 0.050, 0.040] m`.
- `stage6_tumor_medium_upper_outer_surface_proximal_xoffset055_025g_preview.toml`: 12 mm surface-proximal upper-outer size-sensitivity case; candidate position `[0.025, 0.056, 0.018] m`.
- `stage6_tumor_medium_upper_outer_superior_xoffset055_025g_preview.toml`: 12 mm superior upper-outer size-sensitivity case; candidate position `[0.025, 0.046, 0.040] m`.
- `stage6_tumor_small_subareolar_xoffset055_025g_preview.toml`: anterior/subareolar probe.
- `stage6_tumor_small_posterior_xoffset055_025g_preview.toml`: posterior/chestwall-proximal probe.

Stiffness sweep:

- `stage6_tumor_stiffness_mild_xoffset055_025g_preview.toml`: modestly elevated tumor coefficients.
- `stage6_tumor_stiffness_stiff_xoffset055_025g_preview.toml`: stronger diagnostic stiffness contrast.

## Required Checks Before Solving

For every candidate:

- Confirm the generated builder has `tumor_enabled = 1` for tumor cases and `0` for the control.
- Confirm `tumor_radius`, `tumor_x`, `tumor_y`, and `tumor_z` match the case definition.
- Inspect `*_comsol_selection_hints.json`; expect tumor metadata under `tumor_material_overlay`, not a separate tumor domain.
- After build-only, open the generated MPH and inspect the scalar variable `tumor_mask` or an isosurface/volume plot of `tumor_mask > 0.5`.
- Confirm the tumor sphere lies inside the breast union and does not visibly intersect skin/nipple/chestwall unless intentionally diagnostic.
- For glandular-region cases, compare the tumor position against the realistic lobule layout; if overlap is unclear, treat the case as a tissue-location sensitivity rather than a glandular tumor claim.

## Later Postprocess Metrics

The generated postprocess scaffold now includes tumor-mask metrics for solved cases:

- `tumor_volume`
- `max_displacement_tumor`
- `avg_displacement_tumor`
- `max_von_mises_tumor`
- `avg_von_mises_tumor`
- tumor displacement/stress time series

These are mask-based local metrics, not separate-domain metrics. If the measured `tumor_volume` is near zero, the placement is outside the breast or the mask was not evaluated correctly.

## Literature Rationale For Initial Tumor Choices

Location:

- Multiple breast-cancer location studies report the upper-outer quadrant as the most frequent site. Large database studies commonly report the upper-outer quadrant as the leading category; examples include about `39.5%`, `57%`, or higher depending on cohort and classification.
- Central/subareolar and inner-quadrant tumors are less frequent than upper-outer tumors, but remain useful sensitivity probes because they can affect nipple/landmark response and may have different detectability.
- Therefore the first location sweep should include an upper-outer style case, but central/subareolar/posterior cases remain useful as EWS sensitivity probes because they test landmark response and chestwall-proximal detectability.

Size:

- TNM staging defines T1 breast tumors as 20 mm or smaller, with T1a above 1-5 mm, T1b above 5-10 mm, and T1c above 10-20 mm.
- Screening studies commonly report screen-detected tumors around the 8-13 mm median range, while non-screen-detected tumors tend to be larger.
- The Stage 6 size sweep therefore uses 6 mm diameter as a small early lesion, 12 mm as a medium T1c-style lesion, and keeps 20 mm as a later diagnostic upper bound only after geometry checks.

Shape:

- ACR BI-RADS descriptors include round, oval, and irregular mass shapes, with margins such as circumscribed, irregular, or spiculated.
- The first Stage 6 implementation uses a spherical material overlay because it is the cleanest FEM sensitivity probe and easiest to validate against the `tumor_mask`.
- A later Stage 6B should add ellipsoidal and possibly irregular/spiculated visual geometry only after the spherical route is build-stable and measurable.
- In the current COMSOL code, the active mechanical tumor is still a sphere: `tumor_mask = 1` for `(x-tumor_x)^2 + (y-tumor_y)^2 + (z-tumor_z)^2 <= tumor_radius^2`. Shape testing therefore needs a small code extension before it can be interpreted mechanically.
- The most defensible next shape step is an ellipsoid in the upper-outer case, because it stays smooth and build-stable while representing the oval/elongated mass descriptor used in imaging. A practical first ellipsoid would preserve the same volume as the 6 mm sphere but use a mild aspect ratio such as `1.5:1.0:1.0`.
- A second, more diagnostic step is an irregular/lobulated upper-outer lesion. This can be approximated by a union of overlapping small ellipsoids or by a perturbed analytic mask. It should be described as irregular-shape sensitivity, not as patient-specific spiculation.
- True spiculated margins are clinically important descriptors, but they are geometrically and numerically more difficult. In this project they should be treated as a later visual/diagnostic extension, because small sharp protrusions can strongly affect mesh quality and local stress.

Surface-proximal/skin-adjacent lesions:

- Superficial breast tumors are clinically relevant, and recent surgical/imaging studies explicitly evaluate tumor-to-skin or tumor-to-dermis distance. This supports a Stage 6 surface-proximal lesion as a useful sensitivity case.
- A tumor placed close to the inner breast surface is not the same as a tumor with true skin invasion. NCI TNM staging treats direct extension to skin with ulceration, skin nodules, or swelling as T4b, which is a different clinical interpretation than a small early internal lesion.
- Published work reports skin involvement in roughly `4.4-11.3%` of breast cancer cases, while tumor-to-skin distance is studied because close tumors can matter surgically and biologically. Therefore a surface-proximal/bump case is defensible as a diagnostic sensitivity, but should not be the default Stage 6 reference case.
- A visible external bump in this COMSOL model would require the lesion to deform or alter the `breast_union` surface. The current analytic material overlay does not change the baseline geometry, so it can represent a stiff internal lesion but cannot by itself create a pre-existing geometric bulge.
- If a visible bump is added later, it should be a separate `Stage 6B surface-proximal bulge` geometry case: place a smooth ellipsoid just under the skin in the upper-outer region, gently blend or add a small outward surface perturbation, and keep a matched no-bulge surface-proximal control. That case should be described as diagnostic/advanced, not as a routine early tumor.

Stiffness:

- Elastography literature generally reports malignant lesions as substantially stiffer than normal tissue or benign lesions, but values vary strongly by modality, lesion type, ROI, and surrounding tissue. Published values often span from tens of kPa to more than 100 kPa.
- Use the current mild/stiff material variants as order-of-magnitude sensitivity cases, not as calibrated pathology. In the current Mooney-Rivlin scaffold, the `stiff` case is approximately `30 kPa` by the small-strain estimate `E ~= 6*(coef1+coef2)`, so a later stronger `~100 kPa` tumor-material target is still useful.

Useful paper sources:

- TNM staging overview for breast cancer: https://www.cancer.gov/types/breast/stages/tnm-staging-system
- UOQ frequency examples: https://pmc.ncbi.nlm.nih.gov/articles/PMC7569667/ and https://pmc.ncbi.nlm.nih.gov/articles/PMC5876694/
- Screen-detected size examples: https://pmc.ncbi.nlm.nih.gov/articles/PMC3326576/ and https://pubmed.ncbi.nlm.nih.gov/34218078/
- Elastography stiffness examples: https://pmc.ncbi.nlm.nih.gov/articles/PMC4687021/ and https://pmc.ncbi.nlm.nih.gov/articles/PMC6223289/
- Surface-proximal tumor examples: https://pubmed.ncbi.nlm.nih.gov/37261133/ and https://pubmed.ncbi.nlm.nih.gov/37098931/
- Skin involvement / surface disease context: https://pubmed.ncbi.nlm.nih.gov/25026875/ and https://pmc.ncbi.nlm.nih.gov/articles/PMC9545220/

Useful clinical/reference sources that are not ordinary journal papers:

- ACR BI-RADS reference/lexicon material: https://cs.acr.org/Clinical-Resources/Reporting-and-Data-Systems/Bi-Rads
- ACR BI-RADS quick reference card for mass shape/margin terminology: https://cs.acr.org/-/media/ACR/Files/RADS/BI-RADS/BIRADS-Reference-Card.pdf
- UCLA Radiology BI-RADS ultrasound mass descriptor summary: https://www.uclahealth.org/departments/radiology/education/breast-imaging-teaching-resources/birads/ultrasound-masses

## Suggested Later Stage 6B Shape/Surface Cases

These cases should be generated build-only first and should use the upper-outer tumor location unless there is a specific reason to test another site:

1. `upper_outer_sphere_6mm`: current reference shape; keep as the clean mechanical baseline.
2. `upper_outer_ellipsoid_volume_matched`: smooth oval/ellipsoid lesion with the same volume as the 6 mm sphere; recommended first shape sensitivity.
3. `upper_outer_ellipsoid_flat_surface_parallel`: elongated parallel to the local skin surface; useful for testing orientation relative to breast-surface motion.
4. `upper_outer_irregular_lobulated`: diagnostic irregular shape, preferably as a smooth multi-lobule union rather than sharp spicules.
5. `upper_outer_surface_proximal`: same size/shape but moved close to the inner skin surface; useful for tumor-to-skin-distance sensitivity.
6. `upper_outer_surface_bulge_diagnostic`: optional geometry-perturbation case where the breast surface has a small visible outward bump. Use only after the non-bulge surface-proximal case is stable.

The recommended order is sphere -> ellipsoid -> surface-proximal ellipsoid -> optional bulge. Spiculated or sharply irregular lesions should wait until the smooth ellipsoid route is stable, because they can make local stress and mesh quality difficult to interpret.

## Recommended First Full Solves

Only after build-only inspection:

1. Control/no tumor.
2. Small central tumor.
3. Small upper-outer tumor.
4. Small subareolar tumor.
5. Small posterior tumor.
6. Mild or stiff central tumor, depending on whether the central placement looked clean.

Do not run all size/location/stiffness cases overnight until the first two or three tumor cases show stable geometry and meaningful tumor-mask volume.

## Current Retained Stage 6 Route After Cleanup

After the Stage 6 cleanup on 2026-06-01, the active run folder intentionally keeps only the current 1.25g diagnostic-excitation tumor scouts. Earlier 0.25g, fast, build-only, and legacy tumor TOMLs/outputs were moved to `_archive_stage6_old_tumor_scouts_2026-06-01` and may be deleted after confirming that this note and the screenshots below are sufficient for provenance.

Active retained TOMLs:

- `stage6_tumor_medium_upper_outer_surface_proximal_xoffset055_125g_solve_only_preview.toml`
  - Purpose: primary Stage 6 tumor scout.
  - Dynamic input: 1.25g diagnostic fixed-support acceleration excitation, 0.60 s pulse.
  - Geometry basis: Stage 5 no-Cooper xoffset055 realistic reference geometry.
  - Tumor: analytic spherical material overlay, 12 mm diameter.
  - Tumor center: `[0.025, 0.056, 0.018] m`.
  - Interpretation: upper-outer, surface-proximal lesion sensitivity. This is the preferred first tumor-vs-no-tumor dynamic comparison against the Stage 5 no-tumor 1.25g control.

- `stage6_tumor_large_central_xoffset055_125g_solve_only_preview.toml`
  - Purpose: diagnostic upper-bound lesion-size scout.
  - Dynamic input: 1.25g diagnostic fixed-support acceleration excitation, 0.60 s pulse.
  - Geometry basis: Stage 5 no-Cooper xoffset055 realistic reference geometry.
  - Tumor: analytic spherical material overlay, 20 mm diameter.
  - Tumor center: `[0.0, 0.043, 0.0] m`.
  - Interpretation: large central lesion sensitivity. Use after the medium upper-outer case, not as the first report-ready tumor claim.

Other visually checked Stage 6 candidate placements retained in screenshots:

- Small upper-outer surface-proximal: 6 mm diameter, candidate center `[0.025, 0.060, 0.018] m`.
- Small upper-outer superior/surface candidate: 6 mm diameter, candidate center `[0.025, 0.050, 0.040] m`.
- Medium upper-outer surface-proximal: 12 mm diameter, candidate center `[0.025, 0.056, 0.018] m`.
- Medium upper-outer superior/surface candidate: 12 mm diameter, candidate center `[0.025, 0.046, 0.040] m`.
- Central size sweep screenshots: 6 mm, 12 mm, and 20 mm central spherical overlays.
- Location screenshots: central, upper-outer, subareolar, posterior, and surface-proximal variants.

The corresponding visual evidence is stored under `model_pictures/stage6_tumor`. These screenshots are sufficient for reporting geometry/placement intent even if the old build/run folders are deleted. The key remaining requirement before quantitative Stage 6 claims is a successful dynamic solve and at least global/summary postprocess for the retained 1.25g tumor case.
