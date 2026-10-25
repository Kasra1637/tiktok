import { useCallback, useEffect, useState } from "react";
import { Check, Clapperboard, ExternalLink, Eye, Link2, Loader2, X } from "lucide-react";
import { ComponentThumbs } from "./ComponentThumbs";
import { GroupLabel } from "./SectionCard";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api, getErrorMessage } from "../lib/api";
import { verdictFor } from "../lib/feedback";

/**
 * Everything about one render's votes: the primary render vote plus the
 * optional per-part ratings behind their disclosure.
 *
 * One owner for all vote state in the drawer. `voteOverrides` holds a
 * just-cast vote ahead of the next fetch; `freshVerdicts` is the server
 * state revalidated every time the drawer opens. The list row's verdicts
 * stand in while the refetch is in flight (or if it fails), and an override
 * always wins over both, so a thumb never visibly un-presses itself.
 *
 * Mounting is the open signal: the drawer unmounts this component on
 * collapse, so mounting means the founder just opened the render and the
 * refetch below fires exactly once per open. A vote the server already
 * confirmed re-arrives through that refetch, which is what restores the
 * highlight after a collapse without depending on the list reloading.
 */
const PART_COMPONENTS = ["goal", "template", "plan", "script"];

export function HistoryFeedback({ row, signalRefs, onUpdated }) {
  const [voteOverrides, setVoteOverrides] = useState({});
  const [freshVerdicts, setFreshVerdicts] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api.getGeneration(row.id)
      .then((d) => { if (!cancelled) setFreshVerdicts(d.verdicts || {}); })
      // A failed refresh is not a lost vote: savedVerdicts falls back to the
      // row's own verdicts, so the tile keeps showing what the founder saved.
      .catch(() => { if (!cancelled) setFreshVerdicts(null); });
    return () => { cancelled = true; };
  }, [row.id]);
  const savedVerdicts = freshVerdicts ?? row.verdicts ?? {};
  const thumbValue = (component) =>
    voteOverrides[component] ?? verdictFor(savedVerdicts, component);
  // Posted link: one nullable text column, saved beside the render. A link
  // marks the render posted and opens the live video — but a link alone
  // carries no weight. Only a thumbs up on the render PLUS a link counts
  // as a real winner for the hook-learning loop.
  const [link, setLink] = useState(row.tiktok_url || "");
  const [savedLink, setSavedLink] = useState(row.tiktok_url || null);
  const [savingLink, setSavingLink] = useState(false);
  const [linkError, setLinkError] = useState(null);
  const isWinner = thumbValue("video") === 1 && !!savedLink;
  // Views pasted back from the posted TikTok: read by hand until any TikTok
  // API. Shown only beside a posted link — views belong to the live video,
  // not the render. Displayed, never decided on: only a thumbs up plus a
  // link counts as a winner.
  const [views, setViews] = useState(row.tiktok_views ?? "");
  const [savedViews, setSavedViews] = useState(row.tiktok_views ?? null);
  const [savingViews, setSavingViews] = useState(false);
  const [viewsError, setViewsError] = useState(null);
  const saveViews = useCallback(async () => {
    const text = String(views).trim();
    if (!/^(\d+|\d{1,3}(,\d{3})+)$/.test(text)) {
      setViewsError("Views must be a whole number of 0 or more.");
      return;
    }
    const count = Number(text.replace(/,/g, ""));
    if (count > 10000000000) {
      setViewsError("That count is too large to be a TikTok view count.");
      return;
    }
    setSavingViews(true);
    setViewsError(null);
    try {
      const updated = await api.setTikTokViews(row.id, count);
      setSavedViews(updated.tiktok_views ?? null);
      setViews(updated.tiktok_views ?? "");
      onUpdated?.(row.id, { tiktok_views: updated.tiktok_views ?? null });
    } catch (err) {
      setViewsError(getErrorMessage(err));
    } finally {
      setSavingViews(false);
    }
  }, [row.id, views, onUpdated]);
  const saveLink = useCallback(async () => {
    setSavingLink(true);
    setLinkError(null);
    try {
      const updated = await api.setTikTokLink(row.id, link.trim());
      setSavedLink(updated.tiktok_url || null);
      setLink(updated.tiktok_url || "");
      onUpdated?.(row.id, { tiktok_url: updated.tiktok_url || null });
    } catch (err) {
      setLinkError(getErrorMessage(err));
    } finally {
      setSavingLink(false);
    }
  }, [row.id, link, onUpdated]);
  const clearLink = useCallback(async () => {
    setSavingLink(true);
    setLinkError(null);
    try {
      await api.setTikTokLink(row.id, "");
      setSavedLink(null);
      setLink("");
      onUpdated?.(row.id, { tiktok_url: null });
    } catch (err) {
      setLinkError(getErrorMessage(err));
    } finally {
      setSavingLink(false);
    }
  }, [row.id, onUpdated]);
  const rememberVote = (component, verdict) => {
    setVoteOverrides((prev) => ({ ...prev, [component]: verdict }));
    onUpdated?.(row.id, { verdicts: { ...savedVerdicts, ...voteOverrides, [component]: verdict } });
  };
  // Rated parts stay visible while the disclosure is collapsed: the summary
  // names how many of the four carry a vote, so a founder sees at a glance
  // whether this render's parts were ever judged. Reads from the same
  // override-then-saved rule as the thumbs, so a just-cast vote counts
  // before the next fetch and a saved one survives a refresh.
  const partsRatedCount = PART_COMPONENTS.filter((c) => thumbValue(c) !== 0).length;

  return (
    <div className="history-vote-block space-y-3 border-t border-[color:var(--hairline)] pt-5" data-testid={`history-feedback-${row.id}`}>
      <GroupLabel icon={Clapperboard}>Rate this render</GroupLabel>
      <ComponentThumbs
        component="video"
        question="Did this render land?"
        hint="One vote on the clip as a whole — the vote that counts most."
        size="default"
        resetKey={row.id}
        initialValue={thumbValue("video")}
        onVoted={rememberVote}
        refs={{
          ...signalRefs,
          detail: row.model ? `model=${row.model}` : "",
        }}
        testId={`history-video-feedback-${row.id}`}
      />
      {/* Posted link lives next to the thumbs, inside the same vote block:
          the winner signal (thumbs up) and the posted proof (link) are read
          together, so they are set together. */}
      <div className="space-y-2" data-testid={`history-tiktok-link-${row.id}`}>
        <div className="flex flex-wrap items-center gap-2">
          {savedLink ? (
            <>
              <Badge variant="secondary" data-testid={`history-posted-${row.id}`}>
                <Check className="h-3 w-3" /> Posted
              </Badge>
              <a
                href={savedLink}
                target="_blank"
                rel="noreferrer"
                data-testid={`history-live-link-${row.id}`}
                className="inline-flex items-center gap-1 text-xs font-semibold text-[color:var(--brand-indigo)] hover:underline"
              >
                Open live video <ExternalLink className="h-3 w-3" />
              </a>
              {isWinner && (
                <Badge variant="indigo" data-testid={`history-winner-${row.id}`} title="Thumbs up plus posted link — a real winner">
                  Winner
                </Badge>
              )}
              <Button
                variant="ghost"
                size="sm"
                disabled={savingLink}
                onClick={clearLink}
                data-testid={`history-tiktok-clear-${row.id}`}
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
                  data-testid={`history-tiktok-input-${row.id}`}
                  disabled={savingLink}
                  className="h-9"
                />
              </div>
              <Button
                variant="secondary"
                size="sm"
                disabled={savingLink || !link.trim()}
                onClick={saveLink}
                data-testid={`history-tiktok-save-${row.id}`}
              >
                {savingLink ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save link"}
              </Button>
            </>
          )}
        </div>
        {linkError && <p role="alert" className="text-xs text-destructive">{linkError}</p>}
        {!savedLink && (
          <p className="text-xs text-muted-foreground">
            Marks this render posted. Only a thumbs up plus a link counts as a winner.
          </p>
        )}
        {savedLink && (
          <div className="space-y-1.5 pt-1" data-testid={`history-tiktok-views-${row.id}`}>
            <div className="flex flex-wrap items-center gap-2">
              <Eye className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              {savedViews != null && (
                <span className="text-xs font-semibold" data-testid={`history-tiktok-views-count-${row.id}`}>
                  {Number(savedViews).toLocaleString("en-US")} views
                </span>
              )}
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <label className="sr-only" htmlFor={`history-views-input-${row.id}`}>Views on the posted TikTok</label>
                <Input
                  id={`history-views-input-${row.id}`}
                  type="text"
                  inputMode="numeric"
                  value={views}
                  onChange={(e) => setViews(e.target.value)}
                  placeholder="Paste the view count…"
                  aria-label="Views on the posted TikTok"
                  data-testid={`history-tiktok-views-input-${row.id}`}
                  disabled={savingViews}
                  className="h-9"
                />
              </div>
              <Button
                variant="secondary"
                size="sm"
                disabled={savingViews || String(views).trim() === ""}
                onClick={saveViews}
                data-testid={`history-tiktok-views-save-${row.id}`}
              >
                {savingViews ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Save views"}
              </Button>
            </div>
            {viewsError && <p role="alert" className="text-xs text-destructive">{viewsError}</p>}
            {savedViews == null && (
              <p className="text-xs text-muted-foreground">
                Read the count off TikTok and paste it back — most-viewed renders sort first.
              </p>
            )}
          </div>
        )}
      </div>
      <details data-testid={`history-parts-feedback-${row.id}`} className="rounded-xl border border-[color:var(--hairline)] px-3 py-1.5">
        <summary className="cursor-pointer list-none py-1 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
          Rate the parts (optional) — goal, template, plan, script
          {partsRatedCount > 0 ? (
            <span className="text-foreground/80"> · {partsRatedCount} of 4 rated</span>
          ) : null}
        </summary>
        <p className="pb-2 text-xs text-muted-foreground">
          Only if one part specifically helped or hurt. Each part&apos;s votes steer only the step that makes it, never the render vote above.
        </p>
        <div className="ml-2 space-y-2 border-l-2 border-[color:var(--hairline)]">
      <ComponentThumbs
        component="goal"
        question="Content goal"
        hint="Shapes future goal suggestions for this app."
        resetKey={`${row.id}:goal`}
        initialValue={thumbValue("goal")}
        onVoted={rememberVote}
        refs={{
          ...signalRefs,
          detail: `objective=${row.objective || ""};kind=${row.angle_kind || ""}`,
        }}
        testId={`history-goal-feedback-${row.id}`}
      />
      <ComponentThumbs
        component="template"
        question="Hook template"
        hint="Reorders and reshapes future template suggestions."
        resetKey={`${row.id}:template`}
        initialValue={thumbValue("template")}
        onVoted={rememberVote}
        refs={signalRefs}
        testId={`history-template-feedback-${row.id}`}
      />
      <ComponentThumbs
        component="plan"
        question="Script plan"
        hint="Steers future script plans for this app."
        resetKey={`${row.id}:plan`}
        initialValue={thumbValue("plan")}
        onVoted={rememberVote}
        refs={{
          ...signalRefs,
          detail: `plan v${Number(row.script_version) || 0}`,
        }}
        testId={`history-plan-feedback-${row.id}`}
      />
      <ComponentThumbs
        component="script"
        question="Spoken script"
        hint="Guides future spoken scripts for this app."
        resetKey={`${row.id}:script`}
        initialValue={thumbValue("script")}
        onVoted={rememberVote}
        refs={{
          ...signalRefs,
          detail: `strategy v${Number(row.strategy_version) || 0}`,
        }}
        testId={`history-script-feedback-${row.id}`}
      />
        </div>
      </details>
    </div>
  );
}
