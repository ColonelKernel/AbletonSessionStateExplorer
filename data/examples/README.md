# Example data

- `example_session.json` — the built-in demo session ("Indie Vocal Production
  Sketch") serialized in this prototype's session schema. Use it as a template
  for the **Upload session JSON** mode, or as the comparison file for the
  session fingerprint feature.
- `example_session_revision.json` — "Revision 2" of the demo session, with
  the heuristic recommendations enacted. Upload it in the **Session diff**
  section to see the recommendation → action → state-change loop.
- `example_cubase_session.json` — the Cubase-style demo ("Alt-Pop Mix Bus"),
  the second dialect instantiation: linear arranger positions instead of
  scenes, wired FX-channel sends, dialect-supplied device families.
- `placeholder.md` — notes on audio placeholders.

The session schema is defined by the pydantic models in
`src/ableton_session_state_explorer/models.py` (`ProjectState` is the root).
A minimal valid session is just:

```json
{
  "project_name": "My Session",
  "tempo": 120.0,
  "tracks": [
    {"id": "t1", "index": 0, "name": "Drums", "track_type": "audio"}
  ]
}
```

All other fields are optional and default sensibly.
