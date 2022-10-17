#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""
# pylint: disable=missing-function-docstring, line-too-long

import sys
from pathlib import Path
import pytest
from docopt import DocoptExit
from pymediainfo import MediaInfo
from video_convert_x265 import ConversionCommand, \
    _get_done_filename, _get_x265_marker_filename, check_metadata_isx265, \
    find_candidates, run, \
    main


class TestConversionCommand:
    """Unit tests for class ConversionCommand."""

    @staticmethod
    def test_constructor():
        with pytest.raises(TypeError):
            # pylint: disable-next=no-value-for-parameter
            ConversionCommand()
        with pytest.raises(TypeError):
            ConversionCommand(0, 0)
        with pytest.raises(TypeError):
            ConversionCommand(None, None)
        with pytest.raises(AssertionError):
            # noinspection PyTypeChecker
            ConversionCommand("template", "fp1")
        ConversionCommand("template %s %s", Path("fp1"))

    def test_get_filepath(self):
        p = Path("foo.mkv")
        cmd = ConversionCommand("foo %s %s", p)
        assert cmd.get_filepath().absolute() == p.absolute()

    def test_get_filepath_new(self):
        cmd = ConversionCommand("foo %s %s", Path("foo.mkv"))
        assert cmd.get_filepath_new().name == "foo_x265.mkv"

    def test_get_filepath_done(self):
        cmd = ConversionCommand("foo %s %s", Path("foo.mkv"))
        assert cmd.get_filepath_done().name == "foo.mkv.x265done"

    @staticmethod
    def test_get_command():
        p = Path("foo.mkv")
        cmd = ConversionCommand("foo %s %s", p)
        assert cmd.get_command() == f"foo {p.absolute()} {cmd.get_filepath_new().absolute()}"


def test_get_done_filename():
    assert _get_done_filename(Path("foo")) == Path("foo.x265done")
    assert _get_done_filename(Path("foo.bar")) == Path("foo.bar.x265done")
    assert _get_done_filename(Path("foo.bar.x265done")) == Path("foo.bar.x265done")
    with pytest.raises(ValueError):
        _get_done_filename(Path(""))
    with pytest.raises(ValueError):
        _get_done_filename(Path("."))


def test_get_x265_marker_filename():
    assert _get_x265_marker_filename(Path("foo")) == Path("foo_x265.mkv")
    assert _get_x265_marker_filename(Path("foo.bar")) == Path("foo_x265.bar.mkv")
    assert _get_x265_marker_filename(Path("foo_x265.bar")) == Path("foo_x265.bar")
    with pytest.raises(ValueError):
        _get_x265_marker_filename(Path(""))
    with pytest.raises(ValueError):
        _get_x265_marker_filename(Path("."))


def test_check_metadata_isx265():
    # an actual x265 file
    mi = MediaInfo.parse("./testdata/correct/Cool Run (1993) [EN]/subdir/cool.run.720p.bluray.hevc.x265.rmteam_cut.mkv")
    assert check_metadata_isx265(mi)

    # x264
    mi = MediaInfo.parse("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv")
    assert not check_metadata_isx265(mi)

    # MP3 audio file, without video tracks
    mi = MediaInfo.parse("./testdata/correct/sample-3s.mp3")
    assert not check_metadata_isx265(mi)

    # invalid input (string instead of mediainfo)
    with pytest.raises(AssertionError):
        # noinspection PyTypeChecker
        check_metadata_isx265("./testdata/correct/sample-3s.mp3")


def test_find_candidates():
    assert len(find_candidates(Path("./testdata"), min_file_size_mb=0)) == 5
    assert len(find_candidates(Path("./testdata"), min_file_size_mb=1)) == 0
    assert len(find_candidates(Path("./testdata"), min_file_size_mb=0.2)) == 2
    assert len(find_candidates(Path("./testdata"), min_file_size_mb=10000)) == 0

    actual = find_candidates(Path("./testdata"), min_file_size_mb=0.2)
    expected = [Path('./testdata/correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß.mkv'),
                Path('./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv')]
    # intersection because ordering could be arbitrary (depending on filesystem type)
    assert set(actual).intersection(set(expected))


