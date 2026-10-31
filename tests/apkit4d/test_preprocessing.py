import numpy as np

from apkit4d.preprocessing import (
    BgMode,
    PreprocParams,
    clahe,
    denoise,
    gamma_correction,
    logarithmic_compression,
    normalize_intensity,
    preprocess,
    subtract_background,
)


def test_denoise_does_no_filter_when_scales_are_set_to_zero():
    shape = (10, 10, 10)
    vol = np.full(shape, 1000, dtype=np.float32)
    params = PreprocParams(denoise_xy_scale_um=0.0, denoise_z_scale_um=0.0)

    result = denoise(vol, params, (1.0, 1.0, 1.0))

    assert result.dtype == np.float32
    assert result.shape == shape
    assert np.array_equal(result, vol.astype(np.float32))  # unchanged


def test_denoise_blurs_sharp_points_with_gaussian_smoothing_when_scales_are_positive():
    shape = (15, 15, 15)
    vol = np.zeros(shape, dtype=np.float32)

    vol[7, 7, 7] = 60_000  # peak

    params = PreprocParams(denoise_xy_scale_um=10.5, denoise_z_scale_um=10.5)

    result = denoise(vol, params, (1.0, 1.0, 1.0))

    assert result.dtype == np.float32
    assert result.shape == shape

    assert result[7, 7, 7] < 60_000  # peak is smoothed

    assert result[7, 7, 8] > 0.0  # smoothing touches neighbors
    assert result[8, 7, 7] > 0.0


def test_preproc_params_defaults_crystallized():
    params = PreprocParams()
    assert params.bg_mode == BgMode.NONE
    assert params.bg_percentile == 50.0
    assert params.bg_sigma_xy_um == 60.0
    assert params.denoise_xy_scale_um == 0.0
    assert params.denoise_z_scale_um == 0.0


def test_preproc_params_to_dict():
    params = PreprocParams(
        denoise_xy_scale_um=1.5,
        denoise_z_scale_um=3.0,
        bg_mode=BgMode.PERCENTILE_PER_SLICE,
        bg_percentile=39.4,
        bg_sigma_xy_um=99.1,
    )
    d = params.to_dict()

    assert isinstance(d, dict)
    assert d["denoise_xy_scale_um"] == 1.5
    assert d["denoise_z_scale_um"] == 3.0
    assert d["bg_mode"] == BgMode.PERCENTILE_PER_SLICE
    assert d["bg_percentile"] == 39.4
    assert d["bg_sigma_xy_um"] == 99.1


def test_preproc_params_from_dict():
    params = PreprocParams.from_dict(
        {
            "denoise_xy_scale_um": 2.0,
            "denoise_z_scale_um": 4.5,
            "bg_mode": BgMode.WIDE_GAUSSIAN,
            "bg_percentile": 38.1,
            "bg_sigma_xy_um": 1.0,
        }
    )

    assert params.denoise_xy_scale_um == 2.0
    assert params.denoise_z_scale_um == 4.5
    assert params.bg_mode == BgMode.WIDE_GAUSSIAN
    assert params.bg_percentile == 38.1
    assert params.bg_sigma_xy_um == 1.0


def test_preproc_params_from_dict_ignores_extra_keys():
    params = PreprocParams.from_dict(
        {
            "denoise_xy_scale_um": 1.0,
            "lalalalal": 1324,
            "bububububu": "test",
        }
    )

    assert params.denoise_xy_scale_um == 1.0
    assert params.bg_mode == BgMode.NONE
    assert not hasattr(params, "unknown_parameter")


def test_preproc_params_from_dict_handles_empty():
    params = PreprocParams.from_dict({})

    assert params.denoise_xy_scale_um == 0.0  # default
    assert params.denoise_z_scale_um == 0.0


def test_preproc_params_from_dict_handles_none():
    params = PreprocParams.from_dict(None)

    assert params.denoise_xy_scale_um == 0.0  # defaults
    assert params.denoise_z_scale_um == 0.0


