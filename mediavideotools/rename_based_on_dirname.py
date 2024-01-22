#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rename_based_on_dirname.py - Rename MKV files based on the parent's folder name.

Sometimes MKV video files are just named "funxd.mkv", without any semantics.
However, the semantic could be in the file's folder name.
The idea is to rename the MKV file based on the folder name.

Usage:
  rename_based_on_dirname.py [options] <directory> [<output-file>]
  rename_based_on_dirname.py -h | --help
  rename_based_on_dirname.py --version

Arguments:
  directory         Starting root directory for recursive scan.
  output-file       Filename of output, or STDOUT.

Options:
  -p --pattern=X    Globbing pattern [default: *.mkv].
  -f --force        Force overwrite of existing output files.
  -h --help         Show this screen.
  --no-color        No colored log output.
  -v --verbose      Be more verbose.
  --version         Show version.
"""
#
# LICENSE:
#
# Copyright (C) 2015-2023 by Ixtalo, ixtalo@gmail.com
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

import colorlog
from docopt import docopt

__appname__ = "rename_based_on_dirname"
__version__ = "1.2.0"
__date__ = "2022-08-19"
__updated__ = "2023-07-03"
__author__ = "Ixtalo"
__email__ = "ixtalo@gmail.com"
__license__ = "AGPL-3.0+"
__status__ = "Production"

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 0):
    sys.stderr.write("Minimum required version is Python 3.x!\n")
    sys.exit(1)


def _get_dst(src: Path):
    dirname = src.parts[-2]
    return src.with_stem(dirname)


def _is_os_windows():
    return os.name == "nt"


def build_renaming_commands(src: Path, dst: Path, output_stream=sys.stdout):
    """Build renaming commands.

    :param src: source/original file path
    :param dst: destination/new file path
    :param output_stream: stream where to print the commands to
    """
    if not src or not dst:
        return
    if src == dst:
        logging.info(
            "Identical names, no renaming needed for: %s", src.absolute())
        return
    if dst.exists():
        logging.warning(
            "Renaming target already exists - do nothing! (%s)", dst.absolute())
        return
    if _is_os_windows():
        output_stream.write("REM ---------------------------------\n")
        # MS Windows rename command only accepts new filename, no other drive or path!
        output_stream.write(f'rename "{src}" "{dst.name}"\n')
    else:
        output_stream.write("## ---------------------------------\n")
        output_stream.write(f'mv --no-clobber "{src}" "{dst}"\n')


def nfo_renaming(src: Path):
    """.nfo file renaming.

    :param src: media file path according to which a matching .nfo is constructed
    """
    assert isinstance(src, Path)
    nfo_filepath = src.with_suffix(".nfo")
    if not nfo_filepath.exists():
        # no matching .nfo file => do nothing
        return None, None
    dirname = src.parts[-2]
    assert dirname != "/"
    nfo_filepath_new = nfo_filepath.with_name(dirname).with_suffix(".nfo")
    return nfo_filepath, nfo_filepath_new


def run(rootdir: Path, output_stream=sys.stdout, pattern: str = "*.mkv"):
    """Run the main job.

    :param rootdir: root directory for recursive scanning
    :param output_stream: where to write the results
    :param pattern: globbing pattern
    :return: exit/return code (for main())
    """
    if not rootdir.is_dir():
        raise NotADirectoryError(f"{rootdir} is not a directory!")

    logging.debug("globbing pattern: %s", pattern)

    for root, dirs, _ in os.walk(str(rootdir.resolve())):
        for dirname in dirs:
            dirpath = Path(root, dirname)
            logging.debug("dirpath: %s", dirpath)

            for src in dirpath.glob(pattern):
                # use the dirpath as the new src
                dst = _get_dst(src)
                logging.debug("src: %s", src)
                logging.debug("dst: %s", dst)

                if len(str(dst)) <= len(str(src)):
                    logging.warning("The new name must be longer! %s (%d) --> %s (%d)",
                                    src.name, len(src.name), dst.name, len(dst.name))
                    continue

                build_renaming_commands(src, dst, output_stream)

                # renaming for .nfo files
                nfo_filepath, nfo_filepath_new = nfo_renaming(src)
                build_renaming_commands(
                    nfo_filepath, nfo_filepath_new, output_stream)

                # only rename once, only first file in directory
                continue

    return 0


def main():
    """Run program's main method.

    :return: exit/return code
    """
    version_string = f"rename-based-on-dirname {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    # print(arguments); return
    arg_root = arguments["<directory>"]
    arg_output = arguments["<output-file>"]
    arg_verbose = arguments["--verbose"]
    arg_force = arguments["--force"]
    arg_nocolor = arguments["--no-color"]
    arg_pattern = arguments["--pattern"]

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

    if arg_output is not None:
        if not arg_force and os.path.exists(arg_output):
            raise FileExistsError(arg_output)
        # pylint: disable-next=consider-using-with
        out = open(arg_output, "w", encoding="utf8")
    else:
        out = sys.stdout

    root = Path(arg_root)
    logging.info("root: %s", root.absolute())
    logging.info("output: %s", out)
    return run(root, out, arg_pattern)


if __name__ == '__main__':
    sys.exit(main())
