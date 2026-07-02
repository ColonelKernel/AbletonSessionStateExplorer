"""Experimental, cautious ``.als`` inspector.

An Ableton Live Set (``.als``) is typically gzipped XML. This module attempts
decompression and shallow XML tag counting to *illustrate partial
observability* — it is explicitly NOT a Live Set parser, and its output is
never fed into the main graph pipeline.
"""

from __future__ import annotations

import gzip
import io
from collections import Counter
from typing import Any
from xml.etree import ElementTree

INSPECTOR_DISCLAIMER = (
    "This is an exploratory inspector, not a reliable parser. It reports "
    "surface-level XML structure only and makes no claims about full Ableton "
    "Live Set compatibility."
)

# Substrings that suggest track/device/clip-like XML elements. These are
# heuristics over observed tag names, not a specification.
TRACK_LIKE_TAGS = ("audiotrack", "miditrack", "grouptrack", "returntrack", "mastertrack")
DEVICE_LIKE_TAGS = ("device", "plugin", "pluginstance", "instrument")
CLIP_LIKE_TAGS = ("audioclip", "midiclip", "clipslot")


def inspect_als_bytes(data: bytes, filename: str = "uploaded.als") -> dict[str, Any]:
    """Inspect raw ``.als`` bytes; always returns a report dict, never raises."""
    report: dict[str, Any] = {
        "filename": filename,
        "file_size_bytes": len(data),
        "is_gzip": False,
        "decompressed": False,
        "xml_parsed": False,
        "root_tag": None,
        "ableton_version_hint": None,
        "track_like_elements": 0,
        "device_like_elements": 0,
        "clip_like_elements": 0,
        "tag_frequency": {},
        "warnings": [INSPECTOR_DISCLAIMER],
    }

    report["is_gzip"] = data[:2] == b"\x1f\x8b"
    xml_bytes: bytes | None = None

    if report["is_gzip"]:
        try:
            xml_bytes = gzip.decompress(data)
            report["decompressed"] = True
        except OSError as exc:
            report["warnings"].append(
                f"File looks gzipped but decompression failed: {exc}"
            )
            return report
    elif data[:5] == b"<?xml" or data.lstrip()[:1] == b"<":
        xml_bytes = data
        report["warnings"].append(
            "File was not gzipped; treating it as plain XML."
        )
    else:
        report["warnings"].append(
            "File is neither gzip nor XML at first glance; cannot inspect."
        )
        return report

    try:
        tag_counts: Counter[str] = Counter()
        root_tag = None
        version_hint = None
        for event, element in ElementTree.iterparse(
            io.BytesIO(xml_bytes), events=("start",)
        ):
            if root_tag is None:
                root_tag = element.tag
                version_hint = element.attrib.get("Creator") or element.attrib.get(
                    "MinorVersion"
                )
            tag_counts[element.tag] += 1
        report["xml_parsed"] = True
        report["root_tag"] = root_tag
        report["ableton_version_hint"] = version_hint
    except ElementTree.ParseError as exc:
        report["warnings"].append(f"XML parsing failed: {exc}")
        return report

    def _count_matching(substrings: tuple[str, ...]) -> int:
        return sum(
            count
            for tag, count in tag_counts.items()
            if any(sub in tag.lower() for sub in substrings)
        )

    report["track_like_elements"] = _count_matching(TRACK_LIKE_TAGS)
    report["device_like_elements"] = _count_matching(DEVICE_LIKE_TAGS)
    report["clip_like_elements"] = _count_matching(CLIP_LIKE_TAGS)
    report["tag_frequency"] = dict(tag_counts.most_common(50))
    report["total_distinct_tags"] = len(tag_counts)
    report["total_elements"] = sum(tag_counts.values())

    return report
