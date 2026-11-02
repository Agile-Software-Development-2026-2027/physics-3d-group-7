"""Spatial neighborhood search indexing abstractions.

This module provides a unified interface for querying spatial neighbors within a specified radius.
The CPU implementation is backed by `scipy.spatial.cKDTree`, while the protocol design enables
plans for future GPU-accelerated spatial structures.
Some example of possibel algorythms are (e.g., uniform grid hashing or batched pairwise distance kernels).
The actual implementation, the legacy one too, focus solely on CPU bu that feels like a dumb choice for
heavy computin on matrices.

RefactorNote:
    This script is pretty simple i wated more times on comments and docstring...
    I will avoid addinmore comments
"""

from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree  # type: ignore ty: ignore[unresolved-import]

# Apparently cKDTree is basically KDTree but written in C so it's faster
# but for some reason ty and intellisense have probelms locating it


class SpatialIndex(Protocol):
    """Protocol defining the interface for spatial neighbor searches.

    Out hate for python interfaces is storng but love for interfaces is storngest.
    """

    def query_radius(self, query_points: NDArray[np.float32], radius: float) -> list[list[int]]:
        """Query indices of stored points within a given radius from each query point.

        Args:
            query_points: (M, D) array of query coordinates.
            radius: Search radius distance threshold.

        Returns:
            A list of length M, where element i is a list of integer indices
            of points within radius from query_points[i].
        """
        ...


class KDTreeSpatialIndex:
    """
    CPU-backed spatial search index using `scipy.spatial.cKDTree`.
    """

    def __init__(self, points: NDArray[np.float32]) -> None:
        """Initialize the KD-tree index.

        Args:
            points: (N, D) array of reference coordinates.
        """
        self._points = np.asarray(points, dtype=np.float32)
        self._tree = cKDTree(self._points) if len(self._points) > 0 else None

    def query_radius(self, query_points: NDArray[np.float32], radius: float) -> list[list[int]]:
        """
        Find neighbor indices within radius.

        Args:
            query_points: (M, D) query positions.
            radius: Radius threshold.

        Returns:
            List of neighbor index lists for each query point.
        """
        pts = np.asarray(query_points, dtype=np.float32)
        if self._tree is None or len(pts) == 0:
            return [[] for _ in range(len(pts))]
        return self._tree.query_ball_point(pts, radius)


class GPUAcceleratedSpatialIndex:
    """Placeholder for a GPU-accelerated spatial search index.

    This class is intended for future implementation of GPU-based spatial indexing.
    """

    def __init__(self, points: NDArray[np.float32]) -> None:
        """
        Initialize the GPU-accelerated index.

        Args:
            points: (N, D) array of reference coordinates.
        """
        raise NotImplementedError("GPUAcceleratedSpatialIndex is not yet implemented.")

    def query_radius(self, query_points: NDArray[np.float32], radius: float) -> list[list[int]]:
        """
        Query neighbor indices within radius on GPU.

        Args:
            query_points: (M, D) query positions.
            radius: Radius threshold.

        Returns:
            List of neighbor index lists for each query point.
        """
        raise NotImplementedError("GPUAcceleratedSpatialIndex is not yet implemented.")


def create_spatial_index(points: NDArray[np.float32]) -> SpatialIndex:
    """Factory function to instantiate a spatial search index.

    Args:
        points: (N, D) array of points.

    Returns:
        An instance conforming to the SpatialIndex protocol.
    """
    # This exists only we we want to seamelessly switch to GPU processing in teh future
    # We will need to have a single point of entry to swtich between CPU and GPu based on availability
    # or any othe factor.
    return KDTreeSpatialIndex(points)
