# Cooper Ligament / Support Scout Notes

This note records the current COMSOL Cooper/support tests and how they should be interpreted in the report.

## Purpose

The goal is not yet to reconstruct patient-specific Cooper ligaments. The current COMSOL implementation is a diagnostic support scaffold used to test whether additional internal support changes the dynamic breast response. This should be described as a support sensitivity, not as an exact anatomical ligament model.

## Relation to Femke / Sioux HGO Approach

Femke's FEBio route used an HGO-type anisotropic reinforcement in adipose tissue as an implicit Cooper-like support representation. That approach is biomechanically richer than the current COMSOL scaffold because it adds direction-dependent stiffness throughout the adipose domain. It is also harder to validate because fiber direction, dispersion, and HGO parameters must be justified.

An initial COMSOL Java API probe for an HGO-like adipose reinforcement was attempted as a build-only diagnostic. The expected HGO adipose physics/material feature did not appear in the generated COMSOL model, so this route was removed from the active pipeline and should remain future work. A future implementation would require direct confirmation of the correct COMSOL anisotropic hyperelastic Java feature and a validated fiber-direction definition before it can be used for results.

The current COMSOL route instead uses explicit scaffold variants:

- `glandular_to_skin`
- `nipple_to_chestwall`
- `dense_network`

These are simpler and easier to compare, but they should be interpreted as mechanical support surrogates.

## Baseline Used for Fast Scouts

The first systematic Cooper scouts use the fast Stage 5 simple-gland baseline:

- simple glandular structure;
- selected xoffset055 chestwall geometry;
- 1.5 mm volumetric skin layer;
- Femke-like soft skin coefficients (`C10 = C01 = 1200 Pa`, `K = 480 kPa`);
- soft interior values (`adipose C10/C01 = 109/106 Pa`, `glandular C10/C01 = 230/195 Pa`);
- 1.25g diagnostic fixed-support acceleration pulse;
- no automatic postprocess; manual Derived Values are used.

This baseline is a computational scout, not the final anatomical model.

## Completed Mild Direction Scout

Manual postprocess compared the no-Cooper baseline with three mild scaffold directions using `cooper_ligament_area_fraction = 0.03`.

| Case | Peak avg displacement | Peak max displacement | Peak avg VM | Peak max VM |
|---|---:|---:|---:|---:|
| No Cooper | 22.55 mm | 45.58 mm | 1.065 kPa | 19.283 kPa |
| Cooper glandular-to-skin, area 0.03 | 22.44 mm | 44.99 mm | 1.061 kPa | 19.069 kPa |
| Cooper nipple-to-chestwall, area 0.03 | 22.55 mm | 45.64 mm | 1.065 kPa | 19.273 kPa |
| Cooper dense network, area 0.03 | 22.44 mm | 44.99 mm | 1.061 kPa | 19.069 kPa |

Interpretation: the mild scaffold has almost no global displacement/stress effect in this scout. This suggests that either the scaffold is too weak, the selected global metrics are too coarse, or the current scaffold does not capture the same distributed anisotropic support as Femke's HGO material approach.

## Next Scaffold Scaling Test

To check whether the COMSOL scaffold is active and scalable, two additional `glandular_to_skin` cases were prepared:

| TOML | Scaffold variant | Area fraction | Purpose |
|---|---|---:|---|
| `stage5_scout_simple_gland_cooper_g2skin_area006_volskin_femke_skin_soft_interior_125g_solve.toml` | `glandular_to_skin` | 0.06 | Conservative increase from the mild 0.03 case |
| `stage5_scout_simple_gland_cooper_g2skin_area012_volskin_femke_skin_soft_interior_125g_solve.toml` | `glandular_to_skin` | 0.12 | Previous default-level support fraction |

If 0.06 and 0.12 still show little effect, the current scaffold should remain diagnostic only and an HGO-like anisotropic adipose material should be considered as a better future Cooper/support route.

## Completed Glandular-to-Skin Scaling Test

The 0.06 and 0.12 area-fraction scaling tests were run and manually postprocessed. The response remained very close to the no-Cooper baseline.

| Case | Peak avg displacement | Peak max displacement | Peak avg VM | Peak max VM |
|---|---:|---:|---:|---:|
| No Cooper | 22.55 mm | 45.58 mm | 1.065 kPa | 19.283 kPa |
| Glandular-to-skin, area 0.03 | 22.44 mm | 44.99 mm | 1.061 kPa | 19.069 kPa |
| Glandular-to-skin, area 0.06 | 22.44 mm | 44.97 mm | 1.061 kPa | 19.062 kPa |
| Glandular-to-skin, area 0.12 | 22.43 mm | 44.96 mm | 1.061 kPa | 19.058 kPa |

Interpretation: increasing the scaffold area fraction from 0.03 to 0.12 did not produce a meaningful global displacement or stress change in this simple-gland scout. This suggests that the current COMSOL support scaffold, in its present implementation, is not a strong surrogate for distributed Cooper-like reinforcement. The result supports keeping this scaffold as diagnostic only and treating a future HGO-like anisotropic adipose formulation as the more plausible route for Cooper/support modelling.

## Report Wording

Use cautious wording:

- "Cooper ligament support was explored as a mechanical support sensitivity."
- "The current scaffold implementation did not produce a strong global displacement effect at mild settings."
- "Femke's HGO-style adipose reinforcement is a more distributed anisotropic support concept and may be a better future implementation route, but an initial COMSOL build-only probe did not create a usable HGO feature and this route was therefore left as future work."
