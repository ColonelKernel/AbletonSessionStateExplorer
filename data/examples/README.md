# Example data

- `example_session.json` — the built-in demo session ("Indie Vocal Production
  Sketch") serialized in this prototype's session schema. Use it as a template
  for the **Upload session JSON** mode, or as the comparison file for the
  session fingerprint feature.
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
