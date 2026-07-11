# Current Limitations And Next-Step Notes

This file summarises the main limitations and attention points for a next student continuing the COMSOL EWS breast FEM model.

## Model Status

The current project produced a reproducible COMSOL-based model-development workflow with scripted case definitions, constructive geometry, material/scout variants, dynamic loading, surface post-processing, and tumor-overlay placement.

It should be treated as a model-development and sensitivity framework, not as a validated clinical Early Warning Scan simulation.

## Main Limitations

### Dynamic Excitation Is Not Experiment-Calibrated

The dynamic loading routes use controlled acceleration or prescribed support-motion inputs. They are useful for comparing variants under the same input, but they are not calibrated to measured patient, phantom, or EWS motion data.

Future work should define an experimentally meaningful input signal and validate whether the resulting surface-motion amplitudes and phase behaviour are realistic.

### Surface Motion Is The Most EWS-Relevant Output

The EWS application depends mainly on externally observable breast-surface motion. Full-field internal stresses are useful for model interpretation, but should not be overinterpreted as directly measurable EWS signals.

Future post-processing should prioritize robust surface displacement, signed vertical displacement, landmark response, and repeatable comparison metrics.

### Skin Has A Strong Influence

Volumetric skin and skin stiffness strongly affected the displacement response. This means future comparisons must report skin thickness and stiffness explicitly.

A future model should check whether the selected skin representation remains numerically stable and physically defensible across the main tumor, Cooper-support, and dynamic-loading cases.

### Cooper-Like Support Is Simplified

The current Cooper implementation is a simplified support approximation. It does not reconstruct the anatomical Cooper-ligament network.

The current results showed only small global displacement changes for the tested support variants. This should be interpreted as limited effect in the implemented support route, not as evidence that Cooper's ligaments are generally unimportant.

### Tumor Overlay Is Analytic

The tumor route uses an analytic spherical mask inside the existing breast volume. It is not a segmented anatomical tumor domain.

Tumor placement was successfully implemented, and selected tumor-mask metrics were produced, but a complete matched tumor/no-tumor dynamic sensitivity study remains future work.

### Material Definitions Are Sensitivity Values

The material values are literature-based modelling scales and sensitivity settings. They are not patient-specific calibrated measurements.

The small-strain stiffness values derived from Mooney-Rivlin coefficients are useful for comparison, but they do not replace the underlying constitutive assumptions.

### COMSOL And FEBio Are Not One-To-One Comparable

The COMSOL model builds on the previous FEBio work conceptually, but it is a separate implementation route. Geometry, support definitions, solver settings, material implementation, loading and post-processing differ.

Previous FEBio results are useful as project context and mechanical benchmarks, not as direct validation of the current COMSOL output.

### Large Result Files And Post-Processing Cost

Some solved `.mph` files are large, and full `ews_surface` post-processing can be slow or impractical on a local laptop. The lightweight `global` mode is useful for smoke tests, but it cannot replace full surface/stress export when those outputs are needed.

Future work should consider shorter paths, clearer case names, selected output reduction, and possibly TU/e/HPC execution for large sweeps.

## Recommended Next Steps

1. Define one clean reference case with short case naming and complete post-processing.
2. Repeat the most important sensitivity comparisons with matched no-tumor/no-Cooper/no-skin controls where needed.
3. Improve dynamic excitation using measured or experimentally motivated motion data.
4. Build a compact surface-evaluation workflow that produces report-ready metrics without manual COMSOL interaction.
5. Revisit the skin and Cooper-support definitions after the dynamic input and surface metrics are stable.
6. Extend tumor analysis only after matched controls and full surface/tumor-mask post-processing are reliable.

## Files Worth Reading

- `parameter_overview.md`
- `pipeline_notes/comsol_pipeline_guide.md`
- `literature_overviews/material_parameter_literature_overview.md`
- `model_justification/tumor_overlay_plan.md`
