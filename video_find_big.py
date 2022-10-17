#!/usr/bin/python
# -*- coding: utf-8 -*-
"""video_find_big.py - finds big video files.

Finds big video files (big in size and bits-per-pixel-per-frame) and
outputs the details in CSV format.

Usage:
  video_find_big.py [options] <directory>
  video_find_big.py -h | --help
  video_find_big.py --version

Arguments:
  directory        Starting root directory for recursive scan.

Options:
  -h --help         Show this screen.
  --no-color        No colored log output.
  -s --size=MB      File size in MB to appear as "big" [default: 300]
  -o --out=FILE     Write to output file, could also be "-" for STDOUT.
  -v --verbose      Increase verbosity.
  --version         Show version.
"""
##
# LICENSE:
##
# Copyright (c) 2016-2022 by Ixtalo, ixtalo@gmail.com
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
import logging
# pylint: disable-next=redefined-builtin
from codecs import open
import colorlog
from pathlib import Path
from docopt import docopt
from pymediainfo import MediaInfo
from mime_checker import is_video
from utils import get_file_size_mb

__version__ = "1.4.2"
__date__ = "2016-05-11"
__updated__ = "2022-10-03"
__author__ = "Ixtalo"
__license__ = "GPL"
__email__ = "ixtalo@gmail.com"
__status__ = "Production"

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))


def scan_file(filepath: Path, output_stream=sys.stdout):
    """Single file scanning.

    :param filepath: single video file
    :param output_stream: output stream
    :return: exit code
    """
    assert isinstance(filepath, Path)
    try:
        media_info = MediaInfo.parse(filepath.absolute(), encoding_errors="replace")
    except Exception as ex:
        logging.error("Error while parsing file '%s': %s", filepath, ex)
        return -1
    if not media_info:
        logging.warning("No media info for: %s", filepath)
        return -2
    if not media_info.tracks:
        logging.warning("No tracks in file: %s", filepath)
        return -3

    filesize_mb = get_file_size_mb(filepath)
    general_track = media_info.tracks[0]

    for track in media_info.tracks:
        if track.kind_of_stream != "Video":
            continue

        # bits__pixel_frame
        # see http://www.streaminglearningcenter.com/articles/configuring-your-streaming-video-%28for-newbies%29.html?page=1
        # can sometimes be None, e.g. when fps is not set/is unknown
        try:
            bits__pixel_frame = float(track.bits__pixel_frame)
        except TypeError:
            bits__pixel_frame = 0

        try:
            bit_rate = int(track.bit_rate)
        except TypeError:
            bit_rate = -1

        try:
            if bits__pixel_frame > 0.2 or (bit_rate / 1000 > 3000 and track.width > 800):
                bits__pixel_frame_str = f"{bits__pixel_frame:.03f}" if bits__pixel_frame else ""
                # pylint: disable-next=consider-using-f-string
                output_stream.write("%s;%d;%s/%s/%s;%d;%s;%d;%d;%s\n" %
                                    (filepath.name, filesize_mb, general_track.format, track.format, track.codec_id,
                                     bit_rate / 1000, track.frame_rate, track.width, track.height,
                                     bits__pixel_frame_str))
        except TypeError as ex:
            logging.warning("No info for file '%s': %s", filepath, ex)

    return 0


def scan_recursive(root_dir, big_size: int, output_stream=sys.stdout):
    """Recursive scanning.

    :param root_dir: root directory for recursive scan
    :param big_size: file size in MB for big files
    :param output_stream: output stream
    """
    for root, _, filenames in os.walk(root_dir):
        for filename in filenames:
            filepath = Path(root, filename)

            filesize_mb = get_file_size_mb(filepath)
            if filesize_mb < big_size:
                logging.debug("File too small (%d < %d): %s",
                              filesize_mb, big_size, filepath)
                continue

            # check if actually a video file
            if not is_video(filepath.absolute()):
                continue

            logging.info("filepath: %s ...", filepath.absolute())
            scan_file(filepath, output_stream)


def scan(root: str, big_size: int, output_stream=sys.stdout):
    """Run the main job.

    :param root: root directory for recursive scanning
    :param big_size: file size in MB for big files
    :param output_stream: output stream
    :return: exit/return code (for main())
    """
    if not os.path.isdir(root):
        raise NotADirectoryError(root)
    # print CSV header
    output_stream.write("filepath;filesize_mb;format;bit_rate;frame_rate;width;height;bits__pixel_frame\n")
    scan_recursive(root, big_size)
    output_stream.flush()
    return 0


def main():
    """Run main program.

    :return: exit/return code
    """
    version_string = f"FindBigVideos {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_root = arguments["<directory>"]
    arg_size = float(arguments["--size"])
    arg_output = arguments["--out"]
    arg_verbose = arguments["--verbose"]
    arg_nocolor = arguments["--no-color"]

    assert arg_size > 0

    # setup logging
    handler = colorlog.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        colorlog.ColoredFormatter('%(log_color)s%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S', no_color=arg_nocolor))
    logging.basicConfig(level=logging.INFO if not DEBUG else logging.DEBUG, handlers=[handler])
    if arg_verbose:
        logging.getLogger("").setLevel(logging.INFO)
    logging.info(version_string)

    out = sys.stdout
    if arg_output is not None and arg_output != "-":
        if os.path.exists(arg_output):
            raise FileExistsError(arg_output)
        # pylint: disable-next=consider-using-with
        out = open(arg_output, "w", encoding="utf8")

    logging.info("base path: %s", os.path.realpath(arg_root))
    logging.info("output: %s", out)
    return scan(arg_root, arg_size, out)


if __name__ == '__main__':
    if DEBUG:
        # sys.argv.append('--verbose')
        pass
    if os.environ.get("PROFILE", "").lower() in ("true", "1", "yes"):
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
