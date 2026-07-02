# stage1_baseline Case Status

This table includes requested cases even when metrics/time-series are still missing.

| case_label | result_mph_exists | metrics_json_exists | time_series_csv_exists | postprocess_completed | image_export_completed | image_png_count | expected_image_png_count | legacy_cooper_image_png_count |
|---|---|---|---|---|---|---|---|---|
| Dynamic simple gland | True | True | True | True | True | 10 | 7 | 3 |
| Static simple gland | True | True | True | True | False | 0 | 0 | 0 |
| Gravity-only reference | True | True | True | True | True | 10 | 7 | 3 |
| Quasi-static gravity sag reference | True | True | True | True | True | 7 | 7 | 0 |
| Fixed-support acceleration pulse | True | True | True | True | False | 0 | 0 | 0 |
| Fixed-support pulse mild 0.25g | True | True | True | True | False | 0 | 0 | 0 |
| Fixed-support pulse moderate 0.50g | False | False | False | False | False | 0 | 0 | 0 |
| Smooth support-motion fallback | True | True | True | True | True | 10 | 7 | 3 |