def test_subtract_background_with_none_bg_mode_leaves_the_volume_unchanged():
    vol = np.full((3, 10, 10), 29834.0, dtype=np.float32)

    result = subtract_background(vol, PreprocParams(bg_mode=BgMode.NONE), (1.0, 1.0, 1.0))

    np.testing.assert_array_almost_equal(result, 29834.0)


def test_subtract_background_with_percentile_per_slice_subtracts_the_percentile_from_the_respective_slice():
    vol = np.zeros((2, 10, 10), dtype=np.float32)

    vol[0, :, :] += 50.0  # slice for z=0, all 50.0 with a peak of 150.0
    vol[0, 0, 0] = 140.0

    vol[1, :, :] += 100.0  # slice for z=1, all 100.0 with a peak of 200.0
    vol[1, 0, 0] = 200.0

    p = PreprocParams(bg_mode=BgMode.PERCENTILE_PER_SLICE, bg_percentile=50.0)

    result = subtract_background(vol, p, (1.0, 1.0, 1.0))

    assert result[0, 5, 5] == 0.0  # the fiftieth percentile is 50.0, so that is subtracted
    assert result[1, 5, 5] == 0.0
    assert result[0, 0, 0] == 90.0

    assert result[1, 2, 3] == 0.0  # fiftieth percentile can only be 100.0
    assert result[1, 0, 0] == 100.0


def test_subtract_background_wide_gaussian_subtracts_a_coarse_grained_blur():
    shape = (5, 20, 20)
    vol = np.ones(shape, dtype=np.float32) * 40.0
    vol[2, 10, 10] = 200.0  # peak in the middle

    p = PreprocParams(bg_mode=BgMode.WIDE_GAUSSIAN, bg_sigma_xy_um=2.0)

    result = subtract_background(vol, p, (1.0, 1.0, 1.0))

    assert result[2, 0, 0] < 2.0  # background close to zero
    assert result[2, 10, 10] > 150.0  # peak much higher


def test_subtract_background_produces_clips_value_above_zero():
    vol = np.ones((1, 5, 5), dtype=np.float32) * 10.0

    vol[0, 0, 0] = 50.0  # this is the percentile

    p = PreprocParams(bg_mode=BgMode.PERCENTILE_PER_SLICE, bg_percentile=100.0)

    result = subtract_background(vol, p, voxel_dim=(1.0, 1.0, 1.0))
    assert result.min() >= 0.0


def test_normalize_intensity():
    vol = np.array([10.0, 60.0, 110.0], dtype=np.float32)
    p = PreprocParams(lowest_intensity=10.0, highest_intensity=110.0)

    result = normalize_intensity(vol, p)

    assert result.dtype == np.float32
    np.testing.assert_almost_equal(result, np.array([0.0, 0.5, 1.0], dtype=np.float32))


def test_normalize_intensity_clips_values_below_lowest_intensity():
    vol = np.array([-5.0, 0.0, 10.0, 50.0], dtype=np.float32)
    p = PreprocParams(lowest_intensity=10.0, highest_intensity=110.0)

    result = normalize_intensity(vol, p)

    assert result[0] == 0.0
    assert result[1] == 0.0
    assert result[2] == 0.0


def test_normalize_intensity_clips_values_above_highest_intensity():
    vol = np.array([50.0, 110.0, 150.0, 300.0], dtype=np.float32)
    p = PreprocParams(lowest_intensity=10.0, highest_intensity=110.0)

    result = normalize_intensity(vol, p)

    assert result[1] == 1.0
    assert result[2] == 1.0
    assert result[3] == 1.0


def test_normalize_intensity_zero_span_is_handled():
    vol = np.array([50.0, 55.0], dtype=np.float32)
    p = PreprocParams(lowest_intensity=50.0, highest_intensity=50.0)

    result = normalize_intensity(vol, p)

    assert result.dtype == np.float32
    assert not np.any(np.isnan(result))
    assert not np.any(np.isinf(result))


def test_logarithmic_compression_maps_zero_to_zero_and_one_to_one():
    vol = np.array([0.0, 1.0], dtype=np.float32)
    result = logarithmic_compression(vol)

    expected = np.array([0.0, 1.0], dtype=np.float32)
    np.testing.assert_almost_equal(result, expected)


