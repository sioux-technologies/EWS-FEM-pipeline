# Literature benchmark for COMSOL FEM stress and displacement

This note summarizes literature ranges that can be used as a sanity check for the current COMSOL FEM pipeline. These values should not be treated as direct validation targets unless the load case, posture, boundary conditions, and tissue definitions match the model.

## Why von Mises stress dropped in the width-curved chestwall cases

The large reduction in von Mises stress in the current width-curved Stage 2 cases is mechanically plausible in direction, but probably too strong in magnitude.

Likely causes:

1. **The flat slab creates a posterior stress concentration.**  
   The slab support produces a relatively sharp posterior attachment/interface. This can create a local bending/stress band near the posterior/superior breast region. Because the reported value is a maximum von Mises stress, a small local concentration can dominate the result.

2. **The curved chestwall distributes support over a smoother surface.**  
   The transverse curvature makes the breast rest on a smoother posterior surface. This reduces the local lever arm and spreads reaction forces over a broader geometry, so the maximum stress drops strongly.

3. **The current curvature is not volume preserving.**  
   The curved variants reduce breast volume:
   - slab: 718.72 mL
   - mild: 666.58 mL
   - medium: 626.23 mL
   - strong: 579.97 mL

   Because body force and inertial force scale with mass/volume, less volume means less load. This makes the stress reduction partly a geometry/support effect and partly a mass/volume effect. *Now fixed in the model --> volume-preserving*

4. **Maximum von Mises stress is sensitive to local numerical details.**  
   Max stress depends strongly on boundary-condition localization, geometry corners, element order, selections, and whether the stress is evaluated at a local hotspot. For reporting, use both maximum stress and a visual/qualitative stress distribution; ideally add average or percentile stress later.

Interpretation for the current model:
- The direction of the effect is defensible: curved support reduces posterior stress concentration.
- The size of the effect is suspiciously large, especially slab ~11.8 kPa to mild ~1.7 kPa at `t=1.125 s`.
- The mild curvature is still the most defensible current Stage 2 variant, but the next technical improvement should be a volume-preserving curvature implementation.

## Current model values for comparison

Shared review time: `t = 1.125 s`

| Case | Max displacement | Breast VM | Gland VM | Notes |
|---|---:|---:|---:|---|
| fixed-material baseline order1 | 12.245 mm | 11.183 kPa | 3.605 kPa | No Cooper scaffold |
| Stage 5B order1 | 11.910 mm | 11.772 kPa | 3.546 kPa | Glandular-to-skin Cooper |
| Stage 2 slab order2 | 11.910 mm | 11.771 kPa | 3.528 kPa | Stage 5B Cooper, slab support |
| Stage 2 mild order2 | 10.229 mm | 1.682 kPa | 1.682 kPa | Width-curved, volume reduced |
| Stage 2 medium order2 | 8.920 mm | 1.648 kPa | 1.648 kPa | Width-curved, volume reduced |
| Stage 2 strong order2 | 7.744 mm | 1.561 kPa | 1.561 kPa | Width-curved, volume reduced |

## Literature ranges

### Dynamic breast motion during running

Unsupported or low-support dynamic breast motion is much larger than the current COMSOL model because the current simulation uses a small jump/early-warning-like dynamic excitation rather than full running.

Reported ranges:
- Walking/running sensor study: vertical breast displacement was reported as about 11-25 mm during walking and 43-68 mm during running.
- Sports/activity literature: unsupported breast vertical displacement has been reported around 4 cm during walking and up to 10 cm during running.
- A 2025 activity comparison cites running around 50 mm vertical displacement and jumping around 87 mm; it also reports running medial-lateral displacement of 15.72-49.17 mm and superior-inferior displacement of 9.73-36.61 mm.

Interpretation for this model:
- Current peak displacement around 8-13 mm is lower than typical unsupported running.
- That is not automatically wrong because the current model is not a full running model and has a fixed chestwall/support condition.
- If the intended early-warning scan movement is mild, 8-13 mm can be plausible. If the intended motion is closer to unsupported running, the current model is under-moving.

Sources:
- Scurr et al.-style breast motion summary in skin strain paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC7365429/
- Fabric sensor breast motion study summary: https://www.sciencedirect.com/science/article/abs/pii/S0021929007000632
- Activity comparison summary: https://journals.sagepub.com/doi/10.1177/15589250251352192

### Prone-to-supine MRI displacement

Prone-to-supine repositioning produces very large anatomical displacement, especially for nipple and lesion positions.

Reported values:
- Lesion displacements: approximately 60 ± 38 mm anterior-posterior, 40 ± 26 mm latero-medial, 41 ± 33 mm cranio-caudal, and 32 ± 31 mm relative to thoracic wall/pectoral muscle.
- Nipple displacements: approximately 84 ± 44 mm anterior-posterior, 54 ± 24 mm latero-medial, 27 ± 15 mm cranio-caudal, and 48 ± 20 mm relative to thoracic wall/pectoral muscle.

