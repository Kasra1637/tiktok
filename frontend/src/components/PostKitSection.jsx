import { useEffect, useState } from "react";
import { Check, Copy, RotateCcw } from "lucide-react";
import { Button } from "./ui/button";
import { GroupLabel } from "./SectionCard";
import { FactChip, FactList } from "./FactChip";
import { useCopyButton } from "../lib/copyClipboard";
import { api, getErrorMessage } from "../lib/api";
import { BUSY_ETA_SECONDS } from "../lib/busyEta";

/**
 * The frozen post copy for one render: 1 caption, a hashtag set, cover text.
 *
 * Owns display and regeneration. `onUpdated` optionally commits confirmed
 * copy to a containing record (History), so reopening a drawer or switching
 * between it and Details cannot resurrect the old snapshot.
 *
 * A null or empty kit renders nothing — no placeholder, no derived copy.
 * Old renders frozen with three `captions` still display their first one.
 * Shared by History's drawer, the Details modal, the studio output moment,
 * and the export card.
 *
 * Regeneration is explicit: it only runs when the founder clicks Regenerate,
 * and a failure keeps the current copy on screen with the error instead of
 * replacing it.
 *
 * Copy is one action for the whole kit. The three fields are selectable text,
 * so a Copy button beside each one only repeated the same clipboard write
 * three more times beside the label it sat next to.
 *
 * `ttsText` is the silent render's text-to-speech line (ADR 0246): the
 * creation surfaces pass the render's spoken words when the project's
 * voice pick is silent, and the kit shows them as the paste-for-TikTok
 * guidance beside the rest of the post copy. Empty — every talking
 * render, and every caller that does not know the pick — shows nothing.
 */
export function PostKitSection({ postKit: initialKit, generationId, onUpdated, ttsText = "" }) {
  const { copiedKey, copy } = useCopyButton();
  const [kit, setKit] = useState(initialKit);
  const [regenBusy, setRegenBusy] = useState(false);
  const [regenError, setRegenError] = useState(null);
  useEffect(() => { setKit(initialKit); }, [initialKit]);

  const legacyFirst = Array.isArray(kit?.captions)
    ? kit.captions.map((c) => String(c || "").trim()).find((c) => c)
    : "";
  const caption =
    (typeof kit?.caption === "string" && kit.caption.trim()) ||
    legacyFirst ||
    "";
  const hashtags = kit && Array.isArray(kit.hashtags)
    ? kit.hashtags.filter((t) => String(t || "").trim())
    : [];
  const coverText = kit && typeof kit.cover_text === "string"
    ? kit.cover_text.trim()
    : "";

  // A null or empty kit renders nothing: there is nothing honest to show.
  if (!caption && hashtags.length === 0 && !coverText) return null;

  const allText = [caption, hashtags.join(" ")].filter(Boolean).join("\n\n");
  const canRegenerate = !!generationId;

  const handleRegenerate = async () => {
    if (regenBusy || !canRegenerate) return;
    setRegenBusy(true);
    setRegenError(null);
    try {
      const res = await api.regeneratePostKit(generationId);
      const nextKit = res && typeof res === "object" && res.post_kit ? res.post_kit : res;
      setKit(nextKit);
      onUpdated?.(nextKit);
    } catch (err) {
      // The stored copy is untouched server-side, so the current copy stays.
      setRegenError(getErrorMessage(err));
    } finally {
      setRegenBusy(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="post-kit">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel>Caption, hashtags, cover</GroupLabel>
        <div className="flex flex-wrap items-center gap-2">
          {canRegenerate && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRegenerate}
              disabled={regenBusy}
              busy={regenBusy}
              etaSeconds={BUSY_ETA_SECONDS.postKit}
              data-testid="postkit-regenerate"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              {regenBusy ? "Regenerating copy" : "Regenerate"}
            </Button>
          )}
          <CopyButton
            testId="postkit-copy-all"
            copied={copiedKey === "all"}
            onCopy={() => copy("all", allText, "Post copy")}
            label="Copy all"
          />
        </div>
      </div>
      {regenError && (
        <p className="text-sm text-destructive-text" role="alert" data-testid="postkit-regenerate-error">
          {regenError}
        </p>
      )}

      {/* A silent render's voice lives here, with the rest of the post
          copy (ADR 0246): the kit is what the founder copies at
          posting time, so the text-to-speech line rides with it —
          the exact words TikTok should read aloud, named at the
          moment they are needed. Callers pass the text only for a
          silent render; a talking render's kit shows nothing. */}
      {String(ttsText || "").trim() && (
        <p role="status" className="text-sm text-muted-foreground" data-testid="post-kit-tts-note">
          This video is silent — the character does not speak in it. For a voice on TikTok,
          paste this into TikTok&rsquo;s text-to-speech so TikTok reads it aloud:{" "}
          <span className="font-semibold text-foreground">&ldquo;{String(ttsText).trim()}&rdquo;</span>
        </p>
      )}

      {/* One panel, three labelled rows divided by hairlines: the copy reads as
          a single spec sheet instead of three stacked boxes that each carried
          their own redundant Copy button. Each label stands above its value
          (ADR 0159), and the panel carries no explainer line — the copy
          stands on its own. The generated values themselves wear the one
          generated-text highlight (ADR 0258): plain words, light wash,
          no box of their own inside the panel. */}
      <dl
        className="inset-panel divide-y divide-[color:var(--hairline)]"
        data-testid="post-kit-fields"
      >
        {caption && (
          <div className="post-kit-row post-kit-row-stacked">
            <dt className="eyebrow">Caption</dt>
            <dd className="min-w-0 break-words text-base leading-relaxed text-foreground/90">
              <span className="generated-highlight">{String(caption)}</span>
            </dd>
          </div>
        )}

        {hashtags.length > 0 && (
          <div className="post-kit-row post-kit-row-stacked">
            <dt className="eyebrow">Hashtags</dt>
            <dd className="min-w-0">
              <FactList>
                {hashtags.map((tag, i) => (
                  <FactChip key={`${tag}-${i}`}>{String(tag)}</FactChip>
                ))}
              </FactList>
            </dd>
          </div>
        )}

        {coverText && (
          <div className="post-kit-row post-kit-row-stacked">
            <dt className="eyebrow">Cover text</dt>
            <dd className="min-w-0">
              <span className="generated-highlight text-base font-semibold">{coverText}</span>
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function CopyButton({ testId, copied, onCopy, label = "Copy" }) {
  return (
    <Button variant="ghost" size="sm" onClick={onCopy} data-testid={testId}>
      {copied ? (
        <Check className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <Copy className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      {copied ? "Copied" : label}
    </Button>
  );
}

export default PostKitSection;
