"""Small CLI for headless use.

    python -m ableton_session_state_explorer export-demo --out exports/demo
    python -m ableton_session_state_explorer inspect-als path/to/set.als
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ableton_export_adapter import (
    export_project_state_to_ableton,
    is_ableton_export_available,
)
from .ableton_session_model import build_demo_session
from .als_inspector import inspect_als_bytes
from .export import build_export_bundle, export_bundle_to_file
from .graph_builder import build_session_graph
from .recommendations import generate_recommendations
from .utils import to_pretty_json


def _cmd_export_demo(out_dir: Path) -> int:
    project = build_demo_session()
    graph = build_session_graph(project)
    recommendations = generate_recommendations(project)
    bundle = build_export_bundle(
        project,
        graph,
        recommendations=recommendations,
        ableton_export_available=is_ableton_export_available(),
    )
    bundle_path = export_bundle_to_file(bundle, out_dir / "session_bundle.json")
    print(f"Wrote {bundle_path}")

    result = export_project_state_to_ableton(project, out_dir / "ableton_export")
    print(f"Ableton export mode: {result.mode}")
    for path in result.output_paths:
        print(f"  {path}")
    for warning in result.warnings:
        print(f"  warning: {warning}")
    return 0


def _cmd_inspect_als(als_path: Path) -> int:
    if not als_path.exists():
        print(f"File not found: {als_path}", file=sys.stderr)
        return 1
    report = inspect_als_bytes(als_path.read_bytes(), als_path.name)
    print(to_pretty_json(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ableton_session_state_explorer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export-demo", help="Export the built-in demo session bundle"
    )
    export_parser.add_argument("--out", type=Path, default=Path("exports/demo"))

    inspect_parser = subparsers.add_parser(
        "inspect-als", help="Cautiously inspect an .als file (not a parser)"
    )
    inspect_parser.add_argument("als_path", type=Path)

    args = parser.parse_args(argv)
    if args.command == "export-demo":
        return _cmd_export_demo(args.out)
    if args.command == "inspect-als":
        return _cmd_inspect_als(args.als_path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
