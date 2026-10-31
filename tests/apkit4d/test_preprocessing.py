import numpy as np

from apkit4d.preprocessing import PreprocParams, denoise


def test_denoise_does_no_filter_when_scales_are_set_to_zero():
    shape = (10, 10, 10)
    vol = np.full(shape, 1000, dtype=np.uint16)
    params = PreprocParams(denoise_xy_scale_um=0.0, denoise_z_scale_um=0.0)

    result = denoise(vol, params, (1.0, 1.0, 1.0))

    assert result.dtype == np.float32
    assert result.shape == shape
    assert np.array_equal(result, vol.astype(np.float32))  # unchanged


def test_denoise_blurs_sharp_points_with_gaussian_smoothing_when_scales_are_positive():
    shape = (15, 15, 15)
    vol = np.zeros(shape, dtype=np.uint16)

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
    assert params.denoise_xy_scale_um == 0.0
    assert params.denoise_z_scale_um == 0.0


def test_preproc_params_to_dict():
    params = PreprocParams(denoise_xy_scale_um=1.5, denoise_z_scale_um=3.0)
    d = params.to_dict()

    assert isinstance(d, dict)
    assert d["denoise_xy_scale_um"] == 1.5
    assert d["denoise_z_scale_um"] == 3.0


def test_preproc_params_from_dict():
    params = PreprocParams.from_dict({"denoise_xy_scale_um": 2.0, "denoise_z_scale_um": 4.5})

    assert params.denoise_xy_scale_um == 2.0
    assert params.denoise_z_scale_um == 4.5


def test_preproc_params_from_dict_ignores_extra_keys():
    params = PreprocParams.from_dict(
        {
            "denoise_xy_scale_um": 1.0,
            "lalalalal": 1324,
            "bububububu": "test",
        }
    )

    assert params.denoise_xy_scale_um == 1.0
    assert not hasattr(params, "unknown_parameter")


def test_preproc_params_from_dict_handles_empty():
    params = PreprocParams.from_dict({})

    assert params.denoise_xy_scale_um == 0.0  # default
    assert params.denoise_z_scale_um == 0.0


def test_preproc_params_from_dict_handles_none():
    params = PreprocParams.from_dict(None)

    assert params.denoise_xy_scale_um == 0.0  # defaults
    assert params.denoise_z_scale_um == 0.0
