# Batch CLI

## JSON parameters (`params.json`)

The `--params` option accepts a JSON file containing processing settings.

Example:

```json
{
  "channel": 0,
  "first_frame": 0,
  "last_frame": 2,
  "preproc": {
    "denoise_xy_scale_um": 0.0,
    "bg_mode": "None",
    "lowest_intensity": 0.0,
    "highest_intensity": 1000.0
  },
  "blob": {
    "diameter_xy_um": 15.0,
    "threshold": 0.1
  }
}
```

**Available parameters:**

- `channel` – CZI channel index (default: `0`).
- `first_frame`, `last_frame` – first and last frame (0-based, inclusive). Legacy keys `t0` and `t1` are also supported.
- `preproc` – preprocessing settings: `denoise_xy_scale_um`, `denoise_z_scale_um`, `bg_mode`, `bg_percentile`, `bg_sigma_xy_um`, `lowest_intensity`, `highest_intensity`, `logarithmic_compression_enabled`, `gamma_correction_to_apply`, `clahe_enabled`, `clahe_clip`, `clahe_kernel_xy_um`.
- `blob` – blob detection settings: `diameter_xy_um`, `diameter_z_um`, `threshold`, `split`, `grow_frac`, `min_volume_um3`, `max_volume_um3`.

Missing fields use their default values. If `--params` is omitted, saved parameters are used, or defaults if none exist.

CLI frame options (`--first-frame`, `--last-frame`) override the JSON values. If both new and legacy frame keys are present, the new keys take precedence.