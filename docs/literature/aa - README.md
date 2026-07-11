# Literature Overview

This folder contains the main literature used to support the COMSOL breast FEM / EWS project. The papers are not all used in the same way. Some are core sources for the model assumptions, while others mainly provide clinical context, screening background, or future-work motivation.

## Core Sources for the FEM Model

These sources should be treated as the most important technical foundation for the report.

| Source | Strength | Main use in this project |
|---|---|---|
| Samani 2001 - Biomechanical 3-D Finite Element Modeling of the Human Breast Using MRI Data | High citation / foundational | Early MRI-based breast FEM modelling and image-based deformation context. |
| Samani 2007 - Elastic Moduli of Normal and Pathological Human Breast Tissues | High citation / foundational | Elastic modulus ranges for normal and pathological breast tissues. |
| Ramiao 2016 - Biomechanical Properties of Breast Tissue Review | High citation / review | Main review for variability in breast tissue mechanical properties. |
| Sturgeon 2016 - FE Modeling of Compression and Gravity on Breast Phantoms | Medium-high citation / strong relevance | FE breast phantom modelling, gravity/compression, and material sensitivity. |
| Hsu 2011 - Mechanical Parameters for Finite Element Compression of a Breast | Medium-high citation / strong relevance | Influence of mesh, material, and compression parameters in breast FE modelling. |
| Goodbrake 2022 - On the Three-Dimensional Mechanical Behavior of Human Breast Tissue | Strong recent tissue mechanics | 3D anisotropic and heterogeneous behaviour of human breast tissue. |
| Babarenda Gamage 2017 - Clinical Applications of Breast Biomechanics | Strong review/book chapter | Clinical context and state of breast biomechanics modelling. |
| Rajagopal 2006 - Finite Element Modelling of Breast Biomechanics | Foundational breast FEM source | Breast biomechanics modelling, gravity/loading context and early FE methodology. |
| Eder 2014 - Comparison of Different Material Models to Simulate 3-D Breast Deformations | Material-model comparison | Supports the discussion of material-model assumptions and their effect on simulated breast deformation. |
| Ruggiero 2014 - Effect of Material Modeling on FE Analysis of Human Breast Biomechanics | Material-model sensitivity | Shows how different constitutive material choices can affect breast FE results. |
| Mazier 2024 - Breast Simulation Pipeline from Medical Imaging to Patient-Specific Simulations | Strong recent pipeline source | Patient-specific simulation direction and realistic limitations. |
| Zhang 2022 - Non-linear FE Model Established on Pectoralis Major Muscle to Investigate Large Breast | Recent anatomy/support FEM source | Pectoralis/chest support modelling and large-breast FE deformation context. |

## Dynamic Breast Motion and Activity FEM

These sources are important for interpreting the dynamic motion input and displacement/stress response.

| Source | Strength | Main use in this project |
|---|---|---|
| Chen 2013 - A Study of Breast Motion Using Non-linear Dynamic FE Analysis | Established dynamic FEM source | Dynamic breast motion, free vibration, and FEM motion amplitudes. |
| Chen 2024 - Multi-Component FE Model to Predict Biomechanical Behaviour of the Breast During Running | Very relevant, recent | Multi-component dynamic breast FEM, running motion, stiffness effects. |
| Chen 2025 - Dynamic Simulation of Breast Behaviour During Different Activities | Very relevant, recent | Activity-dependent stress and displacement response. |
| Yu 2026 - Dynamic Breast Response Under Different Running Intensities | Very recent, use cautiously | Recent running-intensity FEM context; low citation expected due to recency. |

## EWS / DIET / Surface-Motion Detection

These sources support the project idea that internal stiffness changes may be detectable from breast surface motion.

| Source | Strength | Main use in this project |
|---|---|---|
| Peters 2004 - Digital Image-Based Elasto-Tomography Proof of Concept | Historical DIET foundation | Surface-based mechanical property reconstruction concept. |
| Peters 2007 - Digital Image Elasto-Tomography Thesis | Technical background | DIET reconstruction and modelling background. |
| Van Houten 2011 - Phantom Elasticity Reconstruction with DIET | Good relevance | Phantom-based elasticity reconstruction. |
| Van Houten 2012 - Localization and Detection of Breast Cancer Tumors with DIET | Good relevance | DIET tumor localization/detection context. |
| Kashif 2013 - Separate Modal Analysis for Tumor Detection with DIET | Good relevance | Tumor size/stiffness phantom sensitivity, including 5/10/20 mm inclusions. |
| Ismail 2018 - Finite Element Modelling and Validation for Breast Cancer Detection | Good relevance | FE validation for DIET-style breast cancer detection. |
| Fitzjohn 2022 - Breast Cancer Diagnosis Using Frequency Decomposition of Surface Motion | Recent clinical/system relevance | Human DIET screening and surface-motion frequency analysis. |
| Wulff 2011 - Correspondence Estimation from Non-Rigid Motion Information | Technical support | Markerless surface correspondence/motion reconstruction. |

## Material Properties, Elastography, and Stiffness Context

These sources support the material sensitivity discussion. They should be used carefully because measured stiffness depends strongly on method, loading, sample state, and material model.

