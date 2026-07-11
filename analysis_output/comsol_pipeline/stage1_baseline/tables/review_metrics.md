# stage1_baseline Review Metrics

All values are extracted from existing COMSOL outputs at the case-specific review time.
Blank cells mean that the metric was not exported for that run.

| case_label | configured_dynamic_motion_mode | configured_review_time_s | result_mph_exists | metrics_json_exists | postprocess_completed | image_export_completed | last_output_time_s | expected_dynamic_end_time_s | solve_reached_review_time | solve_reached_expected_end | glandular_fraction_pct | review_avg_displacement_mm | review_max_displacement_mm | review_surface_signed_w_mean_mm | review_surface_signed_w_from_dynamic_start_mm | review_surface_signed_w_relative_to_support_mm | review_surface_disp_mag_mean_mm | review_breast_vm_avg_kpa | review_breast_vm_max_kpa | review_gland_vm_avg_kpa | review_gland_vm_max_kpa | review_adipose_vm_avg_kpa | review_adipose_vm_max_kpa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dynamic simple gland |  | 1.295 | True | True | True | True | 1.256 |  | False |  | 11.945 | 16.741 | 34.019 | -20.079 | 0.106 | -20.079 | 20.452 | 0.408 | 13.931 | 0.671 | 2.077 | 0.372 | 13.931 |
| Static simple gland |  | 1.125 | True | True | True | False | 1.253 |  | True |  | 11.944 | 4.298 | 8.564 |  |  |  |  |  | 4.974 |  | 4.974 |  |  |
| Gravity-only reference | gravity_only | 2.200 | True | True | True | True | 2.190 | 2.200 | False | False | 11.945 | 16.787 | 33.923 | -20.142 | 0.042 | -20.142 | 20.509 | 0.409 | 13.950 | 0.673 | 2.092 | 0.373 | 13.950 |
| Quasi-static gravity sag reference | gravity_only | 5.000 | True | True | True | True | 4.990 | 5.000 | False | False | 11.945 | 17.879 | 36.731 | -21.492 | -0.708 | -21.492 | 21.908 | 0.438 | 14.863 | 0.720 | 2.203 | 0.399 | 14.863 |
| Fixed-support acceleration pulse | fixed_support_acceleration_pulse | 1.475 | True | True | True | False | 2.200 | 2.200 | True | True | 11.945 | 34.149 | 78.796 | -41.491 | -21.312 | -41.491 | 42.761 | 0.864 | 27.747 | 1.420 | 3.863 | 0.789 | 27.747 |
| Fixed-support pulse mild 0.25g | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 2.200 | 2.200 | True | True | 11.944 | 17.758 | 35.686 | -21.310 | -1.129 | -21.310 | 21.688 | 0.433 | 10.733 | 0.713 | 2.368 | 0.395 | 10.733 |
| Smooth support-motion fallback | smooth_support_displacement | 1.295 | True | True | True | True | 1.256 | 2.200 | False | False | 11.945 | 16.741 | 34.019 | -20.079 | 0.106 | -20.079 | 20.452 | 0.408 | 13.931 | 0.671 | 2.090 | 0.372 | 13.931 |
