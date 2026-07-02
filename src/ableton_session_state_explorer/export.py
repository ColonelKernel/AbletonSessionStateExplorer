"""JSON export of session state, graph, descriptors, and recommendations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import networkx as nx

from . import SCHEMA_VERSION
from .graph_builder import graph_to_dict
from .models import AudioDescriptorSet, ProjectState, Recommendation
from .utils import to_pretty_json


def build_export_bundle(
    project: ProjectState,
    graph: nx.DiGraph,
    descriptors: Optional[list[AudioDescriptorSet]] = None,
    recommendations: Optional[list[Recommendation]] = None,
    ableton_export_available: bool = False,
    mode: str = "graph_only",
) -> dict[str, Any]:
    """Assemble the complete export bundle as a JSON-friendly dict."""
    descriptors = descriptors or []
    recommendations = recommendations or []
    warnings = list(project.warnings)
    for descriptor in descriptors:
        warnings.extend(descriptor.warnings)

    return {
        "schema_version": SCHEMA_VERSION,
        "project": project.model_dump(mode="json"),
        "graph": graph_to_dict(graph),
        "descriptors": [d.model_dump(mode="json") for d in descriptors],
        "recommendations": [r.model_dump(mode="json") for r in recommendations],
        "warnings": warnings,
        "export_metadata": {
            "mode": mode,
            "ableton_export_available": ableton_export_available,
        },
    }


def export_bundle_to_file(bundle: dict[str, Any], output_path: Path) -> Path:
    """Write an export bundle to disk as pretty-printed JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_pretty_json(bundle), encoding="utf-8")
    return output_path


def project_to_json(project: ProjectState) -> str:
    return to_pretty_json(project.model_dump(mode="json"))


def graph_to_json(graph: nx.DiGraph) -> str:
    return to_pretty_json(graph_to_dict(graph))


def descriptors_to_json(descriptors: list[AudioDescriptorSet]) -> str:
    return to_pretty_json([d.model_dump(mode="json") for d in descriptors])


def recommendations_to_json(recommendations: list[Recommendation]) -> str:
    return to_pretty_json([r.model_dump(mode="json") for r in recommendations])
