"""Structural diff between two session states.

Answers "what changed between versions?" at the level producers act on:
tracks, device chains, sends, returns, tempo — plus graph-size deltas.
Tracks are matched by case-insensitive name (ids are not assumed stable
across versions; renames therefore appear as remove + add, which the
narrative states explicitly as a limitation).
"""

from __future__ import annotations

from collections import Counter

from .graph_builder import build_session_graph
from .models import ProjectState, TrackState


def _device_names(track: TrackState) -> Counter:
    return Counter(device.name for device in track.devices)


def _send_targets(track: TrackState, project: ProjectState) -> Counter:
    """Sends of a track, expressed as target return-track names."""
    return_names = {r.id: r.name for r in project.return_tracks}
    return Counter(
        return_names.get(send.target_return_id, send.target_return_id)
        for send in track.sends
        if send.enabled is not False
    )


def diff_projects(base: ProjectState, revised: ProjectState) -> dict:
    """Compute a structural diff and a human-readable narrative."""
    narrative: list[str] = []

    tempo_change = None
    if base.tempo != revised.tempo:
        tempo_change = {"base": base.tempo, "revised": revised.tempo}
        narrative.append(f"Tempo changed from {base.tempo} to {revised.tempo} BPM.")

    base_tracks = {t.name.lower(): t for t in base.tracks}
    revised_tracks = {t.name.lower(): t for t in revised.tracks}

    tracks_added = [
        revised_tracks[k].name for k in revised_tracks if k not in base_tracks
    ]
    tracks_removed = [
        base_tracks[k].name for k in base_tracks if k not in revised_tracks
    ]
    for name in tracks_added:
        narrative.append(f"Track added: '{name}'.")
    for name in tracks_removed:
        narrative.append(f"Track removed: '{name}'.")

    track_changes: list[dict] = []
    for key in sorted(set(base_tracks) & set(revised_tracks)):
        old, new = base_tracks[key], revised_tracks[key]
        devices_added = list((_device_names(new) - _device_names(old)).elements())
        devices_removed = list((_device_names(old) - _device_names(new)).elements())
        sends_added = list(
            (_send_targets(new, revised) - _send_targets(old, base)).elements()
        )
        sends_removed = list(
            (_send_targets(old, base) - _send_targets(new, revised)).elements()
        )
        volume_change = (
            {"base": old.volume_db, "revised": new.volume_db}
            if old.volume_db != new.volume_db
            else None
        )
        clip_count_change = (
            {"base": len(old.clips), "revised": len(new.clips)}
            if len(old.clips) != len(new.clips)
            else None
        )
        if not any(
            [devices_added, devices_removed, sends_added, sends_removed,
             volume_change, clip_count_change]
        ):
            continue
        track_changes.append(
            {
                "track": new.name,
                "devices_added": devices_added,
                "devices_removed": devices_removed,
                "sends_added": sends_added,
                "sends_removed": sends_removed,
                "volume_db_change": volume_change,
                "clip_count_change": clip_count_change,
            }
        )
        parts = []
        if devices_added:
            parts.append("added " + ", ".join(devices_added))
        if devices_removed:
            parts.append("removed " + ", ".join(devices_removed))
        if sends_added:
            parts.append("new send to " + ", ".join(sends_added))
        if sends_removed:
            parts.append("send removed to " + ", ".join(sends_removed))
        if volume_change:
            parts.append(
                f"volume {volume_change['base']} → {volume_change['revised']} dB"
            )
        if clip_count_change:
            parts.append(
                f"clips {clip_count_change['base']} → {clip_count_change['revised']}"
            )
        narrative.append(f"'{new.name}': " + "; ".join(parts) + ".")

    base_returns = Counter(r.name for r in base.return_tracks)
    revised_returns = Counter(r.name for r in revised.return_tracks)
    returns_added = list((revised_returns - base_returns).elements())
    returns_removed = list((base_returns - revised_returns).elements())
    for name in returns_added:
        narrative.append(f"Return track added: '{name}'.")
    for name in returns_removed:
        narrative.append(f"Return track removed: '{name}'.")

    def _master_devices(project: ProjectState) -> Counter:
        if project.master_track is None:
            return Counter()
        return Counter(d.name for d in project.master_track.devices)

    master_added = list((_master_devices(revised) - _master_devices(base)).elements())
    master_removed = list((_master_devices(base) - _master_devices(revised)).elements())
    if master_added:
        narrative.append("Master chain added: " + ", ".join(master_added) + ".")
    if master_removed:
        narrative.append("Master chain removed: " + ", ".join(master_removed) + ".")

    base_graph = build_session_graph(base)
    revised_graph = build_session_graph(revised)
    stats = {
        "base_nodes": base_graph.number_of_nodes(),
        "revised_nodes": revised_graph.number_of_nodes(),
        "base_edges": base_graph.number_of_edges(),
        "revised_edges": revised_graph.number_of_edges(),
    }

    if not narrative:
        narrative.append("No structural differences detected.")

    return {
        "base_project": base.project_name,
        "revised_project": revised.project_name,
        "tempo_change": tempo_change,
        "tracks_added": tracks_added,
        "tracks_removed": tracks_removed,
        "track_changes": track_changes,
        "returns_added": returns_added,
        "returns_removed": returns_removed,
        "master_devices_added": master_added,
        "master_devices_removed": master_removed,
        "graph_stats": stats,
        "narrative": narrative,
        "caveats": [
            "Tracks are matched by name; a renamed track appears as a "
            "removal plus an addition.",
            "Parameter-level changes are not diffed in v0.1.",
        ],
    }
