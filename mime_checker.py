# -*- coding: utf-8 -*-
"""Utility/helper functions to detect the filetype."""
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
from pathlib import Path
import magic


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
    mimetype = magic.from_file(filepath.absolute(), mime=True)
    if "No such file or directory" in str(mimetype):
        raise FileNotFoundError(filepath.absolute())
    return mimetype


def __mime_mainclass_check(filepath: Path, expected_main_type: Path) -> bool:
    mimetype = get_mime_type(filepath)
    main_type = mimetype.split('/')[0]
    return main_type.lower() == expected_main_type.lower()


if __name__ == "__main__":
    import sys
    print(get_mime_type(Path(sys.argv[1])))
