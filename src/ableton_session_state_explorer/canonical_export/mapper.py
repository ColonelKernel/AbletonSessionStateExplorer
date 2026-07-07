"""Ableton native ↔ canonical mapping.

Relocated verbatim from the analyzer's ``session_explorer.drivers.ableton.
mapper`` (origin: SessionStateExplorer@041f529 — the round-trip-verified
reference), rewired to import the nested canonical models from the shared
``canonical_snapshot`` contract package and the native :class:`~..models.
ProjectState` family from this repo's own :mod:`..models` (of which the
analyzer copies were ports).

``to_canonical`` maps the verbatim native :class:`~..models.ProjectState`
into a :class:`canonical_snapshot.nested.CanonicalSession`; the complete
``model_dump()`` of the native model rides along as ``session.native``, so
``to_native(to_canonical(x)).model_dump() == x.model_dump()`` holds exactly.

The mapper is dialect-parameterised: the Cubase-style demo session is the
same ``ProjectState`` family (built by this prototype's
``cubase_session_model``), so a Cubase-side adapter can reuse these
functions with ``dialect="cubase"`` — ids are then namespaced ``cubase:...``
and the native payload declares that dialect. (Cross-repo imports are not
allowed; the Cubase repo carries its own copy per the relocation plan.)

Provenance policy (documented deviation-by-design): ``validate_project_dict``
backfills missing track roles and device families with the keyword
classifiers (this repo's :mod:`..utils`), and the payload does not record
which values were backfilled versus dialect-supplied. The simplest faithful
approach is therefore to mark ``role`` / ``family`` field provenance as
*inferred* ("keyword classifier") always — roles/families are explorer-side
heuristics in this dialect, never DAW facts.
"""

from __future__ import annotations

from canonical_snapshot.ids import namespaced
from canonical_snapshot.nested import (
    CanonicalSession,
    Clip,
    NativePayload,
    Processor,
    ProcessorParameter,
    Provenance,
    Route,
    Scene,
    Track,
    inferred,
)

from ..models import (
    ClipState,
    DeviceState,
    ProjectState,
    ReturnTrackState,
    TrackState,
)

NATIVE_MODEL_NAME = "ProjectState"

_ROLE_FAMILY_EXPLANATION = "keyword classifier"


def _observed(source_artifact: str) -> Provenance:
    return Provenance(observability="observed", source_artifact=source_artifact)


def _map_parameters(
    device: DeviceState, dialect: str
) -> list[ProcessorParameter]:
    return [
        ProcessorParameter(
            id=namespaced(dialect, param.id),
            processor_id=namespaced(dialect, device.id),
            name=param.name,
            value=param.value,
            normalized_value=param.normalized_value,
            unit=param.unit,
            is_automated=param.is_automated,
            is_visible_to_host=param.is_visible_to_host,
        )
        for param in device.parameters
    ]


def _map_device(
    device: DeviceState, owner_id: str, dialect: str, source_artifact: str
) -> Processor:
    return Processor(
        id=namespaced(dialect, device.id),
        track_id=namespaced(dialect, owner_id),
        index=device.index,
        name=device.name,
        kind=device.device_type,
        family=device.device_family,
        enabled=device.enabled,
        preset=device.preset_name,
        parameters=_map_parameters(device, dialect),
        provenance=_observed(source_artifact),
        field_provenance={
            "family": inferred(
                _ROLE_FAMILY_EXPLANATION, source_artifact=source_artifact
            )
        },
        raw_source=device.raw_source or None,
    )


def _map_clip(clip: ClipState, dialect: str, source_artifact: str) -> Clip:
    return Clip(
        id=namespaced(dialect, clip.id),
        track_id=namespaced(dialect, clip.track_id),
        scene_id=namespaced(dialect, clip.scene_id) if clip.scene_id else None,
        name=clip.name,
        clip_type=clip.clip_type,
        start_time_beats=clip.start_time_beats,
        length_beats=clip.length_beats,
        loop_start_beats=clip.loop_start_beats,
        loop_end_beats=clip.loop_end_beats,
        warp_enabled=clip.warp_enabled,
        midi_note_count=clip.midi_note_count,
        audio_file=clip.audio_file,
        provenance=_observed(source_artifact),
        raw_source=clip.raw_source or None,
    )


