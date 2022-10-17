#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

# pylint: disable=missing-function-docstring

from pathlib import Path
import pytest
from mime_checker import is_mediafile, is_video, is_audio


def test_is_mediafile():
    assert is_mediafile(Path("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv"))
    assert is_mediafile(Path("./testdata/correct/SampleVideoFlv/sample_640x360_1sec.flv"))
    assert is_mediafile(Path("./testdata/correct/sample-3s.mp3"))
    assert is_mediafile(Path("./testdata/incorrect/nocontent.mp3"))
    assert not is_mediafile(Path("./testdata/incorrect/justfilename.mkv"))
    assert not is_mediafile(Path("./testdata/incorrect/justfilename.mp3"))
    assert not is_mediafile(Path("./testdata/incorrect/encounters-infinitywar_1080p_ger_forced.sub"))
    assert not is_mediafile(Path("./testdata/correct/symlinks/SampleVideo_1280x720_1sec.mkv"))

    with pytest.raises(FileNotFoundError):
        is_mediafile(Path("./testdata/incorrect/broken_links/doesnotexist"))
    with pytest.raises(OSError):
        is_mediafile(Path("./testdata/incorrect/broken_links/foo"))
    with pytest.raises(IsADirectoryError):
        is_mediafile(Path("."))
    with pytest.raises(IsADirectoryError):
        is_mediafile(Path(""))
    with pytest.raises(FileNotFoundError):
        is_mediafile(Path("None"))
    with pytest.raises(FileNotFoundError):
        is_mediafile(Path("DOESNOTEXIST"))
    with pytest.raises(TypeError):
        is_mediafile(None)
    with pytest.raises(TypeError):
        is_mediafile("STRINSTEADOFPATH")


def test_is_video():
    """Tests for video-file checks."""
    # pylint: disable=line-too-long
    assert is_video(Path("./testdata/correct/Cool Run (1993) [EN]/subdir/cool.run.720p.bluray.hevc.x265.rmteam_cut.mkv"))
    assert is_video(Path("./testdata/correct/Forrest Video (1994) [DE][EN]/Forrest.1994.German.AC3.DL.1080p.BluRay.x265-FURTUM_cut.mkv"))
    assert is_video(Path("./testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut.avi"))
    assert is_video(Path("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv"))
    assert is_video(Path("./testdata/correct/SampleVideoFlv/sample_640x360_1sec.flv"))
    assert is_video(Path("./testdata/incorrect/nocontent.mkv"))
    assert not is_video(Path("./testdata/incorrect/justfilename.mkv"))
    assert not is_video(Path("test_mime_checker.py"))

    with pytest.raises(TypeError):
        assert not is_video("STRINSTEADOFPATH")
    with pytest.raises(FileNotFoundError):
        assert not is_video(Path("DOESNOTEXIST"))


def test_is_audio():
    """Tests for audio-file checks."""
    assert is_audio(Path("./testdata/correct/sample-3s.mp3"))
    assert is_audio(Path("./testdata/incorrect/nocontent.mp3"))
    assert not is_audio(Path("./testdata/incorrect/justfilename.mp3"))
    assert not is_audio(Path("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv"))
    assert not is_audio(Path("./testdata/correct/SampleVideoFlv/sample_640x360_1sec.flv"))
