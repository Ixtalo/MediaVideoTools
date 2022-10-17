#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

# pylint: disable=missing-function-docstring, missing-class-docstring, no-self-use, invalid-name

from io import StringIO
from pathlib import Path
import pytest
from docopt import DocoptExit
from media_stats import DirectoryMediaStats, MyMediaInfo, scan, get_media_file_info, main

# pushd tests && python ../media_stats.py -v ./testdata/ 2>/dev/null
TESTDATA_OUTPUT = """path;level;num_entries;cum_filesize_bytes;cum_duration_seconds;mean_bit_rate
"testdata/incorrect/NamesWithDelimiter(a;b)";3;1;21960;1.02;172235.0
"testdata/incorrect/mp3";3;1;48057;95.608;236803.0
"testdata/incorrect/lang/missing_EN_toomuch_DE [DE]";4;1;11228;0.125;718592.0
"testdata/incorrect/lang/mixed_missing_EN [DE]";4;2;21365;0.25;683680.0
"testdata/incorrect/lang/mixed_missing_DE_EN_toomuch_XX [XX]";4;2;21365;0.25;683680.0
"testdata/incorrect/lang/mixed_missing_DE [EN]";4;2;21365;0.25;683680.0
"testdata/incorrect/lang/mixed_missing_DE_EN_toomuch_XX_ignored [XX][__]";4;2;21365;0.25;683680.0
"testdata/incorrect/lang/missing_DE_toomuch_EN [EN]";4;1;10137;0.125;648768.0
"testdata/incorrect/lang/mixed_missing_DE_EN";4;2;21365;0.25;683680.0
"testdata/incorrect/lang";3;7;128190;1.5;683680.0
"testdata/incorrect/no_duration";3;1;46676;3.142;0
"testdata/incorrect";2;4;244883;101.27;273179.5
"testdata/correct/Der Stiefelkater (2011) [DE]";3;1;66352;0.992;535097.0
"testdata/correct/SampleVideoFlv";3;1;119684;1.001;956515.0
"testdata/correct/SampleVideoMkvDone";3;2;481382;2.004;1921684.5
"testdata/correct/Forrest Video (1994) [DE][EN]";3;1;278565;1.009;2208642.0
"testdata/correct/lang/mixed [DE][EN]";4;2;21365;0.25;683680.0
"testdata/correct/lang";3;1;21365;0.25;683680.0
"testdata/correct/SampleVideoMkv";3;1;242994;1.002;1940072.0
"testdata/correct/Unicode-äöüß";3;1;242994;1.002;1940072.0
"testdata/correct/Cool Run (1993) [EN]/subdir";4;1;21960;1.02;172235.0
"testdata/correct/Cool Run (1993) [EN]";3;1;21960;1.02;172235.0
"testdata/correct";2;9;1527375;11.519;1165110.6
"testdata";1;2;1772258;112.789;719145.1
"""

# pushd tests && python ../media_stats.py -v . 2>/dev/null | tail -1
TESTDATA_OUTPUT_MAINDIR_EXTRALINE = '".";0;1;1772258;112.789;719145.1'


class TestMyMediaStats:

    def test_constructor(self):
        MyMediaInfo(Path("."))

    def test_constructor_invalid(self):
        with pytest.raises(TypeError):
            MyMediaInfo(None)
        with pytest.raises(TypeError):
            MyMediaInfo("ASTRING")


