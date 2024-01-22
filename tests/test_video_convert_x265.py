#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""
# pylint: disable=missing-function-docstring, line-too-long

import subprocess
import sys
from io import StringIO
from pathlib import Path
from string import Template

import pytest
from docopt import DocoptExit
from pymediainfo import MediaInfo

from mediavideotools.video_convert_x265 import \
    ConversionCommand, \
    __handle_args_cmdtemplate, \
    _get_done_filename, _build_filename_with_marker, check_metadata_isx265, \
    find_candidates, \
    run, \
    run_conversion_process, \
    main, \
    CONVERT_CMD_TEMPLATE, ConversionProcessResult

EXAMPLE_TEMPLATE = Template("foo ${input} ${output} ${additional}")


class TestConversionCommand:
    """Unit tests for class ConversionCommand."""

    # noinspection PyArgumentList
    @staticmethod
    def test_constructor():
        with pytest.raises(TypeError):
            # pylint: disable-next=no-value-for-parameter
            # noinspection PyTypeChecker
            ConversionCommand()
        with pytest.raises(AssertionError):
            # noinspection PyTypeChecker
            ConversionCommand(0, 0)
        with pytest.raises(AssertionError):
            # noinspection PyTypeChecker
            ConversionCommand(None, None)
        with pytest.raises(AssertionError):
            # noinspection PyTypeChecker
            ConversionCommand("must-not-be-string", Path("."))
        with pytest.raises(AssertionError):
            ConversionCommand(Template("missing-template-strings"), Path("."))
        with pytest.raises(AssertionError):
            ConversionCommand(Template("${input} ${output}"), Path("."))
        with pytest.raises(AssertionError):
            ConversionCommand(Template("${input} ${additional}"), Path("."))
        with pytest.raises(AssertionError):
            # invalid Path-parameter type
            # noinspection PyTypeChecker
            ConversionCommand(EXAMPLE_TEMPLATE, ".")
        ConversionCommand(EXAMPLE_TEMPLATE, Path("."))

    def test_get_filepath(self):
        p = Path("foo.mkv")
        cmd = ConversionCommand(EXAMPLE_TEMPLATE, p)
        assert cmd.get_filepath().absolute() == p.absolute()

    def test_get_filepath_new(self):
        cmd = ConversionCommand(EXAMPLE_TEMPLATE, Path("foo.mkv"))
        assert cmd.get_filepath_new().name == "foo_x265.mkv"

        cmd = ConversionCommand(EXAMPLE_TEMPLATE, Path("foo_x264.mkv"))
        assert cmd.get_filepath_new().name == "foo_x265.mkv"

        cmd = ConversionCommand(EXAMPLE_TEMPLATE, Path("foo_h264.mkv"))
        assert cmd.get_filepath_new().name == "foo_x265.mkv"

        cmd = ConversionCommand(EXAMPLE_TEMPLATE, Path("foo.x264.mkv"))
        assert cmd.get_filepath_new().name == "foo_x265.mkv"

    def test_eliminate_x264(self):
        assert ConversionCommand.eliminate_x264(
            Path("foo.bar")) == Path("foo.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo x264.bar")) == Path("foo.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo_x264.bar")) == Path("foo.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo.x264.bar")) == Path("foo.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo-x264.bar")) == Path("foo.bar")

        assert ConversionCommand.eliminate_x264(
            Path("foo_x264_x264.bar")) == Path("foo.bar")

        assert ConversionCommand.eliminate_x264(
            Path("foo h264.bar")) == Path("foo.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo_h264.bar")) == Path("foo.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo.h264.bar")) == Path("foo.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo-h264.bar")) == Path("foo.bar")

        assert ConversionCommand.eliminate_x264(
            Path("foo_x265.bar")) == Path("foo_x265.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo x265.bar")) == Path("foo x265.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo_X264.bar")) == Path("foo_X264.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo_r264.bar")) == Path("foo_r264.bar")
        assert ConversionCommand.eliminate_x264(
            Path("foo#x264.bar")) == Path("foo#x264.bar")

    def test_get_filepath_done(self):
        cmd = ConversionCommand(EXAMPLE_TEMPLATE, Path("foo.mkv"))
        assert cmd.get_filepath_done().name == "foo.mkv.x265done"

    @staticmethod
    def test_get_command():
        p = Path("foo.mkv")
        cmd = ConversionCommand(EXAMPLE_TEMPLATE, p)
        assert cmd.get_command(
        ) == f"foo {p.absolute()} {cmd.get_filepath_new().absolute()}"


def __make_invariant_to_local_environment(data: str) -> str:
    """The test checks should be invariant towards different deployment environments."""
    # replace the paths to make the checks invariant to different deployment scenarios
    data = data.replace(str(Path(".").absolute()), "")
    return data


def test_get_done_filename():
    assert _get_done_filename(Path("foo")) == Path("foo.x265done")
    assert _get_done_filename(Path("foo.bar")) == Path("foo.bar.x265done")
    assert _get_done_filename(Path("foo.bar.x265done")
                              ) == Path("foo.bar.x265done")
    with pytest.raises(ValueError):
        _get_done_filename(Path(""))
    with pytest.raises(ValueError):
        _get_done_filename(Path("."))


