# Quantitative material-parameter literature overview

Purpose: provide a compact quantitative literature overview for Appendix E and for the presentation. The values below combine direct tissue testing, imaging-based elastography, finite-element material definitions and phantom materials. They should not be treated as one mechanically identical measurement type. In the report, describe them as literature stiffness scales and modelling ranges.

## Main takeaway

- Normal breast soft tissues are commonly represented in the low-kPa range, but reported values depend strongly on test method, strain level, preload, imaging modality and constitutive model.
- The current COMSOL reference values are within a defensible modelling scale: adipose about 3.66 kPa, glandular about 10 kPa, posterior support about 10 kPa, and stiff skin about 500 kPa.
- The skin range is especially broad. A separate skin layer can be much stiffer than internal breast tissue, but calibrated effective skin values in patient-specific models may be far lower than 500 kPa.
- Tumor and malignant-mass stiffness values vary from tens of kPa to more than 100 kPa in elastography-style literature. The 100 kPa hard tumor-overlay setting is therefore a clear sensitivity contrast, not a patient-specific tumor calibration.
- Use the small-strain estimate `E ~= 6(C10 + C01)` only for the nearly incompressible two-coefficient Mooney-Rivlin route used in this project. Do not apply it to MRE shear stiffness, phantom storage modulus, or anisotropic fitted material models.

## Extracted literature values

| Source | Type of value | Reported quantitative values | Useful interpretation for this project |
|---|---|---:|---|
| Samani et al. (2007) | Ex vivo Young's modulus from breast tissue samples | Normal fat: `3.25 +/- 0.91 kPa`; normal fibroglandular: `3.24 +/- 0.61 kPa`; fibroadenoma: `6.41 +/- 2.86 kPa`; low-grade IDC: `10.40 +/- 2.60 kPa`; intermediate-grade IDC: `19.99 +/- 4.2 kPa`; high-grade IDC: `42.52 +/- 12.47 kPa` | Strong support for low-kPa normal tissue values and a stiffer tumor/pathology contrast. |
| Hsu et al. (2011) | Linear-elastic FE compression sensitivity and literature ranges | Literature ranges reported in the paper: adipose `0.5-25 kPa`, glandular `0.08-272 kPa`, skin `0.088-3 MPa`. Tested scenarios included fat/glandular/skin combinations from `1/1/1 kPa` up to `10/50/100 kPa`. | Useful for showing how wide reported FE stiffness choices are and why sensitivity testing is justified. |
| Chen et al. (2024, 2025) | Dynamic multi-component breast FE material definitions | Adipose: density `950 kg/m3`, Mooney-Rivlin `C10=0.31 kPa`, `C01=0.30 kPa`, `C11=2.25 kPa`, `C20=3.8 kPa`, `C02=4.72 kPa`; small-strain scale from first two coefficients `E ~= 3.66 kPa`. Skin: `500 kPa`; soft tissue layer: `10 kPa`; pectoralis major: `10 kPa`; Cooper's ligaments: `100 kPa`; glandular tissue: `10 kPa`. | Closest match to this project because it uses a dynamic multi-component breast FE route with adipose Mooney-Rivlin coefficients and separate skin/glandular/support components. |
| Mazier and Bordas (2024) | Patient-specific elastic model calibration | Optimized mechanical parameters: `E_breast = 0.32 kPa`, `E_skin = 22.72 kPa`. The paper also discusses parameter distributions around `E_breast ~= 0.32 kPa` and `E_skin ~= 23 kPa`. | Shows that calibrated effective patient-specific values can be much softer than the stiff-skin dynamic FE route. Useful caveat for not claiming one universal skin/breast stiffness. |
| Aloufi et al. (2025) | MRE shear stiffness in normal breasts | Fatty tissue: about `0.81-0.82 kPa`; fibroglandular tissue: about `1.46-1.55 kPa`. | Supports fibroglandular tissue being stiffer than fatty tissue in MRE, but these are shear-stiffness values and should not be directly equated with Young's modulus in the FE model. |
| McKnight et al. (2002) | Breast MRE shear stiffness | In patients, carcinoma regions ranged approximately `18-94 kPa` with mean about `33 kPa`; adjacent adipose/fibroglandular tissue ranged about `4-16 kPa` with mean about `8 kPa`. The mean carcinoma shear stiffness was reported as `418%` higher than surrounding tissue. | Useful for tumor contrast context. Do not present as direct Mooney-Rivlin input data. |
| Kashif et al. (2013) | Silicone breast phantom storage modulus for DIET/MRE validation | Tested silicone storage modulus range: `2-570 kPa`. One DIET phantom used a healthy-tissue-mimicking composition around `E'=9 kPa` and a tumor-mimicking inclusion around `E'=35 kPa`, giving almost `4x` contrast. The paper also notes literature values from about `0.42 kPa` for adipose to `460 +/- 178 kPa` for carcinoma at 20% compression. | Useful bridge to EWS/DIET-style surface-motion work and phantom stiffness contrast. Mark as storage modulus, not identical to static Young's modulus. |
| Fitzjohn et al. (2022) | DIET surface-motion diagnostic assumption | Tumors are described as approximately `4-10x` stiffer than healthy tissue in the frequency-decomposition rationale. | Useful for explaining why stiffness contrast could affect surface motion, without claiming direct clinical detectability from this model. |
| Goodbrake et al. (2022) | 3D anisotropic constitutive fitting | Fitted model parameters are given for adipose and fibroglandular tissue, but the study is not reducible to a single Young's modulus. Fibroglandular tissue showed stronger direction-dependent behaviour. | Best used as a caveat: real breast tissue is heterogeneous and anisotropic, while this COMSOL model uses simplified isotropic material scales. |