class TestDirectoryMediaStats:

    @pytest.fixture
    def example_mediainfo(self):
        mmi = MyMediaInfo(Path("foo/bar/mmi"))
        mmi.file_size = 0.1
        mmi.duration = 0.2
        mmi.bit_rate = 0.3
        return mmi

    @pytest.fixture
    def example_dirmediastats(self, example_mediainfo):
        instance = DirectoryMediaStats(Path("foo/bar/"))
        instance += example_mediainfo
        return instance

    def test_constructor(self, example_dirmediastats):
        assert example_dirmediastats.num_entries == 1

    def test_constructor_invalid(self):
        with pytest.raises(TypeError):
            DirectoryMediaStats(None)
        with pytest.raises(TypeError):
            DirectoryMediaStats("ASTRING")

    def test_path_setter(self):
        instance = DirectoryMediaStats(Path("."))
        instance.path = Path("tests")
        with pytest.raises(TypeError):
            instance.path = "ASTRING"

    def test_str_empty(self):
        assert str(DirectoryMediaStats(Path("foobar/"))) == ""

    def test_str(self, example_dirmediastats):
        assert str(example_dirmediastats) == f"\"{Path('.', 'foo', 'bar')}\";2;1;0.1;0.2;0.3"

    def test_str_paths(self, example_mediainfo):
        paths = {
            # input : (normalized-path, level)
            "foo": ("foo", 1),
            "foo/": ("foo", 1),
            "foo/bar": ("foo/bar", 2),
            "foo/bar/": ("foo/bar", 2),
            "./foo": ("foo", 1),
            "./foo/": ("foo", 1),
            "./foo/bar": ("foo/bar", 2),
            "./foo/bar/": ("foo/bar", 2),
            "./foo/bar/bla": ("foo/bar/bla", 3),
            "./foo/bar/bla/blubb": ("foo/bar/bla/blubb", 4),
        }
        for path, normpath_level in paths.items():
            dms = DirectoryMediaStats(Path(".", path))
            dms += example_mediainfo
            normalized, levels = normpath_level
            assert str(dms) == f"\"{normalized}\";{levels};1;0.1;0.2;0.3"

    def test_str_rounding(self, example_mediainfo):
        example_mediainfo.duration = 1.0 / 3
        dms = DirectoryMediaStats(Path("foo"))
        dms += example_mediainfo
        assert str(dms) == "\"foo\";1;1;0.1;0.333;0.3"

    def test_add_instance2(self, example_dirmediastats, example_mediainfo):
        # prepare
        instance2 = DirectoryMediaStats(Path("foo2/bar2/"))
        instance2 += example_mediainfo
        # do action
        example_dirmediastats += instance2
        # check
        # first instance should have been modified!
        assert instance2.path == Path("foo2/bar2")
        assert instance2.num_entries == 1
        assert instance2.cum_filesize_bytes == 0.1
        assert instance2.cum_duration_seconds == 0.2
        assert instance2.mean_bit_rate == 0.3
        # second instance should be unmodified!
        assert example_dirmediastats.path == Path("foo/bar")
        assert example_dirmediastats.num_entries == 2
        assert example_dirmediastats.cum_filesize_bytes == 0.1 + 0.1
        assert example_dirmediastats.cum_duration_seconds == 0.2 + 0.2
        assert example_dirmediastats.mean_bit_rate == (0.3 + 0.3) / 2

    def test_add_instance2_twice(self, example_dirmediastats, example_mediainfo):
        # prepare
        instance2 = DirectoryMediaStats(Path("foo2/bar2/"))
        instance2 += example_mediainfo
        # do action
        example_dirmediastats += instance2
        example_dirmediastats += instance2
        # check
        # first instance should have been modified!
        assert instance2.path == Path("foo2/bar2")
        assert instance2.cum_filesize_bytes == 0.1
        assert instance2.cum_duration_seconds == 0.2
        assert instance2.mean_bit_rate == 0.3
        # second instance should be unmodified!
        assert example_dirmediastats.path == Path("foo/bar")
        assert example_dirmediastats.cum_filesize_bytes == 0.1 + 0.1 + 0.1
        assert example_dirmediastats.cum_duration_seconds == 0.2 + 0.2 + 0.2
        assert example_dirmediastats.mean_bit_rate == (0.3 + 0.3 + 0.3) / 3

    def test_add(self, example_dirmediastats):
        # pylint: disable=expression-not-assigned
        example_dirmediastats + DirectoryMediaStats(Path("dms/"))
        example_dirmediastats + MyMediaInfo(Path("mmi/"))

    def test_add_invalidtype(self, example_dirmediastats):
        # pylint: disable=pointless-statement
        with pytest.raises(TypeError):
            example_dirmediastats + "foo"
        with pytest.raises(TypeError):
            example_dirmediastats + 11

    def test_add_MyMediaInfo(self, example_dirmediastats):
        # preparation
        mmi = MyMediaInfo(Path("foo/bar/mmi"))
        mmi.file_size = 0.1
        mmi.duration = 0.2
        mmi.bit_rate = 0.3
        # action
        example_dirmediastats += mmi
        # check
        assert example_dirmediastats.path == Path("foo/bar")
        assert example_dirmediastats.cum_filesize_bytes == 0.1 + 0.1
        assert example_dirmediastats.cum_duration_seconds == 0.2 + 0.2
        assert example_dirmediastats.mean_bit_rate == (0.3 + 0.3) / 2

    def test_add_MyMediaInfo_None(self, example_dirmediastats):
        # preparation
        mmi = MyMediaInfo(Path("mmi/"))
        assert mmi.file_size is None
        assert mmi.duration is None
        assert mmi.bit_rate is None
        # action
        example_dirmediastats += mmi
        # check
        assert example_dirmediastats.cum_filesize_bytes == 0.1  # unmodified because of None
        assert example_dirmediastats.cum_duration_seconds == 0.2  # unmodified because of None
        assert example_dirmediastats.mean_bit_rate == 0.3  # unmodified because of None


