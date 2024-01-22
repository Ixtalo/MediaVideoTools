#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""
# pylint: disable=missing-function-docstring, missing-class-docstring, no-self-use, invalid-name
from io import StringIO
from pathlib import Path

import pytest
from docopt import DocoptExit

from mediavideotools import rename_based_on_dirname
from mediavideotools.rename_based_on_dirname import \
    run, main, nfo_renaming, _get_dst, build_renaming_commands


def test_get_dst():
    actual = _get_dst(
        Path("testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut.avi"))
    assert actual == Path(
        'testdata/correct/Der Stiefelkater (2011) [DE]/Der Stiefelkater (2011) [DE].avi')


def test_nfo_renaming():
    a, b = nfo_renaming(
        Path("testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut_x264.avi"))
    assert a == Path(
        'testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut_x264.nfo')
    assert b == Path(
        'testdata/correct/Der Stiefelkater (2011) [DE]/Der Stiefelkater (2011) [DE].nfo')


def test_nfo_renaming_existsalready():
    a, b = nfo_renaming(
        Path("testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv"))
    # (None, None) because no .nfo file in folder
    assert a is None
    assert b is None


def test_build_renaming_commands_linux(monkeypatch):
    def mock_is_windows():
        return False

    monkeypatch.setattr(rename_based_on_dirname,
                        "_is_os_windows", mock_is_windows)
    src = Path("foo/src.bar")
    dst = Path("foo/dst.bar")
    sio = StringIO()
    build_renaming_commands(src, dst, output_stream=sio)
    assert sio.getvalue() == '## ---------------------------------\nmv --no-clobber "foo/src.bar" "foo/dst.bar"\n'


def test_build_renaming_commands_windows(monkeypatch):
    def mock_is_windows():
        return True

    monkeypatch.setattr(rename_based_on_dirname,
                        "_is_os_windows", mock_is_windows)
    src = Path("foo/src.bar")
    dst = Path("foo/dst.bar")
    sio = StringIO()
    build_renaming_commands(src, dst, output_stream=sio)
    assert sio.getvalue() == 'REM ---------------------------------\nrename "foo/src.bar" "dst.bar"\n'


def test_build_renaming_commands_invalid1():
    sio = StringIO()
    build_renaming_commands(None, None, output_stream=sio)
    assert sio.getvalue() == ""


def test_build_renaming_commands_invalid2():
    sio = StringIO()
    build_renaming_commands(None, Path(), output_stream=sio)
    assert sio.getvalue() == ""


def test_build_renaming_commands_invalid3():
    sio = StringIO()
    build_renaming_commands(Path(), None, output_stream=sio)
    assert sio.getvalue() == ""


def test_build_renaming_commands_invalid4():
    sio = StringIO()
    build_renaming_commands(Path(), Path(), output_stream=sio)
    assert sio.getvalue() == ""


def test_build_renaming_commands_dstexists():
    sio = StringIO()
    build_renaming_commands(Path(), Path(
        "testdata/incorrect/nocontent.mp3"), output_stream=sio)
    assert sio.getvalue() == ""


def test_run(capsys):
    sio = StringIO()
    exit_code = run(Path("testdata"), output_stream=sio)
    assert exit_code == 0
    assert capsys.readouterr().err == ""
    assert capsys.readouterr().out == ""
    text = sio.getvalue()
    lines = text.splitlines()
    assert len(text) == 2041  # size depends on filesystem (ramdisk etc.)
    assert len(lines) == 14
    assert lines[0] == "## ---------------------------------"
    assert lines[1].startswith("mv --no-clobber ")
    assert lines[1].endswith("/x265_abundant_x264.mkv\"")
    assert lines[2] == "## ---------------------------------"
    assert lines[7].startswith("mv --no-clobber ")
    assert lines[7].endswith(
        "/mixed_missing_DE_EN_toomuch_XX_ignored [XX][__].mkv\"")


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
    monkeypatch.setattr("sys.argv", ("foo", "--out", "testdata/"))
    with pytest.raises(DocoptExit):
        main()

    # mandatory basepath argument is missing!
    monkeypatch.setattr("sys.argv", ("foo",))
    with pytest.raises(DocoptExit):
        main()

    # invalid/unknown parameter
    monkeypatch.setattr("sys.argv", ("foo", "--NOTASPECIFIEDPARAM"))
    with pytest.raises(DocoptExit):
        main()
