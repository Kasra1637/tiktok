import { useEffect, useState } from "react";
import { Check, Copy, ListChecks, RotateCcw } from "lucide-react";
import { Button } from "../ui/button";
import { GroupLabel } from "../SectionCard";
import { useCopyButton } from "../../lib/copyClipboard";
import { api, getErrorMessage } from "../../lib/api";
import { BUSY_ETA_SECONDS } from "../../lib/busyEta";

/**
 * The story kit for one finished frame (ADR 0236; the kit itself is
 * ADR 0228): the posting layer the render cannot carry — the
 * caption, the accepted screen text verbatim (the founder's native
 * text sticker, placed at posting, never burned in), the sticker
 * plan with each sticker's platform, exact wording and placement,
 * and the posting checklist.
 *
 * The post kit's sibling in shape and discipline, and never the
 * same panel: a story render carries this kit and no post kit, a
 * hook video the reverse, and the two endpoints are as separate as
 * the two kits. Regeneration is explicit — it only runs on this
 * panel's own click, and a failure keeps the current kit on screen
 * with the error beside it. A null kit renders nothing: the panel
 * appears when the kit exists, exactly as the post kit's does.
 */
export default function StoryKitPanel({ storyKit: initialKit, generationId, onUpdated }) {
  const { copiedKey, copy } = useCopyButton();
  const [kit, setKit] = useState(initialKit);
  const [regenBusy, setRegenBusy] = useState(false);
  const [regenError, setRegenError] = useState(null);
  useEffect(() => { setKit(initialKit); }, [initialKit]);

  const caption = typeof kit?.caption === "string" ? kit.caption.trim() : "";
  const screenText = typeof kit?.screen_text === "string" ? kit.screen_text.trim() : "";
  const stickerPlan = Array.isArray(kit?.sticker_plan)
    ? kit.sticker_plan.filter((entry) => entry && (entry.sticker || entry.wording))
    : [];
  const checklist = Array.isArray(kit?.checklist)
    ? kit.checklist.map((line) => String(line || "").trim()).filter(Boolean)
    : [];

  if (!caption && !screenText && stickerPlan.length === 0 && checklist.length === 0) {
    return null;
  }

  const stickerText = stickerPlan
    .map((entry) => [entry.sticker, entry.wording, entry.placement].filter(Boolean).join(" — "))
    .join("\n");
  const allText = [caption, screenText, stickerText, checklist.join("\n")]
    .filter(Boolean)
    .join("\n\n");
  const canRegenerate = !!generationId;

  const handleRegenerate = async () => {
    if (regenBusy || !canRegenerate) return;
    setRegenBusy(true);
    setRegenError(null);
    try {
      const res = await api.regenerateStoryKit(generationId);
      const nextKit = res && typeof res === "object" && res.story_kit ? res.story_kit : res;
      setKit(nextKit);
      onUpdated?.(nextKit);
    } catch (err) {
      // The stored kit is untouched server-side, so the current kit stays.
      setRegenError(getErrorMessage(err));
    } finally {
      setRegenBusy(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="story-kit-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel icon={ListChecks}>Story kit</GroupLabel>
        <div className="flex flex-wrap items-center gap-2">
          {canRegenerate && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRegenerate}
              disabled={regenBusy}
              busy={regenBusy}
              etaSeconds={BUSY_ETA_SECONDS.postKit}
              data-testid="story-kit-regenerate"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              {regenBusy ? "Regenerating kit" : "Regenerate"}
            </Button>
          )}
          <KitCopyButton
            testId="story-kit-copy-all"
            copied={copiedKey === "all"}
            onCopy={() => copy("all", allText, "Story kit")}
            label="Copy all"
          />
        </div>
      </div>
      {regenError && (
        <p className="text-sm text-destructive-text" role="alert" data-testid="story-kit-regenerate-error">
          {regenError}
        </p>
      )}

      {/* One panel, labelled rows divided by hairlines — the post
          kit's spec-sheet shape (ADR 0159: labels above values). */}
      <dl className="inset-panel divide-y divide-[color:var(--hairline)]" data-testid="story-kit-fields">
        {caption && (
          <div className="post-kit-row post-kit-row-stacked">
            <dt className="eyebrow">Caption</dt>
            <dd className="min-w-0">
              <div className="flex items-start justify-between gap-2">
                <span className="break-words text-base leading-relaxed text-foreground/90">
                  {caption}
                </span>
                <KitCopyButton
                  testId="story-kit-copy-caption"
                  copied={copiedKey === "caption"}
                  onCopy={() => copy("caption", caption, "Caption")}
                />
              </div>
            </dd>
          </div>
        )}

        {screenText && (
          <div className="post-kit-row post-kit-row-stacked">
            <dt className="eyebrow">Screen text — add as a native text sticker</dt>
            <dd className="min-w-0">
              <div className="flex items-start justify-between gap-2">
                <span className="post-kit-cover">{screenText}</span>
                <KitCopyButton
                  testId="story-kit-copy-screen-text"
                  copied={copiedKey === "screenText"}
                  onCopy={() => copy("screenText", screenText, "Screen text")}
                />
              </div>
            </dd>
          </div>
        )}

        {stickerPlan.length > 0 && (
          <div className="post-kit-row post-kit-row-stacked">
            <dt className="eyebrow">Sticker plan</dt>
            <dd className="min-w-0">
              <ul className="space-y-2">
                {stickerPlan.map((entry, i) => (
                  <li key={i} className="text-base leading-relaxed text-foreground/90">
                    <span className="font-semibold">{String(entry.sticker || "Sticker")}</span>
                    {entry.platform && (
                      <span className="text-muted-foreground"> · {String(entry.platform)}</span>
                    )}
                    {entry.wording && <span> — {String(entry.wording)}</span>}
                    {entry.placement && (
                      <span className="block text-sm text-muted-foreground">{String(entry.placement)}</span>
                    )}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}

        {checklist.length > 0 && (
          <div className="post-kit-row post-kit-row-stacked">
            <dt className="eyebrow">Posting checklist</dt>
            <dd className="min-w-0">
              <ul className="space-y-2" data-testid="story-kit-checklist">
                {checklist.map((line, i) => (
                  <li key={i} className="flex items-start gap-2 text-base leading-relaxed text-foreground/90">
                    <Check className="mt-1 h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" aria-hidden="true" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function KitCopyButton({ testId, copied, onCopy, label = "Copy" }) {
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
