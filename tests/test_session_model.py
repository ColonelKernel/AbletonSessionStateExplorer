"""Tests for the session data model and built-in demo session."""

from ableton_session_state_explorer.ableton_session_model import (
    build_demo_session,
    compare_fingerprints,
    compute_session_fingerprint,
)
from ableton_session_state_explorer.models import ProjectState, validate_project_dict


def test_demo_session_loads():
    project = build_demo_session()
    assert isinstance(project, ProjectState)
    assert project.project_name == "Indie Vocal Production Sketch"
    assert project.tempo == 96.0


def test_demo_session_has_tracks():
    project = build_demo_session()
    assert len(project.tracks) == 6
    track_types = {t.track_type for t in project.tracks}
    assert "audio" in track_types
    assert "midi" in track_types


def test_demo_session_has_scenes():
    project = build_demo_session()
    assert len(project.scenes) == 3
    assert [s.name for s in project.scenes] == ["Intro", "Verse", "Chorus"]


def test_demo_session_has_return_tracks():
    project = build_demo_session()
    assert len(project.return_tracks) == 2
    names = {rt.name for rt in project.return_tracks}
    assert names == {"Reverb Return", "Delay Return"}


def test_demo_tracks_contain_devices():
    project = build_demo_session()
    for track in project.tracks:
        assert track.devices, f"track {track.name} should have devices"
    assert project.master_track is not None
    assert project.master_track.devices


def test_schema_round_trip_validates():
    project = build_demo_session()
    payload = project.model_dump(mode="json")
    restored = validate_project_dict(payload)
    assert restored.project_name == project.project_name
    assert len(restored.tracks) == len(project.tracks)
    assert len(restored.all_devices()) == len(project.all_devices())


def test_fingerprint_and_comparison():
    project = build_demo_session()
    fingerprint = compute_session_fingerprint(project)
    assert fingerprint["num_tracks"] == 6
    assert fingerprint["num_return_tracks"] == 2
    assert fingerprint["has_master_limiter"] is True
    assert fingerprint["num_vocal_like_tracks"] >= 2
    # A fingerprint compared with itself is maximally similar.
    assert compare_fingerprints(fingerprint, fingerprint) == 1.0