Interpretation for this model:
- These values are posture-transfer displacements, not small dynamic scan displacements.
- They show that the breast can deform by centimeters under posture change, but they are not a direct target for a fixed-chestwall dynamic model.

Source:
- https://pubmed.ncbi.nlm.nih.gov/22502792/

### Mammography/mechanical imaging stress

Mechanical imaging and mammography-like compression produce stresses in the same broad kPa range as the slab/report cases, but the load case is much stronger and more direct than the current dynamic model.

Reported values:
- A finite element mechanical imaging model reported average stress of 6.2-6.5 kPa over the breast surface and 7.8-11.4 kPa at lesion locations.
- A simulated compression phantom study reported pressure ranges of 2.76-22.06 kPa under broad compression.
- A palpation/self-examination FE model used an applied pressure of 10 kPa and healthy breast tissue Young's modulus around 7 kPa.

Interpretation for this model:
- Current slab/report breast VM around 11-12 kPa is in the same order of magnitude as compression/mechanical-imaging studies.
- Current mild/medium/strong curved VM around 1.6-1.7 kPa is much lower than typical compression stress and may be low if interpreted as a strongly loaded dynamic model.
- However, without external compression plates, a lower stress than mammography is expected.

Sources:
- Mechanical imaging FE model: https://portal.research.lu.se/en/publications/finite-element-model-of-mechanical-imaging-of-the-breast/
- Compression phantom pressure abstract: https://pubmed.ncbi.nlm.nih.gov/7824714/
- Palpreast FE model: https://www.mdpi.com/2076-3417/9/3/381

### Dynamic FE stress in internal breast components

A recent multi-component dynamic FE model of breast motion during running reports stress ranges by component:

- Cooper ligaments: anterior side about 1.68-19.17 kPa; posterior side about 4.41-30.95 kPa.
- Adipose tissue near glandular tissue/Cooper ligaments: about 8.01-15.9 kPa.
- Pectoralis major muscle areas: about 0.10-5.21 kPa.
- Glandular tissue: higher posterior/bottom regions reaching about 3.41 kPa and 2.92 kPa.

Interpretation for this model:
- Current slab/report glandular VM around 3.5 kPa matches the reported glandular stress order of magnitude.
- Current slab/report breast VM around 11-12 kPa matches the reported adipose-region order of magnitude.
- Current curved VM around 1.6-1.7 kPa is closer to low glandular/pectoral stress than adipose or Cooper ligament stress.

Sources:
- Dynamic multi-component FE breast model: https://pmc.ncbi.nlm.nih.gov/articles/PMC11584448/
- PDF copy/metadata snippets with component stress ranges: https://ira.lib.polyu.edu.hk/bitstream/10397/108836/1/s10237-024-01862-2.pdf

### Subject-specific shape matching / validation error

Subject-specific FE breast models are often judged by how well the deformed geometry matches imaging data, not only by stress magnitude.

Reported values:
- A biomechanical breast model evaluated against MRI in prone, supine and tilted configurations reported Hausdorff distances of 2.17 mm, 1.72 mm and 5.90 mm respectively.
- A 3D structured-light scanning system reported average geometric accuracy within 0.4 mm on a phantom/model comparison; volume analysis differences around 0.1% for their controlled setup.

Interpretation for this model:
- For an Early Warning Scan direction, shape/displacement validation against scan geometry would be more meaningful than matching one absolute stress value.
- A realistic future target would be surface error in the low-mm range if scan comparison becomes available.

Sources:
- Subject-specific FE breast model: https://arxiv.org/abs/1811.10221
- Structured-light breast scanning: https://www.nature.com/articles/s41598-020-70476-2

## Why volume preservation matters

Volume preservation is important because breast tissue is nearly incompressible and because the comparison goal is to isolate the effect of chestwall shape.

Reasons:

1. **Physical realism.**  
   Soft breast tissues are commonly modeled as nearly incompressible. A geometry operation that removes 7-19% of total breast volume is not just changing the support surface; it is changing the body being simulated.

2. **Mass and inertia.**  
   Dynamic loading depends on mass. If volume drops from 718.72 mL to 579.97 mL, the strong curvature case has about 19% less tissue mass. That alone reduces gravitational/inertial forces and can reduce displacement/stress.

3. **Fair comparison.**  
   To claim that curvature reduces stress, the breast volume, glandular fraction, material parameters, mesh settings and Cooper settings should stay similar. Otherwise the observed difference may be caused by reduced volume rather than improved chestwall support.

4. **Glandular/adipose ratio.**  
   The current curvature changes total breast volume and slightly changes glandular percentage. Since adipose and glandular tissue have different material properties, this affects stiffness and stress distribution.

5. **Report defensibility.**  
   A reviewer/supervisor can reasonably ask: "Did the stress go down because the chestwall is more anatomical, or because the model contains less breast tissue?" A volume-preserving curvature removes that ambiguity.

Practical threshold:
- Try to keep total breast volume within roughly 1-3% of the slab reference for a clean geometry comparison.
- If that is not possible yet, present the current mild/medium/strong cases explicitly as curvature-plus-volume sensitivity cases.

