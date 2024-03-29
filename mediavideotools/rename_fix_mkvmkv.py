#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rename_fix_mkvmkv.py - Print rename commands to fix filenames with ...mkv_x265.mkv.

Print the renaming commands to fix filenames which have ".mkv_x265.mkv" to just "_x265.mkv"

Usage:
  rename_fix_mkvmkv.py [options] <directory>
  rename_fix_mkvmkv.py -h | --help
  rename_fix_mkvmkv.py --version

Arguments:
  directory         Starting root directory for recursive scan.

Options:
  -h --help         Show this screen.
  -l --list         Do not rename just print list of files.
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
from pathlib import Path

# pylint: disable-next=redefined-builtin
from docopt import docopt

__appname__ = "rename_fix_mkvmkv"
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


def run(rootdir: Path, print_list=False):
    """Run the main job.

    :param rootdir: root directory for recursive scanning
    :param print_list: just list files
    :return: exit/return code (for main())
    """
    # e.g., ".mkv_x265.mkv"
    marker = f"{FILENAME_EXTENSION}{FILENAME_MARKER_X265}{FILENAME_EXTENSION}"
    logging.debug("marker: %s", marker)

    for root, _, files in os.walk(rootdir):
        for filename in files:
            if filename.endswith(marker):
                filepath = Path(root, filename)
                logging.debug("filepath: %s", filepath)

                if print_list:
                    print(filepath.resolve())
                    continue

                filename_new = filename.replace(
                    marker, f"{FILENAME_MARKER_X265}{FILENAME_EXTENSION}")
                filepath_new = Path(root, filename_new)
                logging.debug("filepath_new: %s", filepath_new)
                print(
                    f'mv --no-clobber --verbose "{filepath.resolve()}" "{filepath_new.resolve()}"')

    return 0


def main():
    """Run main program entry.

    :return: exit/return code
    """
    version_string = f"Renamer Fix MkvMkv {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_root = arguments["<directory>"]
    arg_verbose = arguments["--verbose"]
    arg_list = arguments["--list"]

    # setup logging
    logging.basicConfig(level=logging.WARNING if not DEBUG else logging.DEBUG,
                        stream=sys.stderr,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    if arg_verbose:
        logging.getLogger("").setLevel(logging.INFO)
    logging.info(version_string)

    root = Path(arg_root)
    logging.info("base path: %s", root.absolute())
    return run(root, arg_list)


if __name__ == '__main__':
    sys.exit(main())
