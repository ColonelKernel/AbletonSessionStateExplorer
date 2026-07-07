"""The 5-file canonical bundle exporter.

``export_bundle`` turns a session JSON (extension export or hand-authored)
into the analyzer's bundle layout::

    adapter_descriptor.json   who captured this, and what it cannot see
    capabilities.json         the measured capability manifest
    native.json               the verbatim native ProjectState payload
    canonical.snapshot.json   the flat v0.2 CanonicalDAWSnapshot wire format
    validation.json           the contract validation report (must be valid)

``export_als_surface`` is the degraded-but-honest pathway for ``.als`` files:
this adapter never decodes a Live Set, so the bundle contains ONLY a PROJECT
entity whose structure fields are explicitly UNKNOWN, a ``failures[]`` entry
recording that ``.als`` decode is UNSUPPORTED, and the cautious surface-count
report under ``extensions["ableton_live"]["als_surface"]``. No fabricated
tracks. The bundle still validates — honesty is the feature.

Determinism: id counters are reset before mapping, ``created_at`` derives
from the input file's mtime (not wall clock), and ``snapshot_id`` is
content-hashed, so re-exporting the same input yields byte-identical
bundles. ``sanitize=True`` strips the exporting user's home-directory prefix
from all string values (paths become ``~/...``).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from canonical_snapshot import (
    CanonicalDAWSnapshot,
    Entity,
    FailureRecord,
    NativeRef,
    ProvenanceRecord,
    SourceInfo,
    flatten_session,
    validate_snapshot,
)
from canonical_snapshot.ids import reset_id_counters as reset_contract_id_counters
from canonical_snapshot.models import DomainCoverage

from ..als_inspector import inspect_als_bytes
from ..models import validate_project_dict
from ..utils import reset_id_counters
from .manifest import (
    ADAPTER_NAME,
    DAW,
    build_adapter_descriptor,
    build_capability_manifest,
)
from .mapper import to_canonical

from .. import __version__

BUNDLE_FILES = (
    "adapter_descriptor.json",
    "capabilities.json",
    "native.json",
    "canonical.snapshot.json",
    "validation.json",
)

SourceKind = Literal["extension_json", "session_json"]

# The .als structure fields whose values this adapter cannot know: the file
# demonstrably contains session structure, but the decode pathway does not
# exist here, so every one of these is an explicit UNKNOWN.
_ALS_STRUCTURE_FIELDS = (
    "tracks",
    "channels",
    "scenes",
    "clips",
    "processors",
    "routing",
    "tempo",
    "time_signature",
)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug or "unnamed"


def sanitize_home_paths(value: Any, home: Optional[str] = None) -> Any:
    """Recursively replace the user's home-dir prefix in strings with ``~``."""

    if home is None:
        home = str(Path.home())
    if isinstance(value, str):
        if value.startswith(home):
            return "~" + value[len(home):]
        return value
    if isinstance(value, dict):
        return {key: sanitize_home_paths(item, home) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_home_paths(item, home) for item in value]
    return value


def _created_at(path: Path) -> str:
    """Deterministic timestamp: the input file's mtime in UTC, not wall clock."""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(int(mtime), tz=timezone.utc).isoformat()


def _dump_json(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _write_bundle(
    out_dir: Path,
    *,
    capture_modes: list[str],
    native_payload: Any,
    snapshot_dict: dict[str, Any],
) -> dict[str, Path]:
    """Write the five bundle files; refuse to emit an invalid snapshot."""

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: out_dir / name for name in BUNDLE_FILES}

    report = validate_snapshot(snapshot_dict)
    paths["validation.json"].write_bytes(
        _dump_json(report.model_dump(mode="json"))
    )
    paths["adapter_descriptor.json"].write_bytes(
        _dump_json(build_adapter_descriptor(capture_modes).model_dump(mode="json"))
    )
    paths["capabilities.json"].write_bytes(
        _dump_json(build_capability_manifest().model_dump(mode="json"))
    )
    paths["native.json"].write_bytes(_dump_json(native_payload))
    paths["canonical.snapshot.json"].write_bytes(_dump_json(snapshot_dict))

    if not report.valid:
        raise RuntimeError(
            "Refusing to publish an invalid canonical bundle; see "
            f"{paths['validation.json']} for the errors: {report.errors}"
        )
    return paths