def test_get_x265_marker_filename():
    assert _build_filename_with_marker(
        Path("foo"), "_XX", target_ext=None) == Path("foo_XX")
    assert _build_filename_with_marker(
        Path("foo"), "_XX", target_ext=".x") == Path("foo_XX.x")
    assert _build_filename_with_marker(Path("foo_XX"), "_XX") == Path("foo_XX")
    assert _build_filename_with_marker(Path("foo"), "") == Path("foo")
    assert _build_filename_with_marker(
        Path("foo.mp4"), "_XY") == Path("foo_XY.mp4")
    assert _build_filename_with_marker(
        Path("foo.mp4"), "_XY", target_ext=".x") == Path("foo_XY.x")
    assert _build_filename_with_marker(
        Path("foo.bar"), "_XY") == Path("foo_XY.bar")
    assert _build_filename_with_marker(
        Path("foo_x265.bar"), "_x265") == Path("foo_x265.bar")
    # already marked --> do not change (neither suffix)
    assert _build_filename_with_marker(
        Path("foo_x265.bar"), "_x265", target_ext=".x") == Path("foo_x265.bar")
    with pytest.raises(ValueError):
        _build_filename_with_marker(Path(""), "FOO")
    with pytest.raises(ValueError):
        _build_filename_with_marker(Path("."), "FOO")


def test_check_metadata_isx265():
    # an actual x265 file
    mi = MediaInfo.parse(
        "./testdata/correct/Cool Run (1993) [EN]/subdir/cool.run.720p.bluray.hevc.x265.rmteam_cut.mkv")
    assert check_metadata_isx265(mi)

    # x264
    mi = MediaInfo.parse(
        "./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv")
    assert not check_metadata_isx265(mi)

    # MP3 audio file, without video tracks
    mi = MediaInfo.parse("./testdata/correct/sample-3s.mp3")
    assert not check_metadata_isx265(mi)

    # invalid input (string instead of mediainfo)
    with pytest.raises(AssertionError):
        # noinspection PyTypeChecker
        check_metadata_isx265("./testdata/correct/sample-3s.mp3")


def test_find_candidates():
    assert len(find_candidates(Path("./testdata"), min_file_size_mb=0)) == 6
    assert len(find_candidates(Path("./testdata"), min_file_size_mb=1)) == 0
    assert len(find_candidates(Path("./testdata"), min_file_size_mb=0.2)) == 3
    assert len(find_candidates(
        Path("./testdata"), min_file_size_mb=10000)) == 0

    actual = find_candidates(Path("./testdata"), min_file_size_mb=0.2)
    expected = [Path('./testdata/correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß.mkv'),
                Path('./testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv')]
    # intersection because ordering could be arbitrary (depending on filesystem type)
    assert set(actual).intersection(set(expected))


def test_handle_args_cmdtemplate():
    actual = __handle_args_cmdtemplate("EXTRA_ARG1 EXTRA_ARG2")
    assert isinstance(actual, Template)
    assert actual.template == \
        'ffmpeg -n -hide_banner -i "${input}" -map 0 -c:s copy -c:v hevc_nvenc ' \
        'EXTRA_ARG1 EXTRA_ARG2 ${additional} "${output}"'


def test_run(monkeypatch, caplog):
    def mock_popen(_, **__):
        proc = subprocess.CompletedProcess("fooargs", 0)
        proc.stderr = StringIO()
        proc.stderr.write("foobar")
        proc.wait = lambda: print("wait()")
        return proc

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    result = run(Path("./testdata"),
                 convert_cmd_template=Template(CONVERT_CMD_TEMPLATE),
                 min_file_size_mb=0,
                 create_report=False,
                 signalling=False)
    assert result == 0
    assert len(caplog.messages) == 8
    assert caplog.messages[0] == "Problem getting file size for: testdata/incorrect/broken_links/cycle"
    assert caplog.messages[1] == "Problem getting file size for: testdata/incorrect/broken_links/doesnotexist"
    assert caplog.messages[2] \
        == "[Errno 2] No such file or directory: 'testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut_x265.mkv'"
    assert caplog.messages[3] \
        == "[Errno 2] No such file or directory: 'testdata/correct/SampleVideoFlv/sample_640x360_1sec_x265.mkv'"
    assert caplog.messages[4] \
        == "[Errno 2] No such file or directory: 'testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec_x265.mkv'"
    assert caplog.messages[5] \
        == "[Errno 2] No such file or directory: 'testdata/correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß_x265.mkv'"
    assert caplog.messages[6] \
        == "[Errno 2] No such file or directory: 'testdata/correct/symlinks/SampleVideo_1280x720_1sec_x265.mkv'"
    assert caplog.messages[7] \
        == "[Errno 2] No such file or directory: 'testdata/incorrect/nocontent_x265.mkv'"


