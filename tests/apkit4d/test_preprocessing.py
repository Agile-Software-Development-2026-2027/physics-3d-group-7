import numpy as np

from apkit4d.preprocessing import BgMode, PreprocParams, denoise, subtract_background


def test_denoise_does_no_filter_when_scales_are_set_to_zero():
    shape = (10, 10, 10)
    vol = np.full(shape, 1000, dtype=np.uint16)
    params = PreprocParams(denoise_xy_um=0.0, denoise_z_um=0.0)

    result = denoise(vol, params, (1.0, 1.0, 1.0))

    assert result.dtype == np.float32
    assert result.shape == shape
    assert np.array_equal(result, vol.astype(np.float32))  # unchanged


def test_denoise_blurs_sharp_points_with_gaussian_smoothing_when_scales_are_positive():
    shape = (15, 15, 15)
    vol = np.zeros(shape, dtype=np.uint16)

    vol[7, 7, 7] = 60_000  # peak

    params = PreprocParams(denoise_xy_um=10.5, denoise_z_um=10.5)

    result = denoise(vol, params, (1.0, 1.0, 1.0))

    assert result.dtype == np.float32
    assert result.shape == shape

    assert result[7, 7, 7] < 60_000  # peak is smoothed

    assert result[7, 7, 8] > 0.0  # smoothing touches neighbors
    assert result[8, 7, 7] > 0.0


def test_preproc_params_defaults_crystallized():
    params = PreprocParams()
    assert params.denoise_xy_um == 0.0
    assert params.denoise_z_um == 0.0
    assert params.bg_mode == BgMode.NONE
    assert params.bg_percentile == 50.0
    assert params.bg_sigma_xy_um == 60.0
    assert params.denoise_xy_um == 0.0
    assert params.denoise_z_um == 0.0


def test_preproc_params_to_dict():
    params = PreprocParams(
        denoise_xy_um=1.5,
        denoise_z_um=3.0,
        bg_mode=BgMode.PERCENTILE_PER_SLICE,
        bg_percentile=39.4,
        bg_sigma_xy_um=99.1,
    )
    d = params.to_dict()

    assert isinstance(d, dict)
    assert d["denoise_xy_um"] == 1.5
    assert d["denoise_z_um"] == 3.0
    assert d["bg_mode"] == BgMode.PERCENTILE_PER_SLICE
    assert d["bg_percentile"] == 39.4
    assert d["bg_sigma_xy_um"] == 99.1


def test_preproc_params_from_dict():
    params = PreprocParams.from_dict(
        {
            "denoise_xy_um": 2.0,
            "denoise_z_um": 4.5,
            "bg_mode": BgMode.WIDE_GAUSSIAN,
            "bg_percentile": 38.1,
            "bg_sigma_xy_um": 1.0,
        }
    )

    assert params.denoise_xy_um == 2.0
    assert params.denoise_z_um == 4.5
    assert params.bg_mode == BgMode.WIDE_GAUSSIAN
    assert params.bg_percentile == 38.1
    assert params.bg_sigma_xy_um == 1.0


def test_preproc_params_from_dict_ignores_extra_keys():
    params = PreprocParams.from_dict(
        {
            "denoise_xy_um": 1.0,
            "lalalalal": 1324,
            "bububububu": "test",
        }
    )

    assert params.denoise_xy_um == 1.0
    assert params.bg_mode == BgMode.NONE
    assert not hasattr(params, "unknown_parameter")


def test_preproc_params_from_dict_handles_empty():
    params = PreprocParams.from_dict({})

    assert params.denoise_xy_um == 0.0  # default
    assert params.denoise_z_um == 0.0


def test_preproc_params_from_dict_handles_none():
    params = PreprocParams.from_dict(None)

    assert params.denoise_xy_um == 0.0  # defaults
    assert params.denoise_z_um == 0.0


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
