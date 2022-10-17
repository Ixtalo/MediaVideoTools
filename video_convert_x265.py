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
  -f --force      Force overwrite of output file.
  --force-encode  Force encoding, even if already x265.
  -h --help       Show this screen.
  -k --keep       Keep encoding artifacts, even if no real size gain.
  -l --list       Just list, do not start conversion process.
  --no-color      No colored log output.
  -o --out=FILE   Write commands to output file or "-" for STDOUT
                  instead of calling ffmpeg directly.
  -q --quiet      Be more quiet, e.g., no "too small" messages.
  -s --size=MB    Minimum necessary file size in MB [default: 100].
  -v --verbose    Be more verbose.
  --version       Show version.
"""
##
# LICENSE:
##
# Copyright (c) 2021-2022 by Ixtalo, ixtalo@gmail.com
##
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
##
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
##
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
##
import os
import sys
import subprocess
import shlex
import logging
import signal
import socket
import threading
import datetime
from time import sleep
from pathlib import Path
# pylint: disable-next=redefined-builtin
from codecs import open

import colorlog
import pymediainfo
from docopt import docopt
from pymediainfo import MediaInfo
from mime_checker import is_video
from utils import get_file_size_mb
from mkv_metadata import mkv_add_metadata_xml, mkv_produce_metadata
from singleton import SingleInstance

__appname__ = "video_convert_x265"
__version__ = "1.13.5"
__date__ = "2021-09-15"
__updated__ = "2022-10-17"
__author__ = "Ixtalo"
__email__ = "ixtalo@gmail.com"
__license__ = "AGPL-3.0+"
__status__ = "Production"

# the video conversion command
# e.g. 'ffmpeg -n -i "%s" -map 0 -c:v libx265 "%s"'
# hevc_nvenc = NVIDIA NVENC hevc encoder (codec hevc). Best options are the default settings!
CONVERT_CMD_TEMPLATE = 'ffmpeg -n -hide_banner -i "%s" -map 0 -c:s copy -c:v hevc_nvenc "%s"'
# duration (in seconds) after which to cooldown/pause
COOLDOWN_AFTER_SECONDS = 120
# seconds for cooldown between conversion processes
COOLDOWN_SECONDS = 60
# the file-type extension, e.g. '.mkv'
FILENAME_EXTENSION = ".mkv"
# marker for converted files
FILENAME_MARKER_X265 = "_x265"
# postfix for original files
FILENAME_POSTFIX_DONE = ".x265done"
# skipped filename extensions (tuple/list)
FILENAME_EXTENSIONS_BLACKLIST = (".rar", ".par2", ".zip", ".jpg", ".jpeg", ".nfo", ".srt", ".idx", ".sub", ".style")
# MKV metadata base tag name
MKV_METADATA_BASETAGNAME = "video_convert_x265"
# MKV metadata key name of the no-gain flag
MKV_METADATA_X265NOGAIN = "x265_no_gain"
# TCP port for socket listener, for stopping the main-loop
TCP_PORT = 12345


DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 9):
    sys.stderr.write("Minimum required version is Python 3.9!\n")
    sys.exit(1)

# flag: keep running until this is set to False
main_loop_running = True


class ConversionCommand:
    """Container for conversion command, used for subprocess calls."""

    def __init__(self, convert_cmd_template: str, filepath: Path):
        """Conversion Command.

        :param convert_cmd_template: string with (ffmpeg) conversion template
        :param filepath: a pathlib.Path object
        """
        assert r"%s" in convert_cmd_template
        self.__convert_cmd_template = convert_cmd_template
        assert isinstance(filepath, Path)
        self.__filepath = filepath

    def get_filepath(self) -> Path:
        """Return the filepath, i.e., the original path and filename."""
        return self.__filepath

    def get_filepath_new(self) -> Path:
        """Return the filepath for marked files, i.e., with x265-marker."""
        return _get_x265_marker_filename(self.__filepath)

    def get_filepath_done(self) -> Path:
        """Return that filepath for done-files."""
        return _get_done_filename(self.__filepath)

    def get_command(self) -> str:
        """Get the final command string.

        e.g. ffmpeg -n -i "%s" -map 0 -c copy -c:v libx265 "%s_x265.mkv"
        :return: command string
        """
        assert self.__convert_cmd_template.count(r"%s") == 2
        return self.__convert_cmd_template % \
            (self.get_filepath().absolute(), self.get_filepath_new().absolute())


def __handle_args_cmdtemplate(arg_ffmpeg_extra_args):
    convert_cmd_template = CONVERT_CMD_TEMPLATE
    if arg_ffmpeg_extra_args:
        # find position of the last "%s" template
        qpos = convert_cmd_template.rfind('"%s"')
        # inject extra arguments just before last "%s"
        convert_cmd_template = convert_cmd_template[0:qpos] + \
            arg_ffmpeg_extra_args + " " + convert_cmd_template[qpos:]
        assert len(convert_cmd_template) > len(CONVERT_CMD_TEMPLATE)
    return convert_cmd_template


def __handle_args_outputstream(arg_force, arg_output):
    output_stream = None
    if arg_output:
        if arg_output == "-":
            output_stream = sys.stdout
        else:
            output_filepath = os.path.abspath(arg_output)
            logging.debug("output_filepath: %s", output_filepath)
            if not arg_force and os.path.exists(arg_output):
                raise FileExistsError(f"Output file exists already: {output_filepath}")
            # pylint: disable-next=consider-using-with
            output_stream = open(output_filepath, "w")
    return output_stream


def __check_is_donefile(filepath: Path):
    return FILENAME_POSTFIX_DONE in filepath.suffixes


def __check_has_marker(filepath: Path):
    return FILENAME_MARKER_X265 in filepath.name


def _get_done_filename(filepath: Path):
    if __check_is_donefile(filepath):
        return filepath
    return filepath.with_suffix(f"{filepath.suffix}{FILENAME_POSTFIX_DONE}")


def __check_is_blacklisted(filepath: Path):
    return filepath.suffix in FILENAME_EXTENSIONS_BLACKLIST


def _get_x265_marker_filename(filepath: Path):
    if __check_has_marker(filepath):
        return filepath
    if filepath.suffix.endswith(FILENAME_EXTENSION):
        return filepath.with_name(f"{filepath.stem}{FILENAME_MARKER_X265}{filepath.suffix}")
    return filepath.with_name(f"{filepath.stem}{FILENAME_MARKER_X265}{filepath.suffix}{FILENAME_EXTENSION}")


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
            pass    # do nothing
        except socket.error as ex:
            logging.exception(ex)


def check_metadata_hasdonotmarker(media_info: pymediainfo.MediaInfo) -> bool:
    """Check if the metadata contains our special do-not-marker.

    :param media_info: metadata object from pymediainfo (libmediainfo)
    """
    key_name = f"{MKV_METADATA_BASETAGNAME}_{MKV_METADATA_X265NOGAIN}"
    for track in media_info.general_tracks:  # typically there's just 1 general track...
        logging.debug("track %s, %s, %s", track, track.internet_media_type, track.format)
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
        logging.debug("track %s, %s, %s", track, track.internet_media_type, track.format)
        if track.internet_media_type != "video/h265" and track.format != "HEVC":
            # return False if any video track is actually not x265/hvec
            return False
    return True


def find_candidates(rootdir: Path, min_file_size_mb: float, forceencode: bool = False) -> list[Path]:
    """Find video files candidates.

    :param rootdir: root directory where to start the recursive scan
    :param min_file_size_mb: minimum file size in MB for actually considering candidates
    :param forceencode: force encoding even if a file has a done-marker
    :return: list of Path objects
    """
    result = []
    for root, _, files in os.walk(rootdir):
        for filename in files:
            filepath = Path(root, filename)
            logging.debug("filepath: %s", filepath)

            if __check_is_blacklisted(filepath):
                # i.e., not a video file (considering the file's extension)
                logging.debug("Skipping extension-blacklisted (FILENAME_EXTENSIONS_BLACKLIST): %s", filename)
                continue

            if __check_has_marker(filepath):
                # e.g., "_x265" in filename
                logging.debug("Marker '%s' (FILENAME_MARKER_X265) is in filename: %s", FILENAME_MARKER_X265, filename)
                continue

            if __check_is_donefile(filepath):
                # e.g., ".x265done" in filename suffix
                logging.debug("Already done (FILENAME_POSTFIX_DONE): %s", filename)
                continue

            # TODO check if redundant to __check_is_donefile() from above/before
            filepath_done = _get_done_filename(filepath)
            if filepath_done.exists():
                logging.warning("done target exists already: %s", filepath_done)
                continue

            # TODO check if redundant to __check_has_marker() from above/before
            filepath_new = _get_x265_marker_filename(filepath)
            if os.path.exists(filepath_new):
                logging.warning("Target file exists already: %s", filepath_new)
                continue

            # check if video file size is actually relevant for re-encoding
            file_mb = get_file_size_mb(filepath)
            logging.debug("file_mb: %.02f", file_mb)
            if file_mb < 0:
                logging.error("Problem getting file size for: %s", filepath)
                continue
            if file_mb < min_file_size_mb:
                logging.info("File is too small (%.02f MB): %s ", file_mb, filename)
                continue

            # MIME type check, skip non-video files
            try:
                if not is_video(filepath.absolute()):
                    continue
            except FileNotFoundError as ex:
                logging.exception(ex, exc_info=False)
            except OSError as ex:
                logging.exception(ex, exc_info=False)

            if forceencode:
                logging.info("Because of override switch consider nevertheless : %s", filepath)
                result.append(filepath)
            else:
                # metadata parsing using pymediainfo (libmediainfo)
                try:
                    media_info = MediaInfo.parse(filepath.absolute())
                except Exception as ex:
                    logging.error("Could not parse media info for '%s': %s", filepath, ex)
                    continue

                if check_metadata_isx265(media_info):
                    logging.info("Based on metadata, already x265: %s", filename)
                    continue
                if check_metadata_hasdonotmarker(media_info):
                    logging.info("Marked as do-not: %s", filename)
                    continue

                # this is a candidate
                result.append(filepath)

    return result


def run_conversion_process(cmd: ConversionCommand, keep: bool = False):
    """Run the actual external conversion tool.

    :param cmd: the ConversionCommand dataclass
    :param keep: keep conversion artifacts
    :return: 0 if all good, >0 otherwise
    """
    cmd_str = cmd.get_command()
    t_start = datetime.datetime.now()
    logging.info("running command (at %s): %s", t_start, cmd_str)
    proc = None
    try:
        if DEBUG:
            logging.warning("****DEBUG*** not actually running '%s'", cmd_str)
        else:
            # now actually run the external conversion program
            proc = subprocess.run(shlex.split(cmd_str), check=False)
    except OSError as ex:
        logging.exception(ex)

    t_stop = datetime.datetime.now()
    t_duration = t_stop - t_start
    logging.info("done (at %s), duration: %s", t_stop, t_duration)

    if proc is None or proc.returncode != 0:
        if proc:
            logging.error("PROBLEM running converter! return code: %d", proc.returncode)
        else:
            logging.error("PROBLEM running converter! Unknown process state.")

        # check if there's only a left-over dummy file
        if cmd.get_filepath_new().exists() and not keep:
            logging.error("Problem with conversion. Removing left-over artifact ...")
            try:
                os.remove(cmd.get_filepath_new())
            except OSError as ex:
                logging.exception("Problem removing left-over artifact!", exc_info=ex)

        return -1

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

        logging.info("marking original file (add metadata) ...")
        meta_custom[MKV_METADATA_X265NOGAIN] = True
        metadata_xml = mkv_produce_metadata(meta_standard={}, meta_custom=meta_custom)
        mkv_add_metadata_xml(cmd.get_filepath(), metadata_xml, keep_times=True)

        if not keep:
            logging.info("encoding artifact is bigger => no re-encoding benefits => remove artifact")
            cmd.get_filepath_new().unlink()
        else:
            logging.info("encoding artifact is bigger => no re-encoding benefits")

        return -2

    # check if new file has a meaningful size (> 5 % of original)
    if newfile_mb > (file_mb * 0.05):
        try:
            # all seems good - rename old file
            cmd.get_filepath().rename(cmd.get_filepath_done())
        except FileNotFoundError as ex:
            logging.exception(ex)
            return -3

        logging.info("marking newly encoded file (add metadata) ...")
        meta_standard = {
            # only the template without the actual paths (privacy concerns...)
            "ENCODER_SETTINGS": CONVERT_CMD_TEMPLATE,
        }
        metadata_xml = mkv_produce_metadata(meta_standard=meta_standard, meta_custom=meta_custom)
        mkv_add_metadata_xml(cmd.get_filepath_new(), metadata_xml)

    # only pause for cooldown if there is a relevant file size and job duration
    # (do not wait/halt for small files, no cool down needed there)
    if file_mb > 100 and t_duration.total_seconds() > COOLDOWN_AFTER_SECONDS:
        logging.info("waiting %d sec to cool down ...", COOLDOWN_SECONDS)
        sleep(COOLDOWN_SECONDS)
        logging.debug("cool down done.")
    else:
        logging.debug("No cooldown because file or job duration too small.")

    return 0


def run(rootdir: Path,
        convert_cmd_template: str,
        min_file_size_mb: float = 40.0,
        output_stream=None,
        just_list: bool = False,
        keep: bool = False,
        abortonerrror: bool = False,
        forceencode: bool = False):
    """Run the main job.

    :param rootdir: root directory where to start the recursive scan
    :param convert_cmd_template: string with (ffmpeg) conversion template
    :param min_file_size_mb: minimum file size in MB for actually considering candidates
    :param output_stream: stream where to write to
    :param just_list: just list, do not start conversion process
    :param keep: keep conversion artifacts (e.g., when broken/aborted/etc.)
    :param abortonerrror: do not continue but abort if there's an error
    :param forceencode: force encoding even if already x265
    :return: exit/return code (int, for main())
    """
    global main_loop_running

    if not rootdir.is_dir():
        raise NotADirectoryError(rootdir)
    if just_list:
        assert output_stream is not None, "Invalid state! just-list must have a valid output stream!"

    # collect list of file candidates
    logging.info("Recursively finding file conversion candidates...")
    candidates = find_candidates(rootdir, min_file_size_mb=min_file_size_mb, forceencode=forceencode)
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
    conversion_commands = [ConversionCommand(convert_cmd_template, filepath) for filepath in candidates]

    # just output the conversion commands
    if output_stream is not None:
        for cmd in conversion_commands:
            output_stream.write(f"{cmd.get_command()}\n")
        output_stream.flush()
        return 0

    ##
    # output_stream is None => run conversion command
    ##

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
        return_code += run_conversion_process(cmd, keep=keep)
        logging.debug("run.return_code: %d", return_code)

        if return_code < 0 and abortonerrror:
            logging.info("Aborting...")
            break
        # else, output cosmetics (logging is on stderr)
        sys.stderr.write(("-" * 80 + "\n") * 2 + "\n" * 2)

    main_loop_running = False
    socket_thread.join(timeout=1)

    # return the accumulated exit codes (should be 0 if everything went correct)
    return return_code


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
    arg_min_file_size_mb = float(arguments["--size"])
    arg_output = arguments["--out"]
    arg_ffmpeg_extra_args = arguments["--extra"]
    arg_force = arguments["--force"]
    arg_keep = arguments["--keep"]
    arg_just_list = arguments["--list"]
    arg_verbose = arguments["--verbose"]
    arg_quiet = arguments["--quiet"]
    arg_nocolor = arguments["--no-color"]
    arg_abortonerrror = arguments["--abort-on-err"]
    arg_forceencode = arguments["--force-encode"]

    # setup logging
    handler = colorlog.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        colorlog.ColoredFormatter('%(log_color)s%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S', no_color=arg_nocolor))
    logging.basicConfig(level=logging.INFO if not DEBUG else logging.DEBUG, handlers=[handler])

    if arg_verbose:
        logging.getLogger("").setLevel(logging.DEBUG)
    elif arg_quiet:
        logging.getLogger("").setLevel(logging.WARNING)

    logging.info(version_string)
    logging.debug("arguments: %s", arguments)

    root = Path(arg_root)
    logging.info("root directory: %s", root.absolute())
    logging.info("min file size: %d", arg_min_file_size_mb)

    convert_cmd_template = __handle_args_cmdtemplate(arg_ffmpeg_extra_args)
    logging.info("conversion command template: %s", convert_cmd_template)
    assert convert_cmd_template.count(r"%s") == 2, r"Template must contain 2 '%s' string-replace tokens!"

    output_stream = __handle_args_outputstream(arg_force, arg_output)
    logging.info("Output stream: %s", output_stream)

    assert not (arg_just_list and output_stream is None), "--list needs --out!"
    assert arg_min_file_size_mb >= 0

    exit_code = run(root,
                    convert_cmd_template,
                    arg_min_file_size_mb,
                    output_stream,
                    arg_just_list,
                    arg_keep,
                    arg_abortonerrror,
                    arg_forceencode)
    logging.debug("exit_code: %d", exit_code)
    return exit_code


if __name__ == '__main__':
    if DEBUG:
        sys.argv.append('--verbose')
    if os.environ.get("PROFILE", "").lower() in ("true", "1", "yes"):
        # pylint: disable-next=ungrouped-imports
        from time import strftime
        import cProfile
        import pstats
        profile_filename = f"{__file__}_{strftime('%Y-%m-%d_%H%M%S')}.profile"
        cProfile.run('main()', profile_filename)
        with open(f"{profile_filename}.txt", "w", encoding="utf8") as statsfp:
            profile_stats = pstats.Stats(profile_filename, stream=statsfp)
            stats = profile_stats.strip_dirs().sort_stats('cumulative')
            stats.print_stats()
        sys.exit(0)
    sys.exit(main())
