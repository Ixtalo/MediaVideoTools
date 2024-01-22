#!pytest
# -*- coding: utf-8 -*-
"""Unit tests."""

# pylint: disable=missing-function-docstring, line-too-long, invalid-name

import xml.etree.ElementTree as ET

from mediavideotools.mkv_metadata import mkv_produce_metadata


def test_mkv_produce_metadata_empty():
    actual = mkv_produce_metadata(meta_standard={}, meta_custom={})
    assert isinstance(actual, ET.ElementTree)
    xml_str = ET.tostring(actual.getroot(), encoding='utf8', method='xml')
    assert xml_str == b"<?xml version='1.0' encoding='utf8'?>\n<Tags />"


def test_mkv_produce_metadata_onlystandardmetadata():
    meta_standard = {"foo1": "bar1", "foo2": 22}
    actual = mkv_produce_metadata(meta_standard=meta_standard, meta_custom={})
    assert isinstance(actual, ET.ElementTree)
    xml_str = ET.tostring(actual.getroot(), encoding='utf8', method='xml')
    assert xml_str == (b"<?xml version='1.0' encoding='utf8'?>\n<Tags><Tag><Simple><Name>foo1</Nam"
                       b'e><String>bar1</String></Simple><Simple><Name>foo2</Name><String>22</String>'
                       b'</Simple></Tag></Tags>')


def test_mkv_produce_metadata_onlycustommetadata():
    meta_custom = {"custom1": "bla1", "custom2": 222}
    actual = mkv_produce_metadata(meta_standard={}, meta_custom=meta_custom)
    assert isinstance(actual, ET.ElementTree)
    xml_str = ET.tostring(actual.getroot(), encoding='utf8', method='xml')
    assert xml_str == (b"<?xml version='1.0' encoding='utf8'?>\n<Tags><Tag><Simple><Name>video_con"
                       b'vert_x265</Name><Simple><Name>custom1</Name><String>bla1</String></Simple><S'
                       b'imple><Name>custom2</Name><String>222</String></Simple></Simple></Tag></Tags>')


def test_mkv_produce_metadata_ok():
    meta_standard = {"foo1": "bar1", "foo2": 22}
    meta_custom = {"custom1": "bla1", "custom2": 222}
    actual = mkv_produce_metadata(
        meta_standard=meta_standard, meta_custom=meta_custom)
    assert isinstance(actual, ET.ElementTree)
    xml_str = ET.tostring(actual.getroot(), encoding='utf8', method='xml')
    assert xml_str == (b"<?xml version='1.0' encoding='utf8'?>\n<Tags><Tag><Simple><Name>foo1</Nam"
                       b'e><String>bar1</String></Simple><Simple><Name>foo2</Name><String>22</String>'
                       b'</Simple></Tag><Tag><Simple><Name>video_convert_x265</Name><Simple><Name>cus'
                       b'tom1</Name><String>bla1</String></Simple><Simple><Name>custom2</Name><String'
                       b'>222</String></Simple></Simple></Tag></Tags>')
