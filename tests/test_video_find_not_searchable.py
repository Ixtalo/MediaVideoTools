#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

from io import StringIO
from pathlib import Path

import pytest
from docopt import DocoptExit

from mediavideotools.video_find_not_searchable import scan, main

TESTDATA_RUNTIME_OUTPUT_LENGTH = 925


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
    monkeypatch.setattr("sys.argv", ("foo", "testdata/"))
    # do action
    main()
    # check
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "filename;format;codecs_video;video_format_list;video_language_list;duration;audio_codecs;audio_format_list;audio_language_list;text_language_list;count_of_audio_streams;count_of_menu_streams;count_of_stream_of_this_kind;count_of_text_streams;count_of_video_streams" in captured.out
    assert "testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut_x264.avi;AVI;MPEG-4 Visual;MPEG-4 Visual;;992;AC-3;AC-3;;;1;;1;;1" in captured.out
    assert "testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv;Matroska;MPEG-4 Visual;MPEG-4 Visual;;1002;AAC LC;AAC LC;;;1;;1;;1" in captured.out
    assert "testdata/correct/SampleVideoMkvDone/SampleVideo_1280x720_1mb_1sec.mkv.x265done;Matroska;MPEG-4 Visual;MPEG-4 Visual;;1002;AAC LC;AAC LC;;;1;;1;;1" in captured.out
    assert "testdata/correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß.mkv;Matroska;MPEG-4 Visual;MPEG-4 Visual;;1002;AAC LC;AAC LC;;;1;;1;;1" in captured.out


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


def test_main_output_verbose(monkeypatch, capsys):
    """Test the main() method with verbose output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--verbose", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert len(captured.out) == TESTDATA_RUNTIME_OUTPUT_LENGTH
    assert captured.err == ""
