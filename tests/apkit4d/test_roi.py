import numpy as np
import pandas as pd
import pytest

from apkit4d.roi import RegionOfInterest
from apkit4d.visualization.data_mapper import create_volume_grid


class TestRegionOfInterestModel:
    def test_valid_creation_and_properties(self):
        roi = RegionOfInterest(x_min=10.0, x_max=50.0, y_min=20.0, y_max=80.0, z_min=5.0, z_max=45.0)
        assert roi.bounds == (10.0, 50.0, 20.0, 80.0, 5.0, 45.0)
        assert roi.size_xyz == (40.0, 60.0, 40.0)
        assert roi.origin_xyz == (10.0, 20.0, 5.0)

    def test_invalid_inverted_coordinates_raise_value_error(self):
        with pytest.raises(ValueError, match="Coordinate ROI non valide"):
            RegionOfInterest(x_min=50.0, x_max=10.0, y_min=0.0, y_max=10.0, z_min=0.0, z_max=10.0)

    def test_dict_roundtrip(self):
        roi = RegionOfInterest(x_min=1.0, x_max=10.0, y_min=2.0, y_max=20.0, z_min=3.0, z_max=30.0)
        d = roi.to_dict()
        assert RegionOfInterest.from_dict(d) == roi

    def test_from_bounds_orders_clamps_and_enforces_min_size(self):
        volume_bounds = (0.0, 100.0, 0.0, 100.0, 0.0, 50.0)
        roi = RegionOfInterest.from_bounds(
            bounds=(120.0, -10.0, 80.0, 30.0, 25.0, 25.0),
            volume_bounds=volume_bounds,
            min_size=2.0,
        )
        assert (roi.x_min, roi.x_max) == (0.0, 100.0)
        assert (roi.y_min, roi.y_max) == (30.0, 80.0)
        assert (roi.z_min, roi.z_max) == (25.0, 27.0)

    def test_from_points_extends_depth_along_view_direction(self):
        volume_bounds = (0.0, 100.0, 0.0, 100.0, 0.0, 80.0)
        p1 = (20.0, 30.0, 80.0)
        p2 = (60.0, 70.0, 80.0)
        roi = RegionOfInterest.from_points(
            p1, p2, volume_bounds=volume_bounds, view_direction=(0.0, 0.0, -1.0)
        )
        assert roi.bounds == (20.0, 60.0, 30.0, 70.0, 0.0, 80.0)

    def test_from_points_extends_flat_axis_when_no_view_direction(self):
        volume_bounds = (0.0, 100.0, 0.0, 100.0, 0.0, 80.0)
        p1 = (10.0, 15.0, 0.0)
        p2 = (50.0, 65.0, 0.0)
        roi = RegionOfInterest.from_points(p1, p2, volume_bounds=volume_bounds)
        assert roi.bounds == (10.0, 50.0, 15.0, 65.0, 0.0, 80.0)


class TestRegionOfInterestSlicingAndFiltering:
    def test_to_voxel_slices_and_sub_origin(self):
        roi = RegionOfInterest(x_min=5.0, x_max=15.0, y_min=10.0, y_max=20.0, z_min=2.0, z_max=6.0)
        slices, sub_origin = roi.to_voxel_slices(
            volume_shape=(10, 50, 50),
            voxel_size=(2.0, 1.0, 1.0),
        )
        assert slices == (slice(1, 4), slice(10, 21), slice(5, 16))
        assert sub_origin == (5.0, 10.0, 2.0)

    def test_to_voxel_slices_clamps_out_of_range_bounds(self):
        roi = RegionOfInterest(x_min=5.0, x_max=99.0, y_min=0.0, y_max=10.0, z_min=-20.0, z_max=999.0)
        slices, sub_origin = roi.to_voxel_slices(
            volume_shape=(10, 20, 20),
            voxel_size=(1.0, 1.0, 1.0),
        )
        assert slices == (slice(0, 10), slice(0, 11), slice(5, 20))
        assert sub_origin == (5.0, 0.0, 0.0)

    def test_extract_subvolume_matches_pyvista_grid_bounds(self):
        shape = (10, 20, 30)  # (Z, Y, X)
        voxel_size = (18.1, 2.8, 2.8)  # (sz, sy, sx) in µm
        volume = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)

        roi = RegionOfInterest(x_min=14.0, x_max=42.0, y_min=5.6, y_max=28.0, z_min=18.1, z_max=72.4)
        sub_vol, sub_origin = roi.extract_subvolume(volume, voxel_size)
        sub_grid = create_volume_grid(sub_vol, voxel_size, offset=sub_origin)

        assert sub_vol.shape == (4, 9, 11)
        np.testing.assert_allclose(sub_grid.bounds, roi.bounds)

    def test_filter_blobs_df_keeps_only_blobs_inside_roi(self):
        roi = RegionOfInterest(x_min=10.0, x_max=20.0, y_min=10.0, y_max=20.0, z_min=10.0, z_max=20.0)
        df = pd.DataFrame(
            {
                "label": [1, 2, 3],
                "x_um": [15.0, 5.0, 20.0],
                "y_um": [15.0, 15.0, 20.0],
                "z_um": [12.0, 12.0, 20.0],
            }
        )
        filtered = roi.filter_blobs_df(df)
        assert list(filtered["label"]) == [1, 3]
