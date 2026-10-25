import numpy as np
from scipy import ndimage

from apkit4d.blob_finder import BlobParams, _ellipsoid, _sigmas, find_seeds, log_response


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


def test_ellipsoid_radii_are_clampled_at_a_minimum_of_one():
    radii = (0.1, 0.0, -2.5)
    mask = _ellipsoid(radii)

    # Clamps at 1. Dimensions along an axis is 2(1) + 1 = 3
    assert mask.shape == (3, 3, 3)


def test_ellipsoid_corners_are_false():
    mask = _ellipsoid((2.0, 2.0, 2.0))

    assert mask[0, 0, 0] is np.False_
    assert mask[-1, -1, -1] is np.False_
    assert mask[2, 2, 2] is np.True_  # center
    assert mask[3, 3, 3] is np.True_
    assert mask[4, 4, 4] is np.False_
    assert mask[-2, -2, -2] is np.True_
    assert mask[-3, -3, -3] is np.True_
    assert mask[4, 3, 4] is np.False_


def test_find_seeds_finds_a_single_peak_above_the_threshold():
    response = np.zeros((7, 7, 7), dtype=np.float32)
    peak_coord = (4, 4, 4)
    response[peak_coord] = 0.8  # above threshold

    seeds = find_seeds(response, BlobParams(threshold=0.1), (1.0, 1.0, 1.0))

    assert len(seeds) == 1
    assert tuple(seeds[0]) == peak_coord


def test_find_seeds_seeds_below_threshold_are_excluded():
    response = np.zeros((10, 10, 10), dtype=np.float32)
    response[3, 2, 4] = 0.05
    response[7, 8, 6] = 0.5

    seeds = find_seeds(response, BlobParams(threshold=0.2), (1.0, 1.0, 1.0))

    assert len(seeds) == 1
    assert tuple(seeds[0]) == (7, 8, 6)


def test_find_seeds_passing_an_explicity_threshold_overrides_the_one_in_blob_params():
    response = np.zeros((7, 7, 7), dtype=np.float32)
    response[4, 3, 5] = 0.3

    seeds = find_seeds(response, BlobParams(threshold=0.1), (1.0, 1.0, 1.0), threshold=0.5)

    assert len(seeds) == 0


def test_find_seeds_suppresses_peaks_closer_than_the_split_distance():
    response = np.zeros((8, 8, 8), dtype=np.float32)

    # Distance along an axis is split * (diameter / voxel_dim) / 2 along that axis. So in this case
    # minimum distance is 2 * 2, because [-r : r + 1]
    response[6, 6, 3] = 0.9  # higher peak
    response[6, 6, 6] = 0.7  # secondary peak, thouches the previous
    response[1, 2, 3] = 0.5  # unrelated peak

    params = BlobParams(threshold=0.1, split=2.0, diameter_xy_um=2.1, diameter_z_um=2.1)

    seeds = find_seeds(response, params, (1.0, 1.0, 1.0))

    assert len(seeds) == 2
    assert [1, 2, 3] in seeds
    assert [6, 6, 3] in seeds
