"""Built-in Ableton-style demo session and session fingerprinting.

The demo session, "Indie Vocal Production Sketch", is a hand-authored
Ableton-style session state. It intentionally includes a few heuristic
workflow issues (individual reverbs instead of shared returns, unused return
tracks, a vocal track without corrective devices, a dense drum chain, and a
master limiter without loudness context) so the recommendation engine has
observable structure to reason about.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    AudioDescriptorSet,
    ClipState,
    DeviceParameterState,
    DeviceState,
    MasterTrackState,
    ProjectState,
    ReturnTrackState,
    SceneState,
    TrackState,
)
from .utils import (
    AMBIENCE_KEYWORDS,
    LIMITER_KEYWORDS,
    classify_device_family,
    classify_track_role,
)

DEMO_SESSION_NAME = "Indie Vocal Production Sketch"


def _device(
    device_id: str,
    track_id: str,
    index: int,
    name: str,
    device_type: str = "audio_effect",
    parameters: Optional[list[tuple[str, float, str]]] = None,
) -> DeviceState:
    """Build a DeviceState with family classification and optional parameters."""
    params = [
        DeviceParameterState(
            id=f"{device_id}-param-{i + 1}",
            device_id=device_id,
            name=param_name,
            value=value,
            normalized_value=None,
            unit=unit,
            is_automated=False,
            is_visible_to_host=True,
        )
        for i, (param_name, value, unit) in enumerate(parameters or [])
    ]
    return DeviceState(
        id=device_id,
        track_id=track_id,
        index=index,
        name=name,
        device_type=device_type,
        device_family=classify_device_family(name),
        enabled=True,
        parameters=params,
    )


def build_demo_session() -> ProjectState:
    """Build the built-in 'Indie Vocal Production Sketch' demo session."""
    scenes = [
        SceneState(id="scene-1", index=0, name="Intro"),
        SceneState(id="scene-2", index=1, name="Verse"),
        SceneState(id="scene-3", index=2, name="Chorus"),
    ]

    tracks: list[TrackState] = []

    # -- Drums (intentionally dense device chain: 7 devices) --------------
    drums_id = "track-1"
    tracks.append(
        TrackState(
            id=drums_id,
            index=0,
            name="Drums",
            track_type="audio",
            role=classify_track_role("Drums"),
            color="#E5573F",
            volume_db=-3.0,
            pan=0.0,
            clips=[
                ClipState(
                    id="clip-1", track_id=drums_id, scene_id="scene-1",
                    name="Drums Intro", clip_type="audio", length_beats=16.0,
                    warp_enabled=True, audio_file="audio/drums_intro.wav",
                ),
                ClipState(
                    id="clip-2", track_id=drums_id, scene_id="scene-2",
                    name="Drums Verse", clip_type="audio", length_beats=32.0,
                    warp_enabled=True, audio_file="audio/drums_verse.wav",
                ),
                ClipState(
                    id="clip-3", track_id=drums_id, scene_id="scene-3",
                    name="Drums Chorus", clip_type="audio", length_beats=32.0,
                    warp_enabled=True, audio_file="audio/drums_chorus.wav",
                ),
            ],
            devices=[
                _device("device-1", drums_id, 0, "EQ Eight",
                        parameters=[("Low Cut Freq", 45.0, "Hz")]),
                _device("device-2", drums_id, 1, "Compressor",
                        parameters=[("Ratio", 4.0, ":1"), ("Threshold", -18.0, "dB")]),
                _device("device-3", drums_id, 2, "Glue Compressor",
                        parameters=[("Makeup", 2.0, "dB")]),
                _device("device-4", drums_id, 3, "Saturator",
                        parameters=[("Drive", 6.0, "dB")]),
                _device("device-5", drums_id, 4, "Gate"),
                _device("device-6", drums_id, 5, "Utility",
                        parameters=[("Gain", 0.0, "dB")]),
                _device("device-7", drums_id, 6, "Limiter"),
            ],
        )
    )

    # -- Bass --------------------------------------------------------------
    bass_id = "track-2"
    tracks.append(
        TrackState(
            id=bass_id,
            index=1,
            name="Bass",
            track_type="audio",
            role=classify_track_role("Bass"),
            color="#7A3FE5",
            volume_db=-4.5,
            pan=0.0,
            clips=[
                ClipState(
                    id="clip-4", track_id=bass_id, scene_id="scene-2",
                    name="Bass Verse", clip_type="audio", length_beats=32.0,
                    warp_enabled=True, audio_file="audio/bass_verse.wav",
                ),
                ClipState(
                    id="clip-5", track_id=bass_id, scene_id="scene-3",
                    name="Bass Chorus", clip_type="audio", length_beats=32.0,
                    warp_enabled=True, audio_file="audio/bass_chorus.wav",
                ),
            ],
            devices=[
                _device("device-8", bass_id, 0, "EQ Eight"),
                _device("device-9", bass_id, 1, "Compressor",
                        parameters=[("Ratio", 3.0, ":1")]),
                _device("device-10", bass_id, 2, "Saturator"),
            ],
        )
    )

    # -- Guitar (individual Echo: ambience-on-track issue) ------------------
    guitar_id = "track-3"
    tracks.append(
        TrackState(
            id=guitar_id,
            index=2,
            name="Guitar",
            track_type="audio",
            role=classify_track_role("Guitar"),
            color="#3FA0E5",
            volume_db=-6.0,
            pan=-0.2,
            clips=[
                ClipState(
                    id="clip-6", track_id=guitar_id, scene_id="scene-2",
                    name="Guitar Verse", clip_type="audio", length_beats=32.0,
                    warp_enabled=False, audio_file="audio/guitar_verse.wav",
                ),
                ClipState(
                    id="clip-7", track_id=guitar_id, scene_id="scene-3",
                    name="Guitar Chorus", clip_type="audio", length_beats=32.0,
                    warp_enabled=False, audio_file="audio/guitar_chorus.wav",
                ),
            ],
            devices=[
                _device("device-11", guitar_id, 0, "EQ Eight"),
                _device("device-12", guitar_id, 1, "Echo",
                        parameters=[("Feedback", 35.0, "%")]),
            ],
        )
    )

    # -- Synth Keys (MIDI) ---------------------------------------------------
    keys_id = "track-4"
    tracks.append(
        TrackState(
            id=keys_id,
            index=3,
            name="Synth Keys",
            track_type="midi",
            role=classify_track_role("Synth Keys"),
            color="#3FE5A0",
            volume_db=-8.0,
            pan=0.15,
            clips=[
                ClipState(
                    id="clip-8", track_id=keys_id, scene_id="scene-1",
                    name="Keys Intro Pad", clip_type="midi", length_beats=16.0,
                    midi_note_count=24,
                ),
                ClipState(
                    id="clip-9", track_id=keys_id, scene_id="scene-3",
                    name="Keys Chorus Stabs", clip_type="midi", length_beats=32.0,
                    midi_note_count=64,
                ),
            ],
            devices=[
                _device("device-13", keys_id, 0, "Wavetable",
                        device_type="instrument",
                        parameters=[("Osc 1 Position", 0.4, "")]),
                _device("device-14", keys_id, 1, "Chorus", device_type="audio_effect"),
            ],
        )
    )

    # -- Lead Vocal (individual Reverb: ambience-on-track issue) --------------
    lead_vox_id = "track-5"
    tracks.append(
        TrackState(
            id=lead_vox_id,
            index=4,
            name="Lead Vocal",
            track_type="audio",
            role=classify_track_role("Lead Vocal"),
            color="#E5C33F",
            volume_db=-2.0,
            pan=0.0,
            clips=[
                ClipState(
                    id="clip-10", track_id=lead_vox_id, scene_id="scene-2",
                    name="Lead Vox Verse", clip_type="audio", length_beats=32.0,
                    warp_enabled=True, audio_file="audio/lead_vox_verse.wav",
                ),
                ClipState(
                    id="clip-11", track_id=lead_vox_id, scene_id="scene-3",
                    name="Lead Vox Chorus", clip_type="audio", length_beats=32.0,
                    warp_enabled=True, audio_file="audio/lead_vox_chorus.wav",
                ),
            ],
            devices=[
                _device("device-15", lead_vox_id, 0, "EQ Eight",
                        parameters=[("High Pass Freq", 90.0, "Hz")]),
                _device("device-16", lead_vox_id, 1, "Compressor",
                        parameters=[("Ratio", 4.0, ":1")]),
                # Note: no de-esser-like device on the lead vocal chain.
                _device("device-17", lead_vox_id, 2, "Reverb",
                        parameters=[("Decay Time", 2.1, "s")]),
            ],
        )
    )

    # -- Backing Vocals (no corrective chain at all: Rule 2 target) ------------
    bgv_id = "track-6"
    tracks.append(
        TrackState(
            id=bgv_id,
            index=5,
            name="Backing Vocals",
            track_type="audio",
            role=classify_track_role("Backing Vocals"),
            color="#E58C3F",
            volume_db=-9.0,
            pan=0.3,
            clips=[
                ClipState(
                    id="clip-12", track_id=bgv_id, scene_id="scene-3",
                    name="BGV Chorus", clip_type="audio", length_beats=32.0,
                    warp_enabled=True, audio_file="audio/bgv_chorus.wav",
                ),
            ],
            devices=[
                # Only ambience — no EQ, dynamics, or de-essing stage.
                _device("device-18", bgv_id, 0, "Reverb",
                        parameters=[("Decay Time", 3.4, "s")]),
            ],
        )
    )

    # -- Return tracks (defined but unused: no track has sends) ----------------
    return_tracks = [
        ReturnTrackState(
            id="return-1",
            index=0,
            name="Reverb Return",
            volume_db=0.0,
            devices=[_device("device-19", "return-1", 0, "Reverb",
                             parameters=[("Decay Time", 2.8, "s")])],
        ),
        ReturnTrackState(
            id="return-2",
            index=1,
            name="Delay Return",
            volume_db=0.0,
            devices=[_device("device-20", "return-2", 0, "Echo",
                             parameters=[("Sync Rate", 0.375, "beats")])],
        ),
    ]

    master_track = MasterTrackState(
        id="master-1",
        name="Master",
        volume_db=0.0,
        devices=[
            _device("device-21", "master-1", 0, "Glue Compressor",
                    parameters=[("Makeup", 1.0, "dB")]),
            _device("device-22", "master-1", 1, "Limiter",
                    parameters=[("Ceiling", -0.3, "dB")]),
        ],
    )

    return ProjectState(
        project_name=DEMO_SESSION_NAME,
        tempo=96.0,
        time_signature="4/4",
        scenes=scenes,
        tracks=tracks,
        return_tracks=return_tracks,
        master_track=master_track,
        warnings=[
            "This is a hand-authored demo session, not an imported Live Set.",
            "Clip audio file paths are placeholders; no audio is bundled.",
        ],
        metadata={
            "source": "built-in demo",
            "daw_dialect": "ableton-style",
            "intentional_heuristic_issues": [
                "individual reverbs/echo on tracks instead of shared returns",
                "return tracks defined but no sends assigned",
                "backing vocal track has no corrective devices",
                "lead vocal chain has no de-esser-like device",
                "drum track has a dense (7-device) chain",
                "master limiter present without loudness/mixdown context",
            ],
        },
    )


def build_demo_session_revision() -> ProjectState:
    """Build 'Revision 2' of the demo session — the v0 recommendations enacted.

    The revision applies exactly the workflow changes the heuristic rules
    suggested on the original: corrective stages on the vocal chains,
    per-track ambience consolidated onto the shared returns, and sends wired.
    Diffing it against :func:`build_demo_session` therefore demonstrates the
    full loop — recommendation, action, verifiable state change.
    """
    from .models import SendState  # local import to keep module header tidy

    project = build_demo_session().model_copy(deep=True)
    project.project_name = f"{DEMO_SESSION_NAME} — Revision 2"

    lead = next(t for t in project.tracks if t.id == "track-5")
    bgv = next(t for t in project.tracks if t.id == "track-6")
    guitar = next(t for t in project.tracks if t.id == "track-3")

    # Lead Vocal: add the missing de-esser, move ambience to the shared return.
    lead.devices = [d for d in lead.devices if d.name != "Reverb"]
    lead.devices.append(_device("device-23", lead.id, 2, "De-Esser"))
    lead.sends.append(
        SendState(
            id="send-1", source_track_id=lead.id, target_return_id="return-1",
            send_name="A — Reverb Return", level_db=-12.0, enabled=True,
        )
    )

    # Backing Vocals: give the chain corrective stages, route ambience out.
    bgv.devices = [d for d in bgv.devices if d.name != "Reverb"]
    bgv.devices.insert(0, _device("device-24", bgv.id, 0, "EQ Eight"))
    bgv.devices.insert(1, _device("device-25", bgv.id, 1, "Compressor"))
    bgv.sends.append(
        SendState(
            id="send-2", source_track_id=bgv.id, target_return_id="return-1",
            send_name="A — Reverb Return", level_db=-10.0, enabled=True,
        )
    )

    # Guitar: replace the insert Echo with a send to the delay return.
    guitar.devices = [d for d in guitar.devices if d.name != "Echo"]
    guitar.sends.append(
        SendState(
            id="send-3", source_track_id=guitar.id, target_return_id="return-2",
            send_name="B — Delay Return", level_db=-15.0, enabled=True,
        )
    )

    for track in (lead, bgv, guitar):
        for i, device in enumerate(track.devices):
            device.index = i

    project.metadata = {
        **project.metadata,
        "revision_of": DEMO_SESSION_NAME,
        "revision_notes": [
            "De-esser added to the lead vocal chain (rule 2).",
            "Backing vocal chain gains EQ and compression (rule 2).",
            "Per-track Reverb/Echo removed; ambience consolidated onto the "
            "shared returns via sends (rules 1 and 3).",
        ],
    }
    project.metadata.pop("intentional_heuristic_issues", None)
    return project


# ---------------------------------------------------------------------------
# Session fingerprint
# ---------------------------------------------------------------------------

def compute_session_fingerprint(
    project_state: ProjectState,
    descriptors: Optional[list[AudioDescriptorSet]] = None,
) -> dict:
    """Compute a compact structural fingerprint of a session state.

    The fingerprint summarizes session structure as counts and ratios so two
    sessions can be compared without exchanging full states.
    """
    descriptors = descriptors or []
    tracks = project_state.tracks
    devices = project_state.all_devices()
    sends = project_state.all_sends()

    def _role_count(role: str) -> int:
        return sum(1 for t in tracks if (t.role or "") == role)

    def _family_count(family: str) -> int:
        return sum(1 for d in devices if (d.device_family or "") == family)

    master_devices = project_state.master_track.devices if project_state.master_track else []
    has_master_limiter = any(
        any(kw in d.name.lower() for kw in LIMITER_KEYWORDS) for d in master_devices
    )

    fingerprint: dict = {
        "num_tracks": len(tracks),
        "num_audio_tracks": sum(1 for t in tracks if t.track_type == "audio"),
        "num_midi_tracks": sum(1 for t in tracks if t.track_type == "midi"),
        "num_vocal_like_tracks": _role_count("Vocal"),
        "num_drum_like_tracks": _role_count("Drums"),
        "num_bass_like_tracks": _role_count("Bass"),
        "num_devices": len(devices),
        "num_eq_like_devices": _family_count("EQ"),
        "num_dynamics_like_devices": _family_count("Dynamics"),
        "num_ambience_like_devices": _family_count("Ambience"),
        "num_return_tracks": len(project_state.return_tracks),
        "num_sends": len(sends),
        "avg_devices_per_track": round(len(devices) / len(tracks), 3) if tracks else 0.0,
        "has_master_limiter": has_master_limiter,
    }

    if descriptors:
        rms_values = [d.rms_mean for d in descriptors if d.rms_mean is not None]
        centroids = [
            d.spectral_centroid_mean
            for d in descriptors
            if d.spectral_centroid_mean is not None
        ]
        fingerprint["descriptor_summary"] = {
            "num_descriptor_sets": len(descriptors),
            "rms_mean_avg": round(sum(rms_values) / len(rms_values), 6) if rms_values else None,
            "spectral_centroid_avg": (
                round(sum(centroids) / len(centroids), 2) if centroids else None
            ),
        }

    return fingerprint


_FINGERPRINT_NUMERIC_KEYS = [
    "num_tracks",
    "num_audio_tracks",
    "num_midi_tracks",
    "num_vocal_like_tracks",
    "num_drum_like_tracks",
    "num_bass_like_tracks",
    "num_devices",
    "num_eq_like_devices",
    "num_dynamics_like_devices",
    "num_ambience_like_devices",
    "num_return_tracks",
    "num_sends",
    "avg_devices_per_track",
]


def compare_fingerprints(fp1: dict, fp2: dict) -> float:
    """Cosine similarity between the numeric parts of two fingerprints.

    Returns a value in [0, 1]; 1.0 means structurally identical counts.
    The boolean master-limiter flag is included as 0/1.
    """
    def _vector(fp: dict) -> list[float]:
        vec = [float(fp.get(key, 0) or 0) for key in _FINGERPRINT_NUMERIC_KEYS]
        vec.append(1.0 if fp.get("has_master_limiter") else 0.0)
        return vec

    v1, v2 = _vector(fp1), _vector(fp2)
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return round(dot / (norm1 * norm2), 4)
