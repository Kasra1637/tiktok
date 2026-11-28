import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ExternalLink, Link2, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api, getErrorMessage } from "../lib/api";

/**
 * The posted-link section from a render's History card, standing in
 * the render flow directly below the Demo + CTA button (Kasra's
 * order, Nov 27 2026): the founder posts the finished video, comes
 * back, and marks it posted here instead of hunting the card down
 * in History. It acts on the very same render record through the
 * very same saves the History card uses — api.setTikTokLink for the
 * link, api.setVideoVerdict for the verdict — so the two surfaces
 * can never disagree about what is posted or what won.
 *
 * One neat row (Kasra's order): the verdict toggles sit in the same
 * row as the link field and its Save button, aligned, nothing
 * floating. The verdict half keeps VideoVerdict's state rules — a
 * just-cast verdict shows at once, a save in flight swallows
 * further taps, a failed save restores the last confirmed verdict,
 * and tapping the active side again clears it. A "worked" verdict
 * plus a link is a winner, here exactly as on the card.
 */
export function PostedLinkSection({ generation, onUpdated }) {
  const generationId = generation.id;
  const [verdict, setVerdict] = useState(generation.video_verdict || null);
  const [verdictSaved, setVerdictSaved] = useState(false);
  const [verdictError, setVerdictError] = useState(null);
  const confirmedRef = useRef(generation.video_verdict || null);
  const pendingRef = useRef(null);

  useEffect(() => {
    if (pendingRef.current) return;
    confirmedRef.current = generation.video_verdict || null;
    setVerdict(generation.video_verdict || null);
  }, [generation.video_verdict, generationId]);
  useEffect(() => () => { pendingRef.current = null; }, [generationId]);

  const cast = async (next) => {
    if (pendingRef.current) return;
    const target = verdict === next ? null : next;
    const request = {};
    pendingRef.current = request;
    setVerdict(target);
    setVerdictSaved(false);
    setVerdictError(null);
    try {
      const updated = await api.setVideoVerdict(generationId, target);
      if (pendingRef.current !== request) return;
      const confirmed = updated?.video_verdict ?? target;
      confirmedRef.current = confirmed;
      setVerdict(confirmed);
      setVerdictSaved(true);
      onUpdated?.(generationId, { video_verdict: confirmed });
    } catch (err) {
      if (pendingRef.current !== request) return;
      setVerdict(confirmedRef.current);
      setVerdictError(getErrorMessage(err));
    } finally {
      if (pendingRef.current === request) pendingRef.current = null;
    }
  };

  // Posted link: the History card's own block, same words, same
  // save. A link marks the render posted; only a "worked" verdict
  // plus the link counts as a winner.
  const [link, setLink] = useState(generation.tiktok_url || "");
  const [savedLink, setSavedLink] = useState(generation.tiktok_url || null);
  const [savingLink, setSavingLink] = useState(false);
  const [linkError, setLinkError] = useState(null);
  useEffect(() => {
    setLink(generation.tiktok_url || "");
    setSavedLink(generation.tiktok_url || null);
  }, [generationId]); // eslint-disable-line react-hooks/exhaustive-deps
  const isWinner = verdict === "up" && !!savedLink;

  const saveLink = useCallback(async () => {
    setSavingLink(true);
    setLinkError(null);
    try {
      const updated = await api.setTikTokLink(generationId, link.trim());
      setSavedLink(updated.tiktok_url || null);
      setLink(updated.tiktok_url || "");
      onUpdated?.(generationId, { tiktok_url: updated.tiktok_url || null });
    } catch (err) {
      setLinkError(getErrorMessage(err));
    } finally {
      setSavingLink(false);
    }
  }, [generationId, link, onUpdated]);

  const clearLink = useCallback(async () => {
    setSavingLink(true);
    setLinkError(null);
    try {
      await api.setTikTokLink(generationId, "");
      setSavedLink(null);
      setLink("");
      onUpdated?.(generationId, { tiktok_url: null });
    } catch (err) {
      setLinkError(getErrorMessage(err));
    } finally {
      setSavingLink(false);
    }
  }, [generationId, onUpdated]);

  return (
    <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3" data-testid={`posted-link-section-${generationId}`}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="thumb-pair flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant={verdict === "up" ? "brand" : "secondary"}
            size="sm"
            className={`tap-chip${verdict === "up" ? " thumb-selected" : ""}`}
            aria-pressed={verdict === "up"}
            aria-label="This one worked"
            title="This one worked"
            data-testid={`posted-link-verdict-${generationId}-up`}
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
            data-testid={`posted-link-verdict-${generationId}-down`}
            onClick={() => cast("down")}
          >
            <ThumbsDown className="h-3.5 w-3.5" /> This one didn&rsquo;t
          </Button>
        </div>
        {savedLink ? (
          <>
            <Badge variant="secondary" data-testid={`posted-link-posted-${generationId}`}>
              <Check className="h-3 w-3" /> Posted
            </Badge>
            <a
              href={savedLink}
              target="_blank"
              rel="noreferrer"
              data-testid={`posted-link-live-${generationId}`}
              className="inline-flex items-center gap-1 text-sm font-semibold text-[color:var(--brand-indigo)] hover:underline"
            >
              Open live video <ExternalLink className="h-3 w-3" />
            </a>
            {isWinner && (
              <Badge variant="indigo" data-testid={`posted-link-winner-${generationId}`} title="Worked verdict plus posted link — a real winner">
                Winner
              </Badge>
            )}
            <Button
              variant="secondary"
              size="sm"
              disabled={savingLink}
              onClick={clearLink}
              data-testid={`posted-link-clear-${generationId}`}
              title="Remove the posted link"
            >
              <X className="h-3.5 w-3.5" /> Remove
            </Button>
          </>
        ) : (
          <>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <Link2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <Input
                type="url"
                value={link}
                onChange={(e) => setLink(e.target.value)}
                placeholder="Paste the TikTok link once posted…"
                aria-label="TikTok link for this render"
                data-testid={`posted-link-input-${generationId}`}
                disabled={savingLink}
                className="h-9"
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={savingLink || !link.trim()}
              busy={savingLink}
              onClick={saveLink}
              data-testid={`posted-link-save-${generationId}`}
            >
              {savingLink ? "Saving link" : "Save link"}
            </Button>
          </>
        )}
      </div>
      {verdictError && (
        <p role="alert" className="text-sm text-destructive-text">
          Could not save your verdict. {verdictError}
        </p>
      )}
      {!verdictError && verdictSaved && (
        <p className="text-sm text-muted-foreground" aria-live="polite">
          Verdict saved — new plans learn from this whole video.
        </p>
      )}
      {linkError && <p role="alert" className="text-sm text-destructive-text">{linkError}</p>}
      {!savedLink && (
        <p className="text-sm text-muted-foreground">
          Marks this render posted. Only a &ldquo;worked&rdquo; verdict plus a link counts as a winner.
        </p>
      )}
    </div>
  );
}

export default PostedLinkSection;
