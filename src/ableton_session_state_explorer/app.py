"""Ableton Session State Explorer v0 — Streamlit application.

Run with:
    streamlit run src/ableton_session_state_explorer/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `streamlit run src/ableton_session_state_explorer/app.py` without
# installing the package: put the src/ directory on sys.path.
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from ableton_session_state_explorer.ableton_export_adapter import (
    export_project_state_to_ableton,
    is_ableton_export_available,
)
from ableton_session_state_explorer.ableton_session_model import (
    build_demo_session,
    compare_fingerprints,
    compute_session_fingerprint,
)
from ableton_session_state_explorer.als_inspector import inspect_als_bytes
from ableton_session_state_explorer.audio_descriptors import (
    LIBROSA_AVAILABLE,
    extract_descriptors,
)
from ableton_session_state_explorer.export import (
    build_export_bundle,
    descriptors_to_json,
    graph_to_json,
    project_to_json,
    recommendations_to_json,
)
from ableton_session_state_explorer.graph_builder import (
    build_session_graph,
    filter_graph,
    graph_to_dict,
)
from ableton_session_state_explorer.models import validate_project_dict
from ableton_session_state_explorer.prediction import (
    predict_chain_gaps,
    prediction_table,
    train_and_evaluate,
)
from ableton_session_state_explorer.recommendations import generate_recommendations
from ableton_session_state_explorer.utils import to_pretty_json
from ableton_session_state_explorer.visualization import (
    PYVIS_AVAILABLE,
    build_plotly_figure,
    build_pyvis_html,
    legend_entries,
)

st.set_page_config(
    page_title="Session State Explorer v0",
    page_icon="🎛️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("Session State Explorer v0")
st.caption(
    "Interpretable DAW-state graphs for AI-assisted music production research "
    "— DAW-agnostic core, Ableton-style demo session"
)

st.session_state.setdefault("descriptors", [])
st.session_state.setdefault("project", None)

# ---------------------------------------------------------------------------
# Mode selector
# ---------------------------------------------------------------------------

MODE_DEMO = "Built-in demo session"
MODE_UPLOAD = "Upload session JSON"
MODE_ALS = "Experimental .als inspector"

with st.sidebar:
    st.header("Mode")
    mode = st.radio(
        "Choose a data pathway",
        [MODE_DEMO, MODE_UPLOAD, MODE_ALS],
        help=(
            "Demo: a hand-authored Ableton-style session. "
            "Upload: your own session in this app's JSON schema. "
            ".als inspector: cautious surface inspection of a Live Set file — "
            "not a parser, and not connected to the graph pipeline."
        ),
    )
    st.markdown(
        f"""
**{MODE_DEMO}** — loads *Indie Vocal Production Sketch*, a hand-authored
Ableton-style session with intentional workflow quirks for the
recommendation engine to find.

**{MODE_UPLOAD}** — validates a session JSON against this prototype's
documented schema and runs the same pipeline.

