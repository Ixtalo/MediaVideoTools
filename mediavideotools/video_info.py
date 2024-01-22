#!/usr/bin/python
# -*- coding: utf-8 -*-
"""video_info.py - Extract video metadata information to CSV.

Extracts important video information (codec, duration, bit_rate, etc.)
and writes it to a CSV file.
Fields of interest are a.o. "format", "codecs_video",
"video_format_list", "video_language_list", "duration",
"audio_codecs", etc. (see below)

Usage:
  video_info.py [options] <directory>
  video_info.py -h | --help
  video_info.py --version

Arguments:
  directory         Starting root directory for recursive scan.

Options:
  -h --help         Show this screen.
  --no-color        No colored log output.
  -o --out=FILE     Write to output file, could also be "-" for STDOUT.
  -v --verbose      Be more verbose.
  --version         Show version.
"""
#
# LICENSE:
#
# Copyright (C) 2015-2022 by Ixtalo, ixtalo@gmail.com
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
import logging
import os
import sys
# pylint: disable-next=redefined-builtin
from codecs import open
from pathlib import Path

import colorlog
from docopt import docopt
from pymediainfo import MediaInfo

# HACK to run file both as module and Python program
try:
    # for running as Python program
    from mime_checker import is_video
except ModuleNotFoundError:
    # for pytest a relative import is needed
    from .mime_checker import is_video


__version__ = "1.4.3"
__date__ = "2015-06-11"
__updated__ = "2022-10-03"
__author__ = "Ixtalo"
__license__ = 'AGPL-3.0+'
__email__ = "ixtalo@gmail.com"
__status__ = "Production"

# CSV delimiter
DELIMITER = ";"

# MediaInfo fields to output
FIELDS_OF_INTEREST = (
    ("General", "file_size"),
    ("General", "format"),
    ("General", "duration"),
    ("General", "video_codecs"),
    ("General", "audio_codecs"),
    ("General", "audio_language_list"),
    ("General", "text_language_list"),

    ("Video", "format"),
    ("Video", "format_profile"),
    ("Video", "encoded_library_name"),
    ("Video", "bit_rate"),
    ("Video", "bit_rate_mode"),
    ("Video", "pixel_aspect_ratio"),
    ("Video", "proportion_of_this_stream")
)

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 0):
    sys.stderr.write('Minimum required version is Python 3.x!\n')
    sys.exit(1)


def scan(rootdir: Path, output_stream=sys.stdout):
    """Recursive scanning for all media files.

    :param rootdir: starting base path
    :param output_stream: output stream, defaults to STDOUT
    """
    if not rootdir.is_dir():
        raise NotADirectoryError(rootdir)

    # CSV header line
    fieldnames = [foi[1] for foi in FIELDS_OF_INTEREST]
    output_stream.write(f"{DELIMITER.join(['filename'] + fieldnames)}\n")
    for root, dirs, files in os.walk(rootdir.resolve()):
        dirs.sort()
        files.sort()
        for filename in files:
            filepath = Path(root, filename)
            logging.info("filepath: %s ...", filepath)

            if filepath.is_symlink() and not filepath.exists():
                logging.warning("skipping broken symlink: %s",
                                filepath.absolute())
                continue

            # check if actually a video file
            try:
                if not is_video(filepath):
                    logging.debug(
                        "Not expected file type, skipping : %s", filepath)
                    continue
            except FileNotFoundError as ex:
                logging.exception(ex, exc_info=False)
                continue
            except OSError as ex:
                logging.exception(ex, exc_info=False)
                continue

            # get the info by using MediaInfo library
            logging.info("Analyzing media type: %s", filepath)
            media_info = MediaInfo.parse(filepath)

            # construct row container
            row = [f'"{filepath.resolve().relative_to(Path(os.getcwd()))}"', ]

            for foi in FIELDS_OF_INTEREST:
                foi_track_name, field_name = foi
                for track in media_info.tracks:
                    if track.track_type == foi_track_name:
                        value = str(track.to_data().get(field_name, ""))
                        if DELIMITER in value:
                            value = f'"{value}"'
                        row.append(value)

            # write row, with delimiter
            output_stream.write(f"{DELIMITER.join(row)}\n")

    output_stream.flush()
    return 0


def main():
    """Run main program.

    :return: exit/return code
    """
    version_string = f"Video Info to CSV {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_root = arguments["<directory>"]
    arg_output = arguments["--out"]
    arg_verbose = arguments["--verbose"]
    arg_nocolor = arguments["--no-color"]

    # setup logging
    handler = colorlog.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        colorlog.ColoredFormatter('%(log_color)s%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S', no_color=arg_nocolor))
    logging.basicConfig(
        level=logging.WARNING if not DEBUG else logging.DEBUG, handlers=[handler])
    if arg_verbose:
        logging.getLogger("").setLevel(logging.INFO)
    logging.info(version_string)

    out = sys.stdout
    if arg_output is not None and arg_output != "-":
        if os.path.exists(arg_output):
            raise FileExistsError(arg_output)
        # pylint: disable-next=consider-using-with
        out = open(arg_output, "w", encoding="utf8")

    root = Path(arg_root)
    logging.info("base path: %s", root.absolute())
    logging.info("output: %s", out)
    return scan(root, out)


if __name__ == '__main__':
    sys.exit(main())
