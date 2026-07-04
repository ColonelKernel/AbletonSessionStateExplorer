"""Tests for the cautious Cubase Track Archive inspector."""

import gzip

from ableton_session_state_explorer.track_archive_inspector import (
    TRACK_ARCHIVE_DISCLAIMER,
    inspect_track_archive_bytes,
)

SYNTHETIC_ARCHIVE = b"""<?xml version="1.0" encoding="utf-8"?>
<tracklist2>
  <list name="track" type="obj">
    <obj class="MAudioTrackEvent" ID="1">
      <obj class="MAudioTrack" name="Track Device" ID="2">
        <list name="InsertPlugins" type="obj">
          <obj class="MInsertPluginSlot" ID="3">
            <obj class="MPluginData" ID="4"/>
          </obj>
        </list>
      </obj>
    </obj>
    <obj class="MAudioTrackEvent" ID="5">
      <obj class="MAudioTrack" name="Track Device" ID="6"/>
    </obj>
  </list>
  <list name="events" type="obj">
    <obj class="MAudioPartEvent" ID="7"/>
  </list>
</tracklist2>
"""


def test_synthetic_archive_surface_counts():
    report = inspect_track_archive_bytes(SYNTHETIC_ARCHIVE, "tracks.xml")
    assert report["xml_parsed"] is True
    assert report["root_tag"] == "tracklist2"
    assert report["track_like_elements"] >= 4  # 2 events + 2 tracks by class
    assert report["event_like_elements"] >= 3
    assert report["plugin_like_elements"] >= 2
    assert "MAudioTrack" in report["class_frequency"]
    assert TRACK_ARCHIVE_DISCLAIMER in report["warnings"]


def test_gzipped_archive_is_decompressed():
    report = inspect_track_archive_bytes(gzip.compress(SYNTHETIC_ARCHIVE))
    assert report["xml_parsed"] is True
    assert report["root_tag"] == "tracklist2"


def test_non_xml_input_degrades_to_warning():
    report = inspect_track_archive_bytes(b"\x00\x01definitely not xml")
    assert report["xml_parsed"] is False
    assert any("cannot inspect" in w for w in report["warnings"])


def test_broken_xml_degrades_to_warning():
    report = inspect_track_archive_bytes(b"<tracklist2><unclosed>")
    assert report["xml_parsed"] is False
    assert any("XML parsing failed" in w for w in report["warnings"])


def test_xml_without_classes_gets_flagged():
    report = inspect_track_archive_bytes(b"<root><child/></root>")
    assert report["xml_parsed"] is True
    assert any("may not be a Cubase Track Archive" in w for w in report["warnings"])