| Source | Strength | Main use in this project |
|---|---|---|
| McKnight 2002 - MR Elastography of Breast Cancer Preliminary Results | Established clinical MRE source | Breast/tumor stiffness contrast. |
| Patel 2021 - MR Elastography of the Breast Evolution of Technique and Future Directions | Review/context | MRE technique and future directions. |
| Patel 2022 - Association of Breast Cancer Risk Density and Stiffness on MRE | Good clinical relevance | Breast stiffness and risk/density relation. |
| Aloufi 2025 - Differentiating Breast Tissue Stiffness with MRE | Recent, use cautiously | Fatty vs fibroglandular tissue stiffness by MRE. |
| Song 2018 - Tumor Stiffness Measured by Shear Wave Elastography of Breast Cancer | Good clinical relevance | Tumor stiffness and elastography context. |
| Denis 2015 - Update on Breast Cancer Detection Using Comb-Push Ultrasound Shear Elastography | Good clinical elastography source | Supports high malignant breast-mass stiffness values around or above 100 kPa. |
| Olgun 2014 - Use of Shear Wave Elastography to Differentiate Benign and Malignant Breast Lesions | Clinical elastography context | Benign/malignant stiffness contrast and lesion elastography background. |
| Goddi 2012 - Breast Elastography A Literature Review | Review/context | General elastography background. |
| Jamshidi 2024 - Magnetic Resonance Elastography for Breast Cancer Diagnosis | Recent review/context | MRE diagnostic context. |
| Teixeira 2023 - Bioengineering Mechanical Properties of Human Breast Tissue Review | Review/context | Mechanical properties, tissue engineering, and FE modelling background. |

## Breast Geometry, Density, and Volume Context

These sources support breast volume, density, glandular tissue, and imaging-related assumptions.

| Source | Strength | Main use in this project |
|---|---|---|
| Nie 2010 - Age and Race Dependence of Fibroglandular Breast Density on 3D MRI | Good context | Fibroglandular density and MRI-based tissue quantification. |
| Nie 2010 - Impact of Skin Removal on Quantitative Measurement of Breast Density Using MRI | Good context | Skin and density measurement considerations. |
| Lu 2012 - Comparison of Breast Tissue Measurements Using MRI, Digital Mammography and Algorithm | Good context | Breast tissue measurement comparison. |
| Sartor 2016 - Measuring Mammographic Density | Good context | Volumetric density assessment. |
| Bakker 2019 - Supplemental MRI Screening for Women with Extremely Dense Breast Tissue | High-impact clinical source | Screening context for dense breasts. |
| Von Euler-Chelpin 2019 - Sensitivity of Screening Mammography by Density and Texture | Good screening source | Mammography sensitivity and density/texture. |
| LETB 2023 - Dutch Breast Cancer Screening Evaluation Report | Authoritative Dutch report | Dutch screening-program context. |

## Tumor Location, Size, and Surface-Proximity Context

These sources support Stage 6 tumor size/location choices.

| Source | Strength | Main use in this project |
|---|---|---|
| Rummel 2015 - Tumour Location within the Breast | Good clinical/anatomical relevance | Tumor location distribution in the breast. |
| Yu 2017 - Non-randomness of the Anatomical Distribution of Tumors | Good clinical/anatomical relevance | Non-random tumor distribution and upper-outer predominance. |
| Brandao 2023 - Ultrasound Measurement of the Distance between the Breast Tumor and the Skin | Recent, specific | Tumor-to-skin distance and superficial lesion context. |
| Yur 2023 - Effect of Tumor-to-Skin Distance on Axillary Lymph Node Metastasis | Recent, specific | Clinical relevance of tumor-to-skin distance. |
| Sisti 2020 - Breast Cancer in Women Descriptive Analysis | Clinical context | Broad breast-cancer descriptive statistics. |
| Sohn 2008 - Primary Tumor Location Impacts Breast Cancer Survival | Clinical context | Tumor location relevance. |
| Silverman 2014 - Skin Involvement and Breast Cancer | Clinical context | Skin involvement / T4b context. |
| NCI TNM / BI-RADS sources in references.bib | Authoritative non-paper sources | Tumor staging and lesion shape terminology. |

## Broader Screening and Technology Context

These are useful for introduction or discussion, but should not carry the mechanical model justification.

| Source | Strength | Main use in this project |
|---|---|---|
| WHO 2025 Breast Cancer | Authoritative public-health source | Global breast-cancer context. |
| Early Warning Scan website | Primary project/system source | Description of the EWS concept, not clinical validation. |
| COMSOL and FEBio websites | Primary software sources | Software identification. |
| Kamal 2023 - Engineering Approaches for Breast Cancer Diagnosis | Review/context | Broad diagnostic technologies. |
| Adapa 2025 - AI Tool for Population-Level Breast Cancer Screening | Recent, indirect | AI screening context, not FEM validation. |
| Mukhmetov 2025 - PINNs with Thermal Imaging | Recent, indirect | Future physics-informed modelling context. |
| Santos 2025 - Elastography Research and Phantoms | Very recent review | Phantom/elastography background. |
| Brazy 2020 - Gradient Based Elastic Property Reconstruction in Digital Image Correlation Elastography | Technical inverse-method source | Digital-image-based elastography and elastic property reconstruction context. |
| Barufaldi 2021 - Computational Breast Anatomy Simulation Using Multi-Scale Perlin Noise | Anatomy simulation context | Synthetic breast anatomy generation and computational phantom context. |

## How to Use This Literature in the Report

- Use the core FEM and material sources for the Materials and Methods justification.
- Use dynamic FEM sources when discussing the acceleration input, displacement amplitude, and stress response.
- Use DIET/EWS surface-motion sources to justify why surface displacement and frequency/motion features are relevant.
- Use tumor-location sources for Stage 6 tumor placement and size choices.
- Use recent 2024-2026 papers carefully: low citation count is expected, so rely on them for current direction rather than as the only evidence.
- Avoid presenting website sources as scientific validation. Use them only for public information, project context, or software descriptions.
