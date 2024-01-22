#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

# pylint: disable=missing-function-docstring, line-too-long, invalid-name

from pathlib import Path

import pytest

from mediavideotools.utils.file_utils import get_file_size_mb


def test_get_file_size_mb():
    with pytest.raises(AttributeError):
        # noinspection PyTypeChecker
        assert get_file_size_mb(None)
    # no existing => -1 (OSError)
    assert get_file_size_mb(Path("DOESNOTEXIST")) == -1
    # a folder should have size 0.0 MB
    assert get_file_size_mb(Path("")) == 0.0
    assert get_file_size_mb(Path("../mediavideotools")) == 0
    # existing files
    assert get_file_size_mb(Path("./testdata/correct/sample-3s.mp3")) == 0.05
    assert get_file_size_mb(Path("./testdata/correct/sample-3s.mp3"), 1) == 0
    assert get_file_size_mb(
        Path("./testdata/correct/sample-3s.mp3"), 2) == 0.05
    assert get_file_size_mb(
        Path("./testdata/correct/sample-3s.mp3"), 3) == 0.05
    assert get_file_size_mb(
        Path("./testdata/correct/sample-3s.mp3"), 4) == 0.0497
    assert get_file_size_mb(
        Path("./testdata/correct/sample-3s.mp3"), 5) == 0.04967
    assert get_file_size_mb(
        Path("/testdata/incorrect/BrokenLinks/doesnotexist")) == -1
    assert get_file_size_mb(
        Path("/testdata/incorrect/BrokenLinks/cycle")) == -1
    assert get_file_size_mb(
        Path("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv")) == 0.23
    assert get_file_size_mb(
        Path("./testdata/correct/symlinks/SampleVideo_1280x720_1sec.mkv")) == 0.23
    assert get_file_size_mb(Path("./testdata/correct/symlinks/null")) == 0
