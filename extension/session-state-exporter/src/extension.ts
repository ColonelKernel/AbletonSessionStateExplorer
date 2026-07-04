/**
 * Session State Exporter — an Ableton Live extension.
 *
 * Walks the Live Set through the public Extensions SDK data model and writes
 * a JSON file in the Session State Explorer's ProjectState schema, so a real
 * session can be loaded into the graph/recommendation pipeline via the
 * app's "Upload session JSON" mode.
 *
 * Observability is partial by design — see the warnings the export embeds:
 * mixer values are raw (not dB), device on/off and track colors are not
 * exposed by API 1.0.0, and the Live Set name is not readable. What cannot
 * be observed is recorded as absent, never guessed.
 */

import {
  initialize,
  type ActivationContext,
  type ExtensionContext,
  AudioClip,
  AudioTrack,
  Clip,
  Device,
  DeviceParameter,
  MidiClip,
  MidiTrack,
  RackDevice,
  Track,
} from "@ableton-extensions/sdk";

import * as fs from "fs/promises";
import * as path from "path";

const API_VERSION = "1.0.0";
const SCHEMA_VERSION = "0.1.0";
/** Bound on per-device value round-trips; names/ranges are always exported. */
const MAX_PARAM_VALUES_PER_DEVICE = 64;

type Api = ExtensionContext<typeof API_VERSION>;

const id = (prefix: string, handleOwner: { handle: { id: bigint } }): string =>
  `${prefix}-${handleOwner.handle.id}`;

async function serializeParameters(
  device: Device<typeof API_VERSION>,
  deviceId: string,
): Promise<Record<string, unknown>[]> {
  const parameters = device.parameters;
  const values = await Promise.all(
    parameters
      .slice(0, MAX_PARAM_VALUES_PER_DEVICE)
      .map((parameter) => parameter.getValue().catch(() => null)),
  );
  return parameters.map((parameter: DeviceParameter<typeof API_VERSION>, i) => {
    const value = i < values.length ? values[i] : null;
    const min = parameter.min;
    const max = parameter.max;
    const normalized =
      value !== null && value !== undefined && max > min
        ? (value - min) / (max - min)
        : null;
    return {
      id: id("param", parameter),
      device_id: deviceId,
      name: parameter.name,
      value: value ?? null,
      normalized_value: normalized,
      unit: null,
      is_automated: null, // not exposed by API 1.0.0
      is_visible_to_host: true,
    };
  });
}

/** Serializes a device; racks are followed into their chains, flattened. */
async function serializeDeviceTree(
  device: Device<typeof API_VERSION>,
  ownerId: string,
  startIndex: number,
  rackPath: string[],
): Promise<Record<string, unknown>[]> {
  const deviceId = id("device", device);
  const entry: Record<string, unknown> = {
    id: deviceId,
    track_id: ownerId,
    index: startIndex,
    name: device.name,
    device_type: device instanceof RackDevice ? "rack" : "device",
    device_family: null, // classified by the explorer on import
    enabled: null, // device on/off is not exposed by API 1.0.0
    preset_name: null,
    parameters: await serializeParameters(device, deviceId),
    raw_source: {
      handle_id: String(device.handle.id),
      parameter_count: device.parameters.length,
      parameter_values_capped:
        device.parameters.length > MAX_PARAM_VALUES_PER_DEVICE,
      ...(rackPath.length > 0 ? { rack_path: rackPath } : {}),
    },
  };
  const entries = [entry];
  if (device instanceof RackDevice) {
    let chainIndex = 0;
    for (const chain of device.chains) {
      for (const chained of chain.devices) {
        entries.push(
          ...(await serializeDeviceTree(chained, ownerId, startIndex, [
            ...rackPath,
            `${device.name}/chain-${chainIndex}`,
          ])),
        );
      }
      chainIndex += 1;
    }
  }
  return entries;
}

async function serializeDeviceChain(
  track: Track<typeof API_VERSION>,
  ownerId: string,
): Promise<Record<string, unknown>[]> {
  const entries: Record<string, unknown>[] = [];
  let index = 0;
  for (const device of track.devices) {
    entries.push(...(await serializeDeviceTree(device, ownerId, index, [])));
    index += 1;
  }
  return entries;
}

