"""The measured capability manifest of the Ableton adapter.

A capability manifest states what this adapter's pathways can even *attempt*
to observe — separate from what any one capture yielded (that is the
snapshot's ``coverage``). The claims below come from the Session State
Exporter extension's documented behaviour (``extension/session-state-exporter/
README.md``, verified end-to-end in Live 12.4.5 beta) and from this repo's
README scope statements; they are TESTED where the extension run proved them
and CLAIMED elsewhere.

Read, write, live observation, and render are SEPARATE dimensions: the
extension can read a Live Set's structure through the official Extensions
SDK, but nothing here can write a Live Set, and no render pathway exists.
"""

from __future__ import annotations

from canonical_snapshot import (
    AdapterDescriptor,
    CapabilityManifest,
    DomainCapability,
    FieldCapability,
)

from .. import __version__

ADAPTER_ID = "ableton-extension"
ADAPTER_NAME = "ableton-session-state-explorer"
DAW = "ableton_live"

# Live version the extension pathway was verified against, per the extension
# README ("Verified end-to-end in Ableton Live 12.4.5 beta").
TESTED_DAW_VERSION = "12.4.5 beta"

# Documented omissions of the extension-export pathway (Extensions SDK / Live
# API 1.0.0) — from the extension README and the repo README. These are the
# adapter's own honest statement of what it cannot see.
KNOWN_LIMITATIONS = [
    "Track colors are not exposed by Extensions API 1.0.0; exported as null.",
    "Device on/off (enabled) state is not exposed by Extensions API 1.0.0.",
    "Automation state is not exported: it exists in the Live Set but is "
    "hidden from this pathway.",
    "Mixer values are not dB-calibrated: the API exposes raw parameter "
    "values, not calibrated volume/pan in dB.",
    "The Live Set name is not exposed; project naming comes from the export "
    "context.",
    "Parameter value round-trips are capped at 64 per device (the cap is "
    "recorded in raw_source when hit).",
    ".als files are surface-inspected only (gzip/XML tag counting); this "
    "adapter never decodes a Live Set into session state.",
    "Track roles and device families are explorer-side keyword heuristics "
    "backfilled on upload — research metadata, never DAW facts.",
]


def _field(
    support: str,
    capture_method: str = "extension_json",
    validation_status: str = "TESTED",
    stability: str = "SUPPORTED_INTEGRATION",
) -> FieldCapability:
    return FieldCapability(
        applicability="APPLICABLE",
        support=support,  # type: ignore[arg-type]
        capture_method=capture_method,
        source_stability=stability,  # type: ignore[arg-type]
        tested_daw_version=TESTED_DAW_VERSION if validation_status == "TESTED" else None,
        validation_status=validation_status,  # type: ignore[arg-type]
    )


def _none(capture_method: str = "extension_json") -> FieldCapability:
    """A field the pathway cannot capture at all (support NONE, no claim)."""
    return FieldCapability(
        applicability="APPLICABLE",
        support="NONE",
        capture_method=capture_method,
        source_stability="SUPPORTED_INTEGRATION",
        validation_status="TESTED",
        tested_daw_version=TESTED_DAW_VERSION,
    )


def build_capability_manifest() -> CapabilityManifest:
    """The Ableton adapter's capability manifest (extension-export pathway)."""

    read = {
        # Structure: tracks, scenes, clips, group membership — the extension
        # walks all of these through the official data model.
        "structure": DomainCapability(
            fields={
                "tracks": _field("FULL"),
                "scenes": _field("FULL"),
                "clips": _field("FULL"),
                "group_membership": _field("FULL"),
                "set_name": _none(),
            }
        ),
        # Channel state: booleans are exposed; dB-calibrated mixer values and
        # colors are not (API 1.0.0) — NONE, with the gap named.
        "channel": DomainCapability(
            fields={
                "mute": _field("FULL"),
                "solo": _field("FULL"),
                "armed": _field("FULL"),
                "volume_db": _none(),
                "pan": _none(),
                "color": _none(),
            }
        ),
        # Routing: active sends, return tracks, and the main chain.
        "routing": DomainCapability(
            fields={
                "sends": _field("FULL"),
                "return_tracks": _field("FULL"),
                "main_chain": _field("FULL"),
            }
        ),
        # Processing: device chains recursing racks; enabled state hidden.
        "processing": DomainCapability(
            fields={
                "device_chains": _field("FULL"),
                "rack_recursion": _field("FULL"),
                "device_enabled": _none(),
            }
        ),
        # Parameters: names/ranges fully, values capped at 64 per device.
        "parameters": DomainCapability(
            fields={
                "parameter_names": _field("FULL"),
                "parameter_values": _field("PARTIAL"),
            }
        ),
        # Automation: exists in the Set, invisible to this pathway.
        "automation": DomainCapability(
            fields={
                "automation_state": _none(),
            }
        ),
    }

    live_observation = {
        # The extension runs inside Live and observes the *current* Set on
        # demand — a partial live-observation pathway (no continuous
        # monitoring, no transport/temporal state).
        "session": DomainCapability(
            fields={
                "current_set_snapshot": _field("PARTIAL"),
                "transport_state": _none(),
            }
        ),
    }

    return CapabilityManifest(
        daw=DAW,
        daw_version=TESTED_DAW_VERSION,
        adapter=ADAPTER_NAME,
        adapter_version=__version__,
        read=read,
        write={},
        live_observation=live_observation,
        render={},
        notes=[
            "Read pathway: the Session State Exporter Live extension "
            "(official Extensions SDK 1.0.0-beta) — SUPPORTED_INTEGRATION.",
            "Hand-authored session_json uploads use the same schema but are "
            "MANUAL-stability captures; the bundle's provenance records "
            "carry that distinction.",
            "Write and render are NONE: no offline Live Set authoring path "
            "exists, and fabricating .als files would overstate "
            "compatibility.",
        ],
    )


def build_adapter_descriptor(capture_modes: list[str]) -> AdapterDescriptor:
    """The bundle-level identity card (``adapter_descriptor.json``)."""

    return AdapterDescriptor(
        adapter_id=ADAPTER_ID,
        daw=DAW,
        capture_modes=list(capture_modes),
        read=(
            "SUPPORTED_INTEGRATION — Session State Exporter Live extension "
            "(Extensions SDK 1.0.0-beta): structure, channel booleans, "
            "routing, device chains fully; parameter values capped at 64 "
            "per device; automation and dB mixer values hidden."
        ),
        write="NONE — no offline Live Set authoring path exists.",
        live_observation=(
            "PARTIAL — the extension observes the current Live Set on "
            "demand from inside Live; no continuous or transport state."
        ),
        render="NONE.",
        known_limitations=list(KNOWN_LIMITATIONS),
    )
