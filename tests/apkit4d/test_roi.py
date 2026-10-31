from apkit4d.roi import RegionOfInterest, roi_offset, roi_slices


def test_roi_slices():
    roi = RegionOfInterest(z0=1, z1=3, y0=10, y1=20, x0=5, x1=15)

    slices = roi_slices(roi, (10, 50, 50))

    assert slices == (slice(1, 4), slice(10, 21), slice(5, 16))
    assert len(slices) == 3


def test_roi_slices_none_is_unbounded():
    roi = RegionOfInterest(z0=None, z1=None, y0=None, y1=None, x0=None, x1=None)

    slices = roi_slices(roi, (10, 20, 30))

    assert slices == (slice(0, 10), slice(0, 20), slice(0, 30))


def test_roi_slices_clamps_back_into_range():
    roi = RegionOfInterest(z0=-5, z1=999, y0=0, y1=10, x0=5, x1=21)
    shape = (10, 20, 20)

    slices = roi_slices(roi, shape)

    assert slices == (slice(0, 10), slice(0, 11), slice(5, 20))


def test_roi_offset_defaults_to_zero_when_bounds_are_none():
    roi = RegionOfInterest(z0=None, z1=None, y0=None, y1=None, x0=None, x1=None)

    assert roi_offset(roi, (10, 20, 30)) == (0, 0, 0)


def test_roi_offset_clamps_to_bounds():
    roi = RegionOfInterest(z0=-10, z1=5, y0=999, y1=1000, x0=5, x1=10)

    assert roi_offset(roi, (20, 50, 50)) == (0, 49, 5)
