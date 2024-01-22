#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video_convert_x265.py - Video to x265/HEVC conversion.

Converts video files using ffmpeg to x265/HEVC.
Recursively scan for all video files for automatic processing.
Processed files are renamed to indicate their processed-status.
Annotate resulting MKV files with metadata (using mkvpropedit).

Usage:
  video_convert_x265.py [options] <directory>
  video_convert_x265.py -h | --help
  video_convert_x265.py --version

Arguments:
  directory        Starting root directory for recursive scan.

Options:
  --abort-on-err  Do not continue (default) but abort after an error.
  -e --extra=X    Extra arguments for ffmpeg.
  -h --help       Show this screen.
  --hdr-remove    Remove HDR color mapping.
  -k --keep       Keep encoding artifacts, even if no real size gain.
  -l --list       Just list, do not start conversion process.
  --no-color      No colored log output.
  -o --out=FILE   Write commands to output file or "-" for STDOUT
                  instead of calling ffmpeg directly.
  --out-overwrite Force overwrite of commands output file.
  -q --quiet      Be more quiet.
  --reencode      Force encoding, even if already x265.
  -s --size=MB    Minimum necessary file size in MB [default: 100].
  --skip-mime     Skip MIME type checking when looking for candidates.
  -v --verbose    Be more verbose.
  --version       Show version.
