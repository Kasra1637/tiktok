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

## Consequences

- The strategy prompt ceiling rises by a measured 2,000 to 26,500 characters.
- Scene detection is lexical; an angle whose moment names no place or time
  leaves options and looks untouched rather than guessing.
