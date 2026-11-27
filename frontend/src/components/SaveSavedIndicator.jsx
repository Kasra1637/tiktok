import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { onSaved } from "../lib/saveSignal";

/**
 * The single saved indicator (Kasra's order, Nov 27 2026): one
 * green check, icon only, no words, seated at the top of the page
 * in the app chrome — AppShell mounts this one instance, so every
 * page reads the same signal in the same seat. It stands only
 * once a save has completed, and every completed autosave
 * re-triggers it: the save count keys the element, so each save
 * remounts it and its pulse plays anew instead of the icon
 * sitting static from the first save on. What saves, and when,
 * is unchanged — the pages' own autosaves call the signal at
 * their existing completion points (see lib/saveSignal.js).
 */
export function SaveSavedIndicator() {
  const [saves, setSaves] = useState(0);
  useEffect(() => onSaved(() => setSaves((count) => count + 1)), []);
  if (!saves) return null;
  return (
    <span
      key={saves}
      data-testid="autosave-saved-check"
      role="status"
      aria-label="All changes saved"
      className="save-check-pop fixed right-4 top-16 z-30 flex h-9 w-9 items-center justify-center rounded-full border border-[color:var(--hairline)] bg-[hsl(228_14%_7%_/_0.85)] backdrop-blur-xl lg:right-6 lg:top-5"
    >
      <Check className="h-5 w-5 text-green-500" aria-hidden="true" />
    </span>
  );
}

export default SaveSavedIndicator;
