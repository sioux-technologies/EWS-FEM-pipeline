# Tier 1 Case Definition Summary

This table explains what is actually different between the Tier 1 comparison cases. It is meant to be read together with `summary_results.csv` and the Tier 1 figures.

| Case | Main purpose | Geometry / model change versus previous row | Dynamic input | What should change in plots? | Current interpretation |
|---|---|---|---|---|---|
| Stage 1 0.25g baseline | Motion sanity baseline | Simple baseline geometry, larger breast volume, simple glandular setup, no selected x-offset chestwall route | Fixed-support acceleration pulse, 0.25g for 0.60 s | Can differ strongly from later stages | Not a clean anatomical comparator for Stage 2-5. It is mainly useful to validate the 0.25g dynamic motion route. |
| Stage 2 xoffset055 chestwall | Selected chestwall geometry | Adds transverse volume-preserving chestwall with +55 mm x-offset and projected-normal auto-alignment | Same 0.25g pulse | Large change versus Stage 1 is expected because volume/support geometry differs | This is the first fair geometry baseline for later anatomical stages. |
| Stage 3 realistic glandular | Glandular realism reference | Keeps Stage 2 chestwall, replaces/simple-extends glandular representation with realistic chestwall-aware lobule spread | Same 0.25g pulse | Moderate or small change versus Stage 2 depending on mass/stiffness distribution | This is the main current anatomical glandular reference, but still should be described carefully if solver/postprocess robustness remains a limitation. |
| Stage 4 realistic reference | Reference for asymmetry stage | Intentionally keeps the same geometry as Stage 3 reference: no profile asymmetry, no nipple shift | Same 0.25g pulse | Almost no change versus Stage 3 is expected | This is a baseline/control for later Stage 4 asymmetry cases, not a new sensitivity by itself. |
| Stage 5 no-Cooper control | No-Cooper control for Cooper stage | Intentionally keeps the same Stage 3/4 reference geometry and disables Cooper scaffold | Same 0.25g pulse | Almost no change versus Stage 4 reference is expected | This is the control case for Stage 5 Cooper comparisons. It should only differ clearly once a stable Cooper case is added. |

## Why Stage 3-5 Look Almost The Same

Stage 4 realistic reference and Stage 5 no-Cooper control are deliberately control cases. In the current Tier 1 comparison:

- Stage 4 reference has `profile_asymmetry_enabled = false`.
- Stage 5 no-Cooper has `enable_cooper_ligament_scaffold = false` and `cooper_ligament_variant = "none"`.
- Both keep the same xoffset055 chestwall, realistic reference lobule spread, and 0.25g dynamic input.

Therefore, Stage 3, Stage 4 reference, and Stage 5 no-Cooper are expected to be very similar. The current summary values confirm this:

| Case | Breast volume (ml) | Glandular fraction (%) | Review avg displacement (mm) | Review surface dynamic w (mm) | Breast mean VM (kPa) | Breast max VM (kPa) |
|---|---:|---:|---:|---:|---:|---:|
| Stage 3 realistic glandular | 585.087 | 24.308 | 2.998 | 0.161 | 0.324 | 1.674 |
| Stage 4 realistic reference | 585.087 | 24.309 | 2.997 | 0.161 | 0.324 | 1.633 |
| Stage 5 no-Cooper control | 585.087 | 24.309 | 2.998 | 0.161 | 0.324 | 1.615 |

## What Is Still Missing For A Real Stage 5 Effect

The current Stage 5B default Cooper run is not report-ready because it failed almost immediately at `t = 2.148e-6 s`. Therefore the Tier 1 figures currently do not yet show a valid Cooper-support effect. A stable mild Cooper run is needed before Stage 5 can be interpreted as a mechanical support sensitivity.

