# stage1_baseline Summary Results

Compact report table for quick cross-case comparison. Values are taken at the case-specific review time unless noted.

| case_label | last_output_time_s | solve_reached_expected_end | breast_volume_ml | glandular_fraction_pct | review_avg_displacement_mm | review_surface_signed_w_from_dynamic_start_mm | review_nipple_w_from_dynamic_start_mm | review_breast_vm_avg_kpa | review_breast_vm_max_kpa | review_gland_vm_avg_kpa | review_adipose_vm_avg_kpa |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Dynamic simple gland | 1.256 |  | 718.711 | 11.945 | 16.741 | 0.106 |  | 0.408 | 13.931 | 0.671 | 0.372 |
| Static simple gland | 1.253 |  | 718.717 | 11.944 | 4.298 |  |  |  | 4.974 |  |  |
| Gravity-only reference | 2.190 | False | 718.711 | 11.945 | 16.787 | 0.042 |  | 0.409 | 13.950 | 0.673 | 0.373 |
| Quasi-static gravity sag reference | 4.990 | False | 718.711 | 11.945 | 17.879 | -0.708 |  | 0.438 | 14.863 | 0.720 | 0.399 |
| Fixed-support acceleration pulse | 2.200 | True | 718.711 | 11.945 | 34.149 | -21.312 |  | 0.864 | 27.747 | 1.420 | 0.789 |
| Fixed-support pulse mild 0.25g | 2.200 | True | 718.715 | 11.944 | 17.758 | -1.129 |  | 0.433 | 10.733 | 0.713 | 0.395 |
| Smooth support-motion fallback | 1.256 | False | 718.711 | 11.945 | 16.741 | 0.106 |  | 0.408 | 13.931 | 0.671 | 0.372 |