def test_run_conversion_process_nonzeroreturncode(monkeypatch, caplog):
    def mock_popen(_, **__):
        proc = subprocess.CompletedProcess("fooargs", 111)
        proc.stderr = StringIO()
        proc.stderr.write("foobar")
        proc.wait = lambda: print("wait()")
        return proc

    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    cmd = ConversionCommand(Template(CONVERT_CMD_TEMPLATE), Path("foo.bar"))
    result = run_conversion_process(cmd, create_report=False)
    assert result == ConversionProcessResult.NON_ZERO
    assert caplog.messages == ["PROBLEM running converter! return code: 111"]


def test_run_invalid_root():
    with pytest.raises(NotADirectoryError):
        # first argument must be a valid directory
        run(Path("NOTEXISTENTNOTADIR.bar"), Template(""))
    with pytest.raises(NotADirectoryError):
        run(Path("/foo/bar"), Template(""))


def test_run_invalid_args():
    with pytest.raises(AssertionError):
        # just_list=True must have a valid output_stream!
        run(Path("."), Template(""), min_file_size_mb=0,
            output_stream=None, just_list=True)


def test_run_justlist(capsys):
    run(Path("./testdata"), EXAMPLE_TEMPLATE, min_file_size_mb=0.2,
        output_stream=sys.stdout, just_list=True)
    captured = capsys.readouterr()
    assert captured.err == ""
    stdout = __make_invariant_to_local_environment(captured.out)
    assert len(stdout) == 186
    lines = stdout.splitlines()
    assert lines[0] == "/testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv"
    assert lines[1] == "/testdata/correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß.mkv"
    assert lines[2] == "/testdata/correct/symlinks/SampleVideo_1280x720_1sec.mkv"


def test_run_outputstdout(capsys):
    result = run(Path("./testdata"), EXAMPLE_TEMPLATE,
                 min_file_size_mb=0.2, output_stream=sys.stdout)
    assert result == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    stdout = __make_invariant_to_local_environment(captured.out)
    assert len(stdout) == 399
    lines = stdout.splitlines()
    assert lines[0] == "foo /testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec.mkv " \
                       "/testdata/correct/SampleVideoMkv/SampleVideo_1280x720_1sec_x265.mkv"
    assert lines[1] == "foo /testdata/correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß.mkv " \
                       "/testdata/correct/Unicode-äöüß/SampleVideo_1280x720_1sec_äöüß_x265.mkv"
    assert lines[2] == "foo /testdata/correct/symlinks/SampleVideo_1280x720_1sec.mkv " \
                       "/testdata/correct/symlinks/SampleVideo_1280x720_1sec_x265.mkv"


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
    monkeypatch.setattr("sys.argv", ("foo",))
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
    monkeypatch.setattr("sys.argv", ("foo", "--list",
                        "--out=-", "--size=0.01", "./testdata"))
    main()
    captured = capsys.readouterr()
    stdout = __make_invariant_to_local_environment(captured.out)
    # no output because of default min-file-size threshold
    assert len(stdout) == 311
    # --list must not have ffmpeg commands!
    assert "ffmpeg" not in stdout
    assert captured.err == ""


def test_main_output_stdout(monkeypatch, capsys):
    """Test the main() method with write commands to STDOUT."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--out=-",
                        "--size=0.01", "./testdata"))
    main()
    captured = capsys.readouterr()
    stdout = __make_invariant_to_local_environment(captured.out)
    assert len(stdout) == 962
    assert "ffmpeg" in stdout
    assert captured.err == ""


def test_main_output_file(monkeypatch, capsys, tmpdir):
    """Test the main() method with write commands to output file."""
    p = tmpdir.join("output.txt")
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr(
        "sys.argv", ("foo", f"--out={p}", "--size=0.01", "./testdata"))
    main()
    # checks
    content = __make_invariant_to_local_environment(p.read())
    assert len(content) == 962
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_arg_hdr_remove(monkeypatch, capsys):
    """Test the main() method with flag HDR remove."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr("sys.argv", ("foo", "--hdr-remove",
                        "--out=-", "--size=0.01", "./testdata"))
    main()
    captured = capsys.readouterr()
    assert captured.err == ""
    stdout = __make_invariant_to_local_environment(captured.out)
    lines = stdout.splitlines()
    assert len(lines) == 5
    assert lines[0] == \
        'ffmpeg -n -hide_banner -i "/testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut_x264.avi" ' \
        '-map 0 -c:s copy -c:v hevc_nvenc ' \
        '-vf "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p" -pix_fmt yuv420p  ' \
        '"/testdata/correct/Der Stiefelkater (2011) [DE]/poe-dgk_cut_x265.mkv"'


def test_main_outputexists(monkeypatch):
    """Test the main() method with invalid parameters."""
    # overwrite/monkeypatch sys.argv
    monkeypatch.setattr(
        "sys.argv", ("foo", "INVALIDINVALIDINVALID", "--out", "__init__.py"))
    with pytest.raises(FileExistsError):
        main()
