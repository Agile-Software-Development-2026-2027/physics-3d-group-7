"""
Texts of the preprocessing stage (2).
"""

# preprocessing stage controls
LABEL_PREPROC_DENOISE_XY: str = "Denoise XY (µm)"
LABEL_PREPROC_DENOISE_Z: str = "Denoise Z (µm)"
LABEL_PREPROC_BG_MODE: str = "Background Mode"
LABEL_PREPROC_BG_PERCENTILE: str = "BG Percentile (%)"
LABEL_PREPROC_BG_SIGMA_XY: str = "BG Sigma XY (µm)"
LABEL_PREPROC_NORMALIZATION_ENABLED: str = "Window Normalize Intensities"
LABEL_PREPROC_LOWEST_INTENSITY: str = "Window Min (AU)"
PREPROC_SUGGEST_WINDOW: str = "Suggest Window"
LABEL_PREPROC_HIGHEST_INTENSITY: str = "Window Max (AU)"
LABEL_PREPROC_LOG_COMPRESSION: str = "Logarithmic Compression"
LABEL_PREPROC_GAMMA: str = "Gamma Correction"
LABEL_PREPROC_CLAHE: str = "CLAHE Enhancement"
LABEL_PREPROC_CLAHE_CLIP: str = "CLAHE Clip Limit"
LABEL_PREPROC_CLAHE_KERNEL_XY: str = "CLAHE Kernel XY (µm)"
PREPROC_DENOISE_XY_TOOLTIP: str = "Scale of the Gaussian smoothing along the X, Y axes for denoise"
PREPROC_DENOISE_Z_TOOLTIP: str = "Scale of the Gaussian smoothing along the Z axis for denoise (anisotropic)"
PREPROC_DENOISE_BG_MODE_TOOLTIP: str = "Background removal strategy"
PREPROC_BG_PERCENTILE_TOOLTIP: str = (
    "Subtract the specified percentile of each 2D Z-slice from each voxel in that slice"
)
PREPROC_BG_WIDE_GAUSSIAN_TOOLTIP: str = """Blur radius in µm along the X, Y axes for the Gaussian
smoothing. The Z axis is not affected. Preserves high intensities."""
PREPROC_NORMALIZATION_TOGGLE_TOOLTIP: str = "Toggle intensity normalization from the window to [0, 1]"
PREPROC_LOGARITHMIC_COMPRESSION_TOOLTIP: str = "Highlights dim details and dims bright peaks"
PREPROC_GAMMA_TOOLTIP: str = "Non-linear gamma correction applied when ≠ 1.0"
PREPROC_CLAHE_TOOLTIP: str = (
    "Contrast Limited Adaptive Histogram Equalization (requires window normalization)"
)
PREPROC_CLAHE_CLIP_TOOLTIP: str = "Controls noise amplification"
PREPROC_CLAHE_KERNEL_TOOLTIP: str = "Size of the local neighborhood (tile) used by CLAHE"
PREPROC_RESET: str = "Reset to defaults"
PREPROC_SUGGEST_WINDOW_TOOLTIP: str = "Computed the intensity window from the current volume"
