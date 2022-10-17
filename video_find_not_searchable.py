#!/usr/bin/python
# -*- coding: utf-8 -*-
"""video_find_not_searchable.py - finds video files which are not searchable.

Some video files are not searchable, e.g., in a video player.
This is typically the case when the index is broken.

Combinations for broken videos:
----------------------------------------------
| format | codecs_video   | video_format_list
|        | ()             | ()
|        | DivX 5         | MPEG-4 Visual
|        | DivX 3 Low     | MPEG-4 Visual
|        | DivX 4         | MPEG-4 Visual
|        | Indeo 3        | Indeo 3
|        | MPEG-4 Visual  | MPEG-4 Visual
| AVI    | XviD           | MPEG-4 Visual
----------------------------------------------


Usage:
  video_find_not_searchable.py [options] <directory>
  video_find_not_searchable.py -h | --help
  video_find_not_searchable.py --version

Arguments:
  directory         Starting root directory for recursive scan.

Options:
  -h --help         Show this screen.
  --no-color        No colored log output.
  -o --out=FILE     Write to output file, could also be "-" for STDOUT.
  -v --verbose      Be more verbose.
  --version         Show version.
"""
##
# LICENSE:
##
# Copyright (c) 2015-2022 by Ixtalo, ixtalo@gmail.com
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
from pathlib import Path
# pylint: disable-next=redefined-builtin
from codecs import open
import colorlog
from docopt import docopt
from pymediainfo import MediaInfo
from mime_checker import is_video

__version__ = "1.2.2"
__date__ = "2015-06-11"
__updated__ = "2022-10-03"
__author__ = "Ixtalo"
__license__ = "GPL"
__email__ = "ixtalo@gmail.com"
__status__ = "Production"

DELIMITER = ";"

FIELDS_OF_INTEREST = (
    "format",
    # "format_version",
    # "codec",
    "codecs_video",
    "video_format_list",
    "video_language_list",
    "duration",
    "audio_codecs",
    "audio_format_list",
    "audio_language_list",
    # "text_codecs",
    "text_language_list",
    "count_of_audio_streams",
    "count_of_menu_streams",
    "count_of_stream_of_this_kind",
    "count_of_text_streams",
    "count_of_video_streams",
)


DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 0):
    sys.stderr.write("Minimum required version is Python 3.x!\n")
    sys.exit(1)


def scan(rootdir: Path, output_stream=sys.stdout):
    """Recursive scan for problematic video files.

    :param rootdir: root directory for recursive scan
    :param output_stream: target output stream
    """
    assert isinstance(rootdir, Path)
    if not rootdir.is_dir():
        raise NotADirectoryError(rootdir)
    # CSV header line
    output_stream.write(f"{DELIMITER.join(('filename',) + FIELDS_OF_INTEREST)}\n")
    # recursive scanning
    for root, dirs, files in os.walk(rootdir.resolve()):
        dirs.sort()
        for filename in files:
            filepath = Path(root, filename)
            logging.info("filepath: %s ...", filepath)

            if filepath.is_symlink() and not filepath.exists():
                logging.warning("skipping broken symlink: %s", filepath.absolute())
                continue

            try:
                # check if actually a video file
                if not is_video(filepath):
                    continue
            except FileNotFoundError as ex:
                logging.exception(ex, exc_info=False)
                continue
            except OSError as ex:
                logging.exception(ex, exc_info=False)
                continue

            data = [str(filepath.resolve().relative_to(os.getcwd())), ]
            media_info = MediaInfo.parse(str(filepath))

            for track in media_info.tracks:
                if track.track_type != "General":
                    continue

                # format	codecs_video	video_format_list
                # DivX 5	MPEG-4 Visual
                # DivX 3 Low	MPEG-4 Visual
                # DivX 4	MPEG-4 Visual
                # Indeo 3	Indeo 3
                # MPEG-4 Visual	MPEG-4 Visual
                # AVI	XviD	MPEG-4 Visual

                hit = False
                if track.codecs_video == "" and track.video_format_list == "":
                    hit = True
                elif track.video_format_list == "Indeo 3":
                    hit = True
                elif track.codecs_video and track.codecs_video.startswith(
                        "DivX ") and track.video_format_list == "MPEG-4 Visual":
                    hit = True
                elif track.codecs_video == "MPEG-4 Visual" and track.video_format_list == "MPEG-4 Visual":
                    hit = True
                elif track.format == "AVI" and track.codecs_video == "XviD" and track.video_format_list == "MPEG-4 Visual":
                    hit = True

                if hit:
                    for foi in FIELDS_OF_INTEREST:
                        if foi in track.__dict__:
                            data.append(str(track.__dict__[foi]))
                        else:
                            data.append("")
                    row = DELIMITER.join(data)
                    output_stream.write(f"{row}\n")

    output_stream.flush()
    return 0


def main():
    """Run main program.

    :return: exit/return code
    """
    version_string = f"Find not Searchable Videos {__version__} ({__updated__})"
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
    logging.basicConfig(level=logging.WARNING if not DEBUG else logging.DEBUG, handlers=[handler])
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


if __name__ == "__main__":
    sys.exit(main())
