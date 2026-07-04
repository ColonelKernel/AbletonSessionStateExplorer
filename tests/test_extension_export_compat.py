"""Compatibility of Session State Exporter (Live extension) output.

The extension emits ProjectState-schema JSON with device_family and track
role left null (they are explorer-side heuristics, not DAW facts) and mixer
values recorded raw in raw_source rather than guessed into dB fields. These
tests pin the contract: such payloads validate, get backfilled, and drive
the full graph + recommendation pipeline.
"""

from ableton_session_state_explorer.graph_builder import build_session_graph
from ableton_session_state_explorer.models import validate_project_dict
from ableton_session_state_explorer.recommendations import generate_recommendations

# Shaped exactly like the extension's output (see
# extension/session-state-exporter/src/extension.ts).
EXTENSION_EXPORT = {
    "schema_version": "0.1.0",
    "project_name": "Live Set (Extensions SDK export)",
    "tempo": 122.0,
    "time_signature": None,
    "scenes": [{"id": "scene-0", "index": 0, "name": None, "tempo": None}],
    "tracks": [
        {
            "id": "track-101",
            "index": 0,
            "name": "Lead Vocal",
            "track_type": "audio",
            "role": None,
            "color": None,
            "volume_db": None,
            "pan": 0.0,
            "mute": False,
            "solo": False,
            "armed": True,
            "clips": [
                {
                    "id": "clip-201",
                    "track_id": "track-101",
                    "scene_id": "scene-0",
                    "name": "Vox Take 3",
                    "clip_type": "audio",
                    "start_time_beats": None,
                    "length_beats": 16.0,
                    "warp_enabled": True,
                    "audio_file": "/samples/vox.wav",
                    "raw_source": {"handle_id": "201", "from_arrangement": False},
                }
            ],
            "devices": [
                {
                    "id": "device-301",
                    "track_id": "track-101",
                    "index": 0,
                    "name": "Reverb",
                    "device_type": "device",
                    "device_family": None,
                    "enabled": None,
                    "parameters": [
                        {
                            "id": "param-401",
                            "device_id": "device-301",
                            "name": "Dry/Wet",
                            "value": 0.3,
                            "normalized_value": 0.3,
                            "unit": None,
                            "is_automated": None,
                            "is_visible_to_host": True,
                        }
                    ],
                    "raw_source": {"handle_id": "301", "parameter_count": 1},
                }
            ],
            "sends": [],
            "group_id": None,
            "raw_source": {"handle_id": "101", "mixer_volume_raw": 0.85},
        }
    ],
    "return_tracks": [
        {"id": "return-1", "index": 0, "name": "A-Reverb", "devices": [], "volume_db": None}
    ],
    "master_track": {
        "id": "master-1",
        "name": "Main",
        "devices": [
            {
                "id": "device-901",
                "track_id": "master-1",
                "index": 0,
                "name": "Limiter",
                "device_family": None,
                "parameters": [],
            }
        ],
        "volume_db": None,
    },
    "warnings": ["Exported through the Ableton Extensions SDK (API 1.0.0)."],
    "metadata": {"source": "ableton-extensions-sdk", "daw_dialect": "ableton-style"},
}


def test_extension_export_validates_and_backfills():
    project = validate_project_dict(EXTENSION_EXPORT)
    track = project.tracks[0]
    assert track.role == "Vocal"
    assert track.devices[0].device_family == "Ambience"
    assert project.master_track.devices[0].device_family == "Dynamics"
    # Raw mixer observations survive untouched.
    assert track.raw_source["mixer_volume_raw"] == 0.85
    assert track.volume_db is None


def test_extension_export_drives_graph_and_rules():
    project = validate_project_dict(EXTENSION_EXPORT)
    graph = build_session_graph(project)
    assert graph.number_of_nodes() > 5

    titles = [r.title for r in generate_recommendations(project)]
    # Vocal track with only a Reverb: corrective-chain rule must fire, which
    # requires the backfilled role and family.
    assert "Vocal track may benefit from a clearer corrective chain." in titles
    # Return track exists, no sends: unused-returns rule must fire.
    assert "Return tracks are defined but not used." in titles


def test_explicit_families_are_not_overwritten():
    payload = {
        "project_name": "Dialect Test",
        "tracks": [
            {
                "id": "t1", "index": 0, "name": "Vox", "track_type": "audio",
                "devices": [
                    {
                        "id": "d1", "track_id": "t1", "index": 0,
                        "name": "REVerence", "device_family": "Ambience",
                        "parameters": [],
                    }
                ],
            }
        ],
    }
    project = validate_project_dict(payload)
    assert project.tracks[0].devices[0].device_family == "Ambience"
