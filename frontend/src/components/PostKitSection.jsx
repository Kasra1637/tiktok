import { useEffect, useState } from "react";
import { Check, Copy, MessageSquareText, RotateCcw } from "lucide-react";
import { Button } from "./ui/button";
import { GroupLabel } from "./SectionCard";
import { FactChip, FactList } from "./FactChip";
import { useCopyButton } from "../lib/copyClipboard";
import { api, getErrorMessage } from "../lib/api";

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
 */
export function PostKitSection({ postKit: initialKit, generationId, onUpdated }) {
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
        <GroupLabel icon={MessageSquareText}>Post copy for this render</GroupLabel>
        <div className="flex flex-wrap items-center gap-2">
          {canRegenerate && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRegenerate}
              disabled={regenBusy}
              data-testid="postkit-regenerate"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              {regenBusy ? "Regenerating…" : "Regenerate"}
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
      <p className="text-sm text-muted-foreground">
        Written for this clip when it finished, from its approved hook. Copy
        all pastes the caption and its hashtags in one go.
      </p>
      {regenError && (
        <p className="text-sm text-destructive" role="alert" data-testid="postkit-regenerate-error">
          {regenError}
        </p>
      )}

      {/* One panel, three labelled rows divided by hairlines: the copy reads as
          a single spec sheet instead of three stacked boxes that each carried
          their own redundant Copy button. */}
      <dl
        className="inset-panel divide-y divide-[color:var(--hairline)]"
        data-testid="post-kit-fields"
      >
        {caption && (
          <div className="post-kit-row">
            <dt className="eyebrow sm:pt-1">Caption</dt>
            <dd className="min-w-0 break-words text-base leading-relaxed text-foreground/90">
              {String(caption)}
            </dd>
          </div>
        )}

        {hashtags.length > 0 && (
          <div className="post-kit-row">
            <dt className="eyebrow sm:pt-0.5">Hashtags</dt>
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
          <div className="post-kit-row">
            <dt className="eyebrow sm:pt-1.5">Cover text</dt>
            <dd className="min-w-0">
              <span className="post-kit-cover">&ldquo;{coverText}&rdquo;</span>
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