def test_run_invalid_root():
    with pytest.raises(NotADirectoryError):
        # first argument must be a valid directory
        run(Path("NOTEXISTENTNOTADIR.bar"), "")
    with pytest.raises(NotADirectoryError):
        run(Path("/foo/bar"), "")


def test_run_invalid_args():
    with pytest.raises(AssertionError):
        # just_list=True must have a valid output_stream!
        run(Path("."), "", min_file_size_mb=0, output_stream=None, just_list=True)


def test_run_justlist(capsys):
    run(Path("./testdata"), "echo foo %s %s", min_file_size_mb=0.2, output_stream=sys.stdout, just_list=True)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(captured.out) in (201, 239)  # size depends on filesystem (ramdisk etc.)
    assert len(captured.out.splitlines()) == 2
    assert "correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv" in captured.out
    assert "correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß.mkv" in captured.out


def test_run_outputstdout(capsys):
    result = run(Path("./testdata"), "echo foo %s %s", min_file_size_mb=0.2, output_stream=sys.stdout)
    assert result == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(captured.out) in (430, 506)  # # size depends on filesystem (ramdisk etc.)
    assert len(captured.out.splitlines()) == 2
    assert "correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß.mkv" in captured.out
    assert "correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß_x265.mkv" in captured.out


def test_main_invalidparams(monkeypatch):
    """Test the main() method with invalid parameters."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "INVALIDINVALIDINVALID"))
    with pytest.raises(NotADirectoryError):
        main()

    monkeypatch.setattr("sys.argv", ("foo", "Pipfile"))
    with pytest.raises(NotADirectoryError):
        main()

    monkeypatch.setattr("sys.argv", ("foo", "'''"))
    with pytest.raises(NotADirectoryError):
        main()

    # --out=... is missing!
    monkeypatch.setattr("sys.argv", ("foo", "--list", "testdata/"))
    with pytest.raises(AssertionError):
        main()

    # --out=... is missing!
    monkeypatch.setattr("sys.argv", ("foo", "--out", "testdata/"))
    with pytest.raises(DocoptExit):
        main()

    # mandatory basepath argument is missing!
    monkeypatch.setattr("sys.argv", ("foo", ))
    with pytest.raises(DocoptExit):
        main()

    # invalid/unknown parameter
    monkeypatch.setattr("sys.argv", ("foo", "--NOTASPECIFIEDPARAM"))
    with pytest.raises(DocoptExit):
        main()


def test_main_list_nofiles(monkeypatch, capsys):
    """Test the main() method."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--list", "--out=-", "./testdata"))
    main()
    captured = capsys.readouterr()
    # no output because of default min-file-size threshold
    assert captured.out == ""
    assert captured.err == ""


def test_main_list_withfiles(monkeypatch, capsys):
    """Test the main() method, adjust the min-file-size threshold."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--list", "--out=-", "--size=0.01", "./testdata"))
    main()
    captured = capsys.readouterr()
    # no output because of default min-file-size threshold
    assert len(captured.out) in (393, 469)  # size depends on filesystem (ramdisk etc.)
    # --list must not have ffmpeg commands!
    assert "ffmpeg" not in captured.out
    assert captured.err == ""


def test_main_output_stdout(monkeypatch, capsys):
    """Test the main() method with output STDOUT."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--out=-", "--size=0.01", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert len(captured.out) in (1066, 1218)    # size depends on filesystem (ramdisk etc.)
    assert "ffmpeg" in captured.out
    assert captured.err == ""


def test_main_output_file(monkeypatch, capsys, tmpdir):
    """Test the main() method with output STDOUT."""
    p = tmpdir.join("output.txt")
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", f"--out={p}", "--size=0.01", "./testdata"))
    main()
    assert len(p.read()) in (1066, 1218)    # size depends on filesystem (ramdisk etc.)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
