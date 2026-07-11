# COMSOL material parameter recommendations

Date: 2026-05-13

This note summarizes a defensible fixed material-parameter set for the COMSOL breast FEM model. The goal is not to claim subject-specific truth, but to stop tuning material values freely between geometry stages.

## Key literature takeaways

- Breast soft tissues are commonly treated as isotropic and nearly incompressible in FE breast models. A Poisson ratio around `0.49` is commonly used for soft tissue components in dynamic breast FE work.
- Normal breast tissue stiffness varies strongly with protocol, preload, strain level, age, subject, and region. Reviews emphasize that reported Young's moduli for fat and fibroglandular tissue vary widely, so a fixed set should be treated as a literature-based reference rather than a universal value.
- A recent dynamic multi-component breast FE model used adipose as a Mooney-Rivlin material and represented skin, glandular tissue, pectoralis muscle, Cooper's ligaments, and soft tissue layers with Neo-Hookean elastic properties.
- Cooper ligament material data are limited. One review reports cadaver ligament tensile data with Young's modulus `5.8 +/- 4.2 MPa`, rupture strain `8.6 +/- 4.2%`, and rupture stress `1.9 +/- 2.5 MPa`. In contrast, some whole-breast dynamic FE models use an effective Cooper ligament Young's modulus around `100 kPa`. For this model's boundary-load surrogate, the high ligament modulus should stay scaled by area fraction/reference length and not be interpreted as direct bulk tissue stiffness.

## Recommended fixed set for the current model

These values map cleanly onto the current two-parameter Mooney-Rivlin scaffold, where the small-strain relation is approximately:

`E ~= 6 * (C10 + C01)` for nearly incompressible tissue.

| Component | Density | Constitutive target | Recommended values for current TOML |
|---|---:|---|---|
| Adipose | `950 kg/m^3` | Samani-style Mooney-Rivlin adipose | `bulk_modulus = 425000 Pa`, `coef1 = 310 Pa`, `coef2 = 300 Pa` |
| Glandular | `1070 kg/m^3` | Neo-Hookean-like `E ~= 10 kPa`, represented with current MR scaffold | `bulk_modulus = 425000 Pa`, `coef1 = 833 Pa`, `coef2 = 833 Pa` |
| Skin | `1100 kg/m^3` | Literature dynamic FE value `E ~= 500 kPa`; only important once skin shell is enabled | `bulk_modulus = 8330000 Pa`, `coef1 = 41667 Pa`, `coef2 = 41667 Pa` |
| Chest / pectoralis surrogate | `1050 kg/m^3` | Soft tissue / pectoralis FE value `E ~= 10 kPa` | keep `chest_youngs_modulus_pa = 10000`, `chest_poissons_ratio = 0.49` |
| Cooper ligament surrogate | `1040 kg/m^3` if explicit ligament material is added | Literature effective FE value around `100 kPa`; cadaver tensile modulus reported around `5.8 MPa` | keep current Stage 5 surrogate as a sensitivity model; document area-fraction scaling |

## Stage 6 tumor stiffness interpretation

The current Stage 6 tumor cases use an analytic material overlay and map tumor stiffness through the same two-coefficient Mooney-Rivlin scaffold as the surrounding tissues. For a nearly incompressible small-strain estimate, use:

`E ~= 6 * (coef1 + coef2)`

This gives the following approximate stiffness levels:

| Stage 6 tumor setting | Coefficients | Approximate small-strain `E` | Interpretation |
|---|---:|---:|---|
| Current small/medium/large central default in adipose expression | `971 + 939 Pa` | `~11.5 kPa` | Stiffer than adipose, similar to the current glandular reference. |
| Current small/medium/large central default in glandular expression | `920 + 870 Pa` | `~10.7 kPa` | Similar to current glandular reference. |
| Mild stiffness variant | `600 + 580 Pa` | `~7.1 kPa` | Modest sensitivity, not a strong malignant-lesion stiffness. |
| Stiff variant | `2500 + 2500 Pa` | `~30 kPa` | Clear stiffness contrast, but still lower than many elastography malignant-mass averages. |

