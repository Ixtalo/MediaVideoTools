#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""
from io import StringIO
from pathlib import Path

import pytest

from mediavideotools import rename_x265_remove_x264
from mediavideotools.rename_x265_remove_x264 import \
    main, run, scan, _handle_filepath, _handle_files, _get_marker, \
    FILENAME_MARKER_X265, FILENAME_EXTENSION


def test_handle_filepath():
    assert _handle_filepath(Path("foo.x264-bar.mkv")) == Path("foo.bar.mkv")
    assert _handle_filepath(Path("foo.h264-bar.mkv")) == Path("foo.bar.mkv")
    assert _handle_filepath(
        Path("foo.h264-bar1.x264-bar2.mkv")) == Path("foo.bar1.bar2.mkv")


def test_handle_filepath_nomarker():
    assert not _handle_filepath(Path(""))
    assert not _handle_filepath(Path("."))
    assert not _handle_filepath(Path("foo"))
    assert not _handle_filepath(Path("foo.bar"))
    assert not _handle_filepath(Path("foo_x264.bar"))       # no x265
    assert not _handle_filepath(Path("foo_x265.bar"))       # no .mkv
    assert not _handle_filepath(Path("foo_x264-bar.mkv"))   # not ".x264-"


def test_handle_filepath_invalid():
    with pytest.raises(AssertionError):
        # noinspection PyTypeChecker
        _handle_filepath("foo.x264-bar.mkv")


def test_get_marker():
    assert _get_marker() == f"{FILENAME_MARKER_X265}{FILENAME_EXTENSION}"


def test_scan():
    actual = scan(Path("./testdata"))
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo.h264-bar_x265.mkv') in actual
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo.x264-bar_x265.MKV') in actual
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo2.x264-bar2.h264-bar2_x265.mkv') in actual


def test_handle_files():
    files = scan(Path("./testdata"))
    actual = _handle_files(files)
    assert len(actual) == 3
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo.h264-bar_x265.mkv') in actual.keys()
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo.x264-bar_x265.MKV') in actual.keys()
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo2.x264-bar2.h264-bar2_x265.mkv') in actual.keys()
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo.bar_x265.mkv') in actual.values()
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo.bar_x265.MKV') in actual.values()
    assert Path(
        'testdata/incorrect/x265_abundant_x264/foo2.bar2.bar2_x265.mkv') in actual.values()


def test_run(monkeypatch):
    def mock_scan(_):
        return [Path("foo1.x264-bar.mkv"), Path("foo2.mkv")]

    monkeypatch.setattr(rename_x265_remove_x264, "scan", mock_scan)
    stream = StringIO()
    returncode = run(Path("NOT_REALLY_NEEDED"), output_stream=stream)
    assert returncode == 0
    actual = stream.getvalue()
    assert actual.startswith("mv --no-clobber --verbose ")
    assert actual.endswith("foo1.bar.mkv\"\n")
    assert "/foo1.x264-bar.mkv\" " in actual


def test_run_no_candidates(monkeypatch, caplog):
    def mock_scan(_):
        return []

    monkeypatch.setattr(rename_x265_remove_x264, "scan", mock_scan)
    stream = StringIO()
    returncode = run(Path("NOT_REALLY_NEEDED"), output_stream=stream)
    assert returncode == -1
    assert caplog.messages == ["No file candidates found."]


def test_run_no_relevant_files(monkeypatch, caplog):
    def mock_scan(_):
        return [Path("not_marker.mkv")]

    monkeypatch.setattr(rename_x265_remove_x264, "scan", mock_scan)
    stream = StringIO()
    returncode = run(Path("NOT_REALLY_NEEDED"), output_stream=stream)
    assert returncode == -2
    assert caplog.messages == ["No relevant files to process."]
    # NOTE: capsys did not work, stdout & stderr were empty :-(


def test_main(monkeypatch):
    def mock_scan(_):
        return [Path("foo1.x264-bar.mkv"), Path("foo2.mkv")]

    monkeypatch.setattr(rename_x265_remove_x264, "scan", mock_scan)
    monkeypatch.setattr("sys.argv", ("foo", "NOT_REALLY_NEEDED"))
    assert main() == 0
    # NOTE: capsys did not work, stdout & stderr were empty :-(
