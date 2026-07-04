"""Built-in Cubase-style demo session.

A second dialect instantiation of the DAW-agnostic session model (see
docs/cubase_mapping.md). Differences from the Ableton-style demo that are
dialect-typical rather than cosmetic:

* no scenes — Cubase has a linear Arranger, not a session grid, so clips
  carry ``start_time_beats`` instead of scene assignments;
* return tracks read as **FX Channel Tracks**, and sends are actually wired
  (the FX-channel workflow is idiomatic in Cubase);
* devices carry Cubase plug-in names with an **explicit** ``device_family``,
  demonstrating that a dialect can ship its own family mapping instead of
  relying on keyword classification (``REVerence`` and ``Magneto`` would not
  keyword-classify).

The session is intentionally *tidier* than the Ableton-style demo: with
sends routed and vocal chains carrying corrective stages, most heuristic
rules stay quiet — a useful contrast when demonstrating that the
recommendation engine reacts to structure, not to session size.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    ClipState,
    DeviceParameterState,
    DeviceState,
    MasterTrackState,
    ProjectState,
    ReturnTrackState,
    SendState,
    TrackState,
)
from .utils import classify_track_role

CUBASE_DEMO_SESSION_NAME = "Alt-Pop Mix Bus (Cubase-style)"


def _device(
    device_id: str,
    track_id: str,
    index: int,
    name: str,
    family: str,
    device_type: str = "audio_effect",
    parameters: Optional[list[tuple[str, float, str]]] = None,
) -> DeviceState:
    """Build a DeviceState with an explicit (dialect-supplied) family."""
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
        device_family=family,
        enabled=True,
        parameters=params,
    )


def build_cubase_demo_session() -> ProjectState:
    """Build the built-in Cubase-style demo session."""
    tracks: list[TrackState] = []

    drums_id = "c-track-1"
    tracks.append(
        TrackState(
            id=drums_id, index=0, name="Drums", track_type="audio",
            role=classify_track_role("Drums"), color="#C44536",
            volume_db=-3.5, pan=0.0,
            clips=[
                ClipState(
                    id="c-clip-1", track_id=drums_id, name="Drums 01",
                    clip_type="audio", start_time_beats=0.0, length_beats=128.0,
                    audio_file="audio/drums_01.wav",
                ),
            ],
            devices=[
                _device("c-device-1", drums_id, 0, "Frequency", "EQ",
                        parameters=[("Band 1 Freq", 50.0, "Hz")]),
                _device("c-device-2", drums_id, 1, "Compressor", "Dynamics",
                        parameters=[("Ratio", 3.0, ":1")]),
                _device("c-device-3", drums_id, 2, "Magneto II", "Saturation",
                        parameters=[("Saturation", 40.0, "%")]),
            ],
        )
    )

    bass_id = "c-track-2"
    tracks.append(
        TrackState(
            id=bass_id, index=1, name="Bass", track_type="audio",
            role=classify_track_role("Bass"), color="#6B3FA0",
            volume_db=-5.0, pan=0.0,
            clips=[
                ClipState(
                    id="c-clip-2", track_id=bass_id, name="Bass 01",
                    clip_type="audio", start_time_beats=16.0, length_beats=112.0,
                    audio_file="audio/bass_01.wav",
                ),
            ],
            devices=[
                _device("c-device-4", bass_id, 0, "Frequency", "EQ"),
                _device("c-device-5", bass_id, 1, "VintageCompressor", "Dynamics"),
            ],
        )
    )

    gtr_id = "c-track-3"
    tracks.append(
        TrackState(
            id=gtr_id, index=2, name="Gtr Wide", track_type="audio",
            role=classify_track_role("Gtr Wide"), color="#2E86AB",
            volume_db=-7.0, pan=-0.25,
            clips=[
                ClipState(
                    id="c-clip-3", track_id=gtr_id, name="Gtr L+R",
                    clip_type="audio", start_time_beats=32.0, length_beats=96.0,
                    audio_file="audio/gtr_wide.wav",
                ),
            ],
            devices=[
                _device("c-device-6", gtr_id, 0, "Frequency", "EQ"),
                _device("c-device-7", gtr_id, 1, "Squasher", "Dynamics"),
            ],
            sends=[
                SendState(
                    id="c-send-1", source_track_id=gtr_id,
                    target_return_id="c-fx-2", send_name="FX 2 — PingPongDelay",
                    level_db=-15.0, enabled=True,
                ),
            ],
        )
    )

    pad_id = "c-track-4"
    tracks.append(
        TrackState(
            id=pad_id, index=3, name="Synth Pad", track_type="midi",
            role=classify_track_role("Synth Pad"), color="#3FB07F",
            volume_db=-9.0, pan=0.1,
            clips=[
                ClipState(
                    id="c-clip-4", track_id=pad_id, name="Pad Part",
                    clip_type="midi", start_time_beats=0.0, length_beats=128.0,
                    midi_note_count=96,
                ),
            ],
            devices=[
                _device("c-device-8", pad_id, 0, "Retrologue", "Instrument",
                        device_type="instrument",
                        parameters=[("Osc 1 Shape", 0.5, "")]),
                _device("c-device-9", pad_id, 1, "StudioChorus", "Modulation"),
            ],
            sends=[
                SendState(
                    id="c-send-2", source_track_id=pad_id,
                    target_return_id="c-fx-1", send_name="FX 1 — REVerence",
                    level_db=-18.0, enabled=True,
                ),
            ],
        )
    )

    vox_id = "c-track-5"
    tracks.append(
        TrackState(
            id=vox_id, index=4, name="Lead Vox", track_type="audio",
            role=classify_track_role("Lead Vox"), color="#D4A017",
            volume_db=-2.5, pan=0.0,
            clips=[
                ClipState(
                    id="c-clip-5", track_id=vox_id, name="Lead Vox Comp",
                    clip_type="audio", start_time_beats=16.0, length_beats=112.0,
                    audio_file="audio/lead_vox_comp.wav",
                ),
            ],
            devices=[
                _device("c-device-10", vox_id, 0, "StudioEQ", "EQ",
                        parameters=[("HP Freq", 85.0, "Hz")]),
                _device("c-device-11", vox_id, 1, "DeEsser", "Dynamics",
                        parameters=[("Reduction", 4.0, "dB")]),
                _device("c-device-12", vox_id, 2, "Tube Compressor", "Dynamics"),
            ],
            sends=[
                SendState(
                    id="c-send-3", source_track_id=vox_id,
                    target_return_id="c-fx-1", send_name="FX 1 — REVerence",
                    level_db=-12.0, enabled=True,
                ),
            ],
        )
    )

    doubles_id = "c-track-6"
    tracks.append(
        TrackState(
            id=doubles_id, index=5, name="Vox Doubles", track_type="audio",
            role=classify_track_role("Vox Doubles"), color="#C97B3D",
            volume_db=-10.0, pan=0.0,
            clips=[
                ClipState(
                    id="c-clip-6", track_id=doubles_id, name="Doubles Chorus",
                    clip_type="audio", start_time_beats=64.0, length_beats=64.0,
                    audio_file="audio/vox_doubles.wav",
                ),
            ],
            devices=[
                _device("c-device-13", doubles_id, 0, "StudioEQ", "EQ"),
                _device("c-device-14", doubles_id, 1, "Compressor", "Dynamics"),
            ],
            sends=[
                SendState(
                    id="c-send-4", source_track_id=doubles_id,
                    target_return_id="c-fx-1", send_name="FX 1 — REVerence",
                    level_db=-10.0, enabled=True,
                ),
            ],
        )
    )

    return_tracks = [
        ReturnTrackState(
            id="c-fx-1", index=0, name="FX 1 — REVerence", volume_db=0.0,
            devices=[
                _device("c-device-15", "c-fx-1", 0, "REVerence", "Ambience",
                        parameters=[("Reverb Time", 2.4, "s")]),
            ],
        ),
        ReturnTrackState(
            id="c-fx-2", index=1, name="FX 2 — PingPongDelay", volume_db=0.0,
            devices=[
                _device("c-device-16", "c-fx-2", 0, "PingPongDelay", "Ambience",
                        parameters=[("Delay", 0.375, "beats")]),
            ],
        ),
    ]

    master_track = MasterTrackState(
        id="c-master-1",
        name="Stereo Out",
        volume_db=0.0,
        devices=[
            _device("c-device-17", "c-master-1", 0, "Limiter", "Dynamics",
                    parameters=[("Output", -0.3, "dB")]),
            _device("c-device-18", "c-master-1", 1, "SuperVision", "Utility"),
        ],
    )

    return ProjectState(
        project_name=CUBASE_DEMO_SESSION_NAME,
        tempo=104.0,
        time_signature="4/4",
        scenes=[],
        tracks=tracks,
        return_tracks=return_tracks,
        master_track=master_track,
        warnings=[
            "This is a hand-authored demo session, not an imported Cubase project.",
            "Clip audio file paths are placeholders; no audio is bundled.",
        ],
        metadata={
            "source": "built-in demo",
            "daw_dialect": "cubase-style",
            "dialect_notes": [
                "No scenes: Cubase uses a linear Arranger, so clips carry "
                "start_time_beats instead of scene assignments.",
                "Return tracks read as FX Channel Tracks; sends are wired, "
                "as is idiomatic in Cubase.",
                "device_family is supplied explicitly by the dialect rather "
                "than keyword-classified (e.g. REVerence, Magneto II).",
            ],
        },
    )
