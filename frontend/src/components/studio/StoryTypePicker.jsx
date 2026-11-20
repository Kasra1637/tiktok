import { Check } from "lucide-react";
import { STORY_TYPES } from "../../lib/storyTypes";

/**
 * The four story types as pickable cards (ADR 0235).
 *
 * A story's type is its aim — where a hook video picks an objective
 * and a template, a story picks one of these, and the type carries
 * the frame's default length with it. The cards wear the wizard's
 * pickable-card treatment (the App Profile step's app cards): the
 * picked card takes the indigo border and wash, a check names the
 * pick, and `aria-pressed` says it to assistive tech.
 *
 * The catalog itself lives in `lib/storyTypes.js`, mirrored from
 * `backend/story_types.py`; this component only presents it.
 */
export function StoryTypePicker({ value, onChange, disabled = false }) {
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2" data-testid="story-type-picker">
      {STORY_TYPES.map((storyType) => {
        const picked = value === storyType.id;
        return (
          <button
            key={storyType.id}
            type="button"
            aria-pressed={picked}
            disabled={disabled}
            onClick={() => onChange(storyType.id)}
            data-testid={`story-type-${storyType.id}`}
            className={`card-pickable row-pad w-full rounded-xl border text-left ${
              picked
                ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-display text-sm font-semibold">{storyType.name}</span>
              {picked && <Check className="h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">{storyType.description}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              Frame length {storyType.defaultSeconds}s
            </p>
          </button>
        );
      })}
    </div>
  );
}

export default StoryTypePicker;
