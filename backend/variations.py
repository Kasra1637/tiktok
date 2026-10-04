"""
Controlled video variations.

A variation is a deliberate, founder-initiated change to one dimension of an
existing project. It copies the project, applies exactly one change, and
records the parent so the whole family stays linked: App Profile, template
version, script version, assets, model, and parent generation.

Two rules shape this module:

- Variations are never generated in bulk. Each one takes a separate, explicit
  founder action, and a variation only produces a DRAFT project. Producing the
  video is a second, separate decision.
- Cheap changes stay cheap. Changing the template, duration, tone, or
  audience only rewrites project fields and needs no model call at all.
  Changing the hook, feature, or visual opening needs a fresh script,
  which is a text call, not a video call.
- No axis promises a call to action. A generated piece has no closing beat:
  the founder records their own demo and close. The axis that used to swap one
  was removed rather than relabelled, because there was nothing left for it to
  change.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Fields a variation is allowed to change. A request naming anything else is
# refused rather than silently ignored, so a client cannot smuggle in an
# unrelated edit.
#
# 'script' is included because a new hook line is spoken first: changing only
# hook_line would leave the script opening with the old line, so the two would
# contradict each other in the finished video.
#
# 'cta' used to be here. It is gone because there is no call to action in a
# generated piece: the middle ends at the moment the viewer would reach for the
# app, and the founder records their own demo and close. An axis that wrote the
# retired column was a control that looked like it changed the video and could
# not. The `cta` column survives in the SQLite schema for rows written before
# this, and nothing writes or reads it.
ALLOWED_FIELDS = frozenset({
    "hook_line", "audience", "tone", "pacing",
    "template_id", "visual_direction", "feature_emphasis", "duration_seconds",
    "script",
})


class VariationSpec:
    """How one variation axis behaves."""

    def __init__(self, key, label, description, needs_plan=False,
                 fields=(), value_kind="text", choices=None):
        self.key = key
        self.label = label
        self.description = description
        # True when the change is creative enough that the script must be
        # rewritten. A video call is never implied by this flag.
        self.needs_plan = needs_plan
        self.fields = tuple(fields)
        self.value_kind = value_kind  # text | int | template | choice
        self.choices = tuple(choices) if choices else ()


PACING_CHOICES = ("faster", "slower")

VARIATIONS = {
    spec.key: spec
    for spec in (
        VariationSpec(
            "hook_line", "New hook line",
            "Rewrites the opening line that earns the first 3 seconds.",
            needs_plan=True, fields=("hook_line",),
        ),
        VariationSpec(
            "audience", "Different audience segment",
            "Retargets the same angle to another segment from the App Profile.",
            needs_plan=True, fields=("audience",),
        ),
        VariationSpec(
            "tone", "Different tone",
            "Re-casts the delivery, e.g. calmer or more playful.",
            needs_plan=True, fields=("tone",),
        ),
        VariationSpec(
            "pacing", "Faster or slower pacing",
            "Tightens or loosens the camera and cut rhythm.",
            needs_plan=True, fields=("pacing",),
            value_kind="choice", choices=PACING_CHOICES,
        ),
        VariationSpec(
            "template", "Different hook template",
            "Same product and script, different creative structure. Free.",
            fields=("template_id",), value_kind="template",
        ),
        VariationSpec(
            "visual_opening", "Alternate visual opening",
            "Reimagine what the camera shows first.",
            needs_plan=True, fields=("visual_direction",),
        ),
        VariationSpec(
            "app_feature", "Alternate app feature",
            "Demonstrate a different verified feature from the same profile.",
            needs_plan=True, fields=("feature_emphasis",),
        ),
        VariationSpec(
            "duration", "Alternate video length",
            "Same content, different length. Free: no model call.",
            fields=("duration_seconds",), value_kind="int",
        ),
    )
}


def list_variations() -> list:
    """Public catalogue for the UI."""
    return [
        {
            "key": v.key,
            "label": v.label,
            "description": v.description,
            "needs_plan": v.needs_plan,
            "fields": list(v.fields),
            "value_kind": v.value_kind,
        }
        for v in VARIATIONS.values()
    ]


def get_variation(key: str) -> Optional[VariationSpec]:
    return VARIATIONS.get((key or "").strip().lower())


def coerce_value(spec: VariationSpec, value):
    """
    Normalise a variation's value for its field type.

    Returns the coerced value, or raises ValueError with a message the API can
    surface directly.
    """
    if spec.value_kind == "int":
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError("Variation value must be a whole number of seconds.")
        if number < 3 or number > 120:
            raise ValueError("Duration must be between 3 and 120 seconds.")
        return number

    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("A variation needs a value.")

    if spec.value_kind == "choice":
        lowered = text.lower()
        if lowered not in spec.choices:
            raise ValueError(
                f"'{text}' is not valid here. Choose one of: {', '.join(spec.choices)}."
            )
        return lowered

    if len(text) > 600:
        raise ValueError("That value is too long to be a useful variation.")
    return text


def pacing_directive(pacing: str) -> str:
    """
    Prompt fragment for a pacing change.

    Pacing is a camera/editing property, so it is expressed as direction
    rather than as a new number: the beat timings stay the reviewer's call.
    """
    if pacing == "faster":
        return (
            "PACING: FAST. Cut on the beat, hold each beat for no longer than it takes "
            "to read it, no lingering shots, energy up throughout."
        )
    if pacing == "slower":
        return (
            "PACING: SLOW AND DELIBERATE. Let each beat land, hold longer on the "
            "product in use, fewer cuts, calmer energy."
        )
    return ""


def apply_variation(project: dict, spec: VariationSpec, value) -> tuple:
    """
    Work out the project changes a variation implies.

    Returns (updates, prompt_additions). The caller writes the updates and
    decides whether to regenerate the plan. Nothing here touches the database
    or touches the database.
    """
    coerced = coerce_value(spec, value)
    updates = {}
    additions = []

    for field in spec.fields:
        if field == "pacing":
            directive = pacing_directive(coerced)
            if directive:
                additions.append(directive)
            # Pacing is not a stored project field of its own; it is folded
            # into the visual direction so it survives an edit round-trip.
            current = (project.get("visual_direction") or "").strip()
            marker = "PACING:"
            base = "\n".join(
                line for line in current.splitlines() if not line.strip().startswith(marker)
            ).strip()
            updates["visual_direction"] = f"{base}\n{directive}".strip() if base else directive
        else:
            updates[field] = coerced

    if spec.key == "hook_line" and coerced:
        # The hook line is spoken first, so the script must open with it.
        current_script = (project.get("script") or "").strip()
        if current_script:
            updates["script"] = f"{coerced} {current_script}".strip()

    return updates, additions
