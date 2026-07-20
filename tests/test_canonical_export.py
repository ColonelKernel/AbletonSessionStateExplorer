"""Tests for the canonical-export adapter (canonical_export/).

Covers the three load-bearing claims:

1. The relocated mapper is still lossless: ``to_native(to_canonical(x))``
   reproduces the native ``ProjectState`` exactly (the round-trip gate that
   was verified in the analyzer repo survives relocation).
2. ``export_bundle`` emits a valid 5-file bundle whose snapshot makes the
   contract's modeling visible: TRACK ≠ CHANNEL joined by TRACK_USES_CHANNEL,
   return tracks as CHANNEL-only effect_return entities, scenes as
   STRUCTURAL_CONTAINERs.
3. ``export_als_surface`` produces a degraded-but-honest bundle: explicit
   failures, UNKNOWN availability, surface report in extensions — and no
   fabricated tracks.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

# The canonical-export adapter depends on the shared contract package, which
# lives in the analyzer repo and is installed only in dev environments. Skip
# cleanly when it is absent (matches the sibling repos' guarded-optional
# dependency policy) so CI without it stays green.
pytest.importorskip("canonical_snapshot")

from ableton_session_state_explorer.ableton_session_model import (  # noqa: E402
    build_demo_session,
    build_demo_session_revision,
)
from ableton_session_state_explorer.canonical_export import (
    export_als_surface,
    export_bundle,
    to_canonical,
    to_native,
)
from ableton_session_state_explorer.canonical_export.exporter import (
    BUNDLE_FILES,
    sanitize_home_paths,
)
from ableton_session_state_explorer.canonical_export.manifest import (
    build_adapter_descriptor,
    build_capability_manifest,
)
from ableton_session_state_explorer.models import validate_project_dict

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "examples"
COMMITTED_BUNDLE_DIR = (
    Path(__file__).resolve().parent.parent / "exports" / "example_session"
)


def _load_example(name: str):
    payload = json.loads((EXAMPLES_DIR / name).read_text(encoding="utf-8"))
    return validate_project_dict(payload)


# ---------------------------------------------------------------------------
# 1. Lossless round-trip through the relocated mapper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "project_factory",
    [
        build_demo_session,
        build_demo_session_revision,
        lambda: _load_example("example_session.json"),
        lambda: _load_example("example_session_revision.json"),
    ],
    ids=["demo", "demo_revision", "example_json", "example_revision_json"],
)
def test_round_trip_is_lossless(project_factory):
    project = project_factory()
    session = to_canonical(project)
    assert to_native(session).model_dump() == project.model_dump()


def test_round_trip_survives_serialization():
    """Losslessness must hold across a JSON round of the nested form too."""
    from canonical_snapshot.nested import CanonicalSession

    project = build_demo_session()
    session = to_canonical(project)
    revived = CanonicalSession.model_validate(
        json.loads(session.model_dump_json())
    )
    assert to_native(revived).model_dump() == project.model_dump()


def test_mapper_keeps_dialect_parameter():
    project = build_demo_session()
    session = to_canonical(project, dialect="cubase")
    assert session.dialect == "cubase"
    assert session.tracks[0].id.startswith("cubase:")
    assert session.native is not None and session.native.dialect == "cubase"


# ---------------------------------------------------------------------------
# 2. The 5-file bundle export
# ---------------------------------------------------------------------------


@pytest.fixture()
def bundle(tmp_path):
    paths = export_bundle(
        EXAMPLES_DIR / "example_session.json",
        tmp_path / "bundle",
        source_kind="session_json",
    )
    snapshot = json.loads(paths["canonical.snapshot.json"].read_text())
    return paths, snapshot


def test_bundle_has_five_files(bundle):
    paths, _ = bundle
    assert set(paths) == set(BUNDLE_FILES)
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0


def test_bundle_validates_clean(bundle):
    paths, _ = bundle
    report = json.loads(paths["validation.json"].read_text())
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["warnings"] == []


def test_bundle_snapshot_revalidates_with_contract(bundle):
    from canonical_snapshot import validate_snapshot

    _, snapshot = bundle
    report = validate_snapshot(snapshot)
    assert report.valid, report.errors


def test_track_is_not_channel(bundle):
    """Every regular track emits TRACK + CHANNEL joined by TRACK_USES_CHANNEL."""
    _, snapshot = bundle
    tracks = [e for e in snapshot["entities"] if e["entity_type"] == "TRACK"]
    channels = [e for e in snapshot["entities"] if e["entity_type"] == "CHANNEL"]
    uses = [
        r for r in snapshot["relationships"] if r["rel_type"] == "TRACK_USES_CHANNEL"
    ]
    assert len(tracks) == 6  # example session: 6 regular tracks
    # 6 fused-track channels + 2 return channels + 1 master channel
    assert len(channels) == 9
    assert len(uses) == len(tracks)
    channel_ids = {c["id"] for c in channels}
    for rel in uses:
        assert rel["target"] in channel_ids


def test_return_tracks_are_channel_only_effect_returns(bundle):
    _, snapshot = bundle
    by_id = {e["id"]: e for e in snapshot["entities"]}
    returns = [
        e
        for e in snapshot["entities"]
        if e["entity_type"] == "CHANNEL" and "effect_return" in e["semantic_roles"]
    ]
    assert len(returns) == 2  # Return A (reverb), Return B (delay)
    track_ids = {
        e["id"] for e in snapshot["entities"] if e["entity_type"] == "TRACK"
    }
    for ret in returns:
        # No TRACK twin, no TRACK_USES_CHANNEL pointing at it from a TRACK
        assert ret["id"] not in track_ids
        assert ret["native"]["native_type"] == "return"
    # The base example deliberately leaves its returns unused (that gap is
    # what the "unused returns" recommendation flags): no send edges here.
    assert by_id is not None
    sends = [
        r for r in snapshot["relationships"] if r["rel_type"] == "CHANNEL_SENDS_TO"
    ]
    assert sends == []


def test_revision_sends_become_channel_sends_to(tmp_path):
    """The revision adds vocal→Return A sends; they must ride as edges."""
    paths = export_bundle(
        EXAMPLES_DIR / "example_session_revision.json", tmp_path / "rev"
    )
    snapshot = json.loads(paths["canonical.snapshot.json"].read_text())
    by_id = {e["id"]: e for e in snapshot["entities"]}
    sends = [
        r for r in snapshot["relationships"] if r["rel_type"] == "CHANNEL_SENDS_TO"
    ]
    assert sends, "the revision session routes sends to the returns"
    return_ids = {
        e["id"]
        for e in snapshot["entities"]
        if e["entity_type"] == "CHANNEL" and "effect_return" in e["semantic_roles"]
    }
    assert any(s["target"] in return_ids for s in sends)
    for send in sends:
        assert by_id[send["source"]]["entity_type"] == "CHANNEL"


def test_scenes_become_structural_containers(bundle):
    _, snapshot = bundle
    scenes = [
        e
        for e in snapshot["entities"]
        if e["entity_type"] == "STRUCTURAL_CONTAINER"
    ]
    assert len(scenes) == 3
    assert {s["name"] for s in scenes} == {"Intro", "Verse", "Chorus"}
    project_id = snapshot["project"]
    scene_edges = [
        r
        for r in snapshot["relationships"]
        if r["rel_type"] == "CONTAINS"
        and r["source"] == project_id
        and r["properties"].get("kind") == "scene"
    ]
    assert len(scene_edges) == 3


def test_bundle_provenance_and_stability(bundle):
    """session_json is a MANUAL capture; role/family stay INFERRED heuristics."""
    _, snapshot = bundle
    records = {p["id"]: p for p in snapshot["provenance"]}
    assert records, "provenance store must not be empty"
    assert {p["source_stability"] for p in records.values()} == {"MANUAL"}
    evidences = {p["evidence"] for p in records.values()}
    assert "OBSERVED" in evidences and "INFERRED" in evidences
    # Every prov reference resolves (validation also checks this).
    for entity in snapshot["entities"]:
        for ref in entity["prov"].values():
            assert ref in records


def test_bundle_native_sidecar_never_embedded(bundle):
    paths, snapshot = bundle
    native = json.loads(paths["native.json"].read_text())
    assert native["model_name"] == "ProjectState"
    assert native["model"]["project_name"] == "Indie Vocal Production Sketch"
    ref = snapshot["extensions"]["ableton_live"]["native_file"]
    assert ref["path"] == "native.json"
    assert len(ref["sha256"]) == 64
    # The snapshot itself must not carry the native payload.
    assert "native" not in snapshot["extensions"]["ableton_live"].get(
        "metadata", {}
    )


def test_bundle_is_deterministic(tmp_path):
    a = export_bundle(EXAMPLES_DIR / "example_session.json", tmp_path / "a")
    b = export_bundle(EXAMPLES_DIR / "example_session.json", tmp_path / "b")
    for name in BUNDLE_FILES:
        assert a[name].read_bytes() == b[name].read_bytes(), name


def test_extension_json_stability(tmp_path):
    paths = export_bundle(
        EXAMPLES_DIR / "example_session.json",
        tmp_path / "ext",
        source_kind="extension_json",
    )
    snapshot = json.loads(paths["canonical.snapshot.json"].read_text())
    stabilities = {p["source_stability"] for p in snapshot["provenance"]}
    assert stabilities == {"SUPPORTED_INTEGRATION"}
    assert snapshot["source"]["capture_modes"] == ["extension_json"]


def test_sanitize_home_paths():
    home = str(Path.home())
    payload = {
        "path": f"{home}/Music/project.als",
        "nested": [{"other": f"{home}/Desktop/x.wav"}, "unrelated"],
        "count": 3,
    }
    clean = sanitize_home_paths(payload)
    assert clean["path"] == "~/Music/project.als"
    assert clean["nested"][0]["other"] == "~/Desktop/x.wav"
    assert clean["nested"][1] == "unrelated"
    assert clean["count"] == 3
    assert home not in json.dumps(clean)


# ---------------------------------------------------------------------------
# 3. The capability manifest and adapter descriptor
# ---------------------------------------------------------------------------


def test_capability_manifest_claims():
    manifest = build_capability_manifest()
    assert manifest.daw == "ableton_live"
    read = manifest.read
    assert read["structure"].fields["tracks"].support == "FULL"
    assert read["parameters"].fields["parameter_values"].support == "PARTIAL"
    assert read["automation"].fields["automation_state"].support == "NONE"
    assert read["channel"].fields["volume_db"].support == "NONE"
    assert read["channel"].fields["color"].support == "NONE"
    # Read/write/live/render are separate: write and render claim nothing.
    assert manifest.write == {} and manifest.render == {}
    assert (
        manifest.live_observation["session"].fields["current_set_snapshot"].support
        == "PARTIAL"
    )


def test_adapter_descriptor_identity():
    descriptor = build_adapter_descriptor(["extension_json"])
    assert descriptor.adapter_id == "ableton-extension"
    assert descriptor.daw == "ableton_live"
    assert descriptor.known_limitations, "known_limitations is product substance"
    joined = " ".join(descriptor.known_limitations).lower()
    assert "automation" in joined and "64" in joined and "color" in joined


# ---------------------------------------------------------------------------
# 4. The degraded .als surface bundle
# ---------------------------------------------------------------------------


@pytest.fixture()
def als_bundle(tmp_path):
    xml = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Ableton Creator="Ableton Live 12.4.5"><LiveSet><Tracks>'
        b"<AudioTrack></AudioTrack><AudioTrack></AudioTrack>"
        b"<MidiTrack></MidiTrack><ReturnTrack></ReturnTrack>"
        b"</Tracks></LiveSet></Ableton>"
    )
    als_path = tmp_path / "tiny_set.als"
    als_path.write_bytes(gzip.compress(xml))
    paths = export_als_surface(als_path, tmp_path / "als_bundle")
    snapshot = json.loads(paths["canonical.snapshot.json"].read_text())
    return paths, snapshot


def test_als_bundle_has_five_files_and_validates(als_bundle):
    paths, _ = als_bundle
    assert set(paths) == set(BUNDLE_FILES)
    report = json.loads(paths["validation.json"].read_text())
    assert report["valid"] is True, report["errors"]


def test_als_bundle_has_no_fabricated_structure(als_bundle):
    """Degraded means degraded: one PROJECT entity and nothing invented."""
    _, snapshot = als_bundle
    assert len(snapshot["entities"]) == 1
    project = snapshot["entities"][0]
    assert project["entity_type"] == "PROJECT"
    assert snapshot["relationships"] == []
    # The surface saw track-like tags, but the snapshot must not claim tracks.
    types = {e["entity_type"] for e in snapshot["entities"]}
    assert "TRACK" not in types and "CHANNEL" not in types


def test_als_bundle_states_unknown_availability(als_bundle):
    _, snapshot = als_bundle
    availability = snapshot["entities"][0]["availability"]
    for field in ("tracks", "scenes", "clips", "processors", "routing", "tempo"):
        assert availability[field] == "UNKNOWN"


def test_als_bundle_records_explicit_failure(als_bundle):
    _, snapshot = als_bundle
    assert snapshot["failures"], "the decode gap must be recorded, not implied"
    failure = snapshot["failures"][0]
    assert failure["stage"] == "als_decode"
    assert "UNSUPPORTED" in failure["message"]


def test_als_bundle_keeps_surface_report_in_extensions(als_bundle):
    _, snapshot = als_bundle
    surface = snapshot["extensions"]["ableton_live"]["als_surface"]
    assert surface["xml_parsed"] is True
    assert surface["root_tag"] == "Ableton"
    assert surface["track_like_elements"] == 4
    # Coverage mirrors the surface honestly: N track-like, N unsupported.
    coverage = snapshot["coverage"]["structure"]
    assert coverage["applicable"] == 4
    assert coverage["unsupported"] == 4
    assert coverage["observed"] == 0


def test_als_bundle_capture_mode(als_bundle):
    paths, snapshot = als_bundle
    assert snapshot["source"]["capture_modes"] == ["als_surface"]
    descriptor = json.loads(paths["adapter_descriptor.json"].read_text())
    assert descriptor["capture_modes"] == ["als_surface"]


# ---------------------------------------------------------------------------
# 4. Committed-bundle drift guard
# ---------------------------------------------------------------------------


def test_committed_example_bundle_is_not_stale(tmp_path):
    """The checked-in ``exports/example_session/`` bundle must equal a fresh
    regeneration from ``data/examples/example_session.json``.

    The bundle is a committed reference artifact, but the mapper here and the
    ``canonical_snapshot`` contract it depends on both evolve independently
    (an editable install ignores the ``>=0.2,<0.3`` pin), so without this
    guard the committed bundle silently drifts from what the code produces —
    exactly what happened before this test existed (a stale project-id prefix
    and 13 missing ``PRECEDES`` edges). The comparison ignores the snapshot's
    ``created_at``: it is the *source file's mtime* (see ``_created_at``), and
    git does not preserve mtimes across checkouts, so a fresh clone (e.g. CI)
    always regenerates it to the checkout time — comparing it would make this
    guard fail on every machine but the one that last wrote the bundle. Every
    other field is deterministic, so a parsed-JSON equality check is stable.
    When it fails on real content, regenerate with::

        PYTHONPATH=src python -m ableton_session_state_explorer \\
            export-canonical data/examples/example_session.json \\
            --out exports/example_session --source session_json
    """
    fresh = export_bundle(
        EXAMPLES_DIR / "example_session.json",
        tmp_path / "regen",
        source_kind="session_json",
    )

    def _stable(name: str, payload: dict) -> dict:
        # Drop the mtime-derived, checkout-dependent timestamp before comparing.
        if name == "canonical.snapshot.json":
            return {k: v for k, v in payload.items() if k != "created_at"}
        return payload

    for name in BUNDLE_FILES:
        committed_path = COMMITTED_BUNDLE_DIR / name
        assert committed_path.exists(), (
            f"committed bundle is missing {name} — regenerate "
            "exports/example_session/ (see this test's docstring)."
        )
        committed = _stable(name, json.loads(committed_path.read_text()))
        regenerated = _stable(name, json.loads(fresh[name].read_text()))
        assert committed == regenerated, (
            f"exports/example_session/{name} is stale: it differs from a fresh "
            "export (ignoring created_at). Regenerate the committed bundle "
            "(see this test's docstring)."
        )