def _map_track(track: TrackState, dialect: str, source_artifact: str) -> Track:
    return Track(
        id=namespaced(dialect, track.id),
        index=track.index,
        name=track.name,
        kind=track.track_type,
        role=track.role,
        color=track.color,
        volume_db=track.volume_db,
        pan=track.pan,
        mute=track.mute,
        solo=track.solo,
        armed=track.armed,
        group_id=namespaced(dialect, track.group_id) if track.group_id else None,
        clips=[_map_clip(clip, dialect, source_artifact) for clip in track.clips],
        processors=[
            _map_device(device, track.id, dialect, source_artifact)
            for device in track.devices
        ],
        provenance=_observed(source_artifact),
        field_provenance={
            "role": inferred(_ROLE_FAMILY_EXPLANATION, source_artifact=source_artifact)
        },
        raw_source=track.raw_source or None,
    )


def _map_return_track(
    return_track: ReturnTrackState, dialect: str, source_artifact: str
) -> Track:
    return Track(
        id=namespaced(dialect, return_track.id),
        index=return_track.index,
        name=return_track.name,
        kind="return",
        role="Bus",
        volume_db=return_track.volume_db,
        processors=[
            _map_device(device, return_track.id, dialect, source_artifact)
            for device in return_track.devices
        ],
        provenance=_observed(source_artifact),
        field_provenance={
            "role": inferred(
                "return tracks read as Bus by construction",
                source_artifact=source_artifact,
            )
        },
    )


def to_canonical(
    project: ProjectState,
    source_artifact: str = "session_json",
    dialect: str = "ableton",
) -> CanonicalSession:
    """Map a native ``ProjectState`` into a canonical session (lossless)."""

    tracks = [_map_track(track, dialect, source_artifact) for track in project.tracks]
    tracks += [
        _map_return_track(rt, dialect, source_artifact)
        for rt in project.return_tracks
    ]
    if project.master_track is not None:
        master = project.master_track
        tracks.append(
            Track(
                id=namespaced(dialect, master.id),
                index=0,
                name=master.name,
                kind="master",
                volume_db=master.volume_db,
                processors=[
                    _map_device(device, master.id, dialect, source_artifact)
                    for device in master.devices
                ],
                provenance=_observed(source_artifact),
            )
        )

    routes = [
        Route(
            id=namespaced(dialect, send.id),
            source_track_id=namespaced(dialect, send.source_track_id),
            target_track_id=namespaced(dialect, send.target_return_id),
            route_type="send",
            volume_db=send.level_db,
            enabled=send.enabled,
            provenance=_observed(source_artifact),
            extras={"send_name": send.send_name} if send.send_name else {},
        )
        for send in project.all_sends()
    ]

    scenes = [
        Scene(
            id=namespaced(dialect, scene.id),
            index=scene.index,
            name=scene.name,
            tempo=scene.tempo,
            provenance=_observed(source_artifact),
        )
        for scene in project.scenes
    ]

    return CanonicalSession(
        dialect=dialect,
        name=project.project_name,
        tempo=project.tempo,
        time_signature=project.time_signature,
        tracks=tracks,
        scenes=scenes,
        routes=routes,
        warnings=list(project.warnings),
        metadata={
            "source_artifact": source_artifact,
            "native_metadata": dict(project.metadata),
        },
        native=NativePayload(
            dialect=dialect,
            model_name=NATIVE_MODEL_NAME,
            model=project.model_dump(),
        ),
    )


def to_native(session: CanonicalSession) -> ProjectState:
    """Reconstruct the verbatim native ``ProjectState`` from the payload."""

    if session.native is None:
        raise ValueError(
            "This session carries no native payload; the native ProjectState "
            "cannot be reconstructed."
        )
    if session.native.model_name != NATIVE_MODEL_NAME:
        raise ValueError(
            f"Expected a {NATIVE_MODEL_NAME!r} native payload, got "
            f"{session.native.model_name!r}."
        )
    return ProjectState.model_validate(session.native.model)
