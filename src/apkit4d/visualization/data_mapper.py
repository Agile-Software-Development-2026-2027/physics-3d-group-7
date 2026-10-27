import numpy as np
import pandas as pd
import pyvista as pv


def create_volume_grid(
    img_array: np.ndarray, voxel_size: tuple[float, float, float], offset: tuple[int, int, int] = (0, 0, 0)
) -> pv.ImageData:
    """
    Create a PyVista ImageData object from a 3D numpy array.

    Parameters:
        img_array (np.ndarray): 3D numpy array representing the volume data.

        voxel_size (tuple): Size of each voxel in the format (z_size, y_size, x_size).

        offset (tuple): Offset for the grid in the format (z_offset, y_offset, x_offset).

        this offset is used to shift the grid in space for future visualization purposes (Ex. ROI selection).

    Returns:
        pv.ImageData: PyVista ImageData object representing the volume grid.
    """

    if img_array is None or img_array.size == 0 or img_array.ndim != 3:
        return pv.ImageData()

    # transpose the array to match PyVista's expected order
    img_xyz = np.transpose(img_array, (2, 1, 0))

    # transpose the voxel size to match the order of the transposed array
    spacing_xyz = (voxel_size[2], voxel_size[1], voxel_size[0])

    grid = pv.ImageData(dimensions=img_xyz.shape, spacing=spacing_xyz, origin=offset)

    """
        VTK do not accept 3d numpy array as point data so we need to flatten the array,
        with order='F' (X axe first)

        point_data is a dictionary-like object that allows you to store additional data,
        associated with the points of the grid.
        we use this to store the flattened image data as point data in the grid
    """
    grid.point_data["values"] = img_xyz.flatten(order="F")
    return grid


def create_blob_mesh(df: pd.DataFrame) -> pv.PolyData:
    """
    This function is used to create the blobs that will be visualized in the 3D space.

    it creates a PyVista PolyData object from a pandas DataFrame containing blob data.
    every row in the DataFrame represents a blob,
    and the columns contain the necessary information to create the mesh.

    Parameters:
        df (pd.DataFrame): DataFrame containing blob data.
        The columns contain the following information:
            - frame: temporal frame index of the image
            - label: unique identifier for the segmented blob
            - z, y, x: centroid coordinates in voxel units (including ROI offset)
            - z_um, y_um, x_um: absolute spatial coordinates of the centroid in micrometers
            - volume_um3: physical volume of the blob in cubic micrometers
            - n_voxels: total number of voxels belonging to the segmented blob
            - z_extent: z dimension of the blob
            - response: number that represents the strenght of the signal
            (how the algorithm is confident that this is a blob)
            - peak: maximum intensity on the smoothed image within the blob's region
            - mean_intensity: average pixel intensity of the raw image within the blob
            - max_intensity: maximum pixel intensity of the raw image within the blob

    Returns:
        pv.PolyData: PyVista PolyData object representing the blobs as spheres in 3D space.

    """
    if df is None or df.empty:
        return pv.PolyData()

    coordinates = df[["x_um", "y_um", "z_um"]].to_numpy()
    poly = pv.PolyData(coordinates)

    column_to_exclude = {"x_um", "y_um", "z_um"}
    # Add the remaining columns as point data to the PolyData object
    for column in df.columns:
        if column not in column_to_exclude:
            poly.point_data[column] = df[column].to_numpy()

    return poly