function serializeClip(
  clip: Clip<typeof API_VERSION>,
  trackId: string,
  sceneId: string | null,
  fromArrangement: boolean,
): Record<string, unknown> {
  const base: Record<string, unknown> = {
    id: id("clip", clip),
    track_id: trackId,
    scene_id: sceneId,
    name: clip.name,
    clip_type: clip instanceof MidiClip ? "midi" : "audio",
    start_time_beats: fromArrangement ? clip.startTime : null,
    length_beats: clip.duration,
    loop_start_beats: clip.looping ? clip.loopStart : null,
    loop_end_beats: clip.looping ? clip.loopEnd : null,
    warp_enabled: clip instanceof AudioClip ? clip.warping : null,
    audio_file: clip instanceof AudioClip ? clip.filePath : null,
    midi_note_count: null as number | null,
    raw_source: {
      handle_id: String(clip.handle.id),
      from_arrangement: fromArrangement,
      muted: clip.muted,
    },
  };
  if (clip instanceof MidiClip) {
    try {
      base.midi_note_count = clip.notes.length;
    } catch {
      base.midi_note_count = null;
    }
  }
  return base;
}

async function serializeSends(
  track: Track<typeof API_VERSION>,
  trackId: string,
  returnIds: string[],
  returnNames: string[],
): Promise<Record<string, unknown>[]> {
  const sendParameters = track.mixer.sends;
  const values = await Promise.all(
    sendParameters.map((parameter) => parameter.getValue().catch(() => null)),
  );
  const sends: Record<string, unknown>[] = [];
  sendParameters.forEach((parameter, i) => {
    const value = values[i];
    if (value === null || value === undefined) return;
    if (i >= returnIds.length) return;
    // Only audibly-routed sends: raw value above the parameter minimum.
    if (value <= parameter.min + 1e-9) return;
    sends.push({
      id: `send-${trackId}-${i}`,
      source_track_id: trackId,
      target_return_id: returnIds[i],
      send_name: returnNames[i],
      level_db: null, // raw normalized value is not a dB figure
      enabled: true,
    });
  });
  return sends;
}

async function serializeTrack(
  track: Track<typeof API_VERSION>,
  index: number,
  returnIds: string[],
  returnNames: string[],
): Promise<Record<string, unknown>> {
  const trackId = id("track", track);
  const trackType =
    track instanceof AudioTrack
      ? "audio"
      : track instanceof MidiTrack
        ? "midi"
        : "group";

  const clips: Record<string, unknown>[] = [];
  track.clipSlots.forEach((slot, sceneIndex) => {
    const clip = slot.clip;
    if (clip !== null) {
      clips.push(serializeClip(clip, trackId, `scene-${sceneIndex}`, false));
    }
  });
  for (const clip of track.arrangementClips) {
    clips.push(serializeClip(clip, trackId, null, true));
  }

  const [volumeRaw, panRaw] = await Promise.all([
    track.mixer.volume.getValue().catch(() => null),
    track.mixer.panning.getValue().catch(() => null),
  ]);

  return {
    id: trackId,
    index,
    name: track.name,
    track_type: trackType,
    role: null, // classified by the explorer on import
    color: null, // not exposed by API 1.0.0
    volume_db: null, // raw mixer value is normalized, not dB — see raw_source
    pan: panRaw,
    mute: track.mute,
    solo: track.solo,
    armed: track.arm,
    clips,
    devices: await serializeDeviceChain(track, trackId),
    sends: await serializeSends(track, trackId, returnIds, returnNames),
    group_id: track.groupTrack ? id("track", track.groupTrack) : null,
    raw_source: {
      handle_id: String(track.handle.id),
      mixer_volume_raw: volumeRaw,
      mixer_volume_min: track.mixer.volume.min,
      mixer_volume_max: track.mixer.volume.max,
      muted_via_solo: track.mutedViaSolo,
    },
  };
}

