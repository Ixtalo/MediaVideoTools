#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

from io import StringIO
from pathlib import Path

import pytest

from mediavideotools.video_subs_check import scan, main


def test_scan():
    """Test the main scanning method."""
    out = StringIO()
    scan(Path("./testdata"), output_stream=out)
    actual = out.getvalue()
    assert len(actual) == 175


def test_scan_nodir():
    """Test the main scanning method, but with wrong paramters."""
    with pytest.raises(NotADirectoryError):
        scan(Path("./NO_SUCH_DIRECTORY"))
    with pytest.raises(NotADirectoryError):
        scan(Path("./__init__.py"))


def test_scan_invaliddir():
    """Test the main scanning method, but with wrong paramters."""
    with pytest.raises(NotADirectoryError):
        scan(Path("./NO_SUCH_DIRECTORY"))


# https://docs.pytest.org/en/latest/how-to/capture-stdout-stderr.html#accessing-captured-output-from-a-test-function
def test_main(monkeypatch, capsys):
    """Test the main() method by monkeypatching sys.argv and capturing STDOUT,
    STDERR and logging output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "./testdata/"))
    # do action
    main()
    # check
    captured = capsys.readouterr()
    assert captured.err == ""
    # pushd tests && python ../video_info.py ./testdata/ 2>/dev/null
    lines = captured.out.splitlines()
    assert len(lines) == 2
    assert lines[0] == "/home/stc/work/dev_workspace/MediaVideoTools/tests/testdata/incorrect/SubtitleSubsDir"
    assert lines[1] == "/home/stc/work/dev_workspace/MediaVideoTools/tests/testdata/incorrect/SubtitleSubsDir sq"


def test_main_existentoutput(monkeypatch):
    """Test the main() method by monkeypatching sys.argv and capturing STDOUT,
    STDERR and logging output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr(
        "sys.argv", ("foo", "./testdata/", "--out", "__init__.py"))
    # do action
    with pytest.raises(FileExistsError):
        main()
