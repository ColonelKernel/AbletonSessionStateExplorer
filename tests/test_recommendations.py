"""Tests for the heuristic recommendation rules."""

from ableton_session_state_explorer.ableton_session_model import build_demo_session
from ableton_session_state_explorer.models import AudioDescriptorSet, SendState
from ableton_session_state_explorer.recommendations import generate_recommendations


def _titles(recommendations):
    return [r.title for r in recommendations]


def test_unused_returns_produce_recommendation():
    project = build_demo_session()  # demo has returns but no sends
    recs = generate_recommendations(project)
    assert "Return tracks are defined but not used." in _titles(recs)


def test_unused_returns_rule_clears_when_sends_added():
    project = build_demo_session()
    for i, return_track in enumerate(project.return_tracks):
        project.tracks[0].sends.append(
            SendState(
                id=f"send-test-{i}",
                source_track_id=project.tracks[0].id,
                target_return_id=return_track.id,
                enabled=True,
            )
        )
    recs = generate_recommendations(project)
    assert "Return tracks are defined but not used." not in _titles(recs)


def test_vocal_missing_corrective_chain():
    project = build_demo_session()  # Backing Vocals track has only a Reverb
    recs = generate_recommendations(project)
    vocal_recs = [
        r for r in recs
        if r.title == "Vocal track may benefit from a clearer corrective chain."
    ]
    assert vocal_recs
    assert any("track-6" in r.related_node_ids for r in vocal_recs)


def test_dense_device_chain_detected():
    project = build_demo_session()  # Drums track has 7 devices
    recs = generate_recommendations(project)
    dense = [r for r in recs if r.title == "Dense device chain detected."]
    assert dense
    assert any("track-1" in r.related_node_ids for r in dense)


def test_shared_ambience_and_master_limiter_rules():
    project = build_demo_session()
    titles = _titles(generate_recommendations(project))
    assert "Consider routing ambience through shared return tracks." in titles
    assert "Master limiter detected without loudness context." in titles


def test_descriptor_imbalance_detected():
    project = build_demo_session()
    descriptors = [
        AudioDescriptorSet(
            id="d1", source_id="track-1", source_type="track",
            file_path="drums.wav", rms_mean=0.05,
        ),
        AudioDescriptorSet(
            id="d2", source_id="track-2", source_type="track",
            file_path="bass.wav", rms_mean=0.06,
        ),
        AudioDescriptorSet(
            id="d3", source_id="track-5", source_type="track",
            file_path="vox.wav", rms_mean=0.30,  # ~5x the median
        ),
    ]
    recs = generate_recommendations(project, descriptors)
    imbalance = [r for r in recs if r.title == "Potential level imbalance detected."]
    assert imbalance
    assert "track-5" in imbalance[0].related_node_ids


def test_recommendations_carry_explanations_and_caveats():
    recs = generate_recommendations(build_demo_session())
    assert len(recs) >= 3
    for rec in recs:
        assert rec.explanation
        assert rec.suggested_action
        assert rec.caveat
        assert 0.0 <= rec.confidence <= 1.0