Elastography studies often report malignant breast masses with mean or maximum stiffness values in the tens to hundreds of kPa, depending on modality, region of interest, lesion type, and surrounding tissue. For example, one comb-push ultrasound shear elastography study reported normal breast tissue around `14 kPa`, benign masses around `39 kPa`, and malignant masses around `115 kPa` on average. Another tumor-stiffness study shows malignant lesions can have high heterogeneous stiffness with mean values around `168 kPa` in example cases. Therefore, the current Stage 6 mild/stiff cases should be described as first-order stiffness sensitivity, not as calibrated malignant-tumor material. A later Stage 6 material sweep should add a stronger `~100 kPa` target after the spherical mask route is stable.

## Why these values are preferable to the current free set

The current Stage 5 runs already behave well numerically, but their adipose and glandular parameters are still inherited from earlier exploratory cases. Fixing the values above would make future comparisons cleaner:

- geometry changes can be compared without material drift;
- glandular tissue is clearly stiffer than adipose, which is commonly assumed in FE models;
- density values match recent multi-component dynamic breast FE literature;
- skin becomes realistic if the shell model is later re-enabled.

## Cooper ligament justification and current limitation

Cooper ligament modelling is still one of the least certain parts of the pipeline. The anatomical structure is a distributed fibrous support network, while the current COMSOL route represents it as a simplified scaffold/sensitivity model. Therefore, Stage 5 should be described as `mechanical support sensitivity`, not as exact Cooper ligament reconstruction.

The literature gives two useful but different stiffness scales:

- cadaver ligament tensile measurements can be in the MPa range;
- whole-breast FE models may use much lower effective Cooper/soft-support stiffness values, around `100 kPa`, because the ligament network is distributed through tissue and acts through geometry, area fraction and connectivity.

This difference is not a contradiction. A direct tensile modulus of an isolated ligament is not the same as the effective stiffness of a sparse ligament network inside a breast model. For this project, the defensible approach is:

1. keep the no-Cooper case as the stable control;
2. test mild/default/stiff Cooper variants only as sensitivity cases;
3. report Cooper effects only after a full dynamic run reaches the intended time range;
4. avoid claiming exact ligament anatomy until the scaffold geometry and solver stability are both robust.

## Suggested implementation path

1. Create a new fixed-material Stage 5B reference case, rather than overwriting the working Stage 5 results.
2. Keep Stage 5B as the main Cooper-ligament variant because it is physically the easiest to defend.
3. Run fixed-material Stage 5B against the current Stage 1 baseline.
4. Only after that, move to chestwall curvature and asymmetry.

## Sources

- Chen J., Zhong Z., Sun Y., Yip J., Yick K.-L. (2025). "Dynamic simulation of breast behaviour during different activities based on finite element modelling of multiple components of breast." Scientific Reports. Table 1 lists adipose Mooney-Rivlin density/coefficients and Neo-Hookean density/Young's modulus values for skin, soft tissue layer, pectoralis major muscles, Cooper's ligaments, and glandular tissues. https://www.nature.com/articles/s41598-024-83598-8/tables/1
- Chen et al. (2025), Materials and methods section: soft tissues are treated as homogeneous isotropic hyperelastic materials, quasi-incompressibility is modeled with `nu = 0.49`, and adipose parameters are based on Samani's ex-vivo breast properties. https://www.nature.com/articles/s41598-024-83598-8
- Ramião N. G. et al. (2016). "Biomechanical properties of breast tissue, a state-of-the-art review." Biomechanics and Modeling in Mechanobiology. The review emphasizes strong variation of reported moduli with compression/preload and tissue type. https://pubmed.ncbi.nlm.nih.gov/26862021/
- Verdier et al. (2023). "A review of bioengineering techniques applied to breast tissue: Mechanical properties, tissue engineering and finite element analysis." Frontiers in Bioengineering and Biotechnology. The review summarizes FE breast-tissue modelling and reports limited Cooper ligament material data, including Briot et al. (2020) tensile ligament measurements. https://www.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2023.1161815/full
- Comb-push ultrasound shear elastography study reporting average Young's modulus values for normal breast tissue, benign masses, and malignant masses. https://pmc.ncbi.nlm.nih.gov/articles/PMC4687021/
- Tumor stiffness measured by quantitative and qualitative shear wave elastography of breast cancer. https://pmc.ncbi.nlm.nih.gov/articles/PMC6223289/