"""
#
# LICENSE:
#
# Copyright (C) 2021-2023 by Ixtalo, ixtalo@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import datetime
import logging
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
# pylint: disable-next=redefined-builtin
from codecs import open
from enum import IntEnum
from io import BytesIO
from pathlib import Path
from string import Template
from time import sleep

import colorlog
import pymediainfo
from docopt import docopt
from pymediainfo import MediaInfo

# HACK to run file both as module and Python program
try:
    # for running as Python program
    from mkv_metadata import mkv_add_metadata_xml, mkv_produce_metadata
    from mime_checker import is_video
    from utils.singleton import SingleInstance
    from utils.file_utils import get_file_size_mb
except ModuleNotFoundError:
    # for pytest a relative import is needed
    from .mkv_metadata import mkv_add_metadata_xml, mkv_produce_metadata
    from .mime_checker import is_video
    from .utils.singleton import SingleInstance
    from .utils.file_utils import get_file_size_mb

__appname__ = "video_convert_x265"
__version__ = "1.22.0"
__date__ = "2021-09-15"
__updated__ = "2024-01-20"
__author__ = "Ixtalo"
__email__ = "ixtalo@gmail.com"
__license__ = "AGPL-3.0+"
__status__ = "Production"

# the video conversion command
# uses string.Template, cf. file:///usr/share/doc/python3.10/html/library/string.html#template-strings
# e.g. 'ffmpeg -n -i "%s" -map 0 -c:v libx265 "%s"'
# hevc_nvenc = NVIDIA NVENC hevc encoder (codec hevc). Best options are the default settings!
CONVERT_CMD_TEMPLATE = 'ffmpeg -n -hide_banner -i "${input}" -map 0 -c:s copy -c:v hevc_nvenc ${additional} "${output}"'
# additional command string to remove HDR
# https://ericswpark.com/blog/2022/2022-12-14-ffmpeg-convert-hdr-to-sdr/
CONVERT_CMD_HDR_REMOVE = '-vf "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p" -pix_fmt yuv420p'
# duration (in seconds) after which to cooldown/pause
COOLDOWN_AFTER_SECONDS = 120
# seconds for cooldown between conversion processes
COOLDOWN_SECONDS = 60
# the file-type extension, e.g. '.mkv'
FILENAME_EXTENSION = ".mkv"
# marker for converted files
FILENAME_MARKER_X265 = "_x265"
# marker for already tried files where conversion is futile
FILENAME_MARKER_NOGAIN = "_x265nogain"
# postfix for original files
FILENAME_POSTFIX_DONE = ".x265done"
# skipped filename extensions (tuple/list)
FILENAME_EXTENSIONS_BLACKLIST = (
    ".rar", ".par2", ".zip", ".jpg", ".jpeg", ".nfo", ".srt", ".idx", ".sub", ".style")
# MKV metadata base tag name
MKV_METADATA_BASETAGNAME = "video_convert_x265"
# MKV metadata key name of the no-gain flag
MKV_METADATA_X265NOGAIN = "x265_no_gain"
# TCP port for socket listener, for stopping the main-loop
TCP_PORT = 12345

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

if sys.version_info < (3, 9):
    sys.stderr.write("Minimum required version is Python 3.9!\n")
    sys.exit(1)

# flag: keep running until this is set to False
main_loop_running = True


class ConversionCommand:
    """Container for conversion command, used for subprocess calls."""

    def __init__(self, convert_cmd_template: Template, filepath: Path):
        """Conversion Command.

        :param convert_cmd_template: string with (ffmpeg) conversion template
        :param filepath: a pathlib.Path object
        """
        assert convert_cmd_template
        assert isinstance(convert_cmd_template, Template)
        assert "input" in convert_cmd_template.template
        assert "output" in convert_cmd_template.template
        assert "additional" in convert_cmd_template.template
        self.__convert_cmd_template = convert_cmd_template
        assert isinstance(filepath, Path)
        self.__filepath = filepath

    def get_filepath(self) -> Path:
        """Return the filepath, i.e., the original path and filename."""
        return self.__filepath

    def get_filepath_new(self) -> Path:
        """Return the filepath for marked files, i.e., with x265-marker."""
        filepath = _build_filename_with_marker(self.__filepath,
                                               marker=FILENAME_MARKER_X265,
                                               target_ext=FILENAME_EXTENSION)
        filepath = self.eliminate_x264(filepath)
        return filepath

    def get_filepath_done(self) -> Path:
        """Return filepath for done-files."""
        return _get_done_filename(self.__filepath)

    def get_command(self) -> str:
        """Get the final run-command string.

        e.g. ffmpeg -n -i "%s" -map 0 -c copy -c:v libx265 "%s_x265.mkv"
        :return: command string
        """
        return self.__convert_cmd_template.substitute(
            input=self.get_filepath().absolute(),
            output=self.get_filepath_new().absolute(),
            additional=""
        ).strip()

    @staticmethod
    def eliminate_x264(filepath: Path) -> Path:
        """Eliminate the x264/h264/etc. in the filename."""
        return filepath.with_stem(re.sub(r"[ ._-][xhH]264", "", filepath.stem))


def __handle_args_cmdtemplate(arg_ffmpeg_extra_args: str) -> Template:
    s = Template(CONVERT_CMD_TEMPLATE)
    if arg_ffmpeg_extra_args:
        # append again, for later possibility to re-use as Template
        arg_ffmpeg_extra_args = f"{arg_ffmpeg_extra_args} ${{additional}}"
        # replace additional-placeholder
        s_new = s.safe_substitute(additional=arg_ffmpeg_extra_args)
        return Template(s_new)
    return s


def __handle_args_outputstream(arg_force, arg_output):
    output_stream = None
    if arg_output:
        if arg_output == "-":
            output_stream = sys.stdout
        else:
            output_filepath = os.path.abspath(arg_output)
            logging.debug("output_filepath: %s", output_filepath)
            if not arg_force and os.path.exists(arg_output):
                raise FileExistsError(
                    f"Output file exists already: {output_filepath}")
            # pylint: disable-next=consider-using-with
            output_stream = open(output_filepath, "w")
    return output_stream


def __check_is_donefile(filepath: Path):
    return FILENAME_POSTFIX_DONE in filepath.suffixes


def __check_has_mark(filepath: Path, marker: str):
    return marker in filepath.name


def _get_done_filename(filepath: Path):
    if __check_is_donefile(filepath):
        return filepath
    return filepath.with_suffix(f"{filepath.suffix}{FILENAME_POSTFIX_DONE}")


def __check_is_blacklisted(filepath: Path):
    return filepath.suffix in FILENAME_EXTENSIONS_BLACKLIST


def _build_filename_with_marker(filepath: Path, marker: str, target_ext: str = None):
    if __check_has_mark(filepath, marker):
        # do nothing if already marked
        return filepath
    # add the marker (e.g., "..._x265done")
    filepath_new = filepath.with_stem(f"{filepath.stem}{marker}")
    if target_ext and not filepath_new.suffix.endswith(target_ext):
        filepath_new = filepath_new.with_suffix(target_ext)
    return filepath_new


def _socket_listener():
    global main_loop_running
    # keep on creating a socket server until the main-loop-running flag is false
    while main_loop_running:
        try:
            with socket.create_server(("localhost", TCP_PORT)) as sock:
                # we need a timeout for non-blocking listening
                sock.settimeout(2)
                while True:
                    # accept() blocks until the timeout is reached
                    con, addr = sock.accept()
                    logging.info("socket connection: %s", str((con, addr)))
                    # set the flag to stop the main loop
                    logging.info("Flagging main loop to stop ...")
                    main_loop_running = False
        except socket.timeout:
            pass  # do nothing
        except socket.error as ex:
            logging.exception(ex)


def check_metadata_hasdonotmarker(media_info: pymediainfo.MediaInfo) -> bool:
    """Check if the metadata contains our special do-not-marker.

    :param media_info: metadata object from pymediainfo (libmediainfo)
    """
    key_name = f"{MKV_METADATA_BASETAGNAME}_{MKV_METADATA_X265NOGAIN}"
    # typically there's just 1 general track...
    for track in media_info.general_tracks:
        logging.debug("track %s, %s, %s", track,
                      track.internet_media_type, track.format)
        if key_name in track.to_data().keys():
            return True
    return False


def check_metadata_isx265(media_info: pymediainfo.MediaInfo) -> bool:
    """Check if video files is x265/HVEC encoded.

    :return: True if already x265, False otherwise
    """
    assert isinstance(media_info, pymediainfo.MediaInfo)
    if not media_info.video_tracks:
        return False
    for track in media_info.video_tracks:  # typically there's just 1 video track...
        logging.debug("track %s, %s, %s", track,
                      track.internet_media_type, track.format)
        if track.internet_media_type != "video/h265" and track.format != "HEVC":
            # return False if any video track is actually not x265/hvec
            return False
    return True


def find_candidates(rootdir: Path,
                    min_file_size_mb: float,
                    forceencode: bool = False,
                    skip_mime: bool = False,
                    ) -> list[Path]:
    """Find video files candidates.

    :param rootdir: root directory where to start the recursive scan
    :param min_file_size_mb: minimum file size in MB for actually considering candidates
    :param forceencode: force encoding even if a file has a done-marker
    :param skip_mime: skip MIME type checking when looking for candidates
    :return: list of Path objects
    """
    result = []
    for root, dirs, files in os.walk(rootdir):
        dirs.sort()
        files.sort()

        for filename in files:
            filepath = Path(root, filename)
            logging.debug("filepath: %s", filepath)

            if __check_is_blacklisted(filepath):
                # i.e., not a video file (considering the file's extension)
                logging.debug(
                    "Skipping extension-blacklisted (FILENAME_EXTENSIONS_BLACKLIST): %s", filename)
                continue

            if __check_has_mark(filepath, marker=FILENAME_MARKER_X265):
                # e.g., "_x265" in filename
                logging.debug("Marker '%s' (FILENAME_MARKER_X265) is in filename: %s",
                              FILENAME_MARKER_X265, filename)
                continue

            if __check_is_donefile(filepath):
                # e.g., ".x265done" in filename suffix
                logging.debug(
                    "Already done (FILENAME_POSTFIX_DONE): %s", filename)
                continue

            # check if video file size is actually relevant for re-encoding
            file_mb = get_file_size_mb(filepath)
            logging.debug("file_mb: %.02f", file_mb)
            if file_mb < 0:
                logging.error("Problem getting file size for: %s", filepath)
                continue
            if file_mb < min_file_size_mb:
                logging.info("File is too small (%.02f MB): %s ",
                             file_mb, filename)
                continue

            # MIME type check, skip non-video files
            if not skip_mime:
                try:
                    if not is_video(filepath):
                        logging.debug(
                            "MIME type check: not a video file: %s", filepath.name)
                        continue
                except Exception as ex:
                    # this could happen on MS Windows and when there are
                    # Unicode characters in the filename
                    logging.exception(
                        "Problem with MIME type check: %s" % ex, exc_info=False)
                    continue

            if forceencode:
                logging.info(
                    "Because of override switch consider it nevertheless: %s", filepath)
                result.append(filepath)
            else:
                # metadata parsing using pymediainfo (libmediainfo)
                try:
                    media_info = MediaInfo.parse(filepath.absolute())
                except Exception as ex:
                    logging.error(
                        "Could not parse media info for '%s': %s", filepath, ex)
                    continue

                if check_metadata_isx265(media_info):
                    logging.info(
                        "Based on metadata, already x265: %s", filename)
                    continue
                if check_metadata_hasdonotmarker(media_info):
                    logging.info("Marked as do-not: %s", filename)
                    continue

                # this is a candidate
                result.append(filepath)

    return result


class ConversionProcessResult(IntEnum):
    """Return code for run_conversion_process(...)."""

    ORIGINAL_MISSING = -3
    NOT_SMALLER = -2
    NON_ZERO = -1
    OK = 0


def run_conversion_process(cmd: ConversionCommand,
                           keep: bool = False,
                           create_report: bool = True):
    """Run the actual external conversion tool.

    :param cmd: the ConversionCommand dataclass
    :param keep: keep conversion artifacts
    :param create_report: if to create a report logfile
    :return: 0 if all good, >0 otherwise
    """
    cmd_str = cmd.get_command()

    # running...
    t_start = datetime.datetime.now()
    logging.info("running command (at %s): %s", t_start, cmd_str)
    stderr = BytesIO()
    proc = None
    try:
        if DEBUG:
            logging.warning("****DEBUG*** not actually running '%s'", cmd_str)
        else:

            # run the external conversion program
            proc = subprocess.Popen(shlex.split(
                cmd_str), stderr=subprocess.PIPE)

            # live output and collecting until nothing more is produced
            while proc.stderr and proc.stderr.readable():
                # only read 1 byte/character (not readline()!)
                # NOTE: readline() does not work for ffmpeg because "frame=..."
                # status message does not end with a newline
                # readline() does not work with later filtering
                c = proc.stderr.read(1)
                if not c:
                    break
                # print to STDERR (console)
                sys.stderr.write(c.decode(encoding="utf8", errors="replace"))
                # store/record for logfile
                stderr.write(c)

            # set proc.returncode
            proc.wait()
    except OSError as ex:
        logging.exception(ex)

    t_stop = datetime.datetime.now()
    t_duration = t_stop - t_start
    logging.info("done (at %s), duration: %s", t_stop, t_duration)

    if create_report:
        report_filepath = cmd.get_filepath_new().with_suffix(".log")
        _create_report_file(report_filepath, cmd_str, stderr.getvalue())

    # post-process checking
    if proc is None or proc.returncode != 0:
        if proc:
            logging.error(
                "PROBLEM running converter! return code: %s", proc.returncode)
        else:
            logging.error("PROBLEM running converter! Unknown process state.")

        # check if there's just a left-over dummy file
        if cmd.get_filepath_new().exists() and not keep:
            logging.error(
                "Problem with conversion. Removing left-over artifact ...")
            try:
                os.remove(cmd.get_filepath_new())
            except OSError as ex:
                logging.exception(
                    "Problem removing left-over artifact!", exc_info=ex)

        # stop right here
        return ConversionProcessResult.NON_ZERO

    file_mb = get_file_size_mb(cmd.get_filepath())
    newfile_mb = get_file_size_mb(cmd.get_filepath_new())
    logging.debug("file_mb: %.2f, newfile_mb: %.2f", file_mb, newfile_mb)

    # custom metadata
    meta_custom = {
        "original_filename": cmd.get_filepath().name,
        "original_size_mb": file_mb,
        "newfile_size_mb": newfile_mb,
        "encoding_duration": str(t_duration),
        "encoding_duration_seconds": t_duration.total_seconds(),
        # only the template without the actual paths (privacy concerns...)
        "encoding_template": CONVERT_CMD_TEMPLATE,
        "encoding_time": datetime.datetime.now().isoformat()
    }

    # check if the new file is actually 95% smaller
    if (file_mb * 0.95) < newfile_mb:
        logging.warning("New file is not really smaller (new:%.02f MB, old:%.02f MB) - mark it.",
                        newfile_mb, file_mb * 0.95)
        _add_metadata_nogain(cmd, meta_custom)
        if keep:
            logging.info(
                "encoding artifact is bigger => no re-encoding benefits")
        else:
            logging.info(
                "encoding artifact is bigger => no re-encoding benefits => remove artifact")
            cmd.get_filepath_new().unlink()
        return ConversionProcessResult.NOT_SMALLER

    # check if new file has a meaningful size (> 5 % of original)
    if newfile_mb > (file_mb * 0.05):
        try:
            # all seems good - rename old file
            cmd.get_filepath().rename(cmd.get_filepath_done())
        except FileNotFoundError as ex:
            logging.exception(ex)
            return ConversionProcessResult.ORIGINAL_MISSING

        logging.info("marking newly encoded file (add metadata) ...")
        meta_standard = {
            # only the template without the actual paths (privacy concerns...)
            "ENCODER_SETTINGS": CONVERT_CMD_TEMPLATE,
        }
        metadata_xml = mkv_produce_metadata(
            meta_standard=meta_standard, meta_custom=meta_custom)
        mkv_add_metadata_xml(cmd.get_filepath_new(), metadata_xml)

    # only pause for cooldown if there is a relevant file size and job duration
    # (do not wait/halt for small files, no cool down needed there)
    if file_mb > 100 and t_duration.total_seconds() > COOLDOWN_AFTER_SECONDS:
        logging.info("waiting %d sec to cool down ...", COOLDOWN_SECONDS)
        sleep(COOLDOWN_SECONDS)
        logging.debug("cool down done.")
    else:
        logging.debug("No cooldown because file or job duration too small.")

    return ConversionProcessResult.OK


def _add_metadata_nogain(cmd: ConversionCommand, meta_custom: dict[str, object]):
    # add metadata (marking) to tell about this futile conversion endeavour
    logging.info("marking original file (add metadata) ...")
    meta_custom[MKV_METADATA_X265NOGAIN] = True
    metadata_xml = mkv_produce_metadata(
        meta_standard={}, meta_custom=meta_custom)
    mkv_add_metadata_xml(cmd.get_filepath(), metadata_xml, keep_times=True)
    # rename original file to indicate that future conversion is futile
    filepath_donemarked = _build_filename_with_marker(cmd.get_filepath(),
                                                      marker=FILENAME_MARKER_NOGAIN)
    logging.debug("renaming original file: %s --> %s",
                  cmd.get_filepath(), filepath_donemarked)
    os.rename(cmd.get_filepath(), filepath_donemarked)


def _create_report_file(report_filepath: Path, cmd_str: str, data: bytes):
    # store into logfile alongside the media file
    logging.debug("report_file: %s", report_filepath.resolve())
    try:
        with Path(report_filepath).open("wb") as fout:
            fout.write(f"cmd_str: {cmd_str}\n".encode())
            fout.write(b"\n")
            for line in data.splitlines():
                if not line.startswith(b"frame="):
                    fout.write(line)
                    fout.write(os.linesep.encode())
    except OSError as ex:
        logging.exception("Problem storing ffmpeg output to logfile '%s'!" %
                          report_filepath.resolve(), exc_info=ex)


def run(rootdir: Path,
        convert_cmd_template: Template,
        min_file_size_mb: float = 40.0,
        output_stream=None,
        just_list: bool = False,
        keep: bool = False,
        abortonerrror: bool = False,
        reencode: bool = False,
        skip_mime: bool = False,
        create_report: bool = True,
        signalling: bool = True):
    """Run the main job.

    :param rootdir: root directory where to start the recursive scan
    :param convert_cmd_template: string run-template (ffmpeg command template)
    :param min_file_size_mb: minimum file size in MB for actually considering candidates
    :param output_stream: stream where to write commands to
    :param just_list: just list, do not start conversion process
    :param keep: keep conversion artifacts (e.g., when broken/aborted/etc.)
    :param abortonerrror: do not continue but abort if there's an error
    :param reencode: force re-encoding even if already x265
    :param skip_mime: skip MIME type checking when looking for candidates
    :param create_report: create report file (FILENAME.log)
    :return: exit/return code (int, for main())
    """
    global main_loop_running

    if not rootdir.is_dir():
        raise NotADirectoryError(rootdir)
    if just_list:
        assert output_stream is not None, "Invalid state! just-list must have a valid output stream!"

    # collect list of file candidates
    logging.info("Recursively finding file conversion candidates...")
    candidates = find_candidates(rootdir,
                                 min_file_size_mb=min_file_size_mb,
                                 forceencode=reencode,
                                 skip_mime=skip_mime)
    logging.info("Found #%d conversion candidates.", len(candidates))

    if not candidates:
        logging.info("No conversion candidates found! Exiting.")
        return 0

    if just_list:
        # just output the found files, do not run conversion process
        for filepath in candidates:
            output_stream.write("%s\n" % filepath.absolute())
        output_stream.flush()
        return 0

    # produce actual conversion commands (just generate, but do not run yet)
    conversion_commands = [ConversionCommand(
        convert_cmd_template, filepath) for filepath in candidates]

    # just output the conversion commands
    if output_stream is not None:
        for cmd in conversion_commands:
            output_stream.write(f"{cmd.get_command()}\n")
        output_stream.flush()
        return 0

    ##
    # output_stream is None => run conversion command
    ##

    if signalling:
        # signal listening/handler for CTRL+C
        def ctrl_c_handler(signalnum, frame):
            global main_loop_running
            logging.info("SIGINT/CTRL+C event! Flagging main loop to stop ...")
            main_loop_running = False

        # allow the processing to be stopped by CTRL+C or by a simple socket/TCP connection
        signal.signal(signal.SIGINT, ctrl_c_handler)  # CTRL+C

        # start a TCP listener (for stop-signalling) in an extra thread
        socket_thread = threading.Thread(target=_socket_listener)
        socket_thread.start()

    return_code = 0
    for i, cmd in enumerate(conversion_commands):
        if not main_loop_running:
            logging.info("main_loop_running is set to false! stopping ...")
            # this could happen if
            # - socket connection
            # - CTRL+C
            break
        logging.info("%d/%d process ...", i + 1, len(conversion_commands))
        return_code += run_conversion_process(cmd,
                                              keep=keep, create_report=create_report)
        logging.debug("run.return_code: %d", return_code)

        if return_code < 0 and abortonerrror:
            logging.info("Aborting...")
            break
        # else, output cosmetics (logging is on stderr)
        sys.stderr.write(("-" * 80 + "\n") * 2 + "\n" * 2)

    if signalling:
        main_loop_running = False
        socket_thread.join(timeout=1)

    # return the accumulated exit codes (should be 0 if everything went correct)
    return return_code


def check_prerequisites():
    """Check if the required things are in place."""
    try:
        # check if port can actually be opened
        with socket.create_server(("localhost", TCP_PORT)):
            pass
    except OSError as ex:
        # i.e., address already in use
        logging.exception(ex)
        return False

    # check for necessary tools
    exe = shlex.split(CONVERT_CMD_TEMPLATE)[0]
    logging.debug("checking for '%s' in PATH...", exe)
    if not shutil.which(exe):
        raise RuntimeError(f"Could not find '{exe}' in PATH!")

    logging.debug("checking for 'mkvpropedit' in PATH...")
    if not shutil.which("mkvpropedit"):
        raise RuntimeError("Could not find mkvpropedit in PATH!")

    return True


def main():
    """Run the main program.

    :return: exit/return code
    """
    # allow only 1 instance
    SingleInstance(flavor_id="video_convert_x265")

    version_string = f"Video x265 Converter {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    # print(arguments)
    arg_root = arguments["<directory>"]

    # output arguments
    arg_nocolor = arguments["--no-color"]
    arg_verbose = arguments["--verbose"]
    arg_quiet = arguments["--quiet"]
    arg_output = arguments["--out"]
    arg_output_overwrite = arguments["--out-overwrite"]
    arg_just_list = arguments["--list"]

    # filtering and ffmpeg control arguments
    arg_min_file_size_mb = float(arguments["--size"])
    arg_skip_mime = arguments["--skip-mime"]
    arg_keep = arguments["--keep"]
    arg_reencode = arguments["--reencode"]
    arg_hdr_remove = arguments["--hdr-remove"]
    arg_ffmpeg_extra_args = arguments["--extra"]
    arg_abortonerrror = arguments["--abort-on-err"]

    # setup logging
    handler = colorlog.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        colorlog.ColoredFormatter('%(log_color)s%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S', no_color=arg_nocolor))
    logging.basicConfig(
        level=logging.INFO if not DEBUG else logging.DEBUG, handlers=[handler])

    if arg_verbose:
        logging.getLogger("").setLevel(logging.DEBUG)
    elif arg_quiet:
        logging.getLogger("").setLevel(logging.WARNING)

    logging.info(version_string)
    logging.debug("arguments: %s", arguments)

    root = Path(arg_root)
    logging.info("root directory: %s", root.absolute())
    logging.info("min file size: %d MB", arg_min_file_size_mb)

    if arg_hdr_remove:
        arg_ffmpeg_extra_args = "%s %s" % (arg_ffmpeg_extra_args, CONVERT_CMD_HDR_REMOVE) \
            if arg_ffmpeg_extra_args else CONVERT_CMD_HDR_REMOVE

    convert_cmd_template = __handle_args_cmdtemplate(arg_ffmpeg_extra_args)
    logging.info("conversion command template: %s", convert_cmd_template)

    output_stream = __handle_args_outputstream(
        arg_output_overwrite, arg_output)
    logging.info("Output stream: %s", output_stream)

    assert not (arg_just_list and output_stream is None), "--list needs --out!"
    assert arg_min_file_size_mb >= 0

    if not check_prerequisites():
        logging.fatal("Preqrequisites failure!")
        return -9

    exit_code = run(root,
                    convert_cmd_template,
                    arg_min_file_size_mb,
                    output_stream,
                    arg_just_list,
                    arg_keep,
                    arg_abortonerrror,
                    arg_reencode,
                    arg_skip_mime)
    logging.debug("exit_code: %d", exit_code)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
