#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from docopt import DocoptExit

from mediavideotools.video_language_check import __get_path_languages, \
    __get_missing_in_path, __get_toomuch_in_path, \
    get_track_languages_for_file, get_track_languages_for_files, \
    scan, main


def test_get_path_languages():
    assert __get_path_languages(Path("./parent/foobar bla/file.xx")) == set()
    assert __get_path_languages(Path("./parent/foobar [XX]/file.xx")) == {"XX"}
    assert __get_path_languages(
        Path("./parent/foobar [XX][DE]/file.xx")) == {"XX", "DE"}

    assert __get_path_languages(
        Path("./parent/foobar bla/file.xx"), use_full_path=False) == set()
    assert __get_path_languages(
        Path("./parent [XX]/foobar [DE]/file.xx"), use_full_path=False) == {"DE"}


def test_get_toomuch_in_path():
    assert __get_toomuch_in_path(set(), set()) == set()
    assert __get_toomuch_in_path({"XX"}, {"YY"}) == {"XX"}
    assert __get_toomuch_in_path({"XX", "DE"}, set()) == {"XX", "DE"}
    assert __get_toomuch_in_path({"XX", "DE"}, {"DE"}) == {"XX"}
    assert __get_toomuch_in_path({"XX", "DE"}, {"XX", "DE"}) == set()


def test_get_missing_in_path():
    assert __get_missing_in_path(set(), set()) == set()
    assert __get_missing_in_path(set(), {"XX"}) == {"XX"}
    assert __get_toomuch_in_path({"XX"}, {"XX"}) == set()


def test_get_track_languages_for_file_ok():
    filepath = Path("./testdata/correct/Cool Run (1993) ["
                    "EN]/subdir/cool.run.720p.bluray.hevc.x265.rmteam_cut.mkv")
    actual = get_track_languages_for_file(filepath)
    expected = {"EN"}
    assert actual == expected


def test_get_track_languages_for_file_nolang():
    filepath = Path(
        "./testdata/correct/SampleVideoFlv/sample_640x360_1sec.flv")
    actual = get_track_languages_for_file(filepath)
    expected = set()
    assert actual == expected


def test_get_track_languages_for_file_novideofile():
    filepath = Path("test_video_language_check.py")  # not a video file
    actual = get_track_languages_for_file(filepath)
    assert actual is None


def test_get_track_languages_for_file_invalid():
    with pytest.raises(TypeError):
        # noinspection PyTypeChecker
        get_track_languages_for_file("JustAStringNotAPath")
    with pytest.raises(IsADirectoryError):
        get_track_languages_for_file(Path("."))  # a directory, not a file
    with pytest.raises(FileNotFoundError):
        get_track_languages_for_file(Path("DOESNOTEXIST"))


def test_get_track_languages_for_files_ok1():
    paths = [
        Path("./testdata/README.md"),  # ignored
        Path(
            "./testdata/correct/lang/mixed [DE][EN]/boundin.2003.720p.bluray.sinners_s_x265.mkv"),
    ]
    actual = get_track_languages_for_files(paths)
    assert actual == {'EN'}


def test_get_track_languages_for_files_ok2():
    paths = [
        Path("./testdata/README.md"),  # ignored
        Path(
            "./testdata/correct/lang/mixed [DE][EN]/boundin.2003.720p.bluray.sinners_s_x265.mkv"),
        Path(
            "./testdata/correct/lang/mixed [DE][EN]/Pixar_Short_Films_Collection_Volume_2_dein freund die ratte_s_x265.mkv")
    ]
    actual = get_track_languages_for_files(paths)
    assert actual == {'DE', 'EN'}


