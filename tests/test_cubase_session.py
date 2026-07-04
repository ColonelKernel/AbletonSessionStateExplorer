"""Tests for the Cubase-style demo session (second dialect instantiation)."""

from ableton_session_state_explorer.cubase_session_model import (
    CUBASE_DEMO_SESSION_NAME,
    build_cubase_demo_session,
)
from ableton_session_state_explorer.graph_builder import build_session_graph
from ableton_session_state_explorer.recommendations import generate_recommendations
from ableton_session_state_explorer.utils import classify_device_family


def test_cubase_demo_builds_and_declares_dialect():
    project = build_cubase_demo_session()
    assert project.project_name == CUBASE_DEMO_SESSION_NAME
    assert project.metadata["daw_dialect"] == "cubase-style"


def test_cubase_demo_has_no_scenes_but_linear_clip_positions():
    project = build_cubase_demo_session()
    assert project.scenes == []
    clips = [clip for track in project.tracks for clip in track.clips]
    assert clips
    assert all(clip.scene_id is None for clip in clips)
    assert all(clip.start_time_beats is not None for clip in clips)


def test_cubase_demo_sends_are_wired_to_fx_channels():
    project = build_cubase_demo_session()
    sends = project.all_sends()
    assert len(sends) >= 4
    fx_ids = {r.id for r in project.return_tracks}
    assert all(send.target_return_id in fx_ids for send in sends)

    graph = build_session_graph(project)
    send_edges = [
        (u, v) for u, v, d in graph.edges(data=True) if d.get("type") == "sends_to"
    ]
    assert send_edges, "wired sends must appear as sends_to edges"


def test_dialect_supplies_families_that_keywords_cannot():
    project = build_cubase_demo_session()
    reverence = next(
        d for r in project.return_tracks for d in r.devices if d.name == "REVerence"
    )
    # The keyword classifier cannot place REVerence; the dialect can.
    assert classify_device_family("REVerence") == "Unknown"
    assert reverence.device_family == "Ambience"

    all_devices = project.all_devices()
    assert all(d.device_family and d.device_family != "Unknown" for d in all_devices)


def test_tidy_session_produces_fewer_recommendations():
    project = build_cubase_demo_session()
    titles = [r.title for r in generate_recommendations(project)]
    assert "Return tracks are defined but not used." not in titles
    assert "Vocal track may benefit from a clearer corrective chain." not in titles
    assert "Consider routing ambience through shared return tracks." not in titles
