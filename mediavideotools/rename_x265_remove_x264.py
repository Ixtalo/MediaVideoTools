#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rename_x265_remove_x264.py - Fix x265 MKV files with abundant "x264".

Print the renaming commands to fix MKV filenames which
contain "x264" but are actually x265.

Example:
    xyz_x264.mkv --> xyz_x265.mkv
    ./x265_abundant_x264/foo.h264-bar_x265.mkv --> ./x265_abundant_x264/foo.bar_x265.mkv

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
#
# LICENSE:
#
# Copyright (C) 2022-2023 by Ixtalo, ixtalo@gmail.com
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
import colorlog
from docopt import docopt

__appname__ = "rename_x265_remove_x264"
__version__ = "1.1.0"
__date__ = "2022-10-03"
__updated__ = "2023-07-06"
__author__ = "Ixtalo"
__email__ = "ixtalo@gmail.com"
__license__ = "AGPL-3.0+"
__status__ = "Production"

# the file-type extension, e.g. '.mkv'
FILENAME_EXTENSION = ".mkv"
# marker for converted files
FILENAME_MARKER_X265 = "_x265"
# strings which should be replaced
STRINGS_TO_REPLACE = (".x264-", ".h264-")
REPLACE_STRING = "."

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

if sys.version_info < (3, 9):
    sys.stderr.write("Minimum required version is Python 3.9!\n")
    sys.exit(1)


def _handle_filepath(filepath: Path) -> Path | None:
    """Handle single files, i.e., erase/replace strings in filenames."""
    assert isinstance(filepath, Path)

    if not any([e in filepath.stem for e in STRINGS_TO_REPLACE]):
        # no string-to-erase in fhe filepath
        return None

    filepath_new = filepath
    for erase in STRINGS_TO_REPLACE:
        stem_new = filepath_new.stem.replace(erase, REPLACE_STRING)
        filepath_new = filepath_new.with_stem(stem_new)

    return filepath_new


def _handle_files(files: list[Path]) -> dict[Path, Path]:
    """Handle (process) list of files."""
    result = {}
    for filepath in files:
        filepath_new = _handle_filepath(filepath)
        if filepath_new:
            result[filepath] = filepath_new
    # return: old-filepath --> new-filepath
    return result


def _get_marker() -> str:
    return f"{FILENAME_MARKER_X265}{FILENAME_EXTENSION}"


def scan(rootdir: Path) -> list[Path]:
    """Scan for relevant MKV file candidates, i.e., files with marker."""
    # e.g., "_x265.mkv"
    marker = _get_marker()
    logging.debug(
        "scanning for relevant files with markers (marker: '%s') ...", marker)

    candidates = []
    for root, dirs, files in os.walk(rootdir):
        dirs.sort()
        files.sort()
        for filename in files:
            if not filename.lower().endswith(marker):
                # skip files not marked as x265 and MKV
                continue
            filepath = Path(root, filename)
            logging.debug("candidate: %s", filepath)
            candidates.append(filepath)
    return candidates


def run(rootdir: Path, print_list=False, output_stream=sys.stdout):
    """Run the main job.

    :param rootdir: root directory for recursive scanning
    :param print_list: just list files
    :param output_stream: target stream to write output to
    :return: exit/return code (for main())
    """
    candidates = scan(rootdir)
    logging.debug("#candidates: %d", len(candidates))

    if not candidates:
        logging.warning("No file candidates found.")
        return -1

    files = _handle_files(candidates)
    logging.debug("#processed: %d", len(files))

    if not files:
        logging.warning("No relevant files to process.")
        return -2

    for old, new in files.items():
        if print_list:
            output = str(old.resolve())
        else:
            output = f'mv --no-clobber --verbose "{old.resolve()}" "{new.resolve()}"'
        output_stream.write(output)
        output_stream.write("\n")

    output_stream.flush()
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
    logging.basicConfig(
        level=logging.WARNING if not DEBUG else logging.DEBUG, handlers=[handler])
    if arg_verbose:
        logging.getLogger("").setLevel(logging.INFO)
    logging.info(version_string)

    root = Path(arg_root)
    logging.info("base path: %s", root.absolute())
    return run(root, arg_list)


if __name__ == '__main__':
    sys.exit(main())
