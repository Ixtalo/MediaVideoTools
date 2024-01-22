#!/usr/bin/python
# -*- coding: utf-8 -*-
"""media_stats.py - Collect statistics on media files, e.g. durations.

Recursively collects statistics (e.g., duration) on video and
audio media files. The output is CSV.

Usage:
  media_stats.py [options] <directory> [<output.csv>]
  media_stats.py -h | --help
  media_stats.py --version

Arguments:
  directory         The root directory to start recursive scanning.
  output.csv        Filename of output CSV (delimiter ";"), or STDOUT.

Options:
  -f --force        Force overwrite of existing output files.
  -h --help         Show this screen.
  --no-color        No colored log output.
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
import subprocess
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
    from mime_checker import is_mediafile
except ModuleNotFoundError:
    # for pytest a relative import is needed
    from .mime_checker import is_mediafile

__version__ = "1.5.2"
__date__ = "2022-03-24"
__updated__ = "2022-10-03"
__author__ = "Ixtalo"
__license__ = 'AGPL-3.0+'
__email__ = "ixtalo@gmail.com"
__status__ = "Production"

# CSV delimiter
DELIMITER = ";"
# number of rounding digits for CSV
NDIGITS = 3

DEBUG = bool(os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"))

# check for Python3
if sys.version_info < (3, 0):
    sys.stderr.write('Minimum required version is Python 3.x!\n')
    sys.exit(1)


class MyMediaInfo:
    """My own data structure for media files information."""

    file_size = None
    duration = None
    bit_rate = None

    def __init__(self, path: Path):
        """Media information data structure."""
        if not isinstance(path, Path):
            raise TypeError("path must be type pathlib.Path!")
        self._path = path

    @property
    def path(self) -> Path:
        """File path."""
        return self._path


class DirectoryMediaStats:
    """Collection of media files information for a directory."""

    def __init__(self, path: Path):
        """Directory media information."""
        if not isinstance(path, Path):
            raise TypeError("path must be type pathlib.Path!")
        self._path = path
        self._num_entries = 0  # >0 when a new entry is added
        self._cum_filesize_bytes = 0
        self._cum_duration_seconds = 0
        self._mean_bit_rate = 0

    @property
    def path(self) -> Path:
        """Directory path."""
        return self._path

    @path.setter
    def path(self, value: Path):
        """Set directory path value."""
        if not isinstance(value, Path):
            raise TypeError("value must be type pathlib.Path!")
        self._path = value

    @property
    def level(self) -> int:
        """Path depth/level."""
        return len(self.path.parents)

    @property
    def num_entries(self) -> int:
        """Get the number of accounted entries."""
        return self._num_entries

    @property
    def cum_filesize_bytes(self) -> int:
        """Cumulated file sizes, in bytes."""
        return self._cum_filesize_bytes

    @property
    def cum_duration_seconds(self) -> int:
        """Cumulated media files durations, in seconds."""
        return self._cum_duration_seconds

    @property
    def mean_bit_rate(self):
        """Mean (average) bit rate of the media files."""
        return self._mean_bit_rate

    @staticmethod
    def get_str_fields_names():
        """Ordered list of property names, e.g., for CSV output."""
        properties_names = (
            "path",
            "level",
            "num_entries",
            "cum_filesize_bytes",
            "cum_duration_seconds",
            "mean_bit_rate"
        )
        return properties_names

    def __str__(self):
        """Get the string representation, as CSV."""
        if not (self.path and self.num_entries > 0):
            return ""
        values = []
        for name in self.get_str_fields_names():
            value = getattr(self, name)
            if isinstance(value, float):
                value = round(value, NDIGITS)
            elif isinstance(value, Path):
                # adjust as relative path to the current working directory
                value = f'"{value.resolve().relative_to(os.getcwd())}"'
            elif isinstance(value, str):
                # value = f'"{value}"'
                raise RuntimeError(
                    "Programming error! Everything should be Path, not string...")
            values.append(str(value))
        return DELIMITER.join(values)

    def __add__(self, other):
        """Adding other elements."""
        if isinstance(other, MyMediaInfo):
            if other.duration is None:
                logging.warning(
                    "Skipping file with invalid duration: %s", other.path)
                return self
            self._num_entries += 1
            self._cum_filesize_bytes += other.file_size
            self._cum_duration_seconds += other.duration
            if other.bit_rate:
                # only update if there's actually a valid (not None) bit_rate
                self._mean_bit_rate = (self._mean_bit_rate * (
                    self._num_entries - 1) + other.bit_rate) / self._num_entries
        elif isinstance(other, DirectoryMediaStats):
            if other._cum_filesize_bytes == 0 or other.cum_duration_seconds == 0:
                # skip directories which do not have accountable media files
                return self
            self._num_entries += 1
            self._cum_filesize_bytes += other.cum_filesize_bytes
            self._cum_duration_seconds += other.cum_duration_seconds
            self._mean_bit_rate = (self._mean_bit_rate * (
                self._num_entries - 1) + other._mean_bit_rate) / self.num_entries
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'")
        # limit decimal places
        self._mean_bit_rate = round(self._mean_bit_rate, 1)
        return self


def get_media_file_info(filepath: Path) -> MyMediaInfo:
    """Get information for a media file.

    :param filepath: full filename and path
    :return: media information
    """
    if not isinstance(filepath, Path):
        raise TypeError("filepath must be type pathlib.Path!")

    media_info = MediaInfo.parse(filepath, encoding_errors="replace")
    mmi = MyMediaInfo(filepath)
    gt0 = media_info.general_tracks[0]
    # duration is in ms
    mmi.duration = gt0.duration / 1000.0 if gt0.duration is not None else None
    mmi.file_size = gt0.file_size if gt0.file_size is not None else None
    mmi.bit_rate = gt0.overall_bit_rate

    if mmi.duration is None:
        logging.warning(
            "MediaInfo detection problems, trying with ffprobe for: %s", filepath)
        # fallback to ffprobe
        cmd_args = ['ffprobe', '-i', filepath, '-show_entries',
                    'format=duration', '-v', 'warning', '-of', 'csv=p=0']
        logging.debug("ffprobe cmd: %s", cmd_args)
        try:
            proc = subprocess.run(
                cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            logging.debug(proc)
            stdout = proc.stdout.strip()
            if stdout:
                mmi.duration = float(proc.stdout)
            if proc.stderr:
                logging.warning("ffprobe warning: %s",
                                proc.stderr.decode().replace(os.linesep, ""))
        except FileNotFoundError as ex:
            logging.error("Could not run ffprobe command: %s", ex)
        except OSError as ex:
            logging.exception(ex)
        except ValueError as ex:
            logging.exception(ex)
        except subprocess.CalledProcessError as ex:
            logging.exception(ex, exc_info=False)

    return mmi


def _scan_recursive(root: Path, output_stream) -> DirectoryMediaStats:
    dirstats = DirectoryMediaStats(root)
    with os.scandir(root) as path_iterator:
        for entry in path_iterator:
            try:
                isdir = entry.is_dir(follow_symlinks=False)
            except OSError as ex:
                # can raise OSError, such as PermissionError, or broken links
                logging.exception(ex)
                continue
            if isdir:
                try:
                    dms = _scan_recursive(Path(entry.path), output_stream)
                    if dms.num_entries > 0:
                        output_stream.write("%s\n" % dms)
                        dirstats.path = root  # parent path!
                        dirstats += dms
                except RuntimeError as ex:
                    if str(ex).startswith("Symlink loop from "):
                        # OSError(40, 'Too many levels of symbolic links'), Symlink loop
                        pass
                    else:
                        raise ex
            else:
                try:
                    if not is_mediafile(Path(entry.path)):
                        continue
                except FileNotFoundError as ex:
                    logging.exception(ex, exc_info=False)
                    continue
                except OSError as ex:
                    logging.exception(ex, exc_info=False)
                    continue
                mmi = get_media_file_info(Path(entry.path))
                dirstats += mmi
    return dirstats


def scan(root: Path, output_stream) -> int:
    """Run the main job.

    :param root: root directory for recursive scanning
    :param output_stream: where to write the results
    :return: exit/return code (for main())
    """
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    header_fields = DirectoryMediaStats.get_str_fields_names()
    output_stream.write("%s\n" % DELIMITER.join(header_fields))
    total = _scan_recursive(root, output_stream)
    output_stream.write("%s\n" % total)
    output_stream.flush()
    return 0


def main():
    """Run the main program entry.

    :return: exit/return code
    """
    version_string = f"Media Files Statistics {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_root = arguments["<directory>"]
    arg_output = arguments["<output.csv>"]
    arg_verbose = arguments["--verbose"]
    arg_force = arguments["--force"]
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

    if arg_output is not None:
        if not arg_force and os.path.exists(arg_output):
            raise FileExistsError(arg_output)
        # pylint: disable-next=consider-using-with
        out = open(arg_output, "w", encoding="utf8")
    else:
        out = sys.stdout

    root = Path(arg_root)
    logging.info("base path: %s", root.absolute())
    logging.info("output: %s", out)
    return scan(root, out)


if __name__ == '__main__':
    sys.exit(main())
