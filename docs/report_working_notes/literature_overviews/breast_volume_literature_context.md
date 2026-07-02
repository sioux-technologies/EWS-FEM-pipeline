# Breast Volume Literature Context for EWS FEM Model

Date: 2026-05-26

## Purpose

This note benchmarks the current 100-sample breast-volume dataset against literature values, to support selection of representative FEM breast volumes for the COMSOL EWS pipeline. The sample volumes should be interpreted cautiously because they were segmented approximately 5 mm inside the outer breast boundary and in a lying/supine-like position, whereas the current COMSOL baseline is an idealized upright/anatomical geometry.

## Current 100-Sample Dataset Catharina Ziekenhuis

Unit: ml, approximately equivalent to cm3 for soft-tissue volume.

| Statistic | Volume (ml) |
|---|---:|
| N | 100 |
| Minimum | 105.68 |
| 10th percentile | 363.86 |
| 25th percentile | 519.65 |
| Median | 691.15 |
| Mean | 728.32 |
| 75th percentile | 928.70 |
| 90th percentile | 1135.46 |
| Maximum | 1777.28 |
| Standard deviation | 327.39 |
| IQR | 409.05 |

The current Stage 2-5 COMSOL anatomical baseline volume is about 585 ml, placing it between the 25th percentile and median of this sample distribution. Stage 1 is about 719 ml, close to the sample mean/median, but Stage 1 should still be treated as a motion sanity baseline rather than the anatomical reference because its geometry differs from the later stages.

## Literature Anchors

### MRI Normative Cohort

Stahl et al. reported MRI-based breast anthropometry in 400 German female patients. Their mean total breast volume was 976 ml, with right-breast mean 973 ml and range 64-4777 ml, and left-breast mean 979 ml and range 55-4670 ml. For BMI 18.5-24.9 kg/m2, the study defined micromastia below 250 ml at the 5th percentile and macromastia above 1250 ml at the 95th percentile.

Source: PubMed, "Definitions of Abnormal Breast Size and Asymmetry: A Cohort Study of 400 Women", https://pubmed.ncbi.nlm.nih.gov/37253846/

### MRI Accuracy and Mastectomy Weight

Yoo et al. compared MRI-estimated breast volume with mastectomy specimen weight in 101 breasts from 99 patients. They reported mean mastectomy specimen weight 340.8 g, range 95-795 g, and mean MRI-estimated volume 322.2 ml. This is a cancer/mastectomy cohort and therefore not a general healthy-population distribution, but it supports MRI as a clinically meaningful volumetric method.

Source: PubMed, "Magnetic resonance imaging-based volumetric analysis and its relationship to actual breast weight", https://pubmed.ncbi.nlm.nih.gov/23730594/

### Skin and Boundary Definition

Nie et al. quantified the effect of skin removal in breast MRI density measurement. In 50 women, measured breast volume had median 703 cm3, range 282-1550 cm3, and mean 740 +/- 303 cm3. Skin volume normalized to breast volume ranged from 5.0% to 15.2%, with median 8.6% and mean 8.8 +/- 2.6%.

Source: PMC, "Impact of skin removal on quantitative measurement of breast density using MRI", https://pmc.ncbi.nlm.nih.gov/articles/PMC2801738/

This is especially relevant to the current 100-sample dataset because the sample volumes were drawn about 5 mm inside the external boundary. That likely makes the dataset a lower-bound estimate of full external breast envelope volume. The expected offset is not just "skin removal"; a uniform 5 mm inward offset may remove skin plus a peripheral soft-tissue shell, so the correction could be larger than the 5-15% skin-volume range depending on breast surface area and shape.

### Measurement Uncertainty

Choppin et al. reviewed breast-volume measurement methods and noted that uncertainty greater than +/-200 ml is common, while MRI can achieve errors below 10% in some studies for small, medium, and large breasts. They emphasized that patient pose, breast shape, and boundary definition strongly affect volume measurement.

Source: ScienceDirect, "The accuracy of breast volume measurement methods: A systematic review", https://www.sciencedirect.com/science/article/pii/S0960977616300698

## Interpretation of the 100-Sample Dataset

The sample distribution is broadly plausible compared with MRI-based literature:

| Comparison point | Literature / model context | Relation to sample |
|---|---|---|
| Sample median 691 ml | Nie et al. MRI median 703 cm3 | Very close |
| Sample mean 728 ml | Nie et al. MRI mean 740 cm3 | Very close |
| Sample Q1-Q3 520-929 ml | Literature reports broad spread and high BMI dependence | Plausible mid-range |
| Sample maximum 1777 ml | Stahl et al. MRI range extends to >4600 ml | High but not implausible |
| Sample minimum 106 ml | Stahl et al. minimum about 55-64 ml | Low but possible |
| COMSOL Stage 2-5 volume ~585 ml | Sample P25-P50 region | Reasonable moderate-sized anatomical baseline |
| COMSOL Stage 1 volume ~719 ml | Sample mean/median region | Volume plausible, but geometry not fair anatomical baseline |

The main caveat is segmentation definition. Because the sample boundary is inset by roughly 5 mm, the full external breast envelope would likely be higher than the reported values. If one applies only a conservative skin-style correction of about 5-15%, then the sample median of 691 ml would correspond roughly to 730-810 ml external volume. A larger shell correction may be possible for small breasts or high surface-area-to-volume shapes, so this should be treated as an approximate context correction rather than a calibrated transformation.

## Recommended FEM Volume Test Set

For the current COMSOL pipeline, a practical sensitivity set should cover the sample distribution without overfitting to uncertain segmentation boundaries:

| Test level | Target volume | Rationale |
|---|---:|---|
| Small | 350-400 ml | Around sample 10th percentile; still above very small outliers |
| Lower-mid | 520-600 ml | Around sample Q1 and current Stage 2-5 baseline |
| Median | 690-750 ml | Around sample median/mean and close to Nie et al. MRI mean/median |
| Large | 900-950 ml | Around sample Q3 |
| Very large sensitivity | 1100-1250 ml | Around sample 90th percentile and near Stahl BMI-normal macromastia threshold |

For report-ready Stage 6 tumor comparisons, avoid changing breast volume and tumor parameters simultaneously unless explicitly testing volume-tumor interactions. The first defensible route is:

1. Fixed volume baseline around 585 ml or 700 ml.
2. Tumor location sweep at fixed volume.
3. Tumor size sweep at fixed volume.
4. Later breast-volume sensitivity at no-tumor and one selected tumor case.

## Suggested Report Wording

The 100-sample breast-volume dataset had a median of 691 ml and mean of 728 ml, with an interquartile range of 520-929 ml. These values are consistent with MRI-based literature values around 700-740 cm3, but direct comparison is limited by segmentation boundary definition and patient pose. Because the sample contours were drawn approximately 5 mm inside the external breast boundary, the reported sample volumes should be interpreted as conservative lower-bound internal-envelope volumes rather than full external breast volumes. The current COMSOL anatomical baseline of about 585 ml falls in the lower-mid range of the sample distribution and is therefore a defensible starting volume for geometry and tumor-sensitivity studies.

## Practical Decision for EWS FEM

Use about 585 ml as the current controlled anatomical baseline because it is already validated through Stage 2-5. Add a later volume sensitivity with approximately 400 ml, 700 ml, 950 ml, and 1200 ml targets if the goal is to demonstrate model scalability across breast sizes. For tumor/lesion Stage 6, prioritize controlled comparisons at one volume first; otherwise volume effects may obscure tumor effects.
