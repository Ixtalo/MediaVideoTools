#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

from io import StringIO
from pathlib import Path
import pytest
from docopt import DocoptExit
from video_info import scan, main

TESTDATA_RUNTIME_OUTPUT_LENGTH = 3991


def test_scan():
    """Test the main scanning method."""
    out = StringIO()
    scan(Path("./testdata"), output_stream=out)
    actual = out.getvalue()
    assert len(actual) == TESTDATA_RUNTIME_OUTPUT_LENGTH


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
    assert len(lines) == 25
    assert lines[0] == "filename;file_size;format;duration;video_codecs;audio_codecs;audio_language_list;text_language_list;format;format_profile;encoded_library_name;bit_rate;bit_rate_mode;pixel_aspect_ratio;proportion_of_this_stream"
    assert len(lines[1].split(";")) == 15
    assert lines[1].startswith('"testdata/correct/Cool Run (1993) [EN]/subdir/cool.run.720p.bluray.hevc.x265.rmteam_cut.mkv";')
    assert lines[1].endswith(";Matroska;1020;;AAC LC;English;English;HEVC;Main@L3.1@Main;x265;6455885;;1.000;")


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
    assert len(p.read()) == TESTDATA_RUNTIME_OUTPUT_LENGTH
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_output_stdout(monkeypatch, capsys):
    """Test the main() method with output STDOUT."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--out=-", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert len(captured.out) == TESTDATA_RUNTIME_OUTPUT_LENGTH
    assert captured.err == ""


def test_main_output_verbose(monkeypatch, capsys, caplog):
    """Test the main() method with verbose output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--verbose", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert len(captured.out) == TESTDATA_RUNTIME_OUTPUT_LENGTH
    assert captured.err == ""
    assert len(caplog.messages) == 77
    assert caplog.messages[0].startswith("Video Info to CSV ")
    assert caplog.messages[1].startswith("base path: ")
    assert caplog.messages[2] == "output: <_io.TextIOWrapper encoding='UTF-8'>"