def test_scan():
    sio = StringIO()
    scan(Path("./testdata/"), output_stream=sio)
    actual = sio.getvalue().splitlines()
    for line in TESTDATA_OUTPUT.splitlines():
        assert line in actual


def test_scan_maindir():
    sio = StringIO()
    scan(Path("."), output_stream=sio)
    actual = sio.getvalue()
    for line in TESTDATA_OUTPUT.splitlines():
        assert line in actual
    assert TESTDATA_OUTPUT_MAINDIR_EXTRALINE in actual


def test_get_media_file_info():
    mmi = get_media_file_info(Path("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv"))
    assert mmi.path == Path("./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv")
    assert mmi.file_size == 242994
    assert mmi.duration == 1.002
    assert mmi.bit_rate == 1940072


def test_get_media_file_info_nosuchfile():
    with pytest.raises(FileNotFoundError):
        # pylint: disable-next=pointless-statement
        get_media_file_info(Path("DOESNOTEXIST"))


def test_get_media_file_info_invalid():
    with pytest.raises(TypeError):
        # pylint: disable-next=pointless-statement
        get_media_file_info("ASTRING")


def test_get_media_file_info_nocontentvideo():
    mmi = get_media_file_info(Path("./testdata/incorrect/nocontent.mkv"))
    assert mmi.path == Path("./testdata/incorrect/nocontent.mkv")
    assert mmi.file_size == 40
    assert mmi.duration is None
    assert mmi.bit_rate is None


# https://docs.pytest.org/en/latest/how-to/capture-stdout-stderr.html#accessing-captured-output-from-a-test-function
def test_main(monkeypatch, capsys, caplog):
    """Test the main() method by monkeypatching sys.argv and capturing STDOUT,
    STDERR and logging output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--verbose", "./testdata/"))
    # do action
    main()
    # check
    captured = capsys.readouterr()
    for line in TESTDATA_OUTPUT.splitlines():
        assert line in captured.out
    assert captured.err == ""
    assert len(caplog.messages) == 13
    assert caplog.messages[0].startswith("Media Files Statistics ")
    assert caplog.messages[1].startswith("base path: ")
    assert caplog.messages[2] == "output: <_io.TextIOWrapper encoding='UTF-8'>"


def test_main_maindir(monkeypatch, capsys, caplog):
    """Test the main() method by monkeypatching sys.argv and capturing STDOUT,
    STDERR and logging output."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--verbose", "."))
    # do action
    main()
    # check
    captured = capsys.readouterr()
    for line in TESTDATA_OUTPUT.splitlines():
        assert line in captured.out
    assert TESTDATA_OUTPUT_MAINDIR_EXTRALINE in captured.out
    assert captured.err == ""
    assert len(caplog.messages) == 13
    assert caplog.messages[0].startswith("Media Files Statistics ")
    assert caplog.messages[1].startswith("base path: ")
    assert caplog.messages[2] == "output: <_io.TextIOWrapper encoding='UTF-8'>"


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
    monkeypatch.setattr("sys.argv", ("foo", ))
    with pytest.raises(DocoptExit):
        main()

    # invalid/unknown parameter
    monkeypatch.setattr("sys.argv", ("foo", "--NOTASPECIFIEDPARAM"))
    with pytest.raises(DocoptExit):
        main()
