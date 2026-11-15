import numpy as np
import pandas as pd
import pytest
import pyvista as pv

from apkit4d.visualization.data_mapper import (
    PreparedTrajectories,
    TrajectoryColorMode,
    TrajectoryRenderConfig,
    build_trajectory_polydata,
    create_blob_mesh,
    create_volume_grid,
)

"""
    Unit tests for the data_mapper module.

    These tests cover the functionality of the create_volume_grid and create_blob_mesh functions.

    In particular, they test the following scenarios:
    - Valid input data
    - Empty input data
    - Non-3D input data for create_volume_grid
    - Axes inversion and spacing for create_volume_grid
    - Valid input data for create_blob_mesh
    - Empty DataFrame for create_blob_mesh
    - Missing required columns in the DataFrame for create_blob_mesh
    - None input for create_blob_mesh
"""


def test_create_volume_grid_with_valid_input():
    img_array = np.random.rand(10, 20, 30)
    voxel_size = (1, 1, 1)
    offset = (0, 0, 0)

    grid = create_volume_grid(img_array, voxel_size, offset)

    assert isinstance(grid, pv.ImageData)
    assert grid.dimensions == (30, 20, 10)
    assert grid.spacing == (1.0, 1.0, 1.0)
    assert grid.origin == (0.0, 0.0, 0.0)
    assert "values" in grid.point_data
    assert grid.point_data["values"].shape[0] == img_array.size


def test_create_volume_grid_with_empty_array():
    grid = create_volume_grid(None, voxel_size=(1, 1, 1))
    assert isinstance(grid, pv.ImageData)
    assert grid.n_points == 0


def test_create_volume_grid_with_non_3d_array():
    img_array = np.random.rand(10, 20)
    grid = create_volume_grid(img_array, voxel_size=(1, 1, 1))
    assert isinstance(grid, pv.ImageData)
    assert grid.n_points == 0


def test_create_volume_grid_axes_inversion():
    img_array = np.random.rand(5, 10, 15)
    voxel_size = (2, 3, 4)
    offset = (1, 2, 3)

    grid = create_volume_grid(img_array, voxel_size, offset)

    assert grid.dimensions == (15, 10, 5)
    assert grid.spacing == (4.0, 3.0, 2.0)
    assert grid.origin == (1.0, 2.0, 3.0)

    assert "values" in grid.point_data
    assert len(grid.point_data["values"]) == img_array.size


def test_create_blob_mesh_with_valid_input():
    data = {
        "x_um": [10.0, 20.0],
        "y_um": [15.0, 25.0],
        "z_um": [5.0, 8.0],
        "volume_um3": [150.0, 300.0],
        "response": [0.8, 0.95],
        "label": [1, 2],
    }
    df = pd.DataFrame(data)

    poly = create_blob_mesh(df)

    assert isinstance(poly, pv.PolyData)
    assert poly.n_points == len(df)

    assert "volume_um3" in poly.point_data
    assert "response" in poly.point_data
    assert "label" in poly.point_data

    assert "x_um" not in poly.point_data


def test_create_blob_mesh_with_empty_dataframe():
    df = pd.DataFrame()
    poly = create_blob_mesh(df)
    assert isinstance(poly, pv.PolyData)
    assert poly.n_points == 0


def test_create_blob_mesh_with_missing_columns():
    data = {
        "x_um": [10.0, 20.0],
        "y_um": [15.0, 25.0],
        # "z_um" column is missing
        "volume_um3": [150.0, 300.0],
        "response": [0.8, 0.95],
        "label": [1, 2],
    }
    df = pd.DataFrame(data)

    with pytest.raises(KeyError):
        create_blob_mesh(df)


def test_create_blob_mesh_with_none_input():
    poly = create_blob_mesh(None)
    assert isinstance(poly, pv.PolyData)
    assert poly.n_points == 0


def _sample_trajectories_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "track_id": [2, 1, 1, 2, 1, 1, 2, -1],
            "frame": [2, 2, 0, 0, 3, 1, 1, 1],
            "x_um": [20.0, 4.0, 0.0, 10.0, 9.0, 1.0, 15.0, 99.0],
            "y_um": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "z_um": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "t_s": [0.2, 0.2, 0.0, 0.0, 0.3, 0.1, 0.1, 0.1],
        }
    )


