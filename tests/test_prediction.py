"""Tests for the synthetic-corpus DAW-state prediction baseline."""

from ableton_session_state_explorer.ableton_session_model import build_demo_session
from ableton_session_state_explorer.models import Recommendation
from ableton_session_state_explorer.prediction import (
    CHAIN_FAMILIES,
    FAMILY_DEVICE_NAMES,
    ChainFamilyModel,
    generate_synthetic_corpus,
    predict_chain_gaps,
    prediction_table,
    train_and_evaluate,
)
from ableton_session_state_explorer.utils import classify_device_family


def test_device_name_pools_classify_to_their_family():
    for family, names in FAMILY_DEVICE_NAMES.items():
        for name in names:
            assert classify_device_family(name) == family, (
                f"{name!r} classifies as {classify_device_family(name)!r}, "
                f"expected {family!r}"
            )


def test_corpus_generation_is_deterministic_under_seed():
    corpus_a = generate_synthetic_corpus(n_sessions=20, seed=7)
    corpus_b = generate_synthetic_corpus(n_sessions=20, seed=7)
    assert [s.model_dump() for s in corpus_a] == [s.model_dump() for s in corpus_b]

    corpus_c = generate_synthetic_corpus(n_sessions=20, seed=8)
    assert [s.model_dump() for s in corpus_a] != [s.model_dump() for s in corpus_c]


def test_corpus_sessions_have_role_labeled_tracks_with_devices():
    corpus = generate_synthetic_corpus(n_sessions=5, seed=1)
    for session in corpus:
        assert 4 <= len(session.tracks) <= 10
        for track in session.tracks:
            assert track.role in {r for r, _ in [
                ("Vocal", 0), ("Drums", 0), ("Bass", 0), ("Guitar", 0),
                ("Keys", 0), ("FX", 0), ("Unknown", 0),
            ]}


def test_model_beats_frequency_baseline():
    _, metrics = train_and_evaluate(n_sessions=300, seed=42)
    assert metrics["n_examples"] > 100
    assert metrics["model_hit_at_1"] > metrics["baseline_hit_at_1"]
    assert metrics["model_hit_at_3"] > metrics["baseline_hit_at_3"]
    assert metrics["model_hit_at_3"] > 0.85


def test_model_recovers_role_priors_approximately():
    corpus = generate_synthetic_corpus(n_sessions=400, seed=42)
    model = ChainFamilyModel().fit(corpus)
    # Ground truth: P(Dynamics | Vocal, audio) = 0.95 in the priors.
    p = model.family_probability("Vocal", "audio", "Dynamics")
    assert 0.85 < p <= 1.0
    # Ambience on Bass is rare (0.10 prior).
    p_rare = model.family_probability("Bass", "audio", "Ambience")
    assert p_rare < 0.25


def test_predict_chain_gaps_on_demo_session():
    model, _ = train_and_evaluate(n_sessions=300, seed=42)
    demo = build_demo_session()
    gaps = predict_chain_gaps(demo, model)

    assert gaps, "demo session should yield predicted chain gaps"
    assert all(isinstance(g, Recommendation) for g in gaps)
    # Backing Vocals (track-6) has only a Reverb; the corpus says vocal
    # tracks nearly always carry Dynamics and EQ.
    bgv_families = {
        g.title for g in gaps if "track-6" in g.related_node_ids
    }
    assert any("Dynamics" in title for title in bgv_families)
    assert any("EQ" in title for title in bgv_families)
    # Every prediction is honestly caveated as synthetic.
    for gap in gaps:
        assert "synthetic" in gap.caveat.lower()
        assert 0.0 <= gap.confidence <= 1.0


def test_prediction_table_covers_all_tracks():
    model, _ = train_and_evaluate(n_sessions=200, seed=42)
    demo = build_demo_session()
    rows = prediction_table(demo, model)
    assert len(rows) == len(demo.tracks)
    assert {"track", "role", "type", "observed_families", "top_predicted_missing"} <= set(
        rows[0].keys()
    )


def test_no_instrument_suggestions_for_audio_tracks():
    model, _ = train_and_evaluate(n_sessions=200, seed=42)
    demo = build_demo_session()
    for gap in predict_chain_gaps(demo, model, probability_threshold=0.0):
        if "Instrument" in gap.title or "MIDI Effect" in gap.title:
            track_id = gap.related_node_ids[0]
            track = demo.track_by_id(track_id)
            assert track is not None and track.track_type == "midi"
