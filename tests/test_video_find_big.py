#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

from pathlib import Path
import pytest
from docopt import DocoptExit
from video_find_big import scan_file, main


def test_scan_file_invalid():
    """Test with an invalid argument type."""
    with pytest.raises(AssertionError):
        scan_file("NOTAPATHOBJECTBUTSTR")


def test_scan_file(capsys):
    """Test the main scanning method."""
    result = scan_file(Path("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv"))
    assert result == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_scan_file_doesnotexist(capsys):
    """Test the main scanning method."""
    result = scan_file(Path("DOESNOTEXIST"))
    assert result == -1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# https://docs.pytest.org/en/latest/how-to/capture-stdout-stderr.html#accessing-captured-output-from-a-test-function
def test_main(monkeypatch, capsys, caplog):
    """Test the main() method by monkeypatching sys.argv and capturing STDOUT,
    STDERR and logging output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--verbose", "testdata/"))
    # do action
    main()
    # check
    captured = capsys.readouterr()
    expected = "filepath;filesize_mb;format;bit_rate;frame_rate;width;height;bits__pixel_frame\n"
    assert captured.out == expected
    assert captured.err == ""
    assert len(caplog.messages) == 3


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


def test_main_output_file(monkeypatch, capsys, tmpdir):
    """Test the main() method with output file."""
    p = tmpdir.join("output.txt")
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", f"--out={p}", "./testdata"))
    main()
    assert len(p.read()) == 79
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_output_stdout(monkeypatch, capsys):
    """Test the main() method with output STDOUT."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--out=-", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert len(captured.out) == 79
    assert captured.err == ""


def test_main_output_verbose(monkeypatch, capsys):
    """Test the main() method with verbose output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--verbose", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert len(captured.out) == 79
    assert captured.err == ""