def export_bundle(
    session_json_path: str | Path,
    out_dir: str | Path,
    *,
    source_kind: SourceKind = "session_json",
    sanitize: bool = True,
) -> dict[str, Path]:
    """Export a session JSON into the 5-file canonical bundle.

    ``source_kind`` states how the JSON was captured and drives
    source-stability honestly: an ``extension_json`` came through the
    official Extensions SDK (SUPPORTED_INTEGRATION); a hand-authored
    ``session_json`` is a MANUAL capture — same schema, weaker claim.
    """

    session_json_path = Path(session_json_path)
    out_dir = Path(out_dir)

    # Deterministic ids for anything counter-generated downstream.
    reset_id_counters()
    reset_contract_id_counters()

    payload = json.loads(session_json_path.read_text(encoding="utf-8"))
    project = validate_project_dict(payload)
    session = to_canonical(project, source_artifact=source_kind, dialect="ableton")

    native_payload: Any = session.native.model_dump() if session.native else None
    if sanitize:
        native_payload = sanitize_home_paths(native_payload)
    native_bytes = _dump_json(native_payload)
    native_sha256 = hashlib.sha256(native_bytes).hexdigest()

    source = SourceInfo(
        daw=DAW,
        adapter=ADAPTER_NAME,
        adapter_version=__version__,
        capture_modes=[source_kind],
    )
    snapshot = flatten_session(
        session,
        source,
        capabilities=build_capability_manifest(),
        native_file="native.json",
        native_sha256=native_sha256,
        snapshot_id=f"{DAW}:{_slug(session.name)}:{native_sha256[:12]}",
        created_at=_created_at(session_json_path),
        default_stability=(
            "SUPPORTED_INTEGRATION" if source_kind == "extension_json" else "MANUAL"
        ),
    )

    snapshot_dict = snapshot.model_dump(mode="json")
    if sanitize:
        snapshot_dict = sanitize_home_paths(snapshot_dict)

    return _write_bundle(
        out_dir,
        capture_modes=[source_kind],
        native_payload=json.loads(native_bytes.decode("utf-8")),
        snapshot_dict=snapshot_dict,
    )


def export_als_surface(
    als_path: str | Path,
    out_dir: str | Path,
    *,
    sanitize: bool = True,
) -> dict[str, Path]:
    """Export a DEGRADED bundle from an ``.als`` file — no fake snapshot.

    The surface inspector counts XML tags; it does not decode session state.
    The resulting snapshot says exactly that: one PROJECT entity with UNKNOWN
    structure fields, an explicit UNSUPPORTED failure, and the surface report
    preserved in extensions. It validates cleanly, because a degraded-but-
    honest snapshot is a contract demonstration, not an error state.
    """

    als_path = Path(als_path)
    out_dir = Path(out_dir)

    data = als_path.read_bytes()
    report = inspect_als_bytes(data, als_path.name)
    if sanitize:
        report = sanitize_home_paths(report)

    content_hash = hashlib.sha256(data).hexdigest()
    project_id = f"{DAW}:project"

    prov = ProvenanceRecord(
        id="prov:0001",
        evidence="OBSERVED",
        capture_method="als_surface_inspection",
        source_stability="HEURISTIC",
        source_ref=str(als_path.name),
        explanation=(
            "Cautious gzip/XML surface inspection of a Live Set: tag counts "
            "only. Not a parser; no session structure was decoded."
        ),
    )

    project = Entity(
        id=project_id,
        entity_type="PROJECT",
        name=als_path.stem,
        properties={
            "source_file": als_path.name,
            "file_size_bytes": report.get("file_size_bytes"),
        },
        native=NativeRef(
            daw=DAW,
            native_type="live_set",
            properties={
                "ableton_version_hint": report.get("ableton_version_hint"),
                "root_tag": report.get("root_tag"),
            },
        ),
        prov={"*": prov.id},
        availability={field: "UNKNOWN" for field in _ALS_STRUCTURE_FIELDS},
    )

    failures = [
        FailureRecord(
            stage="als_decode",
            message=(
                ".als session-state decode is UNSUPPORTED by this adapter: "
                "a Live Set is a proprietary format and this repo "
                "deliberately ships only a surface inspector."
            ),
            detail=(
                "Use the Session State Exporter Live extension "
                "(extension/session-state-exporter) to capture this Set "
                "through the official Extensions SDK instead."
            ),
        )
    ]

    # Coverage stays honest: the surface count suggests track-like elements
    # exist, and every one of them is unsupported for decode. When even the
    # surface could not be read, applicability itself is unknown — no counts.
    coverage = {}
    if report.get("xml_parsed"):
        track_like = int(report.get("track_like_elements", 0))
        coverage["structure"] = DomainCoverage(
            applicable=track_like, unsupported=track_like
        )

    native_payload = {
        "artifact_type": "als_surface_report",
        "filename": als_path.name,
        "report": report,
    }
    native_bytes = _dump_json(native_payload)
    native_sha256 = hashlib.sha256(native_bytes).hexdigest()

    snapshot = CanonicalDAWSnapshot(
        snapshot_id=f"{DAW}:{_slug(als_path.stem)}:{content_hash[:12]}",
        created_at=_created_at(als_path),
        source=SourceInfo(
            daw=DAW,
            daw_version=report.get("ableton_version_hint"),
            adapter=ADAPTER_NAME,
            adapter_version=__version__,
            capture_modes=["als_surface"],
        ),
        project=project_id,
        entities=[project],
        relationships=[],
        capabilities=build_capability_manifest(),
        coverage=coverage,
        provenance=[prov],
        extensions={
            DAW: {
                "als_surface": report,
                "native_file": {"path": "native.json", "sha256": native_sha256},
            }
        },
        warnings=[str(w) for w in report.get("warnings", [])],
        failures=failures,
    )

    snapshot_dict = snapshot.model_dump(mode="json")
    if sanitize:
        snapshot_dict = sanitize_home_paths(snapshot_dict)

    return _write_bundle(
        out_dir,
        capture_modes=["als_surface"],
        native_payload=json.loads(native_bytes.decode("utf-8")),
        snapshot_dict=snapshot_dict,
    )
