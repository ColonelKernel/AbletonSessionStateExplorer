"""Adapter for optional Ableton-compatible project export.

Design intent (Pathway B in the research framing): if a public Ableton Live
Set export library is importable in this environment, use it to produce a
minimal Live Set / project structure. Otherwise fall back to a transparent
mock export — a folder of JSON plus an explicit limitations note — so the
research pipeline never depends on proprietary tooling being present.

Notes on the current tooling landscape (July 2026):

* Ableton's public developer offering for Live 12.3 is the **Extensions SDK**,
  a TypeScript/JavaScript SDK for building extensions that run inside Live.
  It is not a Python library and does not provide offline Live Set authoring.
* No official Ableton Live Set export package is published on PyPI.
* This adapter therefore probes a small list of candidate module names and,
  when none is available, performs a mock export. We deliberately do NOT
  hand-craft ``.als`` gzip/XML files: that format is proprietary and
  unversioned from our perspective, and fabricating one would overstate
  compatibility.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Optional

from .graph_builder import build_session_graph, graph_to_dict
from .models import ExportResult, ProjectState
from .utils import to_pretty_json

# Candidate module names for a public Ableton Live Set export package.
# None of these currently exist on PyPI; the list documents what we probe for
# so a future official package can be dropped in without code changes here.
CANDIDATE_EXPORT_MODULES = (
    "ableton_live_set_export",
    "live_set_export",
    "abletonliveset",
)

MOCK_EXPORT_README = """\
# Export limitations

This folder was produced by **Ableton Session State Explorer v0** operating in
**research graph mode** (mock export).

## Why is this not an Ableton Live Set?

No public Ableton Live Set export library was available in this Python
environment. Ableton's current public developer tooling (the Extensions SDK)
targets extensions running *inside* Live and does not provide offline Live
Set authoring from Python. Rather than fabricate a `.als` file — a proprietary
format we cannot guarantee compatibility with — this prototype exports its
full session representation as transparent JSON.

## What is in this folder

- `project_state.json` — the complete Ableton-style session state
  (tracks, clips, scenes, devices, sends, returns, master) in this
  prototype's documented schema.
- `session_graph.json` — the same session as a typed node/edge graph.

## What was omitted

- A binary `.als` Live Set file (no supported export path available).
- Device presets, automation curves, and audio media (out of scope for v0).

If a supported export library becomes available, the adapter in
`ableton_export_adapter.py` will use it automatically.
"""


def _find_export_module() -> Optional[ModuleType]:
    """Return the first importable candidate export module, if any."""
    for module_name in CANDIDATE_EXPORT_MODULES:
        try:
            if importlib.util.find_spec(module_name) is not None:
                return importlib.import_module(module_name)
        except (ImportError, ValueError):
            continue
    return None


def is_ableton_export_available() -> bool:
    """True if a public Ableton Live Set export library is importable."""
    return _find_export_module() is not None


def _mock_export(project_state: ProjectState, output_dir: Path) -> ExportResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    project_path = output_dir / "project_state.json"
    project_path.write_text(
        to_pretty_json(project_state.model_dump(mode="json")), encoding="utf-8"
    )

    graph = build_session_graph(project_state)
    graph_path = output_dir / "session_graph.json"
    graph_path.write_text(to_pretty_json(graph_to_dict(graph)), encoding="utf-8")

    readme_path = output_dir / "README_EXPORT_LIMITATIONS.md"
    readme_path.write_text(MOCK_EXPORT_README, encoding="utf-8")

    return ExportResult(
        success=True,
        mode="mock_export",
        output_paths=[str(project_path), str(graph_path), str(readme_path)],
        warnings=[
            "No public Ableton Live Set export library was available; "
            "the app is operating in research graph mode.",
            "No .als file was produced. The JSON export is the canonical artifact.",
        ],
        message=(
            "Mock export complete: session state and graph written as JSON with "
            "an explicit limitations note."
        ),
    )


def export_project_state_to_ableton(
    project_state: ProjectState, output_dir: Path
) -> ExportResult:
    """Export the session in the most Ableton-compatible way available.

    Attempts a real Live Set export if a public export library is importable;
    otherwise (the normal case today) performs a transparent mock export.
    Never raises on missing tooling.
    """
    output_dir = Path(output_dir)
    module = _find_export_module()

    if module is None:
        return _mock_export(project_state, output_dir)

    # A candidate library is present. Attempt a conservative minimal export:
    # tracks and clips only, no devices/automation unless clearly supported.
    try:
        exporter = getattr(module, "LiveSetExporter", None) or getattr(
            module, "export_live_set", None
        )
        if exporter is None:
            result = _mock_export(project_state, output_dir)
            result.warnings.append(
                f"Module '{module.__name__}' was found but exposes no known "
                "export entry point; fell back to mock export."
            )
            return result

        output_dir.mkdir(parents=True, exist_ok=True)
        payload = project_state.model_dump(mode="json")
        exported = exporter(payload, str(output_dir))  # type: ignore[operator]
        return ExportResult(
            success=True,
            mode="ableton_export",
            output_paths=[str(exported)] if exported else [str(output_dir)],
            warnings=[
                "Devices, parameters, and automation were not exported; only "
                "tracks and clips were attempted.",
            ],
            message=f"Ableton export attempted via '{module.__name__}'.",
        )
    except Exception as exc:
        result = _mock_export(project_state, output_dir)
        result.warnings.append(
            f"Ableton export via '{module.__name__}' failed ({exc}); "
            "fell back to mock export."
        )
        return result
