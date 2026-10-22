import { Check, Copy, MessageSquareText } from "lucide-react";
import { Button } from "./ui/button";
import { GroupLabel } from "./SectionCard";
import { FactChip, FactList } from "./FactChip";
import { useCopyButton } from "../lib/copyClipboard";

/**
 * The frozen post copy for one render: 3 captions, a hashtag set, cover text.
 *
 * Read-only: `postKit` is the stored object, and a null or empty kit renders
 * nothing — no placeholder, no derived copy. Shared by History's drawer,
 * the Details modal, the studio output moment, and the export card.
 */
export function PostKitSection({ postKit }) {
  const { copiedKey, copy } = useCopyButton();

  const captions = postKit && Array.isArray(postKit.captions)
    ? postKit.captions.filter((c) => String(c || "").trim())
    : [];
  const hashtags = postKit && Array.isArray(postKit.hashtags)
    ? postKit.hashtags.filter((t) => String(t || "").trim())
    : [];
  const coverText = postKit && typeof postKit.cover_text === "string"
    ? postKit.cover_text.trim()
    : "";

  // A null or empty kit renders nothing: there is nothing honest to show.
  if (captions.length === 0 && hashtags.length === 0 && !coverText) return null;

  const allText = [...captions, hashtags.join(" ")].filter(Boolean).join("\n\n");

  return (
    <div className="space-y-3" data-testid="post-kit">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel icon={MessageSquareText}>Post copy for this render</GroupLabel>
        <CopyButton
          testId="postkit-copy-all"
          copied={copiedKey === "all"}
          onCopy={() => copy("all", allText, "Post copy")}
          label="Copy all"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Written for this clip when it finished, from its approved hook. Paste a
        caption with the hashtags when you publish.
      </p>

      {captions.length > 0 && (
        <ol className="space-y-2">
          {captions.map((caption, i) => (
            <li key={`caption-${i}`} className="inset-panel space-y-1">
              <div className="flex items-center justify-between gap-2">
                <span className="eyebrow">Caption {i + 1}</span>
                <CopyButton
                  testId={`postkit-copy-caption-${i}`}
                  copied={copiedKey === `caption-${i}`}
                  onCopy={() => copy(`caption-${i}`, String(caption), `Caption ${i + 1}`)}
                />
              </div>
              <p className="break-words text-sm leading-relaxed text-foreground/90">
                {String(caption)}
              </p>
            </li>
          ))}
        </ol>
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
          <p className="break-words text-sm font-semibold leading-relaxed text-foreground/90">
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