def test_logarithmic_compression_mid_range_are_boosted():
    vol = np.array([0.1], dtype=np.float32)
    result = logarithmic_compression(vol)

    # log1p(1000 * 0.1) / log1p(1000) = 4.615 / 6.909 = 0.668
    assert 0.65 < result[0] < 0.70


def test_gamma_correction_does_nothing_if_gamma_is_one():
    vol = np.array([0.0, 0.5, 1.0], dtype=np.float32)

    result = gamma_correction(vol, PreprocParams(gamma_correction_to_apply=1.0))

    np.testing.assert_array_equal(result, vol)
    assert result is vol  # same reference


def test_gamma_correction_less_than_one_lifts_mid_tones():
    vol = np.array([0.0, 0.25, 1.0], dtype=np.float32)

    result = gamma_correction(vol, PreprocParams(gamma_correction_to_apply=0.5))

    expected = np.array([0.0, 0.5, 1.0], dtype=np.float32)  # 0.25 ^ 0.5 = 0.5
    np.testing.assert_almost_equal(result, expected)
    assert result.dtype == np.float32


def test_gamma_correction_greater_than_one_darkens_mid_tones():
    vol = np.array([0.0, 0.5, 1.0], dtype=np.float32)
    p = PreprocParams(gamma_correction_to_apply=2.0)

    result = gamma_correction(vol, p)

    expected = np.array([0.0, 0.25, 1.0], dtype=np.float32)  # 0.5 ^ 2.0 = 0.25
    np.testing.assert_allclose(result, expected, atol=1e-5)
    assert result.dtype == np.float32


def test_clahe():
    vol = np.random.rand(4, 32, 32).astype(np.float32)  # 4 slices 32x32
    p = PreprocParams(clahe_clip=0.01, clahe_kernel_xy_um=4.0)
    voxel_dim = (1.0, 0.5, 0.5)  # kxy = max(8, int(round(4.0 / 0.5))) = 8

    result = clahe(vol, p, voxel_dim)

    assert result.shape == (4, 32, 32)
    assert result.dtype == np.float32
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_clahe_clamps_kz_kxy_to_boundaries():
    vol = np.random.rand(2, 16, 16).astype(np.float32)  # volume.shape[0] // 4 = 0, kz becomes max(2, 0) = 2
    p = PreprocParams(clahe_clip=0.01, clahe_kernel_xy_um=0.01)  # small kernel, kxy becomse 8

    result = clahe(vol, p, (1.0, 1.0, 1.0))

    assert result.shape == (2, 16, 16)
    assert result.dtype == np.float32
    assert not np.any(np.isnan(result))


def test_preprocess_pipeline():
    vol = np.random.rand(2, 10, 16).astype(np.float32) * 100.0

    p = PreprocParams(
        lowest_intensity=0.0,
        highest_intensity=100.0,
        logarithmic_compression_enabled=False,
        clahe_enabled=False,
    )

    result = preprocess(vol, p, (1.0, 1.0, 1.0))

    assert result.shape == (2, 10, 16)
    assert result.dtype == np.float32
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_preprocess_pipeline_with_clache():
    vol = np.random.rand(4, 32, 32).astype(np.float32) * 100.0

    p = PreprocParams(
        lowest_intensity=0.0,
        highest_intensity=100.0,
        logarithmic_compression_enabled=False,
        clahe_enabled=True,
    )
    voxel_dim = (1.0, 1.0, 1.0)

    result = preprocess(vol, p, voxel_dim)

    assert result.shape == (4, 32, 32)
    assert result.dtype == np.float32
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_preprocess_logarithmic_compression():
    vol = np.random.rand(2, 10, 16).astype(np.float32) * 100.0

    p = PreprocParams(
        lowest_intensity=0.0,
        highest_intensity=100.0,
        logarithmic_compression_enabled=True,
    )

    result = preprocess(vol, p, (1.0, 1.0, 1.0))

    assert result.shape == (2, 10, 16)
    assert result.dtype == np.float32
    assert result.min() >= 0.0
    assert result.max() <= 1.0
