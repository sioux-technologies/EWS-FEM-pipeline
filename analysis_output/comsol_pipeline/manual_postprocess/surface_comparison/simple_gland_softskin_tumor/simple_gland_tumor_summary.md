# Simple-Gland Tumor vs Control Summary

Comparison: simple-gland 1.5 mm soft volumetric skin + soft interior, 1.25g, no-Cooper.

## Global Derived Values

| Case | Peak avg disp (mm) | Peak max disp (mm) | Peak max VM (kPa) |
|---|---:|---:|---:|
| simple_softskin_control | 22.554127 | 45.582 | 19.283 |
| simple_softskin_tumor | 22.536 | 45.486 | 19.275 |

Tumor minus control: peak avg displacement -0.018127 mm (-0.0804%), peak max displacement -0.096 mm (-0.2106%), peak max VM -0.008 kPa (-0.0415%).

## Outer-Surface Summary

| Case | Nodes | Peak mean surface disp (mm) | Peak max surface disp (mm) | Peak max surface VM (kPa) |
|---|---:|---:|---:|---:|
| simple_softskin_control | 2776 | 27.999 | 45.349 | 16.458 |
| simple_softskin_tumor | 2776 | 27.948 | 45.204 | 16.455 |

Interpretation: this simple-gland tumor scout shows no meaningful global or aggregate surface-displacement effect. This is useful as a pipeline/material-coupling check, but not yet evidence that the tumor signal is absent in the final model.
