# tier1_comparison_without_stage1 Review Metrics

All values are extracted from existing COMSOL outputs at the case-specific review time.
Blank cells mean that the metric was not exported for that run.

| case_label | configured_dynamic_motion_mode | configured_review_time_s | result_mph_exists | metrics_json_exists | postprocess_completed | image_export_completed | last_output_time_s | expected_dynamic_end_time_s | solve_reached_review_time | solve_reached_expected_end | glandular_fraction_pct | review_avg_displacement_mm | review_max_displacement_mm | review_surface_signed_w_mean_mm | review_surface_signed_w_from_dynamic_start_mm | review_surface_signed_w_relative_to_support_mm | review_surface_disp_mag_mean_mm | review_breast_vm_avg_kpa | review_breast_vm_max_kpa | review_gland_vm_avg_kpa | review_gland_vm_max_kpa | review_adipose_vm_avg_kpa | review_adipose_vm_max_kpa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Stage 2 xoffset055 chestwall | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 2.200 | 2.200 | True | True | 9.162 | 3.033 | 6.164 | -3.634 | 0.133 | -3.634 | 3.664 | 0.311 | 1.348 | 0.687 | 1.348 | 0.273 | 0.640 |
| Stage 3 realistic glandular | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 2.200 | 2.200 | True | True | 24.308 | 2.998 | 5.535 | -3.432 | 0.161 | -3.432 | 3.463 | 0.324 | 1.674 | 0.451 | 1.674 | 0.284 | 1.104 |
| Stage 4 realistic reference | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 2.200 | 2.200 | True | True | 24.309 | 2.997 | 5.534 | -3.431 | 0.161 | -3.431 | 3.462 | 0.324 | 1.633 | 0.451 | 1.633 | 0.284 | 1.049 |
| Stage 5 no-Cooper control | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 2.200 | 2.200 | True | True | 24.309 | 2.998 | 5.535 | -3.432 | 0.161 | -3.432 | 3.463 | 0.324 | 1.615 | 0.451 | 1.615 | 0.284 | 1.076 |
