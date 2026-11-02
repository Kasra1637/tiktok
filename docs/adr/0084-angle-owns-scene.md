# 0084 — The selected angle owns where, when and what happens

Status: accepted

## Context

A voice-journaling angle opened on "a person steps outside an office building
after a call", yet the video rendered indoors. The look dropdowns were
profile-only (living room, lamp), the plan prompt let the founder's look
override the angle, a template example described "lies in bed at eleven at
night", and the hook read "I don't want to type anything" instead of naming
the real task. Each step was internally reasonable; together they disagreed.

## Decision

- The angle's `hook_promise` is the video's opening moment and fixes its place
  (indoor/outdoor) and time of day. `backend/angle_scene.py` (pure policy)
  derives that scene.
- Direction dropdowns (setting, lighting, wardrobe, voice, tone) are filtered
  against the angle, with the angle's moment offered first and safe fallbacks
  keeping at least three options. The model refresh is filtered the same way.
- A stored look that contradicts the angle is reconciled server-side before
  plan and strategy; the conflicting parts are dropped and the project stores
  `angle_scene_note`, shown on Review. The angle wins (product decision).
- Strategy and plan prompts carry ANGLE SCENE / PLACE + TIME rules; the render
  prompt drops template staging lines that conflict with the locked scene.
- Templates that cannot fit stay listed, ranked lower (-3.0), with a plain
  "Doesn't fit this angle" note first; conflicting examples are hidden and the
  card shows "In your video: <moment>".
- A vague hook ("type anything", "the last thing I want to do") is an advisory
  risk warning only; nothing blocks a render (ADR 0081). The prompt gains a
  NAME THE ACTION rule.
- Only new or regenerated plans follow these rules. Existing drafts keep their
  stored plans; `angle_scene_note` is NULL for old rows.

### Follow-up

- The scene lexicon covers travel and room wording (commute, station, porch,
  cafe; car, gym, apartment). `train`/`bus` are not indoor words, and a
  doorway clause ("steps out of the car outside the cafe") reads as outdoors.
- `scene_is_unclear`: when the moment names no place, strategy and plan
  prompts carry an ANGLE PLACE rule asking the writer to state one concrete
  place that fits the angle, instead of the system guessing.
- One-click hook rewrite: `POST /studio/projects/{id}/rewrite-hook` returns a
  suggested `hook_line` and writes nothing. Review shows "Suggest a clearer
  hook" only beside a vague-hook warning; "Use this line" applies it through
  the normal draft edit (autosave + claim check rerun), "Keep mine" dismisses.
  A failed or unchanged rewrite returns 502 with a next step, never a silent
  fallback line.
- Matching voice/tone mood to the angle's emotion is deferred until a real
  render confirms the place/time binding works end to end.

## Consequences

- The strategy prompt ceiling rises by a measured 2,000 to 26,500 characters.
- Scene detection is lexical; an angle whose moment names no place gets the
  ANGLE PLACE rule, and options and looks stay untouched rather than guessed.
- The hook rewrite is one extra model call, only on founder request.