**{MODE_ALS}** — attempts gzip/XML surface inspection of an Ableton `.als`
file to illustrate partial observability. It is *not* a Live Set parser.
"""
    )

# ---------------------------------------------------------------------------
# Session builder / loader
# ---------------------------------------------------------------------------

st.header("1 · Session")

if mode == MODE_DEMO:
    if st.session_state.project is None or st.session_state.get("mode") != MODE_DEMO:
        st.session_state.project = build_demo_session()
        st.session_state.mode = MODE_DEMO
    project = st.session_state.project

    with st.expander("Edit demo session basics", expanded=False):
        new_tempo = st.number_input(
            "Tempo (BPM)", min_value=20.0, max_value=300.0,
            value=float(project.tempo or 120.0), step=1.0,
        )
        project.tempo = new_tempo
        for track in project.tracks:
            new_name = st.text_input(
                f"Track {track.index + 1} name", value=track.name, key=f"name-{track.id}"
            )
            if new_name.strip():
                track.name = new_name.strip()

elif mode == MODE_UPLOAD:
    st.session_state.mode = MODE_UPLOAD
    uploaded_json = st.file_uploader(
        "Upload a session JSON (this app's schema — see data/examples/)",
        type=["json"],
    )
    if uploaded_json is not None:
        try:
            payload = json.load(uploaded_json)
            # Accept either a bare ProjectState or a full export bundle.
            if "project" in payload and "schema_version" in payload:
                payload = payload["project"]
            st.session_state.project = validate_project_dict(payload)
            st.success(
                f"Session '{st.session_state.project.project_name}' validated."
            )
        except json.JSONDecodeError as exc:
            st.session_state.project = None
            st.error(f"Not valid JSON: {exc}")
        except ValidationError as exc:
            st.session_state.project = None
            st.error("Schema validation failed:")
            st.code(str(exc))
    project = st.session_state.project
    if project is None:
        st.info(
            "Upload a session JSON to continue, or switch to the built-in demo. "
            "An example file lives at `data/examples/example_session.json`."
        )

else:  # MODE_ALS
    st.session_state.mode = MODE_ALS
    st.warning(
        "The `.als` inspector is exploratory. It reports surface-level XML "
        "structure only and does not feed the graph pipeline."
    )
    uploaded_als = st.file_uploader("Upload an Ableton Live Set (.als)", type=["als"])
    if uploaded_als is not None:
        report = inspect_als_bytes(uploaded_als.getvalue(), uploaded_als.name)
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Track-like elements", report["track_like_elements"])
        col_b.metric("Device-like elements", report["device_like_elements"])
        col_c.metric("Clip-like elements", report["clip_like_elements"])
        col_d.metric("Distinct tags", report.get("total_distinct_tags", 0))
        st.write(f"**Root tag:** `{report['root_tag']}`")
        if report.get("ableton_version_hint"):
            st.write(f"**Creator hint:** {report['ableton_version_hint']}")
        for warning in report["warnings"]:
            st.caption(f"⚠️ {warning}")
        if report["tag_frequency"]:
            st.subheader("Tag frequency (top 50)")
            st.dataframe(
                pd.DataFrame(
                    sorted(report["tag_frequency"].items(), key=lambda kv: -kv[1]),
                    columns=["tag", "count"],
                ),
                use_container_width=True,
            )
        st.download_button(
            "Download inspection summary (JSON)",
            data=to_pretty_json(report),
            file_name="als_inspection.json",
            mime="application/json",
        )
    project = None
    st.stop()

if project is None:
    st.stop()

# ---------------------------------------------------------------------------
# Optional audio upload
# ---------------------------------------------------------------------------

st.header("2 · Audio descriptors (optional)")

if not LIBROSA_AVAILABLE:
    st.warning(
        "librosa is not installed — descriptor extraction is disabled. "
        "Install requirements.txt to enable it."
    )
else:
    assignment_options = {"Project mixdown": ("mixdown", "project")}
    for track in project.tracks:
        assignment_options[f"Track: {track.name}"] = ("track", track.id)
    for clip in project.all_clips():
        track = project.track_by_id(clip.track_id)
        track_name = track.name if track else clip.track_id
        assignment_options[f"Clip: {clip.name} ({track_name})"] = ("clip", clip.id)

    upload_col, assign_col = st.columns([2, 1])
    with upload_col:
        audio_files = st.file_uploader(
            "Upload stems, loops, or a mixdown (WAV / AIFF / FLAC / MP3)",
            type=["wav", "aiff", "aif", "flac", "mp3"],
            accept_multiple_files=True,
        )
    with assign_col:
        assignment_label = st.selectbox(
            "Associate uploads with", list(assignment_options.keys())
        )

    if audio_files and st.button("Extract descriptors", type="primary"):
        source_type, source_id = assignment_options[assignment_label]
        for uploaded in audio_files:
            descriptor_id = f"desc-{len(st.session_state.descriptors) + 1}"
            with st.spinner(f"Analyzing {uploaded.name}…"):
                descriptor = extract_descriptors(
                    uploaded.getvalue(),
                    descriptor_id=descriptor_id,
                    source_id=source_id,
                    source_type=source_type,
                    file_path=uploaded.name,
                )
            st.session_state.descriptors.append(descriptor)
        st.success(f"Extracted descriptors for {len(audio_files)} file(s).")

    if st.session_state.descriptors and st.button("Clear descriptors"):
        st.session_state.descriptors = []
        st.rerun()

descriptors = st.session_state.descriptors

# ---------------------------------------------------------------------------
# Pipeline: graph + recommendations
# ---------------------------------------------------------------------------

graph = build_session_graph(project)
recommendations = generate_recommendations(project, descriptors)

# ---------------------------------------------------------------------------
# Session summary
# ---------------------------------------------------------------------------

st.header("3 · Session summary")

meta = graph.graph
summary_cols = st.columns(8)
summary_values = [
    ("Tempo", f"{project.tempo:g} BPM" if project.tempo else "—"),
    ("Tracks", meta.get("num_tracks", 0)),
    ("Clips", meta.get("num_clips", 0)),
    ("Scenes", len(project.scenes)),
    ("Devices", meta.get("num_devices", 0)),
    ("Returns", meta.get("num_return_tracks", 0)),
    ("Sends", meta.get("num_sends", 0)),
    ("Warnings", len(project.warnings)),
]
for col, (label, value) in zip(summary_cols, summary_values):
    col.metric(label, value)

audio_tracks = sum(1 for t in project.tracks if t.track_type == "audio")
midi_tracks = sum(1 for t in project.tracks if t.track_type == "midi")
master_desc = (
    f"master with {len(project.master_track.devices)} device(s)"
    if project.master_track
    else "no master track"
)
st.caption(
    f"**{project.project_name}** — {audio_tracks} audio track(s), "
    f"{midi_tracks} MIDI track(s), {len(project.return_tracks)} return "
    f"track(s), {master_desc}. Graph density: {meta.get('graph_density', 0)}."
)
if project.warnings:
    with st.expander("Session warnings"):
        for warning in project.warnings:
            st.write(f"- {warning}")

# ---------------------------------------------------------------------------
# Graph visualization
# ---------------------------------------------------------------------------

st.header("4 · DAW-state graph")

with st.sidebar:
    st.header("Graph filters")
    structure_only = st.checkbox("Production structure only", value=False)
    show_clips = st.checkbox("Show clips", value=True, disabled=structure_only)
    show_scenes = st.checkbox("Show scenes", value=True, disabled=structure_only)
    show_devices = st.checkbox("Show devices", value=True, disabled=structure_only)
    show_parameters = st.checkbox(
        "Show parameters", value=False, disabled=structure_only,
        help="Hidden by default to keep the graph legible.",
    )
    show_sends_returns = st.checkbox(
        "Show sends/returns", value=True, disabled=structure_only
    )
    show_audio_files = st.checkbox(
        "Show audio files", value=True, disabled=structure_only
    )
    track_options = ["All tracks"] + [t.name for t in project.tracks]
    selected_track_name = st.selectbox("Focus on track", track_options)
    only_track_id = None
    if selected_track_name != "All tracks":
        only_track_id = next(
            t.id for t in project.tracks if t.name == selected_track_name
        )

display_graph = filter_graph(
    graph,
    show_clips=show_clips,
    show_scenes=show_scenes,
    show_devices=show_devices,
    show_parameters=show_parameters,
    show_sends_returns=show_sends_returns,
    show_audio_files=show_audio_files,
    only_track_id=only_track_id,
    structure_only=structure_only,
)

legend_html = " ".join(
    f'<span style="display:inline-block;margin:2px 8px 2px 0;">'
    f'<span style="display:inline-block;width:11px;height:11px;'
    f'border-radius:50%;background:{color};margin-right:4px;"></span>'
    f"{label}</span>"
    for label, color in legend_entries()
)
st.markdown(legend_html, unsafe_allow_html=True)

st.caption(
    f"Showing {display_graph.number_of_nodes()} of {graph.number_of_nodes()} "
    f"nodes and {display_graph.number_of_edges()} of {graph.number_of_edges()} edges."
)

if PYVIS_AVAILABLE:
    try:
        html = build_pyvis_html(display_graph)
        st.components.v1.html(html, height=660, scrolling=False)
    except Exception as exc:
        st.warning(f"PyVis rendering failed ({exc}); falling back to Plotly.")
        st.plotly_chart(build_plotly_figure(display_graph), use_container_width=True)
else:
    st.plotly_chart(build_plotly_figure(display_graph), use_container_width=True)

# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

st.header("5 · Tables")

(
    tab_tracks,
    tab_clips,
    tab_devices,
    tab_sends,
    tab_returns,
    tab_descriptors,
    tab_recs,
) = st.tabs(
    ["Tracks", "Clips", "Devices", "Sends", "Returns", "Descriptors", "Recommendations"]
)

with tab_tracks:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "id": t.id, "name": t.name, "type": t.track_type,
                    "role": t.role, "volume_db": t.volume_db, "pan": t.pan,
                    "clips": len(t.clips), "devices": len(t.devices),
                    "sends": len(t.sends),
                }
                for t in project.tracks
            ]
        ),
        use_container_width=True,
    )

with tab_clips:
    clips = project.all_clips()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "id": c.id, "name": c.name, "type": c.clip_type,
                    "track": c.track_id, "scene": c.scene_id,
                    "length_beats": c.length_beats, "warped": c.warp_enabled,
                    "audio_file": c.audio_file, "midi_notes": c.midi_note_count,
                }
                for c in clips
            ]
        )
        if clips
        else pd.DataFrame(),
        use_container_width=True,
    )

with tab_devices:
    devices = project.all_devices()
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "id": d.id, "name": d.name, "family": d.device_family,
                    "owner": d.track_id, "enabled": d.enabled,
                    "parameters": len(d.parameters),
                }
                for d in devices
            ]
        )
        if devices
        else pd.DataFrame(),
        use_container_width=True,
    )

with tab_sends:
    sends = project.all_sends()
    if sends:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "id": s.id, "from": s.source_track_id,
                        "to": s.target_return_id, "level_db": s.level_db,
                        "enabled": s.enabled,
                    }
                    for s in sends
                ]
            ),
            use_container_width=True,
        )
    else:
        st.info("No sends defined in this session.")

with tab_returns:
    if project.return_tracks:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "id": rt.id, "name": rt.name,
                        "volume_db": rt.volume_db, "devices": len(rt.devices),
                    }
                    for rt in project.return_tracks
                ]
            ),
            use_container_width=True,
        )
    else:
        st.info("No return tracks defined.")

with tab_descriptors:
    if descriptors:
        st.dataframe(
            pd.DataFrame([d.model_dump(exclude={"warnings"}) for d in descriptors]),
            use_container_width=True,
        )
    else:
        st.info("No descriptors yet — upload audio in section 2.")

with tab_recs:
    if recommendations:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "title": r.title, "severity": r.severity,
                        "confidence": r.confidence,
                        "related_nodes": len(r.related_node_ids),
                    }
                    for r in recommendations
                ]
            ),
            use_container_width=True,
        )
    else:
        st.info("No recommendations triggered.")

# ---------------------------------------------------------------------------
# Recommendations detail
# ---------------------------------------------------------------------------

st.header("6 · Explainable recommendations")

SEVERITY_ICON = {"info": "ℹ️", "suggestion": "💡", "warning": "⚠️"}

if not recommendations:
    st.info("No heuristic rules triggered on this session.")
for rec in recommendations:
    icon = SEVERITY_ICON.get(rec.severity, "💡")
    with st.expander(f"{icon} {rec.title}", expanded=True):
        st.markdown(
            f"**Severity:** {rec.severity} · **Confidence:** {rec.confidence:.0%}"
        )
        st.write(rec.explanation)
        st.markdown(f"**Suggested action:** {rec.suggested_action}")
        st.caption(f"Caveat: {rec.caveat}")
        related = ", ".join(f"`{n}`" for n in rec.related_node_ids[:12])
        if len(rec.related_node_ids) > 12:
            related += f" … (+{len(rec.related_node_ids) - 12} more)"
        st.markdown(f"**Related graph nodes:** {related}")

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

st.header("7 · Export")

ableton_available = is_ableton_export_available()
export_mode = "ableton_export" if ableton_available else "graph_only"
bundle = build_export_bundle(
    project, graph, descriptors, recommendations,
    ableton_export_available=ableton_available, mode=export_mode,
)

dl_cols = st.columns(5)
dl_cols[0].download_button(
    "Session JSON", data=project_to_json(project),
    file_name="project_state.json", mime="application/json",
)
dl_cols[1].download_button(
    "Graph JSON", data=graph_to_json(graph),
    file_name="session_graph.json", mime="application/json",
)
dl_cols[2].download_button(
    "Descriptors JSON", data=descriptors_to_json(descriptors),
    file_name="descriptors.json", mime="application/json",
)
dl_cols[3].download_button(
    "Recommendations JSON", data=recommendations_to_json(recommendations),
    file_name="recommendations.json", mime="application/json",
)
dl_cols[4].download_button(
    "Complete bundle JSON", data=to_pretty_json(bundle),
    file_name="session_bundle.json", mime="application/json",
)

st.subheader("Ableton-compatible export (optional)")
if ableton_available:
    st.success("A public Ableton Live Set export library was detected.")
else:
    st.info(
        "No public Ableton Live Set export library is available in this "
        "environment — the export button below produces a transparent mock "
        "export (JSON + limitations note) in research graph mode."
    )
export_dir = st.text_input("Export directory", value="exports/ableton_export")
if st.button("Attempt Ableton-compatible export"):
    result = export_project_state_to_ableton(project, Path(export_dir))
    if result.success:
        st.success(f"{result.message} (mode: `{result.mode}`)")
    else:
        st.error(result.message)
    for path in result.output_paths:
        st.write(f"- `{path}`")
    for warning in result.warnings:
        st.caption(f"⚠️ {warning}")

# ---------------------------------------------------------------------------
# Session fingerprint
# ---------------------------------------------------------------------------

st.header("8 · Session fingerprint (optional)")

fingerprint = compute_session_fingerprint(project, descriptors)
fp_col, cmp_col = st.columns(2)
with fp_col:
    st.json(fingerprint)
with cmp_col:
    other_json = st.file_uploader(
        "Compare with another session JSON", type=["json"], key="fingerprint-upload"
    )
    if other_json is not None:
        try:
            other_payload = json.load(other_json)
            if "project" in other_payload and "schema_version" in other_payload:
                other_payload = other_payload["project"]
            other_project = validate_project_dict(other_payload)
            other_fp = compute_session_fingerprint(other_project)
            similarity = compare_fingerprints(fingerprint, other_fp)
            st.metric(
                f"Structural similarity vs '{other_project.project_name}'",
                f"{similarity:.2%}",
            )
            st.caption(
                "Cosine similarity over structural counts — a coarse heuristic, "
                "not a perceptual measure."
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            st.error(f"Could not read comparison session: {exc}")

# ---------------------------------------------------------------------------
# DAW-state prediction (experimental)
# ---------------------------------------------------------------------------

st.header("9 · DAW-state prediction (experimental)")

st.warning(
    "**Synthetic-data proof-of-concept.** The model below is trained on a "
    "seeded synthetic session corpus generated from role-conditioned "
    "device-chain priors — not on real productions. It demonstrates the "
    "*prediction* pathway of the research framing (masked device-family "
    "prediction from session context), not real-world mixing knowledge."
)


@st.cache_resource
def _trained_chain_model():
    return train_and_evaluate()


chain_model, chain_metrics = _trained_chain_model()

metric_cols = st.columns(4)
metric_cols[0].metric(
    "Model hit@1", f"{chain_metrics['model_hit_at_1']:.0%}",
    help="Masked device-family prediction accuracy on held-out synthetic sessions.",
)
metric_cols[1].metric(
    "Model hit@3", f"{chain_metrics['model_hit_at_3']:.0%}")
metric_cols[2].metric(
    "Frequency baseline hit@1", f"{chain_metrics['baseline_hit_at_1']:.0%}")
metric_cols[3].metric(
    "Held-out examples", chain_metrics["n_examples"])
st.caption(
    f"Trained on {chain_metrics['n_train_sessions']} synthetic sessions, "
    f"evaluated on {chain_metrics['n_test_sessions']} held-out sessions. "
    "The model conditions on track role, track type, and chain context; the "
    "baseline ranks families by global frequency."
)

st.subheader("Predicted vs observed chain families")
st.dataframe(pd.DataFrame(prediction_table(project, chain_model)), use_container_width=True)

predicted_gaps = predict_chain_gaps(project, chain_model)
if predicted_gaps:
    st.subheader("Data-grounded chain suggestions")
    for gap in predicted_gaps:
        with st.expander(f"🧪 {gap.title}", expanded=False):
            st.markdown(
                f"**Severity:** {gap.severity} · **Confidence:** {gap.confidence:.0%}"
            )
            st.write(gap.explanation)
            st.markdown(f"**Suggested action:** {gap.suggested_action}")
            st.caption(f"Caveat: {gap.caveat}")
            st.markdown(
                "**Related graph nodes:** "
                + ", ".join(f"`{n}`" for n in gap.related_node_ids)
            )
else:
    st.info("No predicted chain gaps above the probability threshold.")

# ---------------------------------------------------------------------------
# Research framing
# ---------------------------------------------------------------------------

st.divider()
st.info(
    "**Research framing** — This prototype represents Ableton-style session "
    "state as a partially observable graph. It does not automate mixing. It "
    "demonstrates how tracks, clips, devices, sends, returns, descriptors, "
    "and recommendations can become inspectable objects for human-centered "
    "AI-assisted production research."
)
