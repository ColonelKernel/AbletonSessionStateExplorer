"""Experimental, cautious Cubase Track Archive (``.xml``) inspector.

Cubase can export selected tracks as a Track Archive — an XML file whose
elements are largely generic (``obj``, ``list``, ``member``) with the
semantics carried in ``class`` attributes (e.g. ``MAudioTrackEvent``).
This module attempts shallow structure counting over that idiom to
*illustrate partial observability* on the Steinberg side, exactly parallel
to the ``.als`` inspector: it is explicitly NOT a Track Archive parser, and
its output is never fed into the main graph pipeline.
"""

from __future__ import annotations

import gzip
import io
from collections import Counter
from typing import Any
from xml.etree import ElementTree

TRACK_ARCHIVE_DISCLAIMER = (
    "This is an exploratory inspector, not a reliable parser. It reports "
    "surface-level XML structure only and makes no claims about Cubase "
    "Track Archive compatibility."
)

# Substrings matched against XML tag names AND `class` attribute values
# (lowercased). Heuristics over observed archives, not a specification.
TRACK_LIKE_HINTS = ("track",)
EVENT_LIKE_HINTS = ("event", "part", "clip")
PLUGIN_LIKE_HINTS = ("plugin", "vst", "insert", "effect")


def inspect_track_archive_bytes(
    data: bytes, filename: str = "uploaded.xml"
) -> dict[str, Any]:
    """Inspect raw Track Archive bytes; always returns a report, never raises."""
    report: dict[str, Any] = {
        "filename": filename,
        "file_size_bytes": len(data),
        "xml_parsed": False,
        "root_tag": None,
        "track_like_elements": 0,
        "event_like_elements": 0,
        "plugin_like_elements": 0,
        "tag_frequency": {},
        "class_frequency": {},
        "warnings": [TRACK_ARCHIVE_DISCLAIMER],
    }

    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
            report["warnings"].append("File was gzipped; decompressed before parsing.")
        except OSError as exc:
            report["warnings"].append(f"Gzip decompression failed: {exc}")
            return report

    if not (data[:5] == b"<?xml" or data.lstrip()[:1] == b"<"):
        report["warnings"].append(
            "File does not look like XML at first glance; cannot inspect."
        )
        return report

    tag_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    root_tag = None
    try:
        for _event, element in ElementTree.iterparse(
            io.BytesIO(data), events=("start",)
        ):
            if root_tag is None:
                root_tag = element.tag
            tag_counts[element.tag] += 1
            class_attr = element.attrib.get("class")
            if class_attr:
                class_counts[class_attr] += 1
    except ElementTree.ParseError as exc:
        report["warnings"].append(f"XML parsing failed: {exc}")
        return report

    report["xml_parsed"] = True
    report["root_tag"] = root_tag

    def _count_matching(hints: tuple[str, ...]) -> int:
        matched = sum(
            count
            for tag, count in tag_counts.items()
            if any(hint in tag.lower() for hint in hints)
        )
        matched += sum(
            count
            for cls, count in class_counts.items()
            if any(hint in cls.lower() for hint in hints)
        )
        return matched

    report["track_like_elements"] = _count_matching(TRACK_LIKE_HINTS)
    report["event_like_elements"] = _count_matching(EVENT_LIKE_HINTS)
    report["plugin_like_elements"] = _count_matching(PLUGIN_LIKE_HINTS)
    report["tag_frequency"] = dict(tag_counts.most_common(50))
    report["class_frequency"] = dict(class_counts.most_common(50))
    report["total_distinct_tags"] = len(tag_counts)
    report["total_elements"] = sum(tag_counts.values())

    if not class_counts:
        report["warnings"].append(
            "No class attributes found — this may not be a Cubase Track "
            "Archive (archives typically carry semantics in class attributes)."
        )

    return report