async function buildProjectState(
  api: Api,
  onProgress: (text: string, progress: number) => Promise<void>,
): Promise<Record<string, unknown>> {
  const song = api.application.song;
  const warnings: string[] = [
    "Exported through the Ableton Extensions SDK (API 1.0.0) — a partial " +
      "observation of the Live Set, not a full reconstruction.",
    "Mixer volume/send values are raw normalized parameter values, not dB; " +
      "raw values are preserved in raw_source.",
    "Track colors, device on/off state, parameter automation state, and " +
      "the Live Set name are not exposed by API 1.0.0.",
  ];

  const returnTrackObjects = song.returnTracks;
  const returnIds = returnTrackObjects.map((r) => id("return", r));
  const returnNames = returnTrackObjects.map((r) => r.name);

  const scenes = song.scenes.map((scene, index) => ({
    id: `scene-${index}`,
    index,
    name: scene.name || null,
    tempo: scene.tempo > 0 ? scene.tempo : null,
  }));

  const tracks: Record<string, unknown>[] = [];
  const trackObjects = song.tracks;
  for (let i = 0; i < trackObjects.length; i++) {
    const track = trackObjects[i];
    if (track === undefined) continue;
    await onProgress(
      `Reading track ${i + 1}/${trackObjects.length}: ${track.name}`,
      Math.round((i / Math.max(trackObjects.length, 1)) * 70),
    );
    try {
      tracks.push(await serializeTrack(track, i, returnIds, returnNames));
    } catch (error) {
      warnings.push(`Track ${i} ('${track.name}') could not be read: ${error}`);
    }
  }

  await onProgress("Reading return tracks…", 75);
  const returnTracks: Record<string, unknown>[] = [];
  for (let i = 0; i < returnTrackObjects.length; i++) {
    const returnTrack = returnTrackObjects[i];
    if (returnTrack === undefined) continue;
    try {
      returnTracks.push({
        id: returnIds[i],
        index: i,
        name: returnTrack.name,
        devices: await serializeDeviceChain(returnTrack, returnIds[i] ?? ""),
        volume_db: null,
      });
    } catch (error) {
      warnings.push(`Return track ${i} could not be read: ${error}`);
    }
  }

  await onProgress("Reading main track…", 85);
  const main = song.mainTrack;
  const masterTrack = {
    id: id("master", main),
    name: main.name || "Main",
    devices: await serializeDeviceChain(main, id("master", main)),
    volume_db: null,
  };

  return {
    schema_version: SCHEMA_VERSION,
    project_name: "Live Set (Extensions SDK export)",
    tempo: song.tempo,
    time_signature: null, // song-level signature is not exposed by API 1.0.0
    scenes,
    tracks,
    return_tracks: returnTracks,
    master_track: masterTrack,
    warnings,
    metadata: {
      source: "ableton-extensions-sdk",
      daw_dialect: "ableton-style",
      api_version: API_VERSION,
      exported_at: new Date().toISOString(),
      scale: {
        root_note: song.rootNote,
        scale_name: song.scaleName,
        scale_mode: song.scaleMode,
      },
    },
  };
}

async function exportSessionState(api: Api): Promise<void> {
  const outputDirectory =
    api.environment.storageDirectory ?? api.environment.tempDirectory;
  if (outputDirectory === undefined) {
    console.error(
      "Session State Exporter: no storage or temp directory available.",
    );
    return;
  }
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const outputPath = path.join(outputDirectory, `session_state_${stamp}.json`);

  await api.ui.withinProgressDialog(
    "Exporting session state…",
    { progress: 0 },
    async (update, signal) => {
      const project = await buildProjectState(api, async (text, progress) => {
        if (signal.aborted) throw new Error("Export cancelled");
        await update(text, progress);
      });
      await update("Writing JSON…", 95);
      await fs.writeFile(outputPath, JSON.stringify(project, null, 2), "utf8");
      await update(`Written: ${outputPath}`, 100);
      console.log(`Session State Exporter: wrote ${outputPath}`);
      return outputPath;
    },
  );
}

export function activate(context: ActivationContext): void {
  const api = initialize(context, API_VERSION);

  api.commands.registerCommand("exportSessionState", () => {
    void exportSessionState(api);
  });

  // No Song-level scope exists in API 1.0.0; the whole-set export is offered
  // from track and scene context menus instead.
  void api.ui.registerContextMenuAction(
    "AudioTrack",
    "Export Session State JSON",
    "exportSessionState",
  );
  void api.ui.registerContextMenuAction(
    "MidiTrack",
    "Export Session State JSON",
    "exportSessionState",
  );
  void api.ui.registerContextMenuAction(
    "Scene",
    "Export Session State JSON",
    "exportSessionState",
  );
}
