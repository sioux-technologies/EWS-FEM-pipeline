# Material and motion scout strategy for the COMSOL EWS model

Date: 2026-06-02

This note explains how material stiffness and dynamic acceleration amplitude should be tested after adding the new volumetric skin layer. The goal is to choose a motion/material basis that produces a visible but defensible breast surface response before running many Stage 6 tumor cases.

## Why this is needed

The Stage 1 fixed-support 0.25g case produced a visually useful displacement amplitude, but it is not directly comparable to the current Stage 5 anatomy. Stage 1 used:

- simple baseline geometry;
- larger breast volume than the current Stage 2-5 route;
- simple glandular setup;
- no active skin shell;
- no volumetric skin layer;
- old soft FEBio-like material parameters.

Therefore, the good Stage 1 displacement should be interpreted as a motion sanity baseline, not as proof that the current Stage 5 model will move the same way at 0.25g.

The current Stage 5 route is more anatomical, has xoffset055 chestwall support, realistic glandular lobules, and now can include a volumetric solid skin layer. That can reduce displacement substantially compared with Stage 1. The next step should therefore separate three effects:

1. What does the volumetric skin layer do?
2. What does softer internal breast tissue do?
3. What does a higher acceleration amplitude do?

Only after those are understood should tumor cases be interpreted.

## Material sets currently in the pipeline

The COMSOL material scaffold uses a two-coefficient Mooney-Rivlin representation. For near-incompressible small-strain interpretation:

```text
E ~= 6 * (C10 + C01)
```

This is only an approximate comparison value, but it is useful for planning stiffness sweeps.

| Material set | Skin E estimate | Adipose E estimate | Glandular E estimate | Interpretation |
|---|---:|---:|---:|---|
| Current COMSOL/Chen-like reference | ~500 kPa | ~3.66 kPa | ~10.0 kPa | Literature-anchored fixed reference; likely more stable and physically conservative. |
| Old FEBio-like all-soft set | ~14.4 kPa | ~1.29 kPa | ~2.55 kPa | Useful lower-stiffness sensitivity; likely more compliant; not best as final skin-layer default. Some old sources differ in density, so this should not be copied directly as the new COMSOL reference. |
| Proposed hybrid: stiff skin + soft interior | ~500 kPa | ~1.29 kPa | ~2.55 kPa | Best first material-sensitivity route if the current reference under-moves. Keep current COMSOL densities and bulk moduli; soften only adipose/glandular C10/C01. |
| Proposed intermediate interior | ~500 kPa skin, ~100 kPa optional mid-skin | ~2.3-2.5 kPa | ~5 kPa | Useful if all-soft is too compliant but current reference is too stiff. |

## Literature interpretation

Breast tissue stiffness is not a single fixed number. Reported values vary strongly with measurement method, preload, strain level, subject, tissue region, ex-vivo versus in-vivo testing, and constitutive model.

The current COMSOL/Chen-like set is defensible because Chen et al. used multi-component dynamic breast FE modelling and represented soft tissues as nearly incompressible, with adipose Mooney-Rivlin parameters and separate skin/glandular/support components. Their model uses a stiff skin value around 500 kPa and a glandular scale around 10 kPa. This supports the current fixed reference as a literature-based, conservative model baseline.

The old FEBio-like soft interior values are also not automatically wrong. Samani et al. measured normal breast fat and fibroglandular tissue with low-kPa moduli under small deformation, and reviews such as Ramiao et al. emphasize that normal breast tissue stiffness spans a wide range. Magnetic resonance elastography studies also often report low-kPa stiffness for normal breast tissue, although MRE shear stiffness is not directly identical to Young's modulus in a finite-element material law.

The questionable part of the all-soft set is the skin. A separate volumetric skin layer with E ~= 14.4 kPa is probably too soft if it is interpreted as true skin. It may still be useful as a diagnostic upper-compliance case, but for a report-ready skin-layer baseline, a stiffer skin layer is more defensible.

Practical conclusion:

- current stiff skin is more defensible for a separate skin layer;
- soft adipose/glandular values are defensible as a material-sensitivity case;
- all-soft including soft skin should be labelled diagnostic/upper-compliance, not final baseline;
- intermediate material values are justified if the two endpoints are too stiff and too soft.

## Dynamic acceleration interpretation

The acceleration pulse is not a literal jump and not a prescribed platform displacement. It is a smooth inertial excitation in a fixed-support frame. For the current full-sine-like pulse with duration T = 0.60 s, the equivalent smooth platform displacement scale is approximately:

```text
s_peak ~= a_max * T^2 / (2*pi^2)
```

Approximate scales:

| Amplitude | Equivalent platform-like displacement scale | Interpretation |
|---:|---:|---|
| 0.25g | ~4.5 cm | Mild baseline, useful if material/geometry are compliant enough. |
| 0.50g | ~8.9 cm | Moderate diagnostic excitation. |
| 0.75g | ~13.4 cm | Strong diagnostic excitation; check stability carefully. |
| 1.00g | ~17.9 cm | High diagnostic excitation, not a direct jump claim. |
| 1.25g | ~22.4 cm | High diagnostic excitation; only defensible if reported clearly as model excitation. |

Motion-capture literature reports much larger breast/nipple accelerations during athletic activities than 0.25g. Recent activity-comparison data report superior-inferior breast acceleration reaching several g during running, jumping rope and high-knee skipping. Reported relative nipple/breast displacement can range from roughly 10-40 mm during running to 50-75 mm or more during jumping/high-knee activities, depending on support condition and activity.

However, that does not mean the COMSOL case should simply be called a real jump. The model uses a fixed chestwall/support frame, simplified damping, no full-body dynamics, and no bra/torso motion model. Higher g values should therefore be described as diagnostic acceleration excitations.

## Why soft material plus high g is risky

If the old all-soft material set is combined directly with 1.25g, the model may move too much or become unstable. That is especially plausible because the Stage 1 0.25g case already produced useful displacement while using soft materials and no active skin layer.

The new volumetric skin layer may reduce motion, but it is not safe to assume it will fully compensate for all-soft tissue plus high acceleration. The clean strategy is to change only one major factor at a time:

- first add volumetric skin at current material values;
- then soften internal materials at moderate g;
- only then increase g if displacement remains too low.

## Recommended scout ladder

### Step 1: Volumetric skin control

Use the current stiff reference materials and 1.25g:

```text
runs\comsol_runs\geometry_stage5\stage5_reference_no_cooper_xoffset055_125g_volumetric_skin_solve_only_preview.toml
```

Purpose:

- determine whether the new volumetric skin layer is numerically stable;
- compare visually against the existing no-skin 1.25g case;
- check whether skin suppresses displacement too much or introduces artifacts.

Interpretation:

- If visually stable, this becomes the main mechanical control for later material/tumor testing.
- If it develops dimples/buckling like the old shell route, do not use skin-on results for final claims yet.

### Step 2: Hybrid material scout, preferably before all-soft high-g

Preferred next material case:

```text
skin = current stiff COMSOL/Chen-like value
adipose/glandular density and bulk modulus = current COMSOL reference
adipose/glandular C10/C01 = soft interior scout
```

Recommended clean soft-interior values:

```text
skin:     density 1100 kg/m3, bulk 8.33 MPa, C10 41667 Pa, C01 41667 Pa
adipose:  density 950 kg/m3,  bulk 425 kPa,  C10 109 Pa,   C01 106 Pa
glandular:density 1070 kg/m3, bulk 425 kPa,  C10 230 Pa,   C01 195 Pa
```

Recommended amplitudes:

1. Use 1.25g after the stiff-reference 1.25g skin case has been visually accepted, so only material stiffness changes.
2. If this becomes too compliant, use the intermediate material scout below.

Purpose:

- test whether lower internal tissue stiffness gives the desired surface motion while retaining a defensible skin layer;
- avoid using unrealistically soft skin as the main explanation for motion.

### Step 3: Intermediate material scout if needed

If the current reference is too stiff and the hybrid/all-soft cases are too compliant, use an intermediate set:

