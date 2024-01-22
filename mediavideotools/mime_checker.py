#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mime_checker.py - Utility/helper functions to detect the filetype.

Using MIMe or magic bytes detect the file's type.

Usage:
  mime_checker.py [options] <path>
  mime_checker.py -h | --help
  mime_checker.py --version

Arguments:
  path            Directory or file (full path).

Options:
  -h --help       Show this screen.
  --no-color      No colored log output.
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
import os
import sys
import json
import logging
from pathlib import Path

import colorlog
import magic  # python-magic, https://pypi.org/project/python-magic/
from docopt import docopt

__appname__ = "mime_checker"
__version__ = "1.3.0"
__date__ = "2021-09-15"
__updated__ = "2023-06-24"
__author__ = "Ixtalo"
__email__ = "ixtalo@gmail.com"
__license__ = "AGPL-3.0+"
__status__ = "Production"

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 9):
    sys.stderr.write("Minimum required version is Python 3.9!\n")
    sys.exit(1)


def is_mediafile(filepath: Path) -> bool:
    """Detect if the specified file is a media-type using MIME type and libmagic.

    :param filepath: media filename and path
    :return: boolean true if file has video MIME type or relevant filename extension.
    """
    return is_video(filepath) or is_audio(filepath)


def is_video(filepath: Path) -> bool:
    """Detect if the specified file is a video-type using MIME type and libmagic.

    :param filepath: media filename and path
    :return: boolean true if file has video MIME type or relevant filename extension.
    """
    if not isinstance(filepath, Path):
        raise TypeError("filepath must be pathlib.Path")
    if filepath.suffix.lower() == ".sub":
        # special handling for .sub files which are detected as MIME "video/mpeg"
        return False
    if filepath.suffix.lower() == ".mts":
        # special handling for .mts video files, detected as "application/octet-stream"
        return True
    return __mime_mainclass_check(filepath, "video")


def is_audio(filepath: Path) -> bool:
    """Check if file is an audiofile, uses filename and MIME type heuristics.

    :param filepath: media filename and path
    :return: boolean true if file has audio MIME type or relevant filename extension.
    """
    return __mime_mainclass_check(filepath, "audio")


def get_mime_type(filepath: Path) -> str:
    """Get the MIME type string, e.g., 'test/plain'.

    :param filepath: filename and path
    :return: MIME type string
    """
    if not isinstance(filepath, Path):
        raise TypeError("filepath must be pathlib.Path")
    # open file in binary mode
    # raises FileNotFoundException or IOError if the file does not exist
    # raises OSError(40, 'Too many levels of symbolic links') for symlink loop
    #
    # NOTE / ATTENTION:
    # magic.from_file(...) does have Unicode decoding problems on MS Windows
    # (use magic.from_buffer() instead!)
    #
    result = magic.from_buffer(filepath.open(mode="rb").read(1024), mime=True)
    # return MIME type (e.g., 'video/x-matroska')
    return result


def __mime_mainclass_check(filepath: Path, expected_main_type: Path) -> bool:
    mimetype = get_mime_type(filepath)
    main_type = mimetype.split('/')[0]
    return main_type.lower() == expected_main_type.lower()


def main():
    """Run the main program.

    :return: exit/return code
    """
    version_string = f"MIME Type Checker {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_path = arguments["<path>"]
    arg_verbose = arguments["--verbose"]
    arg_nocolor = arguments["--no-color"]

    # setup logging
    handler = colorlog.StreamHandler(stream=sys.stderr)
    handler.setFormatter(
        colorlog.ColoredFormatter('%(log_color)s%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S', no_color=arg_nocolor))
    logging.basicConfig(
        level=logging.INFO if not DEBUG else logging.DEBUG, handlers=[handler])

    if arg_verbose:
        logging.getLogger("").setLevel(logging.DEBUG)

    logging.info(version_string)
    logging.debug("arguments: %s", arguments)

    path = Path(arg_path)
    logging.info("path: %s", path.absolute())

    def log_infos(filepath: Path):
        infos = {
            "mime_type": get_mime_type(filepath),
            "is_mediafile": is_mediafile(filepath),
            "is_video": is_video(filepath),
            "is_audio": is_audio(filepath)
        }
        logging.info("infos for '%s': %s",
                     filepath.absolute(), json.dumps(infos))

    if not path.exists():
        raise FileNotFoundError(path.resolve())
    elif path.is_dir() and not path.is_file():
        for root, _, files in os.walk(path):
            for file in files:
                try:
                    log_infos(Path(root, file))
                except (OSError, FileNotFoundError) as ex:
                    logging.exception(ex, stack_info=False)
                except Exception as ex:
                    logging.exception(ex, stack_info=False)
    elif path.is_file():
        log_infos(path)
    else:
        raise NotImplementedError("Unsupported file/path type!")

    return 0


if __name__ == '__main__':
    sys.exit(main())
