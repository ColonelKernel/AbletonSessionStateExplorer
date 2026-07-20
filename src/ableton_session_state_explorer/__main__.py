"""Small CLI for headless use.

    python -m ableton_session_state_explorer export-demo --out exports/demo
    python -m ableton_session_state_explorer export-demo --dialect cubase
    python -m ableton_session_state_explorer export-canonical session.json --out exports/session
    python -m ableton_session_state_explorer export-canonical set.als --out exports/set
    python -m ableton_session_state_explorer diff-demo
    python -m ableton_session_state_explorer inspect-als path/to/set.als
    python -m ableton_session_state_explorer inspect-track-archive path/to/tracks.xml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ableton_export_adapter import (
    export_project_state_to_ableton,
    is_ableton_export_available,
)
from .ableton_session_model import build_demo_session, build_demo_session_revision
from .als_inspector import inspect_als_bytes
from .cubase_session_model import build_cubase_demo_session
from .export import build_export_bundle, export_bundle_to_file
from .graph_builder import build_session_graph
from .recommendations import generate_recommendations
from .session_diff import diff_projects
from .track_archive_inspector import inspect_track_archive_bytes
from .utils import to_pretty_json

DEMO_BUILDERS = {
    "ableton": build_demo_session,
    "cubase": build_cubase_demo_session,
}


def _cmd_export_demo(out_dir: Path, dialect: str) -> int:
    project = DEMO_BUILDERS[dialect]()
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


def _cmd_export_canonical(input_path: Path, out_dir: Path, source_kind: str) -> int:
    try:
        from .canonical_export import export_als_surface, export_bundle
    except ImportError as exc:
        # The adapter needs the shared canonical-snapshot contract, which is
        # not on PyPI. Turn the bare ModuleNotFoundError into guidance.
        print(
            f"export-canonical needs the 'canonical-snapshot' contract package "
            f"({exc}).\n"
            "Install it from the session-state-analyzer repo, e.g.:\n"
            "  pip install -e <session-state-analyzer>/packages/canonical_snapshot\n"
            "or:  pip install "
            '"canonical-snapshot @ '
            "git+https://github.com/ColonelKernel/session-state-analyzer"
            '@main#subdirectory=packages/canonical_snapshot"',
            file=sys.stderr,
        )
        return 1

    if not input_path.exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        return 1
    if input_path.suffix.lower() == ".als":
        paths = export_als_surface(input_path, out_dir)
        print("Degraded .als surface bundle (no session-state decode):")
    else:
        paths = export_bundle(input_path, out_dir, source_kind=source_kind)  # type: ignore[arg-type]
        print(f"Canonical bundle ({source_kind}):")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0


def _cmd_diff_demo() -> int:
    result = diff_projects(build_demo_session(), build_demo_session_revision())
    print(to_pretty_json(result))
    return 0


def _cmd_inspect_als(als_path: Path) -> int:
    if not als_path.exists():
        print(f"File not found: {als_path}", file=sys.stderr)
        return 1
    report = inspect_als_bytes(als_path.read_bytes(), als_path.name)
    print(to_pretty_json(report))
    return 0


def _cmd_inspect_track_archive(xml_path: Path) -> int:
    if not xml_path.exists():
        print(f"File not found: {xml_path}", file=sys.stderr)
        return 1
    report = inspect_track_archive_bytes(xml_path.read_bytes(), xml_path.name)
    print(to_pretty_json(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ableton_session_state_explorer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export-demo", help="Export a built-in demo session bundle"
    )
    export_parser.add_argument("--out", type=Path, default=Path("exports/demo"))
    export_parser.add_argument(
        "--dialect", choices=sorted(DEMO_BUILDERS), default="ableton",
        help="Which built-in demo dialect to export",
    )

    canonical_parser = subparsers.add_parser(
        "export-canonical",
        help=(
            "Export a session JSON (or, degraded, an .als file) as the "
            "5-file canonical v0.2 snapshot bundle"
        ),
    )
    canonical_parser.add_argument("input_path", type=Path)
    canonical_parser.add_argument(
        "--out", type=Path, default=Path("exports/canonical")
    )
    canonical_parser.add_argument(
        "--source",
        choices=["extension_json", "session_json"],
        default="session_json",
        help=(
            "How the JSON was captured: extension_json (Session State "
            "Exporter extension) or session_json (hand-authored/manual)"
        ),
    )

    subparsers.add_parser(
        "diff-demo",
        help="Diff the built-in demo against its Revision 2 (JSON to stdout)",
    )

    inspect_parser = subparsers.add_parser(
        "inspect-als", help="Cautiously inspect an .als file (not a parser)"
    )
    inspect_parser.add_argument("als_path", type=Path)

    archive_parser = subparsers.add_parser(
        "inspect-track-archive",
        help="Cautiously inspect a Cubase Track Archive .xml (not a parser)",
    )
    archive_parser.add_argument("xml_path", type=Path)

    args = parser.parse_args(argv)
    if args.command == "export-demo":
        return _cmd_export_demo(args.out, args.dialect)
    if args.command == "export-canonical":
        return _cmd_export_canonical(args.input_path, args.out, args.source)
    if args.command == "diff-demo":
        return _cmd_diff_demo()
    if args.command == "inspect-als":
        return _cmd_inspect_als(args.als_path)
    if args.command == "inspect-track-archive":
        return _cmd_inspect_track_archive(args.xml_path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
