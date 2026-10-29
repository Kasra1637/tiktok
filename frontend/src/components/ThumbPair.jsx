import { ThumbsUp, ThumbsDown } from "lucide-react";
import { Button } from "./ui/button";

/**
 * Thumbs-only verdict control for the CreateVideo AI refinement loop.
 *
 * Two buttons, no text input: up locks the current option and (via the
 * parent) advances, down records the rejection and asks the AI to refine.
 * Clicking the active thumb again clears the verdict (undo) without
 * recording a second event — the parent records only on a real change.
 *
 * Parent owns advancement and refinement; this is presentation + undo only.
 */
export function ThumbPair({
  value = 0,
  onChange,
  disabled = false,
  size = "sm",
  upLabel = "Looks good",
  downLabel = "Refine this",
  testId = "thumb-pair",
}) {
  const current = value > 0 ? 1 : value < 0 ? -1 : 0;
  const pick = (next) => {
    if (disabled) return;
    onChange?.(current === next ? 0 : next);
  };
  return (
    <div className="thumb-pair flex flex-wrap items-center gap-2" data-testid={testId}>
      <Button
        type="button"
        variant={current === 1 ? "brand" : "secondary"}
        size={size}
        className={`tap-chip${current === 1 ? " thumb-selected" : ""}`}
        disabled={disabled}
        aria-pressed={current === 1}
        aria-label={upLabel}
        title={upLabel}
        data-testid={`${testId}-up`}
        onClick={() => pick(1)}
      >
        <ThumbsUp className="h-4 w-4" />
        {upLabel}
      </Button>
      <Button
        type="button"
        variant={current === -1 ? "brand" : "secondary"}
        size={size}
        className={`tap-chip${current === -1 ? " thumb-selected" : ""}`}
        disabled={disabled}
        aria-pressed={current === -1}
        aria-label={downLabel}
        title={downLabel}
        data-testid={`${testId}-down`}
        onClick={() => pick(-1)}
      >
        <ThumbsDown className="h-4 w-4" />
        {downLabel}
      </Button>
    </div>
  );
}
