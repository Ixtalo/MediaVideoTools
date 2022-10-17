#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rename_x265_remove_x264.py - Fix x265 MKV files with abundant "x264".

Print the renaming commands to fix MKV filenames which contain "x264" but are actually x265.

Usage:
  rename_x265_remove_x264.py [options] <directory>
  rename_x265_remove_x264.py -h | --help
  rename_x265_remove_x264.py --version

Arguments:
  directory         Starting root directory for recursive scan.

Options:
  -h --help         Show this screen.
  -l --list         Do not rename just print list of files.
  --no-color        No colored log output.
  -v --verbose      Be more verbose.
  --version         Show version.
"""
##
# LICENSE:
##
# Copyright (c) 2022 by Ixtalo, ixtalo@gmail.com
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

__appname__ = "rename_x265_remove_x264"
__version__ = "1.0.0"
__date__ = "2022-10-03"
__updated__ = "2022-10-03"
__author__ = "Ixtalo"
__email__ = "ixtalo@gmail.com"
__license__ = "AGPL-3.0+"
__status__ = "Production"

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 0):
    sys.stderr.write("Minimum required version is Python 3.x!\n")
    sys.exit(1)

# the file-type extension, e.g. '.mkv'
FILENAME_EXTENSION = ".mkv"
# marker for converted files
FILENAME_MARKER_X265 = "_x265"
# strings which should be removed
ABDUNDANT_STRINGS = (".x264-", ".h264-")


def run(rootdir: Path, print_list=False):
    """Run the main job.

    :param rootdir: root directory for recursive scanning
    :param print_list: just list files
    :return: exit/return code (for main())
    """
    # e.g., "_x265.mkv"
    marker = f"{FILENAME_MARKER_X265}{FILENAME_EXTENSION}"
    logging.debug("marker: %s", marker)

    for root, _, files in os.walk(rootdir):
        for filename in files:
            if not filename.lower().endswith(marker):
                # skip files which are not marked as x265 and MKV
                continue
            for abundant in ABDUNDANT_STRINGS:
                if abundant in filename:
                    filepath = Path(root, filename)
                    logging.debug("filepath: %s", filepath)

                    if print_list:
                        print(filepath.resolve())
                        continue

                    filename_new = filename.replace(abundant, ".")
                    filepath_new = Path(root, filename_new)
                    logging.debug("filepath_new: %s", filepath_new)
                    print(f'mv --no-clobber --verbose "{filepath.resolve()}" "{filepath_new.resolve()}"')

                    # only rename once
                    break

    return 0


def main():
    """Run main program entry.

    :return: exit/return code
    """
    version_string = f"Renamer Fix Abundant x264 {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_root = arguments["<directory>"]
    arg_list = arguments["--list"]
    arg_nocolor = arguments["--no-color"]
    arg_verbose = arguments["--verbose"]

    # setup logging
    handler = colorlog.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        colorlog.ColoredFormatter('%(log_color)s%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S', no_color=arg_nocolor))
    logging.basicConfig(level=logging.WARNING if not DEBUG else logging.DEBUG, handlers=[handler])
    if arg_verbose:
        logging.getLogger("").setLevel(logging.INFO)
    logging.info(version_string)

    root = Path(arg_root)
    logging.info("base path: %s", root.absolute())
    return run(root, arg_list)


if __name__ == '__main__':
    if DEBUG:
        # sys.argv.append('--verbose')
        pass
    if os.environ.get("PROFILE", "").lower() in ("true", "1", "yes"):
        import cProfile
        import pstats
        profile_filename = f"{__file__}.profile"
        cProfile.run('main()', profile_filename)
        with open(f'{profile_filename}.txt', 'w', encoding="utf8") as statsfp:
            profile_stats = pstats.Stats(profile_filename, stream=statsfp)
            stats = profile_stats.strip_dirs().sort_stats('cumulative')
            stats.print_stats()
        sys.exit(0)
    sys.exit(main())
