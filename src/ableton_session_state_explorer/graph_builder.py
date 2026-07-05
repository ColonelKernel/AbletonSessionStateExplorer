"""Build an interpretable directed graph from an Ableton-style session state.

Node types:
    project, scene, track, clip, audio_file, midi_clip, device, parameter,
    send, return_track, master_track

Edge types:
    contains_scene, contains_track, contains_clip, clip_in_scene,
    uses_audio_file, has_device, has_parameter, sends_to, routes_to_master,
    group_contains, has_return, has_master
"""

from __future__ import annotations

from typing import Any, Optional

import networkx as nx

from .models import DeviceState, ProjectState

NODE_TYPES = [
    "project",
    "scene",
    "track",
    "clip",
    "audio_file",
    "midi_clip",
    "device",
    "parameter",
    "send",
    "return_track",
    "master_track",
]

EDGE_TYPES = [
    "contains_scene",
    "contains_track",
    "contains_clip",
    "clip_in_scene",
    "uses_audio_file",
    "has_device",
    "has_parameter",
    "sends_to",
    "routes_to_master",
    "group_contains",
    "has_return",
    "has_master",
]

PROJECT_NODE_ID = "project"


def _add_device_nodes(
    graph: nx.DiGraph, owner_node_id: str, devices: list[DeviceState]
) -> None:
    for device in devices:
        graph.add_node(
            device.id,
            label=device.name,
            type="device",
            device_family=device.device_family,
            device_type=device.device_type,
            enabled=device.enabled,
            owner_id=owner_node_id,
        )
        graph.add_edge(owner_node_id, device.id, type="has_device")
        for param in device.parameters:
            graph.add_node(
                param.id,
                label=param.name,
                type="parameter",
                value=param.value,
                unit=param.unit,
                is_automated=param.is_automated,
            )
            graph.add_edge(device.id, param.id, type="has_parameter")


def build_session_graph(project_state: ProjectState) -> nx.DiGraph:
    """Convert a ProjectState into a typed directed graph."""
    graph = nx.DiGraph()

    graph.add_node(
        PROJECT_NODE_ID,
        label=project_state.project_name,
        type="project",
        tempo=project_state.tempo,
        time_signature=project_state.time_signature,
    )

    # Scenes ---------------------------------------------------------------
    for scene in project_state.scenes:
        graph.add_node(
            scene.id,
            label=scene.name or f"Scene {scene.index + 1}",
            type="scene",
            index=scene.index,
        )
        graph.add_edge(PROJECT_NODE_ID, scene.id, type="contains_scene")

    # Master ----------------------------------------------------------------
    master = project_state.master_track
    if master:
        graph.add_node(
            master.id,
            label=master.name,
            type="master_track",
            volume_db=master.volume_db,
        )
        graph.add_edge(PROJECT_NODE_ID, master.id, type="has_master")
        _add_device_nodes(graph, master.id, master.devices)

    # Return tracks -----------------------------------------------------------
    for return_track in project_state.return_tracks:
        graph.add_node(
            return_track.id,
            label=return_track.name,
            type="return_track",
            index=return_track.index,
            volume_db=return_track.volume_db,
        )
        graph.add_edge(PROJECT_NODE_ID, return_track.id, type="has_return")
        _add_device_nodes(graph, return_track.id, return_track.devices)
        if master:
            graph.add_edge(return_track.id, master.id, type="routes_to_master")

    # Tracks -------------------------------------------------------------------
    for track in project_state.tracks:
        graph.add_node(
            track.id,
            label=track.name,
            type="track",
            track_type=track.track_type,
            role=track.role,
            index=track.index,
            volume_db=track.volume_db,
            pan=track.pan,
            mute=track.mute,
            solo=track.solo,
            track_color=track.color,
        )
        graph.add_edge(PROJECT_NODE_ID, track.id, type="contains_track")

        if track.group_id:
            # Edge added later once all track nodes exist; record intent now.
            graph.add_edge(track.group_id, track.id, type="group_contains")

        if master and track.track_type not in ("return", "master"):
            graph.add_edge(track.id, master.id, type="routes_to_master")

        # Clips ---------------------------------------------------------------
        for clip in track.clips:
            node_type = "midi_clip" if clip.clip_type == "midi" else "clip"
            graph.add_node(
                clip.id,
                label=clip.name,
                type=node_type,
                clip_type=clip.clip_type,
                length_beats=clip.length_beats,
                warp_enabled=clip.warp_enabled,
                midi_note_count=clip.midi_note_count,
            )
            graph.add_edge(track.id, clip.id, type="contains_clip")
            if clip.scene_id and graph.has_node(clip.scene_id):
                graph.add_edge(clip.id, clip.scene_id, type="clip_in_scene")
            if clip.audio_file:
                file_node_id = f"file:{clip.audio_file}"
                if not graph.has_node(file_node_id):
                    graph.add_node(
                        file_node_id,
                        label=clip.audio_file.split("/")[-1],
                        type="audio_file",
                        path=clip.audio_file,
                    )
                graph.add_edge(clip.id, file_node_id, type="uses_audio_file")

        # Devices --------------------------------------------------------------
        _add_device_nodes(graph, track.id, track.devices)

        # Sends -----------------------------------------------------------------
        for send in track.sends:
            graph.add_node(
                send.id,
                label=send.send_name or f"Send to {send.target_return_id}",
                type="send",
                level_db=send.level_db,
                enabled=send.enabled,
            )
            graph.add_edge(track.id, send.id, type="sends_to")
            if graph.has_node(send.target_return_id):
                graph.add_edge(send.id, send.target_return_id, type="sends_to")

    graph.graph.update(compute_graph_metadata(graph, project_state))
    return graph