def test_scan():
    with pytest.raises(AssertionError):
        # noinspection PyTypeChecker
        scan("DOESNOTEXIST")
    with pytest.raises(NotADirectoryError):
        scan(Path("DOESNOTEXIST"))

    actual = scan(Path("./testdata/"), use_full_path=True)
    expected = {'incorrect/NamesWithDelimiter(a;b)': {'missing_in_path': ['EN']},
                'incorrect/lang/missing_DE_toomuch_EN [EN]': {'missing_in_path': ['DE'],
                                                              'toomuch_in_path': ['EN']},
                'incorrect/lang/missing_EN_toomuch_DE [DE]': {'missing_in_path': ['EN'],
                                                              'toomuch_in_path': ['DE']},
                'incorrect/lang/mixed_missing_DE [EN]': {'missing_in_path': ['DE']},
                'incorrect/lang/mixed_missing_DE_EN': {'missing_in_path': ['DE', 'EN']},
                'incorrect/lang/mixed_missing_DE_EN_toomuch_XX [XX]': {'missing_in_path': ['DE',
                                                                                           'EN'],
                                                                       'toomuch_in_path': ['XX']},
                'incorrect/lang/mixed_missing_EN [DE]': {'missing_in_path': ['EN']}}
    assert actual == expected


def test_scan_nofullpath():
    actual = scan(Path("./testdata/"), use_full_path=False)
    expected = {'correct/Cool Run (1993) [EN]/subdir': {'missing_in_path': ['EN']},
                'incorrect/NamesWithDelimiter(a;b)': {'missing_in_path': ['EN']},
                'incorrect/lang/missing_DE_toomuch_EN [EN]': {'missing_in_path': ['DE'],
                                                              'toomuch_in_path': ['EN']},
                'incorrect/lang/missing_EN_toomuch_DE [DE]': {'missing_in_path': ['EN'],
                                                              'toomuch_in_path': ['DE']},
                'incorrect/lang/mixed_missing_DE [EN]': {'missing_in_path': ['DE']},
                'incorrect/lang/mixed_missing_DE_EN': {'missing_in_path': ['DE', 'EN']},
                'incorrect/lang/mixed_missing_DE_EN_toomuch_XX [XX]': {'missing_in_path': ['DE',
                                                                                           'EN'],
                                                                       'toomuch_in_path': ['XX']},
                'incorrect/lang/mixed_missing_EN [DE]': {'missing_in_path': ['EN']}}
    assert actual == expected


# # https://docs.pytest.org/en/latest/how-to/capture-stdout-stderr.html#accessing-captured-output-from-a-test-function
def test_main(monkeypatch, capsys):
    """Test the main() method by monkeypatching sys.argv and capturing STDOUT,
    STDERR and logging output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "./testdata/"))
    # do action
    main()
    # check
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_verbose(monkeypatch, capsys):
    """Test the main() method with verbose output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--verbose", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_json(monkeypatch, capsys):
    """Test the main() method with verbose output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--json", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ('{"incorrect/NamesWithDelimiter(a;b)": {"missing_in_path": ["EN"]}, '
                            '"incorrect/lang/missing_DE_toomuch_EN [EN]": {"missing_in_path": ["DE"], '
                            '"toomuch_in_path": ["EN"]}, "incorrect/lang/missing_EN_toomuch_DE [DE]": '
                            '{"missing_in_path": ["EN"], "toomuch_in_path": ["DE"]}, '
                            '"incorrect/lang/mixed_missing_DE [EN]": {"missing_in_path": ["DE"]}, '
                            '"incorrect/lang/mixed_missing_DE_EN": {"missing_in_path": ["DE", "EN"]}, '
                            '"incorrect/lang/mixed_missing_DE_EN_toomuch_XX [XX]": {"missing_in_path": '
                            '["DE", "EN"], "toomuch_in_path": ["XX"]}, "incorrect/lang/mixed_missing_EN '
                            '[DE]": {"missing_in_path": ["EN"]}}\n')


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

    # mandatory basepath argument is missing!
    monkeypatch.setattr("sys.argv", ("foo",))
    with pytest.raises(DocoptExit):
        main()

    # invalid/unknown parameter
    monkeypatch.setattr("sys.argv", ("foo", "--NOTASPECIFIEDPARAM"))
    with pytest.raises(DocoptExit):
        main()
