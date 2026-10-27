import numpy as np
import pandas as pd
import pytest
import pyvista as pv

from apkit4d.visualization.data_mapper import create_blob_mesh, create_volume_grid

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