def compute_graph_metadata(
    graph: nx.DiGraph, project_state: Optional[ProjectState] = None
) -> dict[str, Any]:
    """Compute graph-level summary metadata."""
    def _count(node_type: str) -> int:
        return sum(1 for _, data in graph.nodes(data=True) if data.get("type") == node_type)

    placeholder_count = 0
    if project_state is not None:
        placeholder_count += len(project_state.warnings)
        # Clip audio references that are placeholders (no real file bundled).
        placeholder_count += sum(
            1 for clip in project_state.all_clips() if clip.audio_file
        )

    return {
        "num_tracks": _count("track"),
        "num_clips": _count("clip") + _count("midi_clip"),
        "num_devices": _count("device"),
        "num_parameters": _count("parameter"),
        "num_sends": _count("send"),
        "num_return_tracks": _count("return_track"),
        "graph_density": round(nx.density(graph), 5) if graph.number_of_nodes() > 1 else 0.0,
        "num_uncertain_or_placeholder_elements": placeholder_count,
    }


def graph_to_dict(graph: nx.DiGraph) -> dict[str, Any]:
    """Serialize the graph to a JSON-friendly dict of nodes, edges, metadata."""
    nodes = []
    for node_id, data in graph.nodes(data=True):
        node = {"id": node_id, "label": data.get("label", node_id), "type": data.get("type")}
        node.update(
            {k: v for k, v in data.items() if k not in ("label", "type") and v is not None}
        )
        nodes.append(node)

    edges = []
    for source, target, data in graph.edges(data=True):
        edge = {"source": source, "target": target, "type": data.get("type")}
        edge.update({k: v for k, v in data.items() if k != "type" and v is not None})
        edges.append(edge)

    return {"nodes": nodes, "edges": edges, "metadata": dict(graph.graph)}


def filter_graph(
    graph: nx.DiGraph,
    show_clips: bool = True,
    show_scenes: bool = True,
    show_devices: bool = True,
    show_parameters: bool = False,
    show_sends_returns: bool = True,
    show_audio_files: bool = True,
    only_track_id: Optional[str] = None,
    structure_only: bool = False,
) -> nx.DiGraph:
    """Return a filtered copy of the graph for display purposes.

    ``structure_only`` keeps only production-structure nodes (project, tracks,
    returns, master, sends). ``only_track_id`` restricts the view to one track
    and everything reachable from it, plus the project and master context.
    """
    hidden_types: set[str] = set()
    if structure_only:
        hidden_types |= {"clip", "midi_clip", "scene", "device", "parameter", "audio_file"}
    else:
        if not show_clips:
            hidden_types |= {"clip", "midi_clip"}
        if not show_scenes:
            hidden_types.add("scene")
        if not show_devices:
            hidden_types |= {"device", "parameter"}
        if not show_parameters:
            hidden_types.add("parameter")
        if not show_sends_returns:
            hidden_types |= {"send", "return_track"}
        if not show_audio_files:
            hidden_types.add("audio_file")

    keep_nodes = [
        node_id
        for node_id, data in graph.nodes(data=True)
        if data.get("type") not in hidden_types
    ]
    subgraph = graph.subgraph(keep_nodes).copy()

    if only_track_id and subgraph.has_node(only_track_id):
        reachable = nx.descendants(subgraph, only_track_id) | {only_track_id}
        context = {
            node_id
            for node_id, data in subgraph.nodes(data=True)
            if data.get("type") in ("project", "master_track")
        }
        subgraph = subgraph.subgraph(reachable | context).copy()

    return subgraph
