"""Typed data models for the Ableton-style session state.

These pydantic models define the explicit, Python-native representation of a
simplified Ableton-style session (Pathway A in the research framing). They do
not claim to capture full Ableton Live Set semantics — fields are the subset
needed for interpretable DAW-state graph research.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"


class DeviceParameterState(BaseModel):
    id: str
    device_id: str
    name: str
    value: Union[float, str, bool, None] = None
    normalized_value: Optional[float] = None
    unit: Optional[str] = None
    is_automated: Optional[bool] = None
    is_visible_to_host: Optional[bool] = None


class DeviceState(BaseModel):
    id: str
    track_id: str
    index: int = 0
    name: str
    device_type: Optional[str] = None
    device_family: Optional[str] = None
    enabled: Optional[bool] = True
    preset_name: Optional[str] = None
    parameters: list[DeviceParameterState] = Field(default_factory=list)
    raw_source: dict = Field(default_factory=dict)


class ClipState(BaseModel):
    id: str
    track_id: str
    scene_id: Optional[str] = None
    name: str
    clip_type: Literal["audio", "midi"] = "audio"
    start_time_beats: Optional[float] = None
    length_beats: Optional[float] = None
    loop_start_beats: Optional[float] = None
    loop_end_beats: Optional[float] = None
    warp_enabled: Optional[bool] = None
    audio_file: Optional[str] = None
    midi_note_count: Optional[int] = None
    raw_source: dict = Field(default_factory=dict)


class SendState(BaseModel):
    id: str
    source_track_id: str
    target_return_id: str
    send_name: Optional[str] = None
    level_db: Optional[float] = None
    enabled: Optional[bool] = True


class TrackState(BaseModel):
    id: str
    index: int = 0
    name: str
    track_type: Literal["audio", "midi", "group", "return", "master"] = "audio"
    role: Optional[str] = None
    color: Optional[str] = None
    volume_db: Optional[float] = None
    pan: Optional[float] = None
    mute: Optional[bool] = None
    solo: Optional[bool] = None
    armed: Optional[bool] = None
    clips: list[ClipState] = Field(default_factory=list)
    devices: list[DeviceState] = Field(default_factory=list)
    sends: list[SendState] = Field(default_factory=list)
    group_id: Optional[str] = None
    raw_source: dict = Field(default_factory=dict)


class SceneState(BaseModel):
    id: str
    index: int = 0
    name: Optional[str] = None
    tempo: Optional[float] = None


class ReturnTrackState(BaseModel):
    id: str
    index: int = 0
    name: str
    devices: list[DeviceState] = Field(default_factory=list)
    volume_db: Optional[float] = None


class MasterTrackState(BaseModel):
    id: str
    name: str = "Master"
    devices: list[DeviceState] = Field(default_factory=list)
    volume_db: Optional[float] = None


class ProjectState(BaseModel):
    schema_version: str = SCHEMA_VERSION
    project_name: str
    tempo: Optional[float] = None
    time_signature: Optional[str] = None
    scenes: list[SceneState] = Field(default_factory=list)
    tracks: list[TrackState] = Field(default_factory=list)
    return_tracks: list[ReturnTrackState] = Field(default_factory=list)
    master_track: Optional[MasterTrackState] = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    # -- convenience accessors -------------------------------------------

    def all_clips(self) -> list[ClipState]:
        return [clip for track in self.tracks for clip in track.clips]

    def all_devices(self) -> list[DeviceState]:
        devices = [device for track in self.tracks for device in track.devices]
        devices += [device for rt in self.return_tracks for device in rt.devices]
        if self.master_track:
            devices += self.master_track.devices
        return devices

    def all_sends(self) -> list[SendState]:
        return [send for track in self.tracks for send in track.sends]

    def track_by_id(self, track_id: str) -> Optional[TrackState]:
        for track in self.tracks:
            if track.id == track_id:
                return track
        return None


class AudioDescriptorSet(BaseModel):
    id: str
    source_id: str
    source_type: str = "file"  # "file" | "track" | "clip" | "mixdown"
    file_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    rms_mean: Optional[float] = None
    rms_std: Optional[float] = None
    peak_amplitude: Optional[float] = None
    spectral_centroid_mean: Optional[float] = None
    spectral_bandwidth_mean: Optional[float] = None
    spectral_rolloff_mean: Optional[float] = None
    zero_crossing_rate_mean: Optional[float] = None
    onset_strength_mean: Optional[float] = None
    estimated_tempo: Optional[float] = None
    dynamic_range_db: Optional[float] = None
    integrated_loudness_lufs: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    id: str
    title: str
    severity: Literal["info", "suggestion", "warning"] = "suggestion"
    confidence: float = 0.5
    related_node_ids: list[str] = Field(default_factory=list)
    explanation: str
    suggested_action: str
    caveat: str


class ExportResult(BaseModel):
    success: bool
    mode: Literal["ableton_export", "mock_export", "json_only"]
    output_paths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""


def validate_project_dict(payload: dict[str, Any]) -> ProjectState:
    """Validate a raw dict against the ProjectState schema.

    Raises pydantic.ValidationError with readable messages on failure.
    """
    return ProjectState.model_validate(payload)