## Min/max tracing for broad literature ranges

This table is useful if the Appendix or presentation mentions broad ranges such as `0.08-272 kPa`. The main point is that these extremes are not all from one harmonised experiment. They combine values from different studies, test protocols and modelling assumptions.

| Tissue / component | Minimum value | Maximum value | Where the bound comes from | How to phrase it safely |
|---|---:|---:|---|---|
| Adipose tissue | `0.5 kPa` | `25 kPa` | Reported by Hsu et al. (2011) as a literature range for breast biomechanical models. | "Hsu et al. reported adipose values in previous biomechanical models ranging from 0.5 to 25 kPa." |
| Fibroglandular / glandular tissue | `0.08 kPa` | `272 kPa` | Hsu et al. (2011) reports the full range as `0.08-272 kPa`. The upper bound is consistent with Wellman et al. (1999), reported in review form by Teixeira et al. as glandular stiffness up to `271.8 +/- 167.7 kPa` and also noted by Ruggiero et al. as `271.8 kPa`. The lower bound is not separately traced in Hsu's text to one named original study; it should be treated as the lower bound of Hsu's compiled model/literature range. | "Hsu et al. reported a very broad glandular range of 0.08-272 kPa across prior biomechanical models; the high end reflects Wellman-style indentation values and should not be treated as a typical glandular stiffness." |
| Skin | `0.088 kPa` | `3 MPa` | Reported by Hsu et al. (2011) as a literature range; Hsu cites Pailler-Mattei et al. (2008) for in-vivo skin indentation among the relevant skin-property references. | "Skin values span orders of magnitude in the literature, so the skin layer was treated as a sensitivity parameter." |
| Normal breast tissue, ex vivo | `3.24 kPa` | `3.25 kPa` | Samani et al. (2007): normal fibroglandular tissue `3.24 +/- 0.61 kPa`; normal fat `3.25 +/- 0.91 kPa`. | "Samani et al. measured normal fat and fibroglandular samples around 3.25 kPa under their ex-vivo small-deformation protocol." |
| Pathological breast tissue, ex vivo | `6.41 kPa` | `42.52 kPa` | Samani et al. (2007): fibroadenoma `6.41 +/- 2.86 kPa`; high-grade IDC `42.52 +/- 12.47 kPa`. | "Samani et al. reported benign and malignant pathological samples as stiffer than normal tissue, with high-grade IDC around 42.5 kPa." |
| Tumor / malignant mass, MRE/SWE context | about `18 kPa` | above `100 kPa` in elastography studies | McKnight et al. (2002) reported carcinoma MRE regions around `18-94 kPa`; comb-push/shear-wave elastography literature can report malignant masses around `115 kPa` or higher, depending on method and ROI. | "Tumor stiffness values in elastography literature commonly fall in the tens to hundreds of kPa, but these are not direct Mooney-Rivlin input values." |

