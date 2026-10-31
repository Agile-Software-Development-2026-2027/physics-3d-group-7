from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from apkit4d.io.czi import CziSource, _parse_iso, suggest_z_range


@pytest.fixture
def mock_czi(monkeypatch, tmp_path):
    """Create a fake CZI file and replace the real CZI reader."""
    path = tmp_path / "sample.czi"
    path.touch()

    scene = MagicMock()
    scene.sizes = {
        "T": 3,
        "Z": 5,
        "Y": 20,
        "X": 30,
        "C": 2,
    }

    # Scales are defined in meters
    scene.coord_scales = {
        "X": 0.5e-6,
        "Y": 0.5e-6,
        "Z": 2e-6,
    }

    scene.dtype = np.dtype("uint16")

    reader = MagicMock()
    reader.scenes = [scene]

    # Simulate image data with zeros, since pixel values are not relevant to these tests
    reader.asarray.return_value = np.zeros((5, 20, 30), dtype=np.uint16)

    # Simulate a CZI file without time interval metadata
    reader.metadata.return_value = "<Metadata />"
    reader.attachments.return_value = []
    reader.subblocks.return_value = []

    # Replace the real CZI reader with a mock to avoid opening actual files during tests
    monkeypatch.setattr(
        "apkit4d.io.czi.czifile.CziFile",
        lambda path: reader,
    )

    return path, reader


@pytest.mark.parametrize("path_type", [str, Path])
def test_path_types(mock_czi, path_type):
    path, _ = mock_czi

    source = CziSource(path_type(path))

    assert source.path == path
    source.close()


def test_file_not_found(tmp_path):
    path = tmp_path / "missing.czi"

    with pytest.raises(FileNotFoundError):
        CziSource(path)


def test_metadata(mock_czi):
    path, _ = mock_czi
    source = CziSource(path)

    assert source.info.path == str(path)
    assert source.info.n_t == 3
    assert source.info.n_z == 5
    assert source.info.n_y == 20
    assert source.info.n_x == 30
    assert source.info.n_c == 2
    assert source.info.dtype == "uint16"
    assert source.info.dt_s is None
    assert source.info.dt_source == "not found"

    assert source.info.px_size_x == pytest.approx(0.5)
    assert source.info.px_size_y == pytest.approx(0.5)
    assert source.info.px_size_z == pytest.approx(2.0)

    # Verify the voxel size is returned in (Z, Y, X) order
    assert source.info.voxel == pytest.approx((2.0, 0.5, 0.5))

    source.close()


@pytest.mark.parametrize("channel", [0, 1])
def test_valid_channel(mock_czi, channel):
    path, reader = mock_czi
    source = CziSource(path, channel=channel)

    source.read()

    reader.asarray.assert_called_once_with(T=0, C=channel)
    source.close()


@pytest.mark.parametrize("channel", [-1, 2, 10])
def test_invalid_channel(mock_czi, channel):
    path, reader = mock_czi

    with pytest.raises(ValueError):
        CziSource(path, channel=channel)

    reader.close.assert_called_once()


@pytest.mark.parametrize("axis", ["Z", "Y", "X"])
def test_missing_required_axis(mock_czi, axis):
    path, reader = mock_czi
    del reader.scenes[0].sizes[axis]

    with pytest.raises(ValueError):
        CziSource(path)

    reader.close.assert_called_once()


def test_unsupported_lightfield_data(mock_czi):
    path, reader = mock_czi
    del reader.scenes[0].sizes["Z"]
    reader.scenes[0].sizes["H"] = 5

    with pytest.raises(ValueError, match="Unsupported CZI data"):
        CziSource(path)

    reader.close.assert_called_once()


@pytest.mark.parametrize("t", [0, 2])
def test_valid_time_point(mock_czi, t):
    path, reader = mock_czi
    source = CziSource(path)

    source.read(t=t)

    reader.asarray.assert_called_once_with(T=t, C=0)
    source.close()


@pytest.mark.parametrize("t", [-1, 3, 10])
def test_invalid_time_point(mock_czi, t):
    path, reader = mock_czi
    source = CziSource(path)

    with pytest.raises(IndexError):
        source.read(t)

    reader.asarray.assert_not_called()
    source.close()


@pytest.mark.parametrize(
    ("sizes", "expected_kwargs"),
    [
        ({"T": 3, "Z": 5, "Y": 20, "X": 30}, {"T": 1}),
        ({"C": 2, "Z": 5, "Y": 20, "X": 30}, {"C": 1}),
        ({"Z": 5, "Y": 20, "X": 30}, {}),
    ],
)
def test_read_optional_axes(mock_czi, sizes, expected_kwargs):
    """Verify that read() passes only available axes to the CZI reader."""
    path, reader = mock_czi
    reader.scenes[0].sizes = sizes

    channel = 1 if "C" in sizes else 0
    source = CziSource(path, channel=channel)

    source.read(t=1 if "T" in sizes else 0)

    reader.asarray.assert_called_once_with(**expected_kwargs)
    source.close()


