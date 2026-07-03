# Mapping the session model to Cubase / VST3 concepts

The session-state model in this prototype is **DAW-agnostic by design**: its
vocabulary (tracks, clips, scenes, devices, parameters, sends, returns,
master) is instantiated here in an Ableton-style dialect, but each concept has
a direct counterpart in Steinberg's Cubase and the VST3 ecosystem. This
document records that mapping — it is a design argument, not an implemented
importer.

Sessions declare their dialect via the `metadata.daw_dialect` convention
(`"ableton-style"`, `"cubase-style"`, or `"generic"`).

## Concept mapping

| Session model | Ableton-style reading | Cubase-style reading |
|---|---|---|
| `ProjectState` | Live Set | Project (`.cpr`) |
| `TrackState` (audio/midi/group) | Audio/MIDI/Group Track | Audio/Instrument/MIDI/Group Track |
| `ClipState` | Session/Arrangement Clip | Audio Event / Part, MIDI Part |
| `SceneState` | Scene (Session View) | Cycle markers / Arranger events (closest analogue — Cubase has no session grid) |
| `DeviceState` | Device in a device chain | Insert effect slot / Instrument (VST3 plug-in or channel strip module) |
| `DeviceParameterState` | Device parameter | VST3 `IEditController` parameter (id, normalized value, unit) |
| `SendState` | Send to a return track | Send slot targeting an FX Channel |
| `ReturnTrackState` | Return track | FX Channel Track |
| `MasterTrackState` | Master track | Stereo Out bus (master channel) |
| `raw_source` / `warnings` | Unparsed `.als` remainder | Unparsed `.cpr` / preset remainder |

## Notes on observability

- **VST3 parameters are the strongest part of the mapping.** The VST3 SDK is
  public, and its parameter model (stable ids, normalized 0–1 values, host
  visibility, automation flags) is exactly what `DeviceParameterState`
  encodes. `is_visible_to_host` and `is_automated` are VST3-native notions.
- **Cubase Track Archives** (`.xml` track export) are a semi-open interchange
  surface: unlike the binary `.cpr` format, they are XML and could ground a
  cautious `cubase-style` importer analogous to this prototype's `.als`
  inspector — same partial-observability posture.
- **Scenes are the one paradigm gap.** Cubase's linear Arranger differs from
  Ableton's session grid; the model keeps `SceneState` optional so a
  cubase-style instantiation simply omits scenes or maps Arranger sections.
- **Channel strip modules** (Cubase's built-in EQ/dynamics per channel) map
  naturally to `DeviceState` entries with a `device_type` of
  `"channel_strip"` — the family classifier already covers them by name.

## Why this matters for the research

The research questions (representation, prediction, outcome linkage,
explanation) are DAW-independent; only the instantiation layer changes. A
Cubase-side instantiation developed with Steinberg would exercise the same
typed graph schema, the same descriptor linkage, and the same explanation
contract — with the advantage of first-party access to project structures and
edit histories that no external tool can observe.
