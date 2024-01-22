#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video_canonavi_rename.py - Canon AVI files renaming according to date-time-schema.

Canon AVI Files renaming based on "mastered date" metadata field.

Usage:
  video_canonavi_rename.py [options] <basepath>
  video_canonavi_rename.py -h | --help
  video_canonavi_rename.py --version

Arguments:
  basepath        Starting root path/directory for recursive scan.

Options:
  -h --help         Show this screen.
  -v --verbose      Be more verbose.
  --version         Show version.
"""
#
# LICENSE:
#
# Copyright (C) 2021-2022 by Ixtalo, ixtalo@gmail.com
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

import arrow
# pylint: disable-next=redefined-builtin
from docopt import docopt
from pymediainfo import MediaInfo

__appname__ = "canon_avi_datetime_rename"
__version__ = "1.2.3"
__date__ = "2021-03-31"
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


def run(basepath: str):
    """Run the main job.

    :param basepath: root directory for recursive scanning
    :return: exit/return code (for main())
    """
    if not os.path.isdir(basepath):
        raise NotADirectoryError(basepath)
    for root, _, files in os.walk(basepath):
        for filename in files:
            basename, ext = os.path.splitext(filename)
            if ext.lower() == ".avi":
                filepath = os.path.abspath(os.path.join(root, filename))
                logging.debug("processing: %s ...", filepath)

                # simple check if already done renaming
                if filename.endswith("].avi"):
                    logging.debug(
                        "Skipping because most probably already renamed: %s", filepath)
                    continue

                media_info = MediaInfo.parse(filepath)
                general_data = media_info.general_tracks[0]

                # local file date (should be equal to that from filesystem)
                file_datetime = arrow.get(
                    general_data.file_last_modification_date__local)

                # creation date from camera
                logging.debug(general_data.mastered_date)
                exif_datetime = None
                try:
                    exif_datetime = arrow.get(general_data.mastered_date)
                except arrow.parser.ParserError:
                    try:
                        # e.g. 'WED JAN 01 16:19:36 2014'
                        exif_datetime = arrow.get(
                            general_data.mastered_date, "ddd MMM DD HH:mm:ss YYYY")
                    except arrow.parser.ParserMatchError:
                        raise ValueError(
                            f"Could not parse mastered-date field, file:'{filepath}', metadata:'{general_data.mastered_date}'") \
                            from arrow.parser.ParserMatchError

                if not exif_datetime:
                    raise RuntimeError("Invalid state! No mastered-date!")

                # check that dates are almost similar
                delta = abs(exif_datetime - file_datetime).seconds
                if delta > 1 and delta not in (3599, 3600):
                    logging.warning(
                        "Problem with filesystem date and mastered-date! file:'%s', filesystem:%s, metadata:%s, delta:%s, seconds:%d",
                        filepath, file_datetime, exif_datetime, str(
                            exif_datetime - file_datetime), delta
                    )
                    continue

                filepath_new = os.path.join(
                    os.path.dirname(filepath),
                    f"{exif_datetime.format('YYYY-MM-DD_HHmmss')} [{basename}].avi"
                )

                print(f'mv "{filepath}" "{filepath_new}"')
    return 0


def main():
    """Run main program.

    :return: exit/return code
    """
    version_string = f"Canon AVI Files Date Time Renaming {__version__} ({__updated__})"
    arguments = docopt(__doc__, version=version_string)
    arg_basepath = arguments["<basepath>"]
    arg_verbose = arguments["--verbose"]

    # setup logging
    logging.basicConfig(level=logging.INFO if not DEBUG else logging.DEBUG,
                        stream=sys.stderr,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    if arg_verbose:
        logging.getLogger("").setLevel(logging.DEBUG)
    logging.info(version_string)
    logging.info("base path: %s", os.path.realpath(arg_basepath))
    return run(arg_basepath)


if __name__ == '__main__':
    sys.exit(main())
