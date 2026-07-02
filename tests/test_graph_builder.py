"""Tests for the DAW-state graph builder."""

from ableton_session_state_explorer.ableton_session_model import build_demo_session
from ableton_session_state_explorer.graph_builder import (
    PROJECT_NODE_ID,
    build_session_graph,
    filter_graph,
    graph_to_dict,
)
from ableton_session_state_explorer.models import SendState


def _nodes_of_type(graph, node_type):
    return [n for n, d in graph.nodes(data=True) if d.get("type") == node_type]


def test_project_node_exists():
    graph = build_session_graph(build_demo_session())
    assert graph.has_node(PROJECT_NODE_ID)
    assert graph.nodes[PROJECT_NODE_ID]["type"] == "project"


def test_scene_track_clip_device_nodes_exist():
    graph = build_session_graph(build_demo_session())
    assert len(_nodes_of_type(graph, "scene")) == 3
    assert len(_nodes_of_type(graph, "track")) == 6
    clips = _nodes_of_type(graph, "clip") + _nodes_of_type(graph, "midi_clip")
    assert len(clips) == 12
    assert len(_nodes_of_type(graph, "device")) == 22


def test_return_and_master_nodes_exist():
    graph = build_session_graph(build_demo_session())
    assert len(_nodes_of_type(graph, "return_track")) == 2
    assert len(_nodes_of_type(graph, "master_track")) == 1


def test_sends_create_edges_when_present():
    project = build_demo_session()
    track = project.tracks[4]  # Lead Vocal
    send = SendState(
        id="send-1",
        source_track_id=track.id,
        target_return_id="return-1",
        send_name="A",
        level_db=-12.0,
        enabled=True,
    )
    track.sends.append(send)
    graph = build_session_graph(project)

    assert graph.has_node("send-1")
    assert graph.nodes["send-1"]["type"] == "send"
    assert graph.has_edge(track.id, "send-1")
    assert graph.edges[track.id, "send-1"]["type"] == "sends_to"
    assert graph.has_edge("send-1", "return-1")
    assert graph.edges["send-1", "return-1"]["type"] == "sends_to"


def test_master_routing_edges():
    graph = build_session_graph(build_demo_session())
    master_id = _nodes_of_type(graph, "master_track")[0]
    for track_id in _nodes_of_type(graph, "track"):
        assert graph.has_edge(track_id, master_id)
        assert graph.edges[track_id, master_id]["type"] == "routes_to_master"


def test_graph_metadata_and_serialization():
    graph = build_session_graph(build_demo_session())
    meta = graph.graph
    assert meta["num_tracks"] == 6
    assert meta["num_clips"] == 12
    assert meta["num_devices"] == 22
    assert meta["num_return_tracks"] == 2
    assert meta["graph_density"] > 0

    payload = graph_to_dict(graph)
    assert set(payload.keys()) == {"nodes", "edges", "metadata"}
    assert all({"id", "label", "type"} <= set(n.keys()) for n in payload["nodes"])
    assert all({"source", "target", "type"} <= set(e.keys()) for e in payload["edges"])


def test_filter_graph_hides_parameters_and_focuses_track():
    project = build_demo_session()
    graph = build_session_graph(project)
    filtered = filter_graph(graph, show_parameters=False)
    assert not _nodes_of_type(filtered, "parameter")

    focused = filter_graph(graph, only_track_id="track-1")
    assert focused.has_node("track-1")
    assert not focused.has_node("track-2")

    structure = filter_graph(graph, structure_only=True)
    assert not _nodes_of_type(structure, "clip")
    assert not _nodes_of_type(structure, "device")
    assert _nodes_of_type(structure, "track")