## Tumor upper-bound context

Use this if a slide or appendix needs to justify why the tumor-overlay sensitivity case used a `100 kPa` stiffness scale.

| Source | Method | Reported tumor / malignant stiffness | Best use in this project |
|---|---|---:|---|
| Samani et al. (2007) | Ex-vivo indentation / Young's modulus | High-grade IDC: `42.52 +/- 12.47 kPa`; intermediate-grade IDC: `19.99 +/- 4.2 kPa`; low-grade IDC: `10.40 +/- 2.60 kPa` | Conservative ex-vivo evidence that pathological tissue is stiffer than normal fat/fibroglandular tissue. |
| McKnight et al. (2002) | MR elastography shear stiffness | Carcinoma regions approximately `18-94 kPa`, mean about `33 kPa`; surrounding tissue about `4-16 kPa`, mean about `8 kPa` | Useful for tumor-to-surrounding-tissue contrast in an imaging context. |
| Denis et al. (2015) | Comb-push ultrasound shear elastography | Malignant masses: `114.9 +/- 40.6 kPa`; benign masses: `39.4 +/- 28.1 kPa`; normal breast tissue: `14.1 +/- 11.8 kPa` | Clearest compact support for saying malignant breast masses can be around or above `100 kPa`. Add `Denis2015` to `references.bib` if used. |
| Song et al. (2018) | Shear wave elastography | Breast cancers: `Emax ~= 169 +/- 70 kPa`, `Emean ~= 131 +/- 53 kPa` | Supports a `100-200 kPa` malignant-lesion stiffness context. Add `Song2018` to `references.bib` if used. |
| Kashif et al. (2013) | Phantom / DIET context and literature comparison | DIET phantom used healthy tissue around `E'=9 kPa` and tumor inclusion around `E'=35 kPa`, nearly `4x` contrast; the paper also notes carcinoma literature values around `460 +/- 178 kPa` at 20% compression. | Useful for EWS/DIET-style surface-motion context, but storage/compression modulus is not identical to the COMSOL stiffness scale. |
| Teixeira and Martins (2023) | Review of breast mechanical properties | Summarises multiple studies ranging from low tens of kPa to much higher ex-vivo compression/indentation values for carcinoma, depending on strain/precompression and method. | Use as a review source to explain why one universal tumor stiffness does not exist. |

Presentation-safe phrasing: "Tumor stiffness values are method-dependent. Some indentation and MRE studies report values mainly in the tens of kPa, while shear-wave elastography studies report malignant masses around or above 100 kPa. The `100 kPa` tumor setting was therefore used as a strong stiffness-contrast sensitivity value, not as a patient-specific calibration."

## Current COMSOL material scales to show beside the literature

| Component / route | Input definition in this project | Approximate stiffness scale |
|---|---|---:|
| Reference adipose | `K=425 kPa`, `C10=310 Pa`, `C01=300 Pa`, density `950 kg/m3` | `E ~= 3.66 kPa` |
| Soft adipose sensitivity | `K=425 kPa`, `C10=109 Pa`, `C01=106 Pa` | `E ~= 1.29 kPa` |
| Reference fibroglandular | `K=425 kPa`, `C10=833 Pa`, `C01=833 Pa`, density `1070 kg/m3` | `E ~= 10.0 kPa` |
| Soft fibroglandular sensitivity | `K=425 kPa`, `C10=230 Pa`, `C01=195 Pa` | `E ~= 2.55 kPa` |
| Soft volumetric skin sensitivity | `K=480 kPa`, `C10=1200 Pa`, `C01=1200 Pa`, density `1100 kg/m3` | `E ~= 14.4 kPa` |
| Intermediate volumetric skin sensitivity | `K=8.33 MPa`, `C10=7333 Pa`, `C01=7333 Pa` | `E ~= 88 kPa` |
| Stiff/reference volumetric skin | `K=8.33 MPa`, `C10=41667 Pa`, `C01=41667 Pa`, density `1100 kg/m3` | `E ~= 500 kPa` |
| Posterior support surrogate | Linear elastic, `E=10 kPa`, `nu=0.49`, density `1050 kg/m3` | `E = 10 kPa` |
| Cooper-like support scale | Restoring-traction support scale from ligament modulus, area fraction and reference length | Support-strength parameter, not bulk tissue stiffness |
| Hard tumor overlay sensitivity | `K=425 kPa`, `C10=8333 Pa`, `C01=8333 Pa` | `E ~= 100 kPa` |

