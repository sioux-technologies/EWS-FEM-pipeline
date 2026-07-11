# stage2_chestwall Review Metrics

All values are extracted from existing COMSOL outputs at the case-specific review time.
Blank cells mean that the metric was not exported for that run.

| case_label | configured_dynamic_motion_mode | configured_review_time_s | result_mph_exists | metrics_json_exists | postprocess_completed | image_export_completed | last_output_time_s | expected_dynamic_end_time_s | solve_reached_review_time | solve_reached_expected_end | glandular_fraction_pct | review_avg_displacement_mm | review_max_displacement_mm | review_surface_signed_w_mean_mm | review_surface_signed_w_from_dynamic_start_mm | review_surface_signed_w_relative_to_support_mm | review_surface_disp_mag_mean_mm | review_breast_vm_avg_kpa | review_breast_vm_max_kpa | review_gland_vm_avg_kpa | review_gland_vm_max_kpa | review_adipose_vm_avg_kpa | review_adipose_vm_max_kpa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| X-offset 0.055 m auto-align 0.25g | fixed_support_acceleration_pulse | 1.550 | True | True | True | False | 2.200 | 2.200 | True | True | 9.162 | 3.033 | 6.164 | -3.634 | 0.133 | -3.634 | 3.664 | 0.311 | 1.348 | 0.687 | 1.348 | 0.273 | 0.640 |
| Slab reference |  | 1.125 | False | True | True | True | 1.252 |  | True |  | 11.944 | 6.002 | 11.911 |  |  |  |  | 0.445 | 11.771 | 0.883 | 3.573 | 0.385 | 11.771 |
| VP mild g1025 |  | 1.125 | False | True | True | True | 1.254 |  | True |  | 11.216 | 5.907 | 11.954 |  |  |  |  | 0.440 | 1.828 | 0.917 | 1.828 | 0.380 | 1.141 |
| VP mild g1050 |  | 1.125 | False | True | True | True | 1.252 |  | True |  | 11.492 | 5.931 | 11.980 |  |  |  |  | 0.442 | 1.916 | 0.908 | 1.916 | 0.382 | 1.506 |
