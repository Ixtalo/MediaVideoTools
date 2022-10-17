#!python3
# -*- coding: utf-8 -*-
"""Various utility methods."""

import logging
from pathlib import Path


def get_file_size_mb(filepath: Path, round_decimals: int = 2) -> float:
    """Get the size of a file in MB.

    :param filepath: file path
    :param round_decimals: number of decimals to round to
    :return: size in MB, float number, rounded to second decimal
    """
    if filepath.is_symlink() and not filepath.exists():
        return -1
    try:
        return round(filepath.stat().st_size / 1024.0 / 1024.0, round_decimals)
    except OSError as ex:
        logging.exception(ex)
    return -1
