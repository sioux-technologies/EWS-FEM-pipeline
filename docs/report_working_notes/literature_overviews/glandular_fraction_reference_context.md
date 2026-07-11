# Glandular Fraction Recommendations

Date: 2026-05-14

## Purpose

This note defines a simple first COMSOL sensitivity set for glandular richness/fibroglandular tissue fraction. The goal is not to reproduce full BI-RADS anatomy, but to create a clean mechanical sensitivity around the current nipple-aligned Stage 2 volume-preserving chestwall case.

## Literature Context

Breast density describes the relative amount of fibroglandular tissue versus adipose tissue. The key issue for this FEM model is definition: clinical BI-RADS breast-composition wording is often based on mammographic appearance, while this model uses a 3D volume fraction:

- `glandular fraction = glandular volume / total breast volume`

That is why volumetric percentages can look surprisingly low compared with mammographic BI-RADS percentages.

Good sources for the FEM interpretation:

- The CDC describes fibrous + glandular tissue as fibroglandular tissue, states that density is assessed relative to fatty tissue, and notes that women are more likely to have dense breasts when they are younger, pregnant/breastfeeding, using hormone replacement therapy, or have lower body weight ([CDC, 2026](https://www.cdc.gov/breast-cancer/about/dense-breasts.html)).
- Volpara-style volumetric breast density is defined as fibroglandular tissue volume divided by total breast volume. In a European Radiology screening study, VDG thresholds were `<4.5%`, `4.5-7.5%`, `7.5-15.5%`, and `>=15.5%`; the measured VBD range was about `1.9-43.3%`, with median `7.2%` in women aged `40-76` ([Eng et al., European Radiology, 2017](https://link.springer.com/article/10.1007/s00330-016-4309-3)).
- In a very large Dutch screening cohort (`n = 485,021`, median age `60`), Volpara percent dense volume had a geometric mean of `7.25%`; `40.5%` were VDG3/VDG4 and `7.9%` were VDG4, with dense classification decreasing from the youngest to oldest screening groups ([Brandt et al., European Radiology, 2016](https://link.springer.com/article/10.1007/s00330-015-3742-z)).
- A 3D breast CT cohort of women aged `40-74` reported percent breast density decreasing from `21 +/- 21%` in the youngest group to `11 +/- 9%` in the oldest group, with an overall average of `14 +/- 13%` ([Shim et al., Diagnostics, 2023](https://www.mdpi.com/2075-4418/13/21/3343)).
- A 3D MRI study in `321` women reported mean breast volume about `779 cm3`, mean fibroglandular volume about `86 cm3`, and mean percent density about `12.1%`, decreasing with age ([Nie et al., Medical Physics, 2010](https://pmc.ncbi.nlm.nih.gov/articles/PMC2885945/)).
- An MRI segmentation study reported FGT percentages around `13-14%` depending on slice thickness ([Niukkanen et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC6113149/)).
- MRI examples can still be much higher in individual dense breasts: Lu et al. show example subjects with about `20%`, `40%`, and `60%` glandular tissue, which is useful as evidence that high-end sensitivity cases can be meaningful, but not as a population-average default ([Lu et al., Physics in Medicine and Biology, 2012](https://pubmed.ncbi.nlm.nih.gov/23044556/)).

## Modeling Choice

The current nipple-aligned Stage 2 g1050 case has:

- breast volume: about `719.19 mL`;
- glandular volume: about `82.65 mL`;
- glandular fraction: about `11.49%`.

That sits well within reported MRI volumetric averages, so it is a reasonable reference/default case.

For a first simple sensitivity, use:

| Variant | Target interpretation | Approx target FGT fraction | COMSOL shape scale |
| --- | --- | ---: | --- |
| low | adipose-dominant / low fibroglandular volume | about 6% | x/z scale 0.720 |
| reference | current Stage 2 g1050-like reference | about 11.5% | x/z scale 1.000 |
| high | dense volumetric sensitivity | about 20% | x/z scale 1.320 |
| very high | upper-tail / very dense sensitivity, especially for younger or very dense breasts | about 30% | x/z scale 1.616 |

The `20%` case is already above the common Volpara `>=15.5%` dense threshold. The `30%` case is added because this project wants a broad range across women roughly `25-70` years old and because individual volumetric examples can be much higher than the population mean.

For clarity in the report: the model fraction is glandular/total-breast volume. If someone asks for glandular/adipose ratio, the corresponding ratios are approximately:

| Glandular / total breast | Glandular / adipose |
| ---: | ---: |
| 6% | 6.4% |
| 11.5% | 13.0% |
| 20% | 25.0% |
| 30% | 42.9% |

The AP/y gland scale is kept at the Stage 2 g1050 value. The first sensitivity varies only glandular width and height (`x` and `z`) so the anterior nipple/Cooper region is not changed at the same time. This keeps the comparison cleaner than changing every semiaxis at once.

## Caveats

- BI-RADS categories are clinically useful but not directly equal to this model's 3D glandular volume fraction.
- A true realistic glandular model would use a branched/heterogeneous fibroglandular distribution rather than a smooth ellipsoid.
- The high case is a mechanical sensitivity, not a claim that this simple ellipsoid fully represents a clinically extremely dense breast.
- Total breast volume should remain nearly unchanged because the glandular domain is internal and replaces adipose tissue rather than changing the outer envelope.

## Recommended Stage 3 Defaults

Use the reference case as the baseline report continuation from Stage 2. Use low/high as the main sensitivity pair to show how glandular richness affects displacement, glandular motion, and local stress. Use `very high` as an optional upper-tail sensitivity, not as the default breast unless the geometry and solver remain clean.

If the high case creates clipping, mesh issues, or unphysical stress hotspots, reduce the high x/z scale from `1.320` to about `1.200-1.250` and document it as a geometry feasibility limit.

If the very-high case creates clipping, mesh issues, or unphysical stress hotspots, keep it as a failed/limit sensitivity rather than forcing it into the report-ready main comparison.

## Future Faster Realistic-Glandular Route

The current realistic Stage 3 route uses explicit COMSOL lobule/duct ellipsoid primitives. This is useful for model screenshots and for demonstrating that the glandular anatomy can be parameterized, but it is expensive for routine dynamic solves because each primitive can add Boolean work, internal boundaries, mesh complexity, and local mesh-quality risk.

A later faster route should keep the current explicit lobule geometry for visualization, but add an implicit mechanical glandular option for solves. In that option, the breast keeps a simpler glandular region or material assignment while the local stiffness/density field is varied by analytic Gaussian, Perlin/fractal-noise, or Voronoi/compartment-style expressions. This follows the direction used in digital breast phantoms such as VICTRE/OpenVCT, where glandular distribution, compartments, TDLU/duct features, and parenchymal texture are generated procedurally rather than as many separate CAD solids.

Recommended staged implementation:

1. Keep current explicit lobules as the report/visual reference.
2. Add an `implicit_fast` glandular mode with the same target glandular fraction and approximate spatial centre-of-mass as the explicit reference.
3. Validate build-only first by comparing total glandular fraction, sagittal/coronal slices, and tumor overlap.
4. Run one matched 0.25g no-tumor case against the current explicit reference.
5. Only use the implicit mode for tumor sweeps if displacement/stress trends are close enough for screening.

This should be described as a solver-efficiency screening model, not as a replacement for patient-specific segmented fibroglandular anatomy.
