#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video_language_check.py - Check if filename contains correct [LANG] tag.

Use MediaInfo to get the list of all audio languages for a video file
and check if the correct [LANGUAGE] tag is in the folder's name.

Usage:
  video_language_check.py [options] <directory>
  video_language_check.py -h | --help
  video_language_check.py --version

Arguments:
  directory       Starting root directory for recursive scan.

Options:
  -h --help       Show this screen.
  -j --json       JSON output, mapping filepath->missingLangCodes.
  --no-color      No colored log output.
  --no-full-path  Do not consider the full path but only single parent dirname.
  -v --verbose    Be more verbose (>= info level).
  --version       Show version.
"""
import json
import logging
import os
import re
#
# LICENSE:
#
# Copyright (C) 2020-2022 by Ixtalo, ixtalo@gmail.com
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
import sys
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

__version__ = "1.7.3"
__date__ = "2020-10-04"
__updated__ = "2022-10-17"
__author__ = "Ixtalo"
__license__ = "AGPL-3.0+"
__email__ = "ixtalo@gmail.com"
__status__ = "Production"

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 0):
    sys.stderr.write("Minimum required version is Python 3.x!\n")
    sys.exit(1)

IGNORE_MARKER = "[__]"


def __get_path_languages(filepath: Path, use_full_path: bool = True) -> set:
    assert len(
        filepath.parts) > 1, "filepath must have filename and parent directory!"
    dirpath = filepath.parent  # full path
    dirname = filepath.parts[-2]  # just the file's parent directory name
    # find 2-letter language codes, e.g., ['DE', 'EN']
    path_languages = re.findall(
        r"\[([A-Z]{2})\]", str(dirpath) if use_full_path else str(dirname))
    return set(path_languages)


def __get_missing_in_path(path_languages: set, track_languages: set) -> set:
    return track_languages - path_languages


def __get_toomuch_in_path(path_languages: set, track_languages: set) -> set:
    return path_languages - track_languages


def get_track_languages_for_file(filepath: Path) -> set:
    """Get the track languages from a video file's metadata.

    :param filepath: file path of the video file to check
    :return: List of upper-case language codes, None if not a video file.
    """
    if not isinstance(filepath, Path):
        raise TypeError("filepath must be pathlib.Path!")
    if filepath.is_dir():
        raise IsADirectoryError(
            "filepath must be a valid file path, not a directory!")
    if not filepath.exists():
        raise FileNotFoundError(filepath)
    if not is_video(filepath):
        return None
    # use pymediainfo to parse the video file
    media_info = MediaInfo.parse(filepath)
    # loop over all tracks (video, audio, text, ...)
    result = set()
    for track in media_info.audio_tracks:
        language = track.language
        if language is None:  # language could be None!
            continue
        # some data harmonization...
        lang_lo = language.lower()
        if lang_lo == "deutsch":
            language = "de"
        elif lang_lo in ('eng', "english", "english[eng]"):
            language = "en"
        elif lang_lo.startswith("commentary"):
            continue
        result.add(language.upper())
    return result


def get_track_languages_for_files(paths: list[Path]) -> set:
    """Collect all track languages in the files.

    :param paths: list of complete file paths
    :return: set of collected track languages
    """
    files_languages = set()
    for filepath in paths:
        if filepath.is_symlink() and not filepath.exists():
            logging.warning("skipping broken symlink: %s", filepath.absolute())
            continue
        track_languages = get_track_languages_for_file(filepath)
        if not track_languages:
            # e.g., not a video file
            continue
        logging.debug("%s in '%s'", ",".join(
            list(track_languages)), filepath.name)
        files_languages = files_languages.union(track_languages)
    return files_languages


def scan(rootdir: Path, use_full_path: bool = True):
    """Recursive directory scan.

    :param rootdir: root directory, starting point
    :param use_full_path: True: consider the full path, False: only single parent dirname
    :return dictionary with filepath->{missing_in_path: [...], toomuch_in_path: [...]}
    """
    assert isinstance(rootdir, Path)
    if not rootdir.is_dir():
        raise NotADirectoryError(rootdir)

    result = {}
    for root, _, files in sorted(os.walk(rootdir.resolve())):
        if IGNORE_MARKER in root:
            logging.info("ignoring (IGNORE_MARKER): %s", root)
            continue
        if not files:
            continue

        logging.info("processing directory: %s", root)

        # from the path name extract the languages, e.g., "[DE][EN]"
        root_languages = __get_path_languages(
            Path(root, "dummy"), use_full_path=use_full_path)
        logging.debug("root_languages: %s", root_languages)

        # construct list of complete paths (root + filenames)
        filespaths = [Path(root, filename) for filename in files]

        # collect all track languages in the files
        files_languages = get_track_languages_for_files(filespaths)

        # path relative to the methods' rootdir
        relative_path = Path(root).relative_to(rootdir.resolve())

        # collect all problems, i.e., missing or surplus languages
        problems = {}
        if files_languages:
            missing = __get_missing_in_path(root_languages, files_languages)
            if missing:
                logging.warning("%s missing in path: %s",
                                ",".join(missing), relative_path)
                problems["missing_in_path"] = sorted(list(missing))
            toomuch = __get_toomuch_in_path(root_languages, files_languages)
            if toomuch:
                logging.warning("%s too much in path: %s",
                                ",".join(toomuch), relative_path)
                problems["toomuch_in_path"] = sorted(list(toomuch))

        if problems:
            result[str(relative_path)] = problems
        else:
            logging.debug("OK: '%s', languages: %s",
                          relative_path, ",".join(files_languages))

    return result


def main():
    """Run main program.

    :return: exit/return code
    """
    version_string = f"Video Filename Language Check {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_root = arguments["<directory>"]
    arg_verbose = arguments["--verbose"]
    arg_json_output = arguments["--json"]
    arg_no_full_path = arguments["--no-full-path"]
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

    root = Path(arg_root)
    logging.info("base path: %s", root.resolve())
    result = scan(root, use_full_path=not arg_no_full_path)
    if arg_json_output:
        print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
