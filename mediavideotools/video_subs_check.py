#!/usr/bin/python
# -*- coding: utf-8 -*-
"""video_subs_check.py - Check matching of Subs-folders and included filenames.

Problem statement:
Sometimes, the filenames in the "./Subs/" sub-folder do not match
the filename of the main video file.
This is a problem, because movie players (e.g., VLC) expect the filenames
in "./Subs/" to be the same as of the movie file.

Solution approach:
This program checks "./Subs/*" for matching filenames.

Usage:
  video_subs_check.py [options] <directory>
  video_subs_check.py -h | --help
  video_subs_check.py --version

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
# Copyright (C) 2023 by Ixtalo, ixtalo@gmail.com
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
##
import glob
import logging
import os
import re
import sys
# pylint: disable-next=redefined-builtin
from codecs import open
from fnmatch import fnmatch
from pathlib import Path

import colorlog
from docopt import docopt

__version__ = "1.0.0"
__date__ = "2023-07-03"
__updated__ = "2023-07-03"
__author__ = "Ixtalo"
__license__ = 'AGPL-3.0+'
__email__ = "ixtalo@gmail.com"
__status__ = "Production"

MOVIE_FILES_PATTERNS = ["*.mkv", "*.avi", "*.mp4"]

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

if sys.version_info < (3, 9):
    sys.stderr.write('Minimum required version is Python 3.9!\n')
    sys.exit(1)


def scan(rootdir: Path, output_stream=sys.stdout):
    """Recursive scanning for all media files.

    :param rootdir: starting base path
    :param output_stream: output stream, defaults to STDOUT
    """
    if not rootdir.is_dir():
        raise NotADirectoryError(rootdir)

    curdir = Path(os.curdir).resolve()
    regex = re.compile(r"^(.+?)[-_.](forced|[a-z]{2,3})(?:[-_.]forced)?$")

    for root, dirs, files in os.walk(rootdir.resolve()):
        dirs.sort()
        root_path = Path(root).resolve()

        # check for a "./Subs/" folder
        if not ("subs" in dirs or "Subs" in dirs):
            # irrelevant -> skip/continue
            continue

        subs_dir = Path(root).joinpath("subs")
        if not subs_dir.exists():
            subs_dir = Path(root).joinpath("Subs")
            if not subs_dir.exists():
                raise RuntimeError(
                    "Invalid program state - this should never happen!")

        # collect all .sub files
        # NOTE: glob.glob(..., root_dir=...) is only after Python 3.10,
        # for lower versions use os.chdir instead
        os.chdir(subs_dir)
        subs_files = glob.glob("*.sub")
        subs_files += glob.glob("*.srt")
        logging.debug("subs_dir: '%s' --> files: #%d",
                      subs_dir.resolve(), len(subs_files))

        # gather just the basenames, i.e., without language code and without extension
        subs_basenames = set()
        for subs_file in subs_files:
            basename = regex.sub(r"\1", Path(subs_file).stem, 1)
            subs_basenames.add(basename)

        logging.debug("subs_basenames: %s", subs_basenames)

        if not subs_basenames:
            logging.warning("No .sub files in '%s'! Skipping.", subs_dir)
            continue

        # collect movie basenames (without extension)
        movies_basenames = set()
        for pattern in MOVIE_FILES_PATTERNS:
            assert "*" in pattern, "Invalid globbing pattern!"
            for file in files:
                if fnmatch(file, pattern):
                    basename = Path(file).stem
                    movies_basenames.add(basename)

        logging.debug("movies: %s; subtitles: %s",
                      movies_basenames, subs_basenames)

        # check if the filenames in the upper folder are according to the .sub basenames
        # (A + B) - (A - B)
        invalid = movies_basenames.union(
            subs_basenames) - movies_basenames.intersection(subs_basenames)
        if invalid:
            logging.warning(
                "Invalid subtitle files found for '%s': %s", root_path, invalid)
            output_stream.write(f"{str(root_path)}\n")

    # back to its original
    os.chdir(curdir)

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