def test_prepared_trajectories_sorts_filters_and_computes_speeds():
    prepared = PreparedTrajectories.from_dataframe(_sample_trajectories_df())

    # Unlinked track_id == -1 rows are excluded and remaining points are sorted by (track_id, frame)
    assert prepared.n_points == 7
    assert prepared.track_ids.tolist() == [1, 1, 1, 1, 2, 2, 2]
    assert prepared.frames.tolist() == [0, 1, 2, 3, 0, 1, 2]

    # Track 1 displacements: 0->1 (1um/0.1s=10), 1->2 (3um/0.1s=30), 2->3 (5um/0.1s=50)
    np.testing.assert_allclose(prepared.speeds[:4], [10.0, 10.0, 30.0, 50.0], rtol=1e-4)
    # Track 2 displacements: 5um/0.1s = 50
    np.testing.assert_allclose(prepared.speeds[4:], [50.0, 50.0, 50.0], rtol=1e-4)


def test_prepared_trajectories_validates_columns_and_empty_inputs():
    assert PreparedTrajectories.from_dataframe(None).n_points == 0
    assert PreparedTrajectories.from_dataframe(pd.DataFrame()).n_points == 0

    with pytest.raises(ValueError, match="missing required columns"):
        PreparedTrajectories.from_dataframe(pd.DataFrame({"frame": [0], "x_um": [1.0]}))


def test_build_trajectory_polydata_respects_frame_tail_visibility_and_colors():
    prepared = PreparedTrajectories.from_dataframe(_sample_trajectories_df())

    # Frame 0 only has 1 point per track -> no polyline segments yet
    poly0 = build_trajectory_polydata(prepared, 0, TrajectoryRenderConfig())
    assert poly0.n_points == 0

    # Frame 2 with tail_length=-1 includes frames 0, 1, 2 for both tracks (6 vertices, 2 lines)
    poly_all = build_trajectory_polydata(
        prepared,
        2,
        TrajectoryRenderConfig(tail_length=-1, color_mode=TrajectoryColorMode.SPEED, colormap="turbo"),
    )
    assert poly_all.n_points == 6
    assert poly_all.n_cells == 2
    assert "rgb" in poly_all.point_data
    assert poly_all.point_data["rgb"].dtype == np.uint8

    # Switching to Track ID mode gives each track a uniform categorical color different from speed mode
    poly_tid = build_trajectory_polydata(
        prepared,
        2,
        TrajectoryRenderConfig(tail_length=-1, color_mode=TrajectoryColorMode.TRACK_ID),
    )
    t1_mask = poly_tid.point_data["track_id"] == 1
    t2_mask = poly_tid.point_data["track_id"] == 2
    t1_colors = np.unique(poly_tid.point_data["rgb"][t1_mask], axis=0)
    t2_colors = np.unique(poly_tid.point_data["rgb"][t2_mask], axis=0)
    assert len(t1_colors) == 1
    assert len(t2_colors) == 1
    assert not np.array_equal(t1_colors[0], t2_colors[0])

    # Tail length 1 at frame 3 keeps frames [2, 3]: track 1 has 2 pts; track 2 has 1 pt (dropped)
    poly_tail = build_trajectory_polydata(prepared, 3, TrajectoryRenderConfig(tail_length=1))
    assert poly_tail.n_points == 2
    assert poly_tail.n_cells == 1
    assert set(poly_tail.point_data["frame"].tolist()) == {2, 3}

    # tail_length=0 or visible=False produces empty PolyData
    assert build_trajectory_polydata(prepared, 3, TrajectoryRenderConfig(tail_length=0)).n_points == 0
    assert build_trajectory_polydata(prepared, 3, TrajectoryRenderConfig(visible=False)).n_points == 0

    # Unknown colormap gracefully falls back without raising
    poly_fallback = build_trajectory_polydata(
        prepared, 2, TrajectoryRenderConfig(colormap="nonexistent_cmap")
    )
    assert poly_fallback.n_points == 6
