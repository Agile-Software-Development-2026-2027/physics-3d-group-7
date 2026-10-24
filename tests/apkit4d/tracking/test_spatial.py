"""
Unit tests for spatial neighborhood search indexing.

RefactorNote:
    Read the ones inside test_motion
"""

import numpy as np

from apkit4d.tracking.spatial import (
    KDTreeSpatialIndex,
    create_spatial_index,
)


class TestSpatialIndex:
    def test_spatial_index_query_basic(self) -> None:
        """
        Verify basic radius queries with KDTreeSpatialIndex.
        """
        points = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0],
                [10.0, 10.0, 10.0],
            ],
            dtype=np.float32,
        )
        index = create_spatial_index(points)

        query = np.array([[0.5, 0.0, 0.0]], dtype=np.float32)
        res = index.query_radius(query, radius=0.6)
        assert len(res) == 1
        assert set(res[0]) == {0, 1}

    def test_spatial_index_empty_points(self) -> None:
        """
        Verify spatial query behavior when reference points are empty.
        """
        points = np.empty((0, 3), dtype=np.float32)
        index = KDTreeSpatialIndex(points)

        query = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
        res = index.query_radius(query, radius=5.0)
        assert len(res) == 1
        assert res[0] == []

    def test_spatial_index_empty_query(self) -> None:
        """
        Verify spatial query behavior when query points are empty.
        """
        points = np.array([[1.0, 1.0, 1.0]], dtype=np.float32)
        index = create_spatial_index(points)

        query = np.empty((0, 3), dtype=np.float32)
        res = index.query_radius(query, radius=5.0)
        assert len(res) == 0