@pytest.mark.parametrize("z_scale", [None, np.nan, np.inf])
def test_invalid_z_calibration(mock_czi, z_scale):
    path, reader = mock_czi

    if z_scale is None:
        del reader.scenes[0].coord_scales["Z"]
    else:
        reader.scenes[0].coord_scales["Z"] = z_scale

    with pytest.raises(ValueError, match="Z spatial calibration"):
        CziSource(path)

    reader.close.assert_called_once()


def test_missing_xy_calibration(mock_czi):
    path, reader = mock_czi
    reader.scenes[0].coord_scales = {"Z": 2e-6}

    source = CziSource(path)

    assert np.isnan(source.info.px_size_x)
    assert np.isnan(source.info.px_size_y)
    assert source.info.px_size_z == pytest.approx(2.0)

    source.close()


def test_time_increment_from_metadata(mock_czi):
    path, reader = mock_czi

    reader.metadata.return_value = """
    <Metadata>
        <Information>
            <Image>
                <Dimensions>
                    <T>
                        <Positions>
                            <Interval>
                                <Increment>2.5</Increment>
                            </Interval>
                        </Positions>
                    </T>
                </Dimensions>
            </Image>
        </Information>
    </Metadata>
    """

    source = CziSource(path)

    assert source.info.dt_s == pytest.approx(2.5)
    assert source.info.dt_source == "metadata (T Increment)"

    source.close()


def test_single_time_point(mock_czi):
    path, reader = mock_czi
    reader.scenes[0].sizes["T"] = 1

    source = CziSource(path)

    assert source.info.n_t == 1
    assert source.info.dt_s is None
    assert source.info.dt_source == "single frame"

    source.close()


def test_as_dask(mock_czi):
    path, reader = mock_czi
    source = CziSource(path)

    array = source.as_dask()

    assert array.shape == (3, 5, 20, 30)
    assert array.dtype == np.dtype("uint16")

    # Verify that image data is not loaded until compute() is called
    reader.asarray.assert_not_called()

    result = array.compute()

    assert isinstance(result, np.ndarray)
    assert result.shape == (3, 5, 20, 30)
    assert reader.asarray.call_count == 3

    source.close()


def test_read_after_close(mock_czi):
    path, reader = mock_czi
    source = CziSource(path)

    source.close()

    with pytest.raises(ValueError, match="closed CZI file"):
        source.read()

    reader.asarray.assert_not_called()


def test_close(mock_czi):
    path, reader = mock_czi
    source = CziSource(path)

    source.close()
    source.close()

    reader.close.assert_called_once()


def test_parse_iso():
    result = _parse_iso("2026-10-22T12:30:45.1234567Z")

    assert result == datetime(2026, 10, 22, 12, 30, 45, 123456)


def test_time_increment_from_timestamps(mock_czi):
    path, reader = mock_czi

    # Simulate a CZI attachment containing timestamps
    attachment = MagicMock()
    attachment.attachment_entry.name = "TimeStamps"
    attachment.data.return_value = [0.0, 2.0, 4.0]

    reader.attachments.return_value = [attachment]

    source = CziSource(path)

    assert source.info.dt_s == pytest.approx(2.0)
    assert source.info.dt_source == "TimeStamps attachment"

    source.close()


def test_time_increment_from_acquisition(mock_czi):
    path, reader = mock_czi

    subblock1 = MagicMock()
    subblock1.directory_entry.dims = ["T", "Z", "C"]
    subblock1.directory_entry.start = [0, 0, 0]
    subblock1.metadata.return_value = "<AcquisitionTime>2026-10-22T12:00:00</AcquisitionTime>"

    subblock2 = MagicMock()
    subblock2.directory_entry.dims = ["T", "Z", "C"]
    subblock2.directory_entry.start = [2, 0, 0]
    subblock2.metadata.return_value = "<AcquisitionTime>2026-10-22T12:00:06</AcquisitionTime>"

    reader.subblocks.return_value = [subblock1, subblock2]

    source = CziSource(path)

    assert source.info.dt_s == pytest.approx(3.0)
    assert source.info.dt_source == "AcquisitionTime of volumes"

    source.close()


@pytest.mark.parametrize("increment", ["0", "-2", "invalid"])
def test_invalid_time_increment(mock_czi, increment):
    path, reader = mock_czi

    reader.metadata.return_value = (
        "<Metadata><Information><Image><Dimensions><T>"
        "<Positions><Interval>"
        f"<Increment>{increment}</Increment>"
        "</Interval></Positions>"
        "</T></Dimensions></Image></Information></Metadata>"
    )

    source = CziSource(path)

    assert source.info.dt_s is None
    assert source.info.dt_source == "not found"

    source.close()


def test_suggest_z_range():
    volume = np.ones((5, 4, 4))
    volume[2] = 100

    z_min, z_max, profile = suggest_z_range(volume)

    assert 0 <= z_min <= z_max < 5
    assert profile.shape == (5,)
    assert profile[2] == pytest.approx(100)


@pytest.mark.parametrize("shape", [(4, 4), (2, 3, 4, 5)])
def test_suggest_z_range_invalid_dimensions(shape):
    volume = np.zeros(shape)

    with pytest.raises(ValueError, match="Expected a 3D volume"):
        suggest_z_range(volume)


def test_suggest_z_range_empty_volume():
    volume = np.zeros((0, 4, 4))

    with pytest.raises(ValueError, match="Volume must not be empty"):
        suggest_z_range(volume)
