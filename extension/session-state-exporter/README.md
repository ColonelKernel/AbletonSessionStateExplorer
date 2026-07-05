# Session State Exporter — Ableton Live extension

A minimal Live extension (built on Ableton's public **Extensions SDK**,
1.0.0-beta) that exports the current Live Set's structure as JSON in the
[Session State Explorer](../../README.md) schema. It turns the explorer's
"Upload session JSON" mode into a **real-session pathway**: right-click a
track or scene in Live → *Export Session State JSON* → load the file in the
explorer for graph, recommendations, diff, and prediction.

## What it exports

- Tracks (audio/MIDI/group), mute/solo/arm, group membership
- Session-view clips (with scene mapping) and arrangement clips
  (with beat positions), audio file paths, warp state, MIDI note counts
- Device chains, recursing through racks (chain path recorded in
  `raw_source.rack_path`); parameter names, ranges, and values
  (value round-trips capped at 64 per device, recorded when capped)
- Active sends (raw level above the parameter minimum), return tracks,
  the main track's chain
- Scenes, song tempo, and the current scale settings

## What it deliberately does not guess

API 1.0.0 does not expose track colors, device on/off state, automation
state, dB-calibrated mixer values, or the Live Set name. The export records
these as `null` and preserves raw observations in `raw_source` — the
explorer treats absence as partial observability, never as fact.
`device_family` and track `role` are left `null` on purpose: they are
explorer-side heuristics, backfilled on upload.

## Build

```bash
cd extension/session-state-exporter
npm install
npm run build        # tsc --noEmit && esbuild bundle → dist/extension.js
```

The SDK and CLI are consumed from the repo's vendored
`extensions-sdk-1.0.0-beta.0/` tarballs.

## Run in Live

Requires a Live version with Extensions support (12.3+ beta) and Developer
Mode enabled (Preferences → Extensions). Then, per the SDK docs:

```bash
npm start            # builds and launches the Extension Host against Live
```

The export lands in the extension's storage directory (path is printed in
the extension console and shown in the progress dialog).

## Status

**Verified end-to-end in Ableton Live 12.4.5 beta**: packaged as `.ablx`,
installed via Live's Extensions settings page, invoked from a track context
menu on a real Live Set, and the resulting JSON (110 KB, 276 graph nodes)
validated and ran through the explorer's full pipeline — graph,
recommendations, tables. Screenshots of the real-session run are in
[docs/screenshots/](../../docs/screenshots/) (`09`–`11`). The Extensions SDK
is beta software; this exporter is a research bridge, not a product.