```text
skin: keep 500 kPa, or test mid-skin around 100 kPa only as sensitivity
adipose: E ~= 2.3-2.5 kPa
glandular: E ~= 5 kPa
```

Example Mooney-Rivlin coefficients:

| Component | C10 | C01 | E estimate |
|---|---:|---:|---:|
| Adipose mid | 200 Pa | 195 Pa | ~2.37 kPa |
| Glandular mid | 450 Pa | 400 Pa | ~5.10 kPa |
| Skin mid, optional | 8333 Pa | 8333 Pa | ~100 kPa |

This is not a new literature-calibrated truth. It is a defensible interpolation between two literature/context endpoints.

### Step 4: All-soft case only as diagnostic upper compliance

The all-soft case already prepared is:

```text
runs\comsol_runs\geometry_stage5\stage5_reference_no_cooper_xoffset055_125g_volumetric_skin_soft_febio_materials_solve_only_preview.toml
```

Use it carefully:

- good as diagnostic upper-compliance case;
- not first choice as final material baseline;
- if it over-moves at 1.25g, make a 0.25g or 0.50g all-soft version instead.

## Best expected route for useful results

The most likely route to a useful, report-defensible result is:

1. Stage 5 volumetric skin + current stiff reference + 1.25g.
2. Stage 5 volumetric skin + stiff skin + soft interior + 0.50g or 0.75g.
3. If still low: same hybrid material at 1.25g.
4. If too high: intermediate adipose/glandular values at 0.75g or 1.25g.
5. Only after choosing the control: matched Stage 6 tumor case with the exact same material/g/skin/Cooper settings.

For tumor detectability, the model does not need to match full unsupported running. It needs a repeatable motion that creates measurable surface displacement differences without nonphysical deformation. A useful target for the current EWS-style diagnostic excitation is roughly:

- clear surface/nipple motion in the 15-40 mm scale;
- no large local collapse or skin wrinkling;
- stress order of magnitude still plausible;
- stable solve to t = 2.2 s;
- same control/tumor settings except tumor parameters.

## Report wording

Suggested wording:

> Because the selected Stage 2-5 anatomical route produced lower displacement than the Stage 1 motion baseline, material stiffness and acceleration amplitude were treated as separate sensitivity axes. The Stage 1 0.25g case used a simpler geometry, no active skin layer and older softer material properties, so its displacement amplitude cannot be transferred directly to the final anatomical route. After adding a volumetric skin layer, the model was therefore tested first with the current literature-anchored material reference, then with softer internal tissue properties while retaining a stiffer skin layer, and only then with higher diagnostic acceleration if needed.

## Sources

- Chen J., Zhong Z., Sun Y., Yip J., Yick K.-L. (2025). Dynamic simulation of breast behaviour during different activities based on finite element modelling of multiple components of breast. Scientific Reports. https://pubmed.ncbi.nlm.nih.gov/39880851/
- Chen J. et al. (2025). Exploration of breast motion under different activities and intensities. Journal of Engineered Fibers and Fabrics. https://journals.sagepub.com/doi/full/10.1177/15589250251352192
- Samani A., Zubovits J., Plewes D. (2007). Elastic moduli of normal and pathological human breast tissues. Physics in Medicine and Biology. https://pubmed.ncbi.nlm.nih.gov/17327649/
- Ramiao N. G. et al. (2016). Biomechanical properties of breast tissue, a state-of-the-art review. Biomechanics and Modeling in Mechanobiology. https://pubmed.ncbi.nlm.nih.gov/26862021/
- Goodbrake C. et al. (2022). On the three-dimensional mechanical behavior of human breast tissue. https://pmc.ncbi.nlm.nih.gov/articles/PMC10116697/
- Patel B. K. et al. (2021). MR Elastography of the Breast: Evolution of Technique, Case Examples, and Future Directions. https://pmc.ncbi.nlm.nih.gov/articles/PMC8486355/
- Current local material note: `docs\report_notes\comsol_pipeline\model_justification\material_parameter_recommendations.md`.
- Current local dynamic note: `docs\report_notes\comsol_pipeline\model_justification\stage1_025g_dynamic_motion_interpretation.md`.
