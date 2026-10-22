import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

/**
 * Copy text and narrate the outcome, the same way everywhere. Success toasts
 * "<label> copied to clipboard"; a refusal toasts the manual fallback
 * instead of rejecting into the click handler. Returns true on success.
 */
export async function copyTextWithToast(text, label) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    toast.error("Copy failed — select the text manually instead.");
    return false;
  }
  toast.success(`${label} copied to clipboard`);
  return true;
}

/**
 * The copied indicator behind a copy button: which key was just copied,
 * clearing itself after `resetMs`. One owner for the clipboard + toast +
 * timer trio; callers keep their own labels and testids.
 */
export function useCopyButton(resetMs = 1500) {
  const [copiedKey, setCopiedKey] = useState(null);
  const resetTimer = useRef(null);

  useEffect(() => () => {
    if (resetTimer.current) clearTimeout(resetTimer.current);
  }, []);

  const copy = useCallback(async (key, text, label) => {
    const ok = await copyTextWithToast(text, label);
    if (!ok) return false;
    setCopiedKey(key);
    if (resetTimer.current) clearTimeout(resetTimer.current);
    resetTimer.current = setTimeout(() => setCopiedKey(null), resetMs);
    return true;
  }, [resetMs]);

  return { copiedKey, copy };
}