## Suggested Appendix E replacement

This can replace the current qualitative Appendix E table, or be added after the current short explanation.

```latex
\section{Material-parameter literature summary}
\label{appendix_material_parameter_literature_summary}

The material parameters used in the COMSOL model were selected as controlled reference and sensitivity values rather than as patient-specific tissue measurements. Reported breast-tissue stiffness values vary strongly between studies because they depend on measurement protocol, tissue preparation, preload, strain level, loading direction, subject characteristics and constitutive model \cite{Samani2007,Ramiao2016,Goodbrake2022,Teixeira2023}. The values in Table~\ref{appendix_quantitative_material_literature_table} therefore provide stiffness-scale context rather than directly interchangeable material constants. Young's modulus values, MRE shear-stiffness values, phantom storage moduli and hyperelastic coefficients should not be interpreted as the same mechanical quantity.

\begin{table}[H]
\centering
\scriptsize
\caption{Quantitative literature context for the material-parameter scales used in the COMSOL model.}
\label{appendix_quantitative_material_literature_table}
\begin{tabular}{p{0.18\linewidth} p{0.22\linewidth} p{0.30\linewidth} p{0.22\linewidth}}
\toprule
Source & Measurement or model type & Reported values & Relevance for this model \\
\midrule
Samani et al. \cite{Samani2007}
& Ex-vivo Young's modulus measurements
& Normal fat: $3.25\pm0.91~\mathrm{kPa}$; normal fibroglandular tissue: $3.24\pm0.61~\mathrm{kPa}$; fibroadenoma: $6.41\pm2.86~\mathrm{kPa}$; intermediate-grade IDC: $19.99\pm4.2~\mathrm{kPa}$; high-grade IDC: $42.52\pm12.47~\mathrm{kPa}$.
& Supports low-kPa normal tissue stiffness and a higher stiffness scale for pathological tissue. \\

Hsu et al. \cite{Hsu2011}
& Linear-elastic breast-compression FE sensitivity
& Reported literature ranges: adipose $0.5$--$25~\mathrm{kPa}$, glandular $0.08$--$272~\mathrm{kPa}$ and skin $0.088$--$3~\mathrm{MPa}$. Tested FE scenarios used fat/glandular/skin stiffness combinations from $1/1/1~\mathrm{kPa}$ to $10/50/100~\mathrm{kPa}$.
& Shows the broad spread of published stiffness choices and supports material-sensitivity testing. \\

Chen et al. \cite{Chen2024,Chen2025}
& Dynamic multi-component breast FE model
& Adipose tissue was represented using Mooney--Rivlin coefficients including $C_{10}=0.31~\mathrm{kPa}$ and $C_{01}=0.30~\mathrm{kPa}$, corresponding to $E\approx3.66~\mathrm{kPa}$ using the small-strain estimate. Skin, glandular tissue, pectoralis/soft tissue and Cooper's ligaments were assigned approximate Young's moduli of $500~\mathrm{kPa}$, $10~\mathrm{kPa}$, $10~\mathrm{kPa}$ and $100~\mathrm{kPa}$, respectively.
& Closest literature match for the current multi-component dynamic FE material route. \\

Mazier and Bordas \cite{Mazier2024}
& Patient-specific elastic calibration
& Optimised values of $E_{\mathrm{breast}}=0.32~\mathrm{kPa}$ and $E_{\mathrm{skin}}=22.72~\mathrm{kPa}$ were reported for shape-fitting between prone and supine configurations.
& Demonstrates that calibrated effective breast and skin stiffness can be much lower than stiff-skin dynamic FE settings. \\

Aloufi et al. \cite{Aloufi2025}
& MRE shear stiffness in normal breasts
& Fatty tissue was reported around $0.81$--$0.82~\mathrm{kPa}$ and fibroglandular tissue around $1.46$--$1.55~\mathrm{kPa}$.
& Supports a higher fibroglandular than fatty stiffness trend, but MRE shear stiffness is not directly the same as Young's modulus. \\

McKnight et al. \cite{McKnight2002}
& Breast MRE shear stiffness
& Breast carcinoma regions ranged approximately $18$--$94~\mathrm{kPa}$ with a mean of about $33~\mathrm{kPa}$, while surrounding breast tissue ranged about $4$--$16~\mathrm{kPa}$ with a mean of about $8~\mathrm{kPa}$.
& Provides tumor-stiffness contrast context for the analytic tumor-overlay route. \\

Kashif et al. \cite{Kashif2013}
& Silicone breast phantom storage modulus
& Silicone compositions covered $E'=2$--$570~\mathrm{kPa}$. A DIET phantom used a healthy-tissue-mimicking material around $E'=9~\mathrm{kPa}$ and a tumor-mimicking inclusion around $E'=35~\mathrm{kPa}$, giving an almost four-fold contrast.
& Relevant to EWS/DIET-style surface-motion studies, but storage modulus is frequency-dependent and not identical to static Young's modulus. \\

Fitzjohn et al. \cite{Fitzjohn2022}
& DIET surface-motion diagnostic rationale
& The diagnostic rationale assumes tumors are approximately $4$--$10$ times stiffer than healthy tissue.
& Supports using stiffness contrast as a sensitivity variable, without implying clinical detectability from the current model. \\
\bottomrule
\end{tabular}
\end{table}

For the nearly incompressible two-coefficient Mooney--Rivlin route used in this project, material coefficients were compared using the small-strain stiffness scale $E\approx6(C_{10}+C_{01})$. The main COMSOL values were therefore $E\approx3.66~\mathrm{kPa}$ for adipose tissue, $E\approx10.0~\mathrm{kPa}$ for fibroglandular tissue, $E\approx500~\mathrm{kPa}$ for the stiff volumetric skin setting and $E\approx100~\mathrm{kPa}$ for the hard tumor-overlay setting. Softer skin and internal-tissue settings were retained as sensitivity cases rather than patient-specific material calibrations.
```

