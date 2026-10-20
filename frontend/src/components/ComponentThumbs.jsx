import { useEffect, useRef, useState } from "react";
import { ThumbPair } from "./ThumbPair";
import { recordThumb } from "../lib/feedback";

/**
 * Thumbs verdict on one piece of the video (goal, template, plan, script or
 * the generated video itself). Each component's votes only ever teach the AI
 * step that produces it.
 *
 * `resetKey` clears the pressed thumb when the rated item changes.
 * `initialValue` restores the founder's saved vote (1, -1 or 0) so a thumb
 * stays highlighted across reloads and return visits; `onVoted` reports a
 * freshly saved vote back so the parent can keep it highlighted even before
 * the next fetch.
 */

export function ComponentThumbs({
  component,
  refs,
  question,
  hint,
  resetKey = "",
  initialValue = 0,
  onVoted,
  disabled = false,
  testId,
}) {
  const startValue = (v) => (v > 0 ? 1 : v < 0 ? -1 : 0);
  const [value, setValue] = useState(() => startValue(initialValue));
  const [saved, setSaved] = useState(null);
  // The last (resetKey, initialValue) actually applied. Without this, an own
  // vote round-tripping back through initialValue would clear the "Thanks"
  // confirmation the vote just earned.
  const appliedRef = useRef({ key: undefined, init: undefined });

  useEffect(() => {
    const start = startValue(initialValue);
    const prev = appliedRef.current;
    if (prev.key !== resetKey || prev.init !== start) {
      appliedRef.current = { key: resetKey, init: start };
      setValue(start);
      // A new item clears everything; a changed vote on the same item only
      // moves the highlight and leaves the confirmation alone.
      if (prev.key !== resetKey) setSaved(null);
    }
  }, [resetKey, initialValue]);

  const onChange = async (next) => {
    setValue(next);
    setSaved(null);
    if (next === 0) return;
    const ok = await recordThumb(component, next, refs);
    if (!ok) {
      setSaved("failed");
      setValue(appliedRef.current.init ?? 0);
      return;
    }
    setSaved("saved");
    appliedRef.current = { key: resetKey, init: next };
    onVoted?.(component, next);
  };

  return (
    <div
      className="inset-panel flex flex-wrap items-center justify-between gap-2"
      data-testid={testId}
    >
      <div className="min-w-0 space-y-0.5">
        <span className="eyebrow block">{question}</span>
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {saved === "saved"
            ? "Thanks — future suggestions for this app will learn from it."
            : saved === "failed"
              ? "Could not save your rating. Try again."
              : hint}
        </p>
      </div>
      <ThumbPair
        value={value}
        disabled={disabled}
        upLabel="Good"
        downLabel="Not good"
        testId={`${testId}-thumb`}
        onChange={onChange}
      />
    </div>
  );
}
