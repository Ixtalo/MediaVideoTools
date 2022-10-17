#!python3
# -*- coding: utf-8 -*-
"""Various MKV metadata utility methods."""
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
import argparse
import os
import logging
import subprocess
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict
from tempfile import mkstemp

MKV_METADATA_BASETAGNAME = "video_convert_x265"


def __get_path_to_mkvpropedit():
    cmd = shutil.which("mkvpropedit")
    if not cmd:
        raise RuntimeError("Could not find mkvpropedit in PATH!")
    return cmd


def mkv_produce_metadata(meta_standard: Dict[str, str],
                         meta_custom: Dict[str, object],
                         basetagname: str = MKV_METADATA_BASETAGNAME) -> ET.ElementTree:
    """Produce MKV metadata.

    :param meta_standard: key-value dictionary with field names according to IETF standard
    :param meta_custom: key-value dictionary with custom field names
    :param basetagname: the tags parent name
    :return: MKV metadata XML as xml.etree.Elementree
    """
    # https://datatracker.ietf.org/doc/html/draft-ietf-cellar-tags-04#section-6.15
    # https://gitlab.com/mbunkus/mkvtoolnix/-/blob/main/examples/matroskatags.dtd
    # https://www.ietf.org/archive/id/draft-ietf-cellar-matroska-06.html#name-tag-element
    # https://www.ietf.org/archive/id/draft-ietf-cellar-matroska-06.html#name-simpleblock-element

    def create_simple(node: ET.Element, key: str, value: object):
        simple = ET.SubElement(node, "Simple")
        ET.SubElement(simple, "Name").text = key
        ET.SubElement(simple, "String").text = str(value)

    def add_meta(node: ET.Element, meta: Dict[str, object]):
        for key, value in meta.items():
            create_simple(node, key, value)

    root = ET.Element("Tags")
    tree = ET.ElementTree(root)

    if meta_standard:
        tag0 = ET.SubElement(root, "Tag")
        add_meta(tag0, meta_standard)

    if meta_custom:
        tag_custom = ET.SubElement(root, "Tag")
        # targets = ET.SubElement(tag_custom, "Targets")
        # ET.SubElement(targets, "TargetTypeValue").text = "50"
        # ET.SubElement(targets, "TrackUID").text = "17166847858402652337"
        tag_custom_simple = ET.SubElement(tag_custom, "Simple")
        ET.SubElement(tag_custom_simple, "Name").text = basetagname
        add_meta(tag_custom_simple, meta_custom)

    return tree


def mkv_add_metadata_xml(filepath: Path, xml: ET.ElementTree,
                         keep_times: bool = False, keep_xml: bool = False):
    """Add XML metadata to an MKV file.

    :param filepath: Path to MKV file
    :param xml: XML ElementTree by mkv_produce_metadata()
    :param keep_times: restore file's access and modification times
    :param keep_xml: keep the temporary XML metadata file (input for mkvpropedit)
    """
    if not isinstance(filepath, Path):
        raise TypeError("filepath must be pathlib.Path")

    # NOTE: NamedTemporaryFile did not work on MS Windows !
    # with NamedTemporaryFile(prefix="metadata_", suffix=".xml", delete=True) as tmpf:
    #   ...
    tmpf_int, tmpfp = mkstemp(prefix="metadata_", suffix=".xml")

    logging.debug("writing metadata XML to temporary file: %s", tmpfp)
    xml_str = ET.tostring(xml.getroot(), encoding='utf8', method='xml')
    with open(tmpf_int, "wb") as fout:
        fout.write(xml_str)

    stats = filepath.stat()

    # run external command to add metadata
    # NOTE:
    # use mkvpropedit which just modifies metadata without creating a new file
    # (ffmpeg would create a whole new file...)
    cmd = __get_path_to_mkvpropedit()
    cmd_args = [cmd, f'{str(filepath.resolve())}', "--tags", f'global:{tmpfp}']
    logging.info("running: %s", " ".join(cmd_args))
    try:
        subprocess.run(cmd_args, check=True, shell=(os.name == "nt"))
    except subprocess.CalledProcessError as ex:
        logging.exception(ex)

    if keep_times:
        logging.debug("restoring file's original access and modification times ...")
        os.utime(filepath.resolve(), ns=(stats.st_atime_ns, stats.st_mtime_ns))

    if not keep_xml:
        # delete temporary file
        logging.debug("deleting temporary file: %s", tmpfp)
        os.unlink(tmpfp)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modify MKV metadata.")
    parser.add_argument("mkvfile", type=Path)
    parser.add_argument("--kv", action="append", required=True,
                        help="key-value metadata pairs, format 'key:value'")
    parser.add_argument("--keep-times", action="store_true",
                        help="restore file's access and modification times")
    parser.add_argument("--keep-xml", action="store_true",
                        help="keep the temporary XML metadata file (input for mkvpropedit)")
    parser.add_argument("--basetagname", type=str, default=MKV_METADATA_BASETAGNAME)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    logging.debug(args)

    mc = {}
    for kv in args.kv:
        k, v = kv.split(":", 1)
        mc[k] = v
    logging.debug("metadata: %s", mc)

    metadata_xml = mkv_produce_metadata(meta_custom=mc, meta_standard={}, basetagname=args.basetagname)
    mkv_add_metadata_xml(args.mkvfile, metadata_xml, keep_times=args.keep_times, keep_xml=args.keep_xml)