## Short presentation version

Use one slide with this simplified message:

| Component | Literature scale to show | My model scale |
|---|---:|---:|
| Adipose / fatty tissue | about `0.5-25 kPa` in FE literature; Samani normal fat `3.25 kPa`; Aloufi MRE fatty tissue about `0.8 kPa` | reference `3.66 kPa`; soft sensitivity `1.29 kPa` |
| Fibroglandular tissue | very broad FE range `0.08-272 kPa`; Samani normal fibroglandular `3.24 kPa`; Chen dynamic FE `10 kPa`; Aloufi MRE fibroglandular about `1.5 kPa` | reference `10.0 kPa`; soft sensitivity `2.55 kPa` |
| Skin | broad FE range `0.088-3 MPa`; Chen dynamic FE `500 kPa`; Mazier calibrated effective skin `22.72 kPa` | soft `14.4 kPa`; intermediate `88 kPa`; stiff `500 kPa` |
| Cooper/support | Chen dynamic FE `100 kPa` for Cooper ligaments; isolated ligament tensile values can be much higher | simplified restoring-traction support, not anatomical ligament reconstruction |
| Tumor / malignant masses | Samani high-grade IDC `42.5 kPa`; McKnight carcinoma MRE mean about `33 kPa`; DIET/phantom contrasts around `4x`; malignant SWE literature can exceed `100 kPa` | hard tumor-overlay sensitivity `100 kPa` |

Suggested spoken caveat: "These numbers are not all the same mechanical measurement. I used them to define a defensible stiffness scale and sensitivity range, not to claim patient-specific tissue properties."

## Reference checklist

Already present in `references.bib`: `Samani2007`, `Hsu2011`, `Chen2024`, `Chen2025`, `Mazier2024`, `Aloufi2025`, `McKnight2002`, `Kashif2013`, `Fitzjohn2022`, `Goodbrake2022`, `Ramiao2016`, `Teixeira2023`.

Potential optional additions if you want a stronger tumor-elastography row: `Denis2015` and/or `Song2018` are available as PDFs in `docs/Literature`, but they do not currently appear as cite keys in `references.bib`.
