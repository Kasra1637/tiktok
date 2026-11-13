import { useEffect, useRef, useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "./ui/button";
import { api, getErrorMessage } from "../lib/api";

/**
 * The founder's one verdict on a whole finished video (ADR 0124).
 *
 * One move, on the video exactly as it went out — spoken words, opening
 * visual, captions and hashtags together — because neither the founder
 * nor TikTok can say which element made a video work. This control is
 * the only rating left: it replaces the per-element thumbs (goal,
 * template, plan, script, render) that used to teach each AI stage
 * separately. Setting a verdict freezes the bundle server-side; later
 * edits never rewrite what was judged.
 *
 * State rules mirror the vote controls this replaces: a just-cast
 * verdict shows at once, a save in flight swallows further taps, a
 * response for a superseded tap is ignored, and a failed save restores
 * the last confirmed verdict instead of leaving a pressed button
 * claiming a verdict the server never took. Clicking the active side
 * again clears the verdict.
 */
export function VideoVerdict({ generationId, value = null, onChanged }) {
  const [verdict, setVerdict] = useState(value || null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const confirmedRef = useRef(value || null);
  const pendingRef = useRef(null);

  // The row's own verdict arriving from a refetch stands in for ours
  // until we cast one; our in-flight tap is never overridden by it.
  useEffect(() => {
    if (pendingRef.current) return;
    confirmedRef.current = value || null;
    setVerdict(value || null);
  }, [value, generationId]);

  // A save in flight belongs to the render it was cast on: if this
  // control unmounts or moves to another generation before the response
  // lands, the response is superseded and must notify no one.
  useEffect(() => () => { pendingRef.current = null; }, [generationId]);

  const cast = async (next) => {
    if (pendingRef.current) return;
    const target = verdict === next ? null : next;
    const request = {};
    pendingRef.current = request;
    setVerdict(target);
    setSaved(false);
    setError(null);
    try {
      const updated = await api.setVideoVerdict(generationId, target);
      if (pendingRef.current !== request) return;
      const confirmed = updated?.video_verdict ?? target;
      confirmedRef.current = confirmed;
      setVerdict(confirmed);
      setSaved(true);
      onChanged?.(confirmed);
    } catch (err) {
      if (pendingRef.current !== request) return;
      setVerdict(confirmedRef.current);
      setError(getErrorMessage(err));
    } finally {
      if (pendingRef.current === request) pendingRef.current = null;
    }
  };

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-2 border-t border-[color:var(--hairline)] pt-2"
      data-testid={`history-verdict-${generationId}`}
    >
      <div className="min-w-0 space-y-0.5">
        <span className="eyebrow block">Did this one work?</span>
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {error
            ? `Could not save your verdict. ${error}`
            : saved
              ? "Verdict saved — new plans learn from this whole video."
              : "One call on the whole video — the words, the look, the captions and the hashtags together."}
        </p>
      </div>
      <div className="thumb-pair flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={verdict === "up" ? "brand" : "secondary"}
          size="sm"
          className={`tap-chip${verdict === "up" ? " thumb-selected" : ""}`}
          aria-pressed={verdict === "up"}
          aria-label="This one worked"
          title="This one worked"
          data-testid={`history-verdict-${generationId}-up`}
          onClick={() => cast("up")}
        >
          <ThumbsUp className="h-3.5 w-3.5" /> This one worked
        </Button>
        <Button
          type="button"
          variant={verdict === "down" ? "brand" : "secondary"}
          size="sm"
          className={`tap-chip${verdict === "down" ? " thumb-selected" : ""}`}
          aria-pressed={verdict === "down"}
          aria-label="This one didn't"
          title="This one didn't"
          data-testid={`history-verdict-${generationId}-down`}
          onClick={() => cast("down")}
        >
          <ThumbsDown className="h-3.5 w-3.5" /> This one didn&rsquo;t
        </Button>
      </div>
    </div>
  );
}
