"""Learned DAW-state prediction — a deliberately small proof-of-concept.

This module demonstrates the *prediction* half of the research framing:
given partial session state, predict withheld DAW state. The task here is
masked device-family prediction: given a track's role, type, and the rest of
its device chain, predict the family of a held-out device.

Scope, stated honestly:

* The model is trained on a **synthetic corpus** of sessions generated from
  seeded, role-conditioned device-chain priors — not on real productions.
  It is a benchmark harness and interpretability baseline, not a claim about
  real-world mixing practice.
* The model is a hand-rolled conditional-probability baseline (role- and
  track-type-conditioned family frequencies with pairwise co-occurrence
  lift). It is interpretable by construction: every score decomposes into
  named counts.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Optional

from .models import DeviceState, ProjectState, Recommendation, TrackState
from .utils import classify_device_family

DEFAULT_SEED = 42
DEFAULT_N_SESSIONS = 500

# Families the predictor reasons over (subset of utils.DEVICE_FAMILY_KEYWORDS
# that occurs in insert chains; "Unknown" is excluded from targets).
CHAIN_FAMILIES = [
    "EQ",
    "Dynamics",
    "Ambience",
    "Saturation",
    "Modulation",
    "Pitch",
    "Utility",
    "Instrument",
    "MIDI Effect",
]

# Device-name pools per family. Every name must classify back to its family
# via utils.classify_device_family (checked in tests).
FAMILY_DEVICE_NAMES: dict[str, list[str]] = {
    "EQ": ["EQ Eight", "Channel EQ", "Pro-Q 3"],
    "Dynamics": ["Compressor", "Glue Compressor", "Limiter", "Gate", "De-Esser"],
    "Ambience": ["Reverb", "Hybrid Reverb", "Delay", "Echo"],
    "Saturation": ["Saturator", "Overdrive", "Amp"],
    "Modulation": ["Chorus", "Phaser", "Auto Pan"],
    "Pitch": ["Auto-Tune Pro", "Vocoder"],
    "Utility": ["Utility", "Gain", "Tuner"],
    "Instrument": ["Wavetable", "Operator", "Analog", "Drift"],
    "MIDI Effect": ["Arpeggiator", "Chord", "Scale"],
}

# Role-conditioned probability that a family appears in a track's chain.
# These priors are hand-authored to be *plausible*, and are the ground truth
# of the synthetic world — the model's job is to recover them from samples.
ROLE_CHAIN_PRIORS: dict[str, dict[str, float]] = {
    "Vocal": {
        "EQ": 0.90, "Dynamics": 0.95, "Ambience": 0.70, "Pitch": 0.35,
        "Saturation": 0.20, "Utility": 0.30, "Modulation": 0.10,
    },
    "Drums": {
        "EQ": 0.80, "Dynamics": 0.85, "Saturation": 0.50, "Ambience": 0.30,
        "Utility": 0.40, "Modulation": 0.05,
    },
    "Bass": {
        "EQ": 0.85, "Dynamics": 0.80, "Saturation": 0.60, "Utility": 0.30,
        "Ambience": 0.10, "Modulation": 0.10,
    },
    "Guitar": {
        "EQ": 0.80, "Dynamics": 0.50, "Ambience": 0.60, "Saturation": 0.50,
        "Modulation": 0.30, "Utility": 0.20,
    },
    "Keys": {
        "EQ": 0.60, "Dynamics": 0.40, "Ambience": 0.60, "Modulation": 0.40,
        "Utility": 0.20, "Saturation": 0.20,
    },
    "FX": {
        "Ambience": 0.80, "Modulation": 0.50, "EQ": 0.40, "Utility": 0.30,
    },
    "Unknown": {
        "EQ": 0.50, "Dynamics": 0.40, "Ambience": 0.30, "Utility": 0.30,
    },
}

ROLE_WEIGHTS = [
    ("Vocal", 0.20), ("Drums", 0.20), ("Bass", 0.15), ("Guitar", 0.12),
    ("Keys", 0.15), ("FX", 0.08), ("Unknown", 0.10),
]

# Canonical chain ordering for generated devices (cosmetic; the model is
# order-agnostic).
_FAMILY_ORDER = [
    "Instrument", "MIDI Effect", "EQ", "Dynamics", "Pitch",
    "Saturation", "Modulation", "Ambience", "Utility",
]


# ---------------------------------------------------------------------------
# Synthetic corpus
# ---------------------------------------------------------------------------

def generate_synthetic_corpus(
    n_sessions: int = DEFAULT_N_SESSIONS, seed: int = DEFAULT_SEED
) -> list[ProjectState]:
    """Generate a seeded corpus of minimal synthetic sessions.

    Sessions contain only tracks with role labels and device chains — the
    parts the masked-family prediction task needs. Deterministic under seed.
    """
    rng = random.Random(seed)
    roles = [r for r, _ in ROLE_WEIGHTS]
    weights = [w for _, w in ROLE_WEIGHTS]

    sessions: list[ProjectState] = []
    for session_index in range(n_sessions):
        n_tracks = rng.randint(4, 10)
        tracks: list[TrackState] = []
        for track_index in range(n_tracks):
            role = rng.choices(roles, weights=weights, k=1)[0]
            if role == "Keys":
                track_type = "midi" if rng.random() < 0.7 else "audio"
            elif role == "Unknown":
                track_type = "midi" if rng.random() < 0.2 else "audio"
            else:
                track_type = "audio"

            track_id = f"s{session_index}-t{track_index}"
            families: list[str] = []
            if track_type == "midi":
                if rng.random() < 0.95:
                    families.append("Instrument")
                if rng.random() < 0.30:
                    families.append("MIDI Effect")
            for family, prob in ROLE_CHAIN_PRIORS[role].items():
                if rng.random() < prob:
                    families.append(family)
            families.sort(key=_FAMILY_ORDER.index)

            devices = [
                DeviceState(
                    id=f"{track_id}-d{device_index}",
                    track_id=track_id,
                    index=device_index,
                    name=rng.choice(FAMILY_DEVICE_NAMES[family]),
                    device_family=family,
                )
                for device_index, family in enumerate(families)
            ]
            tracks.append(
                TrackState(
                    id=track_id,
                    index=track_index,
                    name=f"{role} {track_index + 1}",
                    track_type=track_type,
                    role=role,
                    devices=devices,
                )
            )
        sessions.append(
            ProjectState(
                project_name=f"synthetic-session-{session_index}",
                tracks=tracks,
                metadata={"source": "synthetic corpus", "seed": seed},
            )
        )
    return sessions


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def _track_families(track: TrackState) -> list[str]:
    """Distinct chain families present on a track (classified from names)."""
    families = []
    for device in track.devices:
        family = device.device_family or classify_device_family(device.name)
        if family in CHAIN_FAMILIES and family not in families:
            families.append(family)
    return families


class ChainFamilyModel:
    """Interpretable conditional baseline for masked device-family prediction.

    score(f | role, type, context) =
        log P(f | role, type) + sum_{c in context} log lift(f, c)

    where P is a Laplace-smoothed frequency and lift is pairwise
    co-occurrence relative to independence. Every term is a named count.
    """

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.n_tracks = 0
        self.condition_counts: Counter[tuple[str, str]] = Counter()
        self.condition_family_counts: Counter[tuple[str, str, str]] = Counter()
        self.family_counts: Counter[str] = Counter()
        self.pair_counts: Counter[tuple[str, str]] = Counter()

    def fit(self, sessions: list[ProjectState]) -> "ChainFamilyModel":
        for session in sessions:
            for track in session.tracks:
                role = track.role or "Unknown"
                families = _track_families(track)
                if not families:
                    continue
                self.n_tracks += 1
                condition = (role, track.track_type)
                self.condition_counts[condition] += 1
                for family in families:
                    self.condition_family_counts[(role, track.track_type, family)] += 1
                    self.family_counts[family] += 1
                for i, fam_a in enumerate(families):
                    for fam_b in families[i + 1:]:
                        key = tuple(sorted((fam_a, fam_b)))
                        self.pair_counts[key] += 1
        return self

    def family_probability(self, role: str, track_type: str, family: str) -> float:
        """Smoothed P(family present | role, track_type)."""
        denominator = self.condition_counts[(role, track_type)] + 2 * self.alpha
        numerator = self.condition_family_counts[(role, track_type, family)] + self.alpha
        return numerator / denominator

    def _lift(self, family_a: str, family_b: str) -> float:
        if self.n_tracks == 0:
            return 1.0
        p_a = (self.family_counts[family_a] + self.alpha) / (self.n_tracks + self.alpha)
        p_b = (self.family_counts[family_b] + self.alpha) / (self.n_tracks + self.alpha)
        key = tuple(sorted((family_a, family_b)))
        p_ab = (self.pair_counts[key] + self.alpha) / (self.n_tracks + self.alpha)
        return p_ab / (p_a * p_b)

    def score_families(
        self, role: str, track_type: str, context_families: list[str]
    ) -> list[tuple[str, float]]:
        """Rank candidate families for a masked chain slot, highest first.

        Families already present in the context are excluded — the masked
        slot holds a family distinct from the observed rest of the chain.
        """
        scores = []
        for family in CHAIN_FAMILIES:
            if family in context_families:
                continue
            score = math.log(self.family_probability(role, track_type, family))
            for context_family in context_families:
                score += math.log(max(self._lift(family, context_family), 1e-9))
            scores.append((family, score))
        return sorted(scores, key=lambda item: -item[1])


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _masked_examples(sessions: list[ProjectState]):
    for session in sessions:
        for track in session.tracks:
            families = _track_families(track)
            if len(families) < 2:
                continue
            role = track.role or "Unknown"
            for target in families:
                context = [f for f in families if f != target]
                yield role, track.track_type, context, target


def evaluate_masked_prediction(
    model: ChainFamilyModel, sessions: list[ProjectState]
) -> dict:
    """hit@1 / hit@3 on masked-family prediction vs a frequency baseline."""
    frequency_ranking = [f for f, _ in model.family_counts.most_common()] or CHAIN_FAMILIES

    n = model_hit1 = model_hit3 = base_hit1 = base_hit3 = 0
    for role, track_type, context, target in _masked_examples(sessions):
        n += 1
        ranked = [f for f, _ in model.score_families(role, track_type, context)]
        if ranked[0] == target:
            model_hit1 += 1
        if target in ranked[:3]:
            model_hit3 += 1
        baseline = [f for f in frequency_ranking if f not in context] or frequency_ranking
        if baseline[0] == target:
            base_hit1 += 1
        if target in baseline[:3]:
            base_hit3 += 1

    if n == 0:
        return {"n_examples": 0}
    return {
        "n_examples": n,
        "model_hit_at_1": round(model_hit1 / n, 4),
        "model_hit_at_3": round(model_hit3 / n, 4),
        "baseline_hit_at_1": round(base_hit1 / n, 4),
        "baseline_hit_at_3": round(base_hit3 / n, 4),
    }


def train_and_evaluate(
    n_sessions: int = DEFAULT_N_SESSIONS, seed: int = DEFAULT_SEED
) -> tuple[ChainFamilyModel, dict]:
    """Train on 80% of a synthetic corpus, evaluate on the held-out 20%."""
    corpus = generate_synthetic_corpus(n_sessions=n_sessions, seed=seed)
    split = int(len(corpus) * 0.8)
    model = ChainFamilyModel().fit(corpus[:split])
    metrics = evaluate_masked_prediction(model, corpus[split:])
    metrics["n_train_sessions"] = split
    metrics["n_test_sessions"] = len(corpus) - split
    metrics["corpus"] = "synthetic (seeded role-conditioned priors)"
    return model, metrics


# ---------------------------------------------------------------------------
# Chain-gap prediction on a real session state
# ---------------------------------------------------------------------------

def predict_chain_gaps(
    project: ProjectState,
    model: ChainFamilyModel,
    probability_threshold: float = 0.6,
) -> list[Recommendation]:
    """Surface predicted-but-absent chain families as data-grounded suggestions.

    A family is suggested for a track when its corpus probability given the
    track's role and type exceeds the threshold and the chain does not
    contain it. Clearly labeled as trained on synthetic data.
    """
    recommendations: list[Recommendation] = []
    for track in project.tracks:
        role = track.role or "Unknown"
        if role not in ROLE_CHAIN_PRIORS and role != "Unknown":
            role = "Unknown"
        present = _track_families(track)
        for family in CHAIN_FAMILIES:
            if family in present:
                continue
            if family in ("Instrument", "MIDI Effect") and track.track_type != "midi":
                continue
            probability = model.family_probability(role, track.track_type, family)
            if probability < probability_threshold:
                continue
            recommendations.append(
                Recommendation(
                    id=f"rec-predicted-gap-{track.id}-{family.lower().replace(' ', '-')}",
                    title=f"Predicted chain stage: {family} is common on similar tracks.",
                    severity="info",
                    confidence=round(min(probability, 0.85), 2),
                    related_node_ids=[track.id],
                    explanation=(
                        f"In the synthetic training corpus, {probability:.0%} of "
                        f"'{role}'-role {track.track_type} tracks include a "
                        f"{family}-family device; the chain on '{track.name}' "
                        "does not show one."
                    ),
                    suggested_action=(
                        f"A possible workflow check is to confirm whether a "
                        f"{family} stage is handled elsewhere (group, return, "
                        "upstream) or intentionally omitted."
                    ),
                    caveat=(
                        "Learned from a synthetic corpus — a proof-of-concept "
                        "for DAW-state prediction, not a claim about your mix."
                    ),
                )
            )
    return recommendations


def prediction_table(project: ProjectState, model: ChainFamilyModel) -> list[dict]:
    """Per-track predicted-vs-observed summary for UI tables."""
    rows = []
    for track in project.tracks:
        role = track.role or "Unknown"
        present = _track_families(track)
        gaps = [
            (family, model.family_probability(role, track.track_type, family))
            for family in CHAIN_FAMILIES
            if family not in present
            and not (family in ("Instrument", "MIDI Effect") and track.track_type != "midi")
        ]
        gaps.sort(key=lambda item: -item[1])
        rows.append(
            {
                "track": track.name,
                "role": role,
                "type": track.track_type,
                "observed_families": ", ".join(present) or "—",
                "top_predicted_missing": ", ".join(
                    f"{family} ({probability:.0%})" for family, probability in gaps[:3]
                ),
            }
        )
    return rows
