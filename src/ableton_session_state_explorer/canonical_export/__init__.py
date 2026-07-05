"""Canonical-export adapter: this explorer as an *observation instrument*.

Relocated from the Session State Analyzer's ``session_explorer.drivers.
ableton`` package (origin: SessionStateExplorer@041f529) per the pivot plan:
the four DAW explorers stay independent instruments in their own repos, and
each gains an ``export-canonical`` verb that emits the shared flat v0.2
``canonical.snapshot.json`` wire format (the ``canonical-snapshot`` package)
for the analyzer to consume.

What moved where:

- ``mapper.py`` — the round-trip-verified native ↔ nested mapper, rewired to
  this repo's :mod:`..models` (the originals; the analyzer copies were ports
  of them) and to ``canonical_snapshot.nested`` for the intermediate form.
- ``exporter.py`` — the 5-file bundle writer (``adapter_descriptor.json``,
  ``capabilities.json``, ``native.json``, ``canonical.snapshot.json``,
  ``validation.json``) plus the degraded-but-honest ``.als`` surface bundle.
- ``manifest.py`` — the measured capability manifest and adapter descriptor.

Deliberately NOT relocated: the analyzer's ``rules.py`` was a thin
core-facing wrapper around this repo's ``recommendations.py`` (the rule logic
itself is verbatim here); with the analyzer's ``core.driver`` registry gone,
the wrapper has no client. ``recommendations.py`` remains the single home of
the rule pack.
"""

from .exporter import export_als_surface, export_bundle
from .manifest import build_adapter_descriptor, build_capability_manifest
from .mapper import to_canonical, to_native

__all__ = [
    "export_bundle",
    "export_als_surface",
    "to_canonical",
    "to_native",
    "build_capability_manifest",
    "build_adapter_descriptor",
]
