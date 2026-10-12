import { useEffect, useState } from "react";
import { ThumbPair } from "./ThumbPair";
import { recordThumb } from "../lib/feedback";

/**
 * Thumbs verdict on one piece of the video (goal, template, plan or script).
 * Each component's votes only ever teach the AI step that produces it.
 * `resetKey` clears the pressed thumb when the rated item changes.
 */
export function ComponentThumbs({
  component,
  refs,
  question,
  hint,
  resetKey = "",
  disabled = false,
  testId,
}) {
  const [value, setValue] = useState(0);
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    setValue(0);
    setSaved(null);
  }, [resetKey]);

  const onChange = async (next) => {
    setValue(next);
    setSaved(null);
    if (next === 0) return;
    const ok = await recordThumb(component, next, refs);
    setSaved(ok ? "saved" : "failed");
    if (!ok) setValue(0);
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
