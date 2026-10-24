import numpy as np
from scipy import ndimage

from apkit4d.blob_finder import BlobParams, _sigmas, log_response


def test_sigmas():
    params = BlobParams(diameter_z_um=384.38, diameter_xy_um=29.234)
    voxel = (17.3, 3.324, 3.324)

    sigma_z = (params.diameter_z_um / 2) / np.sqrt(3) / voxel[0]
    sigma_xy = (params.diameter_xy_um / 2) / np.sqrt(3) / voxel[1]

    np.testing.assert_almost_equal(_sigmas(params, voxel), (sigma_z, sigma_xy, sigma_xy), decimal=7)


def test_sigmas_clamps_at_a_miniminum():
    params = BlobParams(diameter_z_um=0.1, diameter_xy_um=0.1)
    voxel = (1.0, 1.0, 1.0)
    assert _sigmas(params, voxel) == (0.5, 0.5, 0.5)


def test_log_response_of_a_flat_image_produces_zoeroes_response():
    img = np.ones((50, 50, 50), dtype=np.float32) * 10.0
    params = BlobParams()
    voxel = (1.0, 1.0, 1.0)

    _, resp = log_response(img, params, voxel)

    np.testing.assert_almost_equal(resp, 0.0)


def test_log_response_finds_the_peak_corresponding_to_a_blob():
    img = np.zeros((40, 40, 40), dtype=np.float32)
    img[20, 20, 20] = 100.0
    img = ndimage.gaussian_filter(img, sigma=3.0)  # diffuse the peak a bit

    params = BlobParams(diameter_xy_um=10.0, diameter_z_um=30.0)
    _, resp = log_response(img, params, (1.0, 1.0, 1.0))

    assert resp[16, 20, 16] > 0.0
    assert resp[20, 20, 20] > 0.0
    assert resp[0, 0, 0] < 0.0
    assert resp[11, 28, 39] < 0.0
