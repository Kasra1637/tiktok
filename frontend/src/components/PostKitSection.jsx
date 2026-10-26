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
      <p className="text-xs text-muted-foreground">
        Written for this clip when it finished, from its approved hook. Paste
        the caption with the hashtags when you publish.
      </p>
      {regenError && (
        <p className="text-xs text-destructive" role="alert" data-testid="postkit-regenerate-error">
          {regenError}
        </p>
      )}

      {caption && (
        <div className="inset-panel space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="eyebrow">Caption</span>
            <CopyButton
              testId="postkit-copy-caption-0"
              copied={copiedKey === "caption-0"}
              onCopy={() => copy("caption-0", String(caption), "Caption")}
            />
          </div>
          <p className="break-words text-base leading-relaxed text-foreground/90">
            {String(caption)}
          </p>
        </div>
      )}

      {hashtags.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="eyebrow">Hashtags</span>
            <CopyButton
              testId="postkit-copy-hashtags"
              copied={copiedKey === "hashtags"}
              onCopy={() => copy("hashtags", hashtags.join(" "), "Hashtags")}
            />
          </div>
          <FactList>
            {hashtags.map((tag, i) => (
              <FactChip key={`${tag}-${i}`}>{String(tag)}</FactChip>
            ))}
          </FactList>
        </div>
      )}

      {coverText && (
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-2">
            <span className="eyebrow">Cover text</span>
            <CopyButton
              testId="postkit-copy-cover"
              copied={copiedKey === "cover"}
              onCopy={() => copy("cover", coverText, "Cover text")}
            />
          </div>
          <p className="break-words text-base font-semibold leading-relaxed text-foreground/90">
            &ldquo;{coverText}&rdquo;
          </p>
        </div>
      )}
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
