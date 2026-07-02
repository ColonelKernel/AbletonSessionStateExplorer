"""Tests for the Ableton export adapter and JSON export bundle."""

import json

from ableton_session_state_explorer.ableton_export_adapter import (
    export_project_state_to_ableton,
    is_ableton_export_available,
)
from ableton_session_state_explorer.ableton_session_model import build_demo_session
from ableton_session_state_explorer.export import build_export_bundle
from ableton_session_state_explorer.graph_builder import build_session_graph
from ableton_session_state_explorer.models import ExportResult


def test_export_adapter_does_not_crash_without_ableton_tooling(tmp_path):
    project = build_demo_session()
    result = export_project_state_to_ableton(project, tmp_path / "export")
    assert isinstance(result, ExportResult)
    assert result.success


def test_mock_export_writes_json(tmp_path):
    project = build_demo_session()
    result = export_project_state_to_ableton(project, tmp_path / "export")

    if is_ableton_export_available():
        # Environment-dependent branch: a real export library is present.
        assert result.mode == "ableton_export"
        return

    assert result.mode == "mock_export"
    export_dir = tmp_path / "export"
    project_json = export_dir / "project_state.json"
    graph_json = export_dir / "session_graph.json"
    limitations = export_dir / "README_EXPORT_LIMITATIONS.md"

    assert project_json.exists()
    assert graph_json.exists()
    assert limitations.exists()

    project_payload = json.loads(project_json.read_text())
    assert project_payload["project_name"] == project.project_name
    graph_payload = json.loads(graph_json.read_text())
    assert graph_payload["nodes"]
    assert graph_payload["edges"]


def test_export_result_has_clear_mode_and_warnings(tmp_path):
    project = build_demo_session()
    result = export_project_state_to_ableton(project, tmp_path / "export")
    assert result.mode in ("ableton_export", "mock_export", "json_only")
    assert result.message
    if result.mode == "mock_export":
        assert result.warnings
        assert any("research graph mode" in w for w in result.warnings)


def test_export_bundle_shape():
    project = build_demo_session()
    graph = build_session_graph(project)
    bundle = build_export_bundle(project, graph)
    assert bundle["schema_version"] == "0.1.0"
    assert set(bundle.keys()) == {
        "schema_version",
        "project",
        "graph",
        "descriptors",
        "recommendations",
        "warnings",
        "export_metadata",
    }
    assert bundle["export_metadata"]["mode"] == "graph_only"
    assert bundle["export_metadata"]["ableton_export_available"] in (True, False)
    assert bundle["graph"]["nodes"]
