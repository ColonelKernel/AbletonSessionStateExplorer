# Research context

**Ableton Session State Explorer v0** is a proof-of-fit prototype for the
research theme *Interpretable DAW-State Graphs for Human-Centered AI-Assisted
Music Production*, prepared for a preliminary PhD application to the Music
Technology Group (Universitat Pompeu Fabra) in collaboration with Steinberg.

## 1. DAW-state representation as a research object

Digital audio workstation sessions encode a substantial fraction of a
producer's craft: track organization, routing topology, device chains and
their ordering, clip/scene arrangement, and gain structure. This knowledge is
largely invisible to current AI music systems, which typically operate on
rendered audio, text prompts, or isolated plugin parameters. The prototype's
premise is that **session state itself is a first-class research object**, and
that making it explicit, typed, and inspectable is a prerequisite for
assistance systems that reason about production practice rather than only its
acoustic output.

## 2. An Ableton-style session model

The prototype defines an explicit, Python-native model of an Ableton-style
session (`models.py`): tracks (audio, MIDI, group, return, master), clips with
scene assignments and audio-file references, devices with parameter
placeholders, sends, return tracks, and a master chain. The model is
*Ableton-style* rather than *Ableton-derived*: it mirrors the structural
vocabulary of Ableton Live's session view without claiming to reproduce Live
Set semantics. This keeps the representation controllable, documentable, and
independent of proprietary internals, while remaining close enough to real
DAW practice to support meaningful analysis.

## 3. Partial observability, taken seriously

Real DAW-state access is always partial: proprietary formats, plugin-internal
state, and undocumented semantics bound what any external system can observe.
The prototype represents this honestly rather than hiding it:

- Every model carries `raw_source` and `warnings` fields; the graph metadata
  counts *uncertain or placeholder elements*.
- The experimental `.als` inspector performs only surface-level gzip/XML tag
  counting on uploaded Live Sets and labels itself as exploratory — a concrete
  demonstration that partial observability is a property of the ecosystem,
  not a temporary implementation gap.
- The export adapter distinguishes cleanly between supported export
  (`ableton_export`), transparent fallback (`mock_export`), and JSON-only
  operation, and documents what was omitted in each case.

Modeling *what is not known* is itself a research contribution direction:
assistance systems should reason under, and communicate, uncertainty about
session structure.

## 4. Graph-based session modeling

Session state is compiled into a directed, typed graph (`graph_builder.py`)
with eleven node types and twelve edge types covering containment
(project→scene/track, track→clip/device), reference (clip→audio file,
clip→scene), and signal-flow (track→send→return, track→master) relations.
The graph form has three research advantages:

1. **Interpretability** — every node and edge corresponds to a nameable
   production concept; nothing is a latent code.
2. **Analyzability** — routing questions ("which tracks reach the reverb
   return?") become graph queries; structural statistics (density, per-type
   counts) become session fingerprints.
3. **Extensibility toward learning** — typed graphs are the natural input for
   graph neural networks, enabling future work on session embeddings,
   next-action prediction, and version diffing without abandoning the
   interpretable substrate.

## 5. Linking structure to sound: audio descriptors

Uploaded stems, loops, or mixdowns are analyzed with standard MIR descriptors
(`audio_descriptors.py`): RMS statistics, peak, spectral centroid/bandwidth/
rolloff, zero-crossing rate, onset strength, tempo estimate, a crest-factor
dynamic-range approximation, and optionally integrated loudness (LUFS).
Descriptor sets attach to graph entities (project mixdown, track, or clip),
so acoustic evidence and symbolic session structure live in one joint
representation. This is the seed of a broader research question: *how do
structural production decisions relate to measurable acoustic outcomes?*

## 6. Explainable recommendations and producer agency

The recommendation engine (`recommendations.py`) is deliberately rule-based
in v0. Six heuristics read the graph and descriptors — shared-ambience routing
opportunities, vocal chains without corrective stages, unused return tracks,
dense device chains, master limiting without loudness context, and
descriptor-level imbalances. Each recommendation carries:

- an **explanation** grounded in named graph structure,
- a **suggested action** phrased as an option, never an instruction,
- an explicit **caveat** acknowledging stylistic legitimacy of the flagged
  pattern,
- a **confidence** value, and
- the **graph node ids** it reasons about, making every claim inspectable.

The engine is presented as a heuristic prototype, not as AI mixing. The design
position is human-centered: the system surfaces *candidate workflow checks*
and preserves the producer's authority over every decision. Rule-based v0
establishes the explanation contract that any future learned model must also
satisfy — a "explanations by construction" baseline against which learned
recommenders can be evaluated for faithfulness.

## 7. Relevance to an MTG / Steinberg PhD

The Music Technology Group's strengths in music information retrieval and
Steinberg's position as a DAW vendor meet exactly at this prototype's seam:
between audio-level analysis and session-level structure. The prototype
demonstrates, at small scale, the full pipeline a thesis would deepen —
**represent** (typed session model), **observe** (partial `.als`/export
bridges), **structure** (typed graphs), **measure** (descriptors), and
**explain** (grounded recommendations). The session model is Ableton-style
but DAW-agnostic in design, which matters for a Steinberg collaboration:
the same graph substrate applies to Cubase-style project state, and the
research questions — representation, partial observability, explanation,
agency — are vendor-independent.
