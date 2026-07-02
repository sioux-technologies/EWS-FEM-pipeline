# stage4_asymmetry Review Metrics

All values are extracted from existing COMSOL outputs at the case-specific review time.
Blank cells mean that the metric was not exported for that run.

| case_label | configured_dynamic_motion_mode | configured_review_time_s | result_mph_exists | metrics_json_exists | postprocess_completed | image_export_completed | last_output_time_s | expected_dynamic_end_time_s | solve_reached_review_time | solve_reached_expected_end | glandular_fraction_pct | review_avg_displacement_mm | review_max_displacement_mm | review_surface_signed_w_mean_mm | review_surface_signed_w_from_dynamic_start_mm | review_surface_signed_w_relative_to_support_mm | review_surface_disp_mag_mean_mm | review_breast_vm_avg_kpa | review_breast_vm_max_kpa | review_gland_vm_avg_kpa | review_gland_vm_max_kpa | review_adipose_vm_avg_kpa | review_adipose_vm_max_kpa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Realistic reference xoffset055 0.25g | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 2.200 | 2.200 | True | True | 24.309 | 2.997 | 5.534 | -3.431 | 0.161 | -3.431 | 3.462 | 0.324 | 1.633 | 0.451 | 1.633 | 0.284 | 1.049 |
| Realistic profile asym. xoffset055 partial | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 0.000 | 2.200 | False | False | 25.197 | 0.000 | 0.000 | -0.000 | 0.000 | -0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
