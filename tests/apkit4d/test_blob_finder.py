import numpy as np
import pandas as pd
from scipy import ndimage

from apkit4d.blob_finder import (
    DETECTION_COLUMNS,
    BlobParams,
    _ellipsoid,
    _sigmas,
    find_blobs,
    find_seeds,
    log_response,
    max_by_label,
    watershed_from_seeds,
)
from apkit4d.image import Image


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


def test_watershed_floods_a_peak_and_generates_a_labeled_region():
    smoothed = np.zeros((30, 30, 30), dtype=np.float32)
    zz, yy, xx = np.ogrid[-10:10, -10:10, -10:10]
    blob = np.exp(-(zz**2 + yy**2 + xx**2) / 10.0).astype(np.float32)

    smoothed[5:25, 5:25, 5:25] = blob

    seeds = np.array([[15, 15, 15]], dtype=np.int64)

    labels = watershed_from_seeds(smoothed, seeds, BlobParams(grow_frac=0.3))

    assert labels[15, 15, 15] == 1
    assert labels[15, 14, 15] == 1
    assert labels[0, 0, 0] == 0


def test_watershed_does_nothing_with_empty_seeds():
    shape = (20, 20, 20)
    smoothed = np.ones(shape, dtype=np.float32)
    seeds = np.empty((0, 3), dtype=np.int64)

    labels = watershed_from_seeds(smoothed, seeds, BlobParams())

    assert labels.shape == shape
    assert np.all(labels == 0)


def test_watershed_segments_regions_with_multiple_seeds():
    smoothed = np.zeros((30, 30, 30), dtype=np.float32)
    smoothed[10, 10, 10] = 1.0
    smoothed[20, 20, 20] = 0.8
    seeds = np.array([[10, 10, 10], [20, 20, 20]], dtype=np.int64)

    labels = watershed_from_seeds(smoothed, seeds, BlobParams(grow_frac=0.1))

    assert labels[10, 10, 10] == 1
    assert labels[20, 20, 20] == 2


def test_find_blobs_returns_empty_df_and_seed_response_when_image_is_below_threshold():
    image = np.zeros((10, 10, 10), dtype=np.float32)
    image[1, 2, 3] = 0.3
    image[9, 8, 6] = 0.234

    df, labels, seed_resp = find_blobs(
        image, BlobParams(threshold=0.5), voxel_dim=(1.0, 1.0, 1.0), return_labels=True
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert list(df.columns) == DETECTION_COLUMNS
    assert labels is None
    assert len(seed_resp) == 0


def give_me_a_smooth_blob(size: tuple[int, int, int], spread: float) -> Image[np.float32]:
    z, y, x = size[0] // 2, size[1] // 2, size[2] // 2
    zz, yy, xx = np.ogrid[-z : z + 1, -y : y + 1, -x : x + 1]
    blob = np.exp(-(zz**2 + yy**2 + xx**2) / spread).astype(np.float32)  # better not to ask...
    return blob


def test_find_blobs_detects_the_blobs_measures_them_and_returns_the_filled_out_data_frame():
    shape = (10, 10, 10)
    image = np.zeros(shape, dtype=np.float32)

    image[2:9, 2:9, 2:9] = give_me_a_smooth_blob((7, 7, 7), 4.0) * 0.9

    params = BlobParams(diameter_xy_um=3.0, diameter_z_um=3.0, threshold=0.01, min_volume_um3=1.0)
    voxel_dim = (1.0, 1.0, 1.0)

    df, labels, seed_resp = find_blobs(
        image, params, voxel_dim, frame=2, offset=(3, 3, 3), return_labels=True
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert df.loc[0, "frame"] == 2
    assert df.loc[0, "z"] == 8.0  # 5 + offset 3
    assert df.loc[0, "y"] == 8.0
    assert df.loc[0, "x"] == 8.0
    assert labels is not None
    assert labels.shape == shape
    assert len(seed_resp) == 1


def test_find_blobs_removes_from_labels_blobs_that_have_a_volume_smaller_than_the_constraint():
    image = np.zeros((10, 10, 10), dtype=np.float32)

    image[2:7, 2:7, 2:7] = give_me_a_smooth_blob((5, 5, 5), 4.0) * 0.9

    params = BlobParams(
        diameter_xy_um=3.0,
        diameter_z_um=3.0,
        threshold=0.01,
        min_volume_um3=10000.0,  # min too big
    )
    df, labels, seed_resp = find_blobs(image, params, (1.0, 1.0, 1.0), return_labels=True)

    assert len(df) == 0
    assert labels is not None
    assert np.all(labels == 0)


def test_find_blobs_removes_from_labels_blobs_that_have_a_volume_bigger_than_the_constraint():
    shape = (10, 10, 10)
    image = np.zeros(shape, dtype=np.float32)
    image[2:9, 2:9, 2:9] = give_me_a_smooth_blob((7, 7, 7), 20.0) * 0.9

    params = BlobParams(
        diameter_xy_um=15.0,
        diameter_z_um=15.0,
        threshold=0.01,
        min_volume_um3=1.0,
        max_volume_um3=5.0,  # max too small
    )

    df, labels, seed_resp = find_blobs(image, params, (1.0, 1.0, 1.0), return_labels=True)

    assert len(df) == 0
    assert labels is not None
    assert np.all(labels == 0)


def test_max_by_label_believe_it_or_not_finds_the_max_for_each_label():
    shape = (3, 3, 3)
    labels = np.zeros(shape, dtype=np.int32)
    values = np.zeros(shape, dtype=np.float32)

    labels[0, 0, 0] = 1
    labels[0, 0, 1] = 1
    values[0, 0, 0] = 2.5
    values[0, 0, 1] = 5.0

    labels[2, 2, 2] = 2
    labels[2, 2, 1] = 2
    values[2, 2, 2] = 10.2
    values[2, 2, 1] = 4.1

    labels[1, 1, 1] = 0  # labeled as background, so should be ignored
    values[1, 1, 1] = 99.0

    out = max_by_label(labels, values, n_lab=3)

    assert isinstance(out, np.ndarray)
    assert out.shape == (3,)
    assert out[0] == 0.0  # background is 0
    assert out[1] == 5.0
    assert out[2] == 10.2


def test_max_by_label_finds_nothing_if_there_is_only_background():
    shape = (3, 3, 3)
    labels = np.zeros(shape, dtype=np.int32)
    values = np.ones(shape, dtype=np.float32) * 5.0

    out = max_by_label(labels, values, n_lab=2)

    assert out.shape == (2,)
    assert np.all(out == 0.0)


def test_max_by_label_returns_the_peak_in_a_singleton_regions():
    labels = np.array([[[1, 2], [0, 0]], [[0, 0], [3, 0]]], dtype=np.int32)
    values = np.array([[[5.4, 9.6], [0.0, 0.0]], [[0.0, 0.0], [1.4, 0.0]]], dtype=np.float32)

    out = max_by_label(labels, values, n_lab=4)

    assert out[0] == 0.0  # background is zeroed
    assert out[1] == 5.4
    assert out[2] == 9.6
    assert out[3] == 1.4
