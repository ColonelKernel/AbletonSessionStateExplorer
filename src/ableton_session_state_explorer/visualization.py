"""Interactive graph visualization.

Primary renderer: PyVis (embedded HTML). Fallback: Plotly network scatter.
Node types are color-coded and a legend is exposed for the Streamlit UI.
"""

from __future__ import annotations

import networkx as nx

try:
    from pyvis.network import Network

    PYVIS_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    PYVIS_AVAILABLE = False

NODE_STYLE: dict[str, dict] = {
    "project": {"color": "#F2C14E", "shape": "star", "size": 34, "legend": "Project"},
    "scene": {"color": "#9B8ADE", "shape": "diamond", "size": 18, "legend": "Scene"},
    "track": {"color": "#4EA8DE", "shape": "dot", "size": 24, "legend": "Track"},
    "clip": {"color": "#80CED7", "shape": "square", "size": 14, "legend": "Clip"},
    "audio_file": {"color": "#B7E4C7", "shape": "triangle", "size": 12, "legend": "Audio file"},
    "midi_clip": {"color": "#F49CBB", "shape": "square", "size": 14, "legend": "MIDI clip"},
    "device": {"color": "#E76F51", "shape": "box", "size": 16, "legend": "Device"},
    "parameter": {"color": "#CCCCCC", "shape": "dot", "size": 8, "legend": "Parameter"},
    "send": {"color": "#F4A261", "shape": "triangleDown", "size": 12, "legend": "Send"},
    "return_track": {"color": "#2A9D8F", "shape": "dot", "size": 22, "legend": "Return track"},
    "master_track": {"color": "#264653", "shape": "dot", "size": 28, "legend": "Master"},
}

DEFAULT_STYLE = {"color": "#999999", "shape": "dot", "size": 12, "legend": "Other"}

# Renderer chrome tokens, shared by the PyVis and Plotly renderers so the
# fallback cannot drift from the primary.
GRAPH_CHROME = {
    "background": "#111111",
    "font": "#EEEEEE",
    "edge": "#666666",
    "node_outline": "#333333",
}

# Unicode glyphs matching each node shape, so the legend preserves the
# shape channel of the color+shape dual encoding.
SHAPE_GLYPH = {
    "star": "★",
    "diamond": "◆",
    "dot": "●",
    "square": "■",
    "triangle": "▲",
    "triangleDown": "▼",
    "box": "▬",
}


def legend_entries() -> list[tuple[str, str, str]]:
    """(label, color, shape glyph) triples for the UI legend."""
    return [
        (style["legend"], style["color"], SHAPE_GLYPH.get(style["shape"], "●"))
        for style in NODE_STYLE.values()
    ]


def _node_tooltip(node_id: str, data: dict) -> str:
    lines = [f"{data.get('label', node_id)}", f"type: {data.get('type')}"]
    for key, value in data.items():
        if key in ("label", "type") or value is None:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def build_pyvis_html(graph: nx.DiGraph, height: str = "640px") -> str:
    """Render the graph to standalone PyVis HTML for embedding in Streamlit."""
    if not PYVIS_AVAILABLE:
        raise RuntimeError("pyvis is not installed")

    network = Network(
        height=height,
        width="100%",
        directed=True,
        bgcolor=GRAPH_CHROME["background"],
        font_color=GRAPH_CHROME["font"],
        notebook=False,
        cdn_resources="in_line",
    )
    network.barnes_hut(gravity=-6000, central_gravity=0.25, spring_length=120)

    for node_id, data in graph.nodes(data=True):
        style = NODE_STYLE.get(data.get("type", ""), DEFAULT_STYLE)
        # Track nodes carry the session's own track color as a border tint,
        # on top of the type color that keeps the visual taxonomy readable.
        track_color = data.get("track_color")
        if track_color:
            color = {"background": style["color"], "border": track_color}
            border_width = 3
        else:
            color = style["color"]
            border_width = 1
        network.add_node(
            node_id,
            label=data.get("label", node_id),
            title=_node_tooltip(node_id, data),
            color=color,
            shape=style["shape"],
            size=style["size"],
            borderWidth=border_width,
        )

    for source, target, data in graph.edges(data=True):
        network.add_edge(
            source,
            target,
            title=data.get("type", ""),
            color=GRAPH_CHROME["edge"],
            arrows="to",
        )

    return network.generate_html()


def build_plotly_figure(graph: nx.DiGraph):
    """Fallback renderer: a Plotly scatter network with spring layout."""
    import plotly.graph_objects as go

    positions = nx.spring_layout(graph, seed=42, k=0.8)

    edge_x, edge_y = [], []
    for source, target in graph.edges():
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.6, color=GRAPH_CHROME["edge"]), hoverinfo="none",
    )

    node_x, node_y, texts, colors, sizes, outlines = [], [], [], [], [], []
    for node_id, data in graph.nodes(data=True):
        x, y = positions[node_id]
        node_x.append(x)
        node_y.append(y)
        texts.append(_node_tooltip(node_id, data).replace("\n", "<br>"))
        style = NODE_STYLE.get(data.get("type", ""), DEFAULT_STYLE)
        colors.append(style["color"])
        sizes.append(style["size"])
        outlines.append(data.get("track_color") or GRAPH_CHROME["node_outline"])

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers",
        marker=dict(color=colors, size=sizes, line=dict(width=1, color=outlines)),
        hovertext=texts, hoverinfo="text",
    )

    figure = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=640,
        ),
    )
    return figure
