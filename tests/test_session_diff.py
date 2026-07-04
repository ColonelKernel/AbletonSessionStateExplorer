"""Tests for the session diff and the built-in Revision 2."""

from ableton_session_state_explorer.ableton_session_model import (
    build_demo_session,
    build_demo_session_revision,
)
from ableton_session_state_explorer.recommendations import generate_recommendations
from ableton_session_state_explorer.session_diff import diff_projects


def test_identical_sessions_diff_to_nothing():
    a, b = build_demo_session(), build_demo_session()
    result = diff_projects(a, b)
    assert result["track_changes"] == []
    assert result["narrative"] == ["No structural differences detected."]


def test_revision_diff_reports_the_enacted_recommendations():
    base = build_demo_session()
    revised = build_demo_session_revision()
    result = diff_projects(base, revised)

    changes = {c["track"]: c for c in result["track_changes"]}
    assert "De-Esser" in changes["Lead Vocal"]["devices_added"]
    assert "Reverb" in changes["Lead Vocal"]["devices_removed"]
    assert "Reverb Return" in changes["Lead Vocal"]["sends_added"]
    assert {"EQ Eight", "Compressor"} <= set(changes["Backing Vocals"]["devices_added"])
    assert "Echo" in changes["Guitar"]["devices_removed"]
    assert "Delay Return" in changes["Guitar"]["sends_added"]
    assert result["tracks_added"] == [] and result["tracks_removed"] == []


def test_revision_resolves_the_heuristic_issues():
    base_titles = [r.title for r in generate_recommendations(build_demo_session())]
    revised_titles = [
        r.title for r in generate_recommendations(build_demo_session_revision())
    ]
    for resolved in (
        "Return tracks are defined but not used.",
        "Vocal track may benefit from a clearer corrective chain.",
        "Consider routing ambience through shared return tracks.",
    ):
        assert resolved in base_titles
        assert resolved not in revised_titles
    # The dense drum chain was deliberately left untouched.
    assert "Dense device chain detected." in revised_titles


def test_diff_counts_graph_growth_from_sends():
    result = diff_projects(build_demo_session(), build_demo_session_revision())
    stats = result["graph_stats"]
    # Three sends become send nodes/edges; device deltas shift totals too.
    assert stats["revised_edges"] != stats["base_edges"]
    assert result["narrative"]


def test_track_rename_appears_as_remove_plus_add():
    base = build_demo_session()
    revised = build_demo_session()
    revised.tracks[0].name = "Drum Bus"
    result = diff_projects(base, revised)
    assert "Drum Bus" in result["tracks_added"]
    assert "Drums" in result["tracks_removed"]
