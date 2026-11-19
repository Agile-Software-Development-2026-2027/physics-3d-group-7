"""
Texts of the histograms.
"""

# histograms
SECTION_HISTOGRAMS: str = "Histograms"
HISTOGRAM_ROI_TITLE: str = "Raw ROI Intensities > 0 (sat: {frac_sat:.2%})"
HISTOGRAM_PREPROC_TITLE: str = "Preprocessed ROI Intensities in [0, 1]"
LABEL_HISTOGRAM_INTENSITY: str = "Intensity"
LABEL_HISTOGRAM_AU: str = "AU"
LABEL_HISTOGRAM_COUNTS: str = "Counts"
ROI_INTENSITIES_MIN_LINE: str = "Normalization window lower bound"
ROI_INTENSITIES_MAX_LINE: str = "Normalization window upper bound"
HISTOGRAMS_TIP: str = """🛈 Some histograms have thresholds and bounds that you can drag. Double-click on each
 histogram to reset its zoom, position and the range of both its axes.""".replace("\n", "")
LABEL_HISTOGRAM_NORMALIZED: str = "norm."
# LoG histogram
SEED_HISTOGRAM_EMPTY: str = "LoG response of the candidates"
SEED_HISTOGRAM_TITLE: str = "{count} candidates above the threshold"
SEED_HISTOGRAM_LEFT_AXIS_LABEL: str = "Counts"
SEED_HISTOGRAM_BOTTOM_AXIS_LABEL: str = "LoG Threshold"
