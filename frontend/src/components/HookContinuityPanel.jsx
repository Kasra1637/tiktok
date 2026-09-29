import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { api, getErrorMessage, mediaUrl } from "../lib/api";
import {
  Loader2, Clapperboard, AlertTriangle, Download, RefreshCw, Check,
  Info, Clock, User, MapPin, Film, Scissors, ShieldQuestion,
  Sparkles, Play, Link2,
} from "lucide-react";

/**
 * The app-specific influencer workflow, end to end.
 *
 *   strategy -> 3-4s hook -> approve -> extend -> extend -> assemble
 *
 * The order is the product. The hook is generated on its own so the concept
 * can be judged in four seconds, approving it is what unlocks extensions, and
 * only approved segments are joined into the final file. An extension always
 * continues the approved take rather than re-imagining it, and the panel says
 * plainly what the provider was actually given so a continuity gap is never
 * something the founder has to infer from a prompt.
 */

const POLL_INTERVAL_MS = 6000;

// Mirrors video_providers.HOOK_LENGTH_CHOICES / DEFAULT_HOOK_SECONDS. The
// backend validates against its own list, so a drift here would be refused
// loudly rather than silently mis-rendered.
const HOOK_LENGTHS = [2, 3, 4, 5, 6];
const DEFAULT_HOOK = 4;

// How much an extension adds. 3s sits below every provider's render floor and
// is therefore always delivered as a trim, which the option label says.
const EXTEND_CHOICES = [3, 5, 8, 10];
const DEFAULT_EXTEND = 5;

const GUARANTEE_COPY = {
  frame_exact_plus_refs: {
    label: "Frame-exact",
    tone: "indigo",
    note: "Opens on the previous clip's final frame, with the clip and your character reference attached.",
  },
  frame_exact: {
    label: "Frame-exact",
    tone: "indigo",
    note: "Opens on the previous clip's final frame. This provider can only carry one anchor, so the clip and the separate face reference were not sent.",
  },
  text_only: {
    label: "Text-only continuity",
    tone: "outline",
    note: "This provider could not receive a visual anchor from the previous clip. The person and scene are carried by the written description instead, so the result may not match the approved hook exactly.",
  },
  single_segment: {
    label: "First segment",
    tone: "secondary",
    note: "Nothing to continue from yet — this is the opening.",
  },
  unsupported: {
    label: "Not supported",
    tone: "destructive",
    note: "This provider cannot generate a continuation.",
  },
};

function money(value) {
  if (value === null || value === undefined) return null;
  return `$${Number(value).toFixed(2)}`;
}

function StatusBadge({ status }) {
  const map = {
    submitted: ["Queued", "secondary"],
    generating: ["Generating", "indigo"],
    completed: ["Completed", "indigo"],
    failed: ["Failed", "destructive"],
    archived: ["Archived", "secondary"],
  };
  const [label, variant] = map[status] || [status, "secondary"];
  return <Badge variant={variant} className="text-xs">{label}</Badge>;
}

function StrategyBlock({ title, icon: Icon, rows }) {
  const filled = rows.filter(([, value]) => String(value || "").trim());
  if (!filled.length) return null;
  return (
    <div className="space-y-1">
      <span className="eyebrow flex items-center gap-1.5">
        <Icon className="h-3 w-3" /> {title}
      </span>
      <dl className="space-y-0.5 text-sm">
        {filled.map(([label, value]) => (
          <div key={label} className="flex gap-2">
            <dt className="shrink-0 text-muted-foreground">{label}</dt>
            <dd className="min-w-0">{String(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function ContinuityNote({ continuity }) {
  if (!continuity || !Object.keys(continuity).length) return null;
  const copy = GUARANTEE_COPY[continuity.guarantee] || null;
  const degraded = continuity.degraded || [];
  const attached = continuity.attached || [];
  if (!copy && !degraded.length) return null;

  return (
    <Alert variant={continuity.guarantee === "text_only" ? "destructive" : "default"}>
      {continuity.guarantee === "text_only" ? (
        <AlertTriangle className="h-4 w-4" />
      ) : (
        <Link2 className="h-4 w-4 text-[color:var(--brand-indigo)]" />
      )}
      <AlertTitle>
        {copy?.label ? `Continuity: ${copy.label}` : "Continuity"}
        {attached.length > 0 && ` — sent: ${attached.join(", ")}`}
      </AlertTitle>
      <AlertDescription className="space-y-1.5">
        {copy && <p>{copy.note}</p>}
        {degraded.length > 0 && (
          <ul className="list-disc space-y-1 pl-4">
            {degraded.map((d, i) => (
              <li key={i}>
                <span className="font-medium">Not sent — {d.anchor}:</span> {d.reason}
              </li>
            ))}
          </ul>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function HookContinuityPanel({ project, onProjectChange, onGenerationChange }) {
  const [models, setModels] = useState(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [hookSeconds, setHookSeconds] = useState(0);
  const [extendBy, setExtendBy] = useState(DEFAULT_EXTEND);
  const [segments, setSegments] = useState([]);
  const [assembled, setAssembled] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const timer = useRef(null);

  const projectId = project?.id;
  const strategy = project?.strategy;
  const hasStrategy = Boolean(strategy?.hook_line);
  const assets = project?.assets || [];
  const hasCharacter = assets.some((a) => a.kind === "character_reference");
  const blocked = project?.safety_report && project.safety_report.passed === false;

  useEffect(() => {
    let cancelled = false;
    api
      .getStudioVideoModels()
      .then((data) => {
        if (cancelled) return;
        setModels(data);
        setSelectedModel(data.default || "");
      })
      .catch(() => !cancelled && setModels(null));
    return () => { cancelled = true; };
  }, []);

  // The chain: every generation on this project, in segment order. The tip is
  // the newest segment, which is the one an extension would continue.
  const loadSegments = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await api.getGenerations({ studio_project_id: projectId, limit: 50 });
      const rows = [...(data.generations || [])].sort(
        (a, b) => (a.segment_index ?? 0) - (b.segment_index ?? 0)
      );
      setSegments(rows);
    } catch {
      setSegments([]);
    }
  }, [projectId]);

  useEffect(() => {
    loadSegments();
  }, [loadSegments]);

  const inFlightId = segments.find(
    (s) => s.status === "submitted" || s.status === "generating"
  )?.id;

  const schedulePoll = useCallback((id) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const updated = await api.pollGeneration(id);
        onGenerationChange?.(updated);
        if (updated.status === "submitted" || updated.status === "generating") {
          schedulePoll(id);
        } else {
          await loadSegments();
        }
      } catch (err) {
        setError(getErrorMessage(err));
      }
    }, POLL_INTERVAL_MS);
  }, [loadSegments, onGenerationChange]);

  useEffect(() => {
    if (inFlightId) schedulePoll(inFlightId);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [inFlightId, schedulePoll]);

  const run = async (key, fn) => {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      return await fn();
    } catch (err) {
      setError(getErrorMessage(err));
      return null;
    } finally {
      setBusy("");
    }
  };

  // -------------------------------------------------------------------------
  // Hook length
  //
  // The wanted length and the length the model can actually render are two
  // different numbers, and every provider's floor is 4s or more while the hook
  // a template declares is 2-3s. So a short hook is rendered at the floor and
  // cut down afterwards. This mirrors the backend's resolve_hook_length() so
  // the option labels are honest BEFORE the render is paid for — the backend
  // still decides, and its plan is what the response reports back.
  // -------------------------------------------------------------------------
  const capability = models?.models?.find((m) => m.key === selectedModel);
  const floor = capability?.min_duration ?? 4;
  const ceiling = capability?.max_duration ?? 30;

  const resolveLength = (target) => {
    const render = Math.min(Math.max(target, floor), ceiling);
    const trimTo = render > target ? target : 0;
    return { target, render, trimTo };
  };

  const savedHook = Number(project?.hook_seconds || 0);
  const effectiveHook = Number(hookSeconds || 0) || savedHook || DEFAULT_HOOK;
  const lengthPlan = resolveLength(effectiveHook);
  // Unset on an older row means the default, which is "yes, extend": the hook
  // is the opening of a video.
  const extendIntent = project?.extend_intent === 0 ? false : true;

  const handleHookLength = (value) => {
    setHookSeconds(value);
    if (!projectId) return;
    // Persisted so a later strategy rebuild, the hook render, and any segment
    // planning all read the SAME length rather than each re-deriving it.
    api
      .setProjectHookLength(projectId, value)
      .then((updated) => onProjectChange?.(updated))
      .catch((err) => setError(getErrorMessage(err)));
  };

  // Declared intent to extend the hook into a full video.
  //
  // Deliberately NOT load-bearing: it changes what the panel offers and shows,
  // never what gets rendered, so flipping it after a strategy exists cannot
  // invalidate that strategy and force a paid rebuild. The hook is still the
  // opening of a video either way, and extending is always available.
  const handleExtendIntent = (value) => {
    if (!projectId) return;
    api
      .setProjectExtendIntent(projectId, value)
      .then((updated) => onProjectChange?.(updated))
      .catch((err) => setError(getErrorMessage(err)));
  };

  // Running total uses the DELIVERED length of each completed segment, so a
  // hook that was rendered at the floor and trimmed to 3s counts 3s, not the
  // 4s that was asked of the model. Adding up the render lengths would
  // overstate the video the founder will actually have.
  const completedSegments = segments.filter(
    (s) => s.status === "completed" && Number(s.duration) > 0
  );
  const runningTotal = completedSegments.reduce(
    (sum, s) => sum + (s.trim_to_seconds > 0 ? s.trim_to_seconds : Number(s.duration || 0)),
    0
  );
  const targetTotal = Number(project?.duration_seconds || 0);
  const reachesTarget = targetTotal > 0 && runningTotal >= targetTotal;
  const remainingToTarget = Math.max(0, targetTotal - runningTotal);
  // How many more segments the strategy can still produce. Surfaced because the
  // plan is finite: a founder extending by 3s could exhaust it before reaching
  // a 30s target, and finding that out at segment 8 would be a dead end.
  const plannedMaxIndex = Number(strategy?.max_planned_index || 0);
  const plannedCoverage = Math.max(0, plannedMaxIndex - segments.length + 1);

  const handleGenerateStrategy = () =>
    run("strategy", async () => {
      const updated = await api.generateStrategy(projectId, { hook_seconds: effectiveHook });
      onProjectChange?.(updated);
      setNotice(
        `Strategy v${updated.strategy_version} built from this app's profile. Review the hook and the locked person, then generate the hook.`
      );
    });

  const handleGenerateHook = () =>
    run("hook", async () => {
      const created = await api.generateHook(projectId, {
        model: selectedModel || undefined,
        duration_seconds: effectiveHook,
      });
      onGenerationChange?.(created);
      const plan = created.hook_length;
      setNotice(
        plan?.trimTo
          ? `Hook submitted as segment 0. It renders at ${plan.render_seconds}s and is cut down to ${plan.trimTo}s — approve it once it looks right, and that is what lets it continue.`
          : `Hook submitted as segment 0 (${created.duration}s). Approve it once it looks right — that is what lets it continue.`
      );
      await loadSegments();
      schedulePoll(created.id);
    });

  const handleApprove = (id) =>
    run(`approve-${id}`, async () => {
      const updated = await api.approveGeneration(id, {});
      onGenerationChange?.(updated);
      setNotice("Approved. This segment can now continue into an extension.");
      await loadSegments();
    });

  const handleExtend = (id, requestedSeconds) =>
    run(`extend-${id}`, async () => {
      const created = await api.extendGeneration(id, {
        duration_seconds: requestedSeconds,
      });
      onGenerationChange?.(created);
      const plan = created.continuity || {};
      const length = created.length_plan;
      let message;
      if (plan.guarantee === "text_only") {
        message =
          "Extension submitted WITHOUT a visual anchor — this provider cannot pin the previous frame. Check the person and scene match before approving.";
      } else if (length?.trimTo) {
        message = `Extension submitted as segment ${created.segment_index}, ${length.trimTo}s. It renders at ${length.renderSeconds}s and is cut down, because this provider cannot render under that.`;
      } else {
        message = `Extension submitted as segment ${created.segment_index}, continuing from the approved clip.`;
      }
      setNotice(message);
      await loadSegments();
      schedulePoll(created.id);
    });

  const handleAssemble = (id) =>
    run("assemble", async () => {
      const result = await api.assembleChain(id, {});
      setAssembled(result);
      const skipped = result.skipped?.length
        ? ` ${result.skipped.length} segment(s) were skipped.`
        : "";
      setNotice(`Joined ${result.segment_count} approved segment(s) into one file.${skipped}`);
    });

  const approvedSegments = segments.filter((s) => s.approved);
  const tip = segments[segments.length - 1];
  const canAssemble = approvedSegments.length > 0 && !inFlightId;

  return (
    <div className="space-y-3 rounded-2xl border border-[color:var(--hairline)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-display text-sm font-semibold">
          <Sparkles className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          App-specific influencer video
        </span>
        {strategy && (
          <Badge variant="outline" className="text-[11px]">strategy v{project.strategy_version}</Badge>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        The hook is the opening of a video, not a finished clip: build the app-specific
        strategy, approve the hook, then extend it while the same person and scene carry
        through. The joined file is the deliverable.
      </p>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {!hasCharacter && (
        <Alert>
          <ShieldQuestion className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>No character reference attached</AlertTitle>
          <AlertDescription>
            Attach a <code>character_reference</code> image in the Assets step, or the
            influencer will be invented by the model rather than being you.
          </AlertDescription>
        </Alert>
      )}
      {blocked && (
        <Alert variant="destructive">
          <AlertTitle>Prohibited claim present</AlertTitle>
          <AlertDescription>
            Fix the flagged claim in the plan above. The hook is blocked until the claim
            check passes.
          </AlertDescription>
        </Alert>
      )}

      {models && (
        <div className="space-y-1.5">
          <label htmlFor="hook-model" className="text-sm font-medium">Model</label>
          <select
            id="hook-model"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={Boolean(busy)}
            className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            {models.models.map((m) => (
              <option key={m.key} value={m.key}>
                {m.name} — {m.supports_last_frame ? "frame-exact continuation" : "no frame continuation"}{m.key === models.default ? " (default)" : ""}
              </option>
            ))}
          </select>
          {(() => {
            const cap = models.models.find((m) => m.key === selectedModel);
            return cap ? <p className="text-xs text-muted-foreground">{cap.notes}</p> : null;
          })()}
        </div>
      )}

      {/* Hook length. Separate from the project's "total video length" because
          it is a different axis: this is the first segment of it. */}
      <div className="space-y-1.5">
        <label htmlFor="hook-length" className="text-sm font-medium">Hook length</label>
        <select
          id="hook-length"
          value={effectiveHook}
          onChange={(e) => handleHookLength(Number(e.target.value))}
          disabled={Boolean(busy) || Boolean(inFlightId)}
          className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
        >
          {HOOK_LENGTHS.map((n) => {
            const p = resolveLength(n);
            return (
              <option key={n} value={n}>
                {n}s{p.trimTo ? ` — trimmed from a ${p.render}s render` : " — as rendered"}
              </option>
            );
          })}
        </select>
        {lengthPlan.trimTo ? (
          <p className="text-xs text-muted-foreground">
            {capability?.name || "This provider"} cannot render under {floor}s, so the hook
            is generated at {lengthPlan.render}s and cut down to {lengthPlan.trimTo}s. The
            total video length is unchanged — this is only the opening segment.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            The opening {lengthPlan.render}s of the video. The total length is set on the
            Audience &amp; goal step.
          </p>
        )}
      </div>

      {/* Declared intent. The hook is always the opening of a video rather than a
          deliverable in its own right; this records whether a full video is
          planned now, and changes only what the panel offers below. */}
      <div className="space-y-1.5">
        <span className="text-sm font-medium">What happens after the hook</span>
        <div className="grid gap-1.5 sm:grid-cols-2">
          {[
            { value: true, label: "Extend into a full video", hint: "Shows a running total against your target length." },
            { value: false, label: "Just the hook for now", hint: "No target shown. You can extend later at any point." },
          ].map((option) => (
            <button
              key={String(option.value)}
              type="button"
              onClick={() => handleExtendIntent(option.value)}
              disabled={Boolean(busy)}
              aria-pressed={extendIntent === option.value}
              className={`rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                extendIntent === option.value
                  ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                  : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
              }`}
            >
              <span className="block font-medium">{option.label}</span>
              <span className="mt-0.5 block text-muted-foreground">{option.hint}</span>
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          This changes nothing about what gets generated, so switching it later never
          discards the strategy or the clips you have already made.
        </p>
      </div>

      {/* 1. Strategy */}
      <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
        <Button
          variant="brand"
          onClick={handleGenerateStrategy}
          disabled={Boolean(busy) || Boolean(inFlightId) || !projectId}
        >
          {busy === "strategy" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {hasStrategy ? "Rebuild strategy" : "Build the app-specific strategy"}
        </Button>

        {hasStrategy && (
          <div className="space-y-3 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-3">
            <div className="space-y-1">
              <span className="eyebrow">Hook concept</span>
              <p className="text-sm">{strategy.hook_concept}</p>
            </div>
            <div className="space-y-1">
              <span className="eyebrow">The line they hear first</span>
              <p className="font-display text-base font-semibold">&ldquo;{strategy.hook_line}&rdquo;</p>
            </div>
            <div className="space-y-1">
              <span className="eyebrow">Why this works for this app</span>
              <p className="text-sm">{strategy.strategy_summary}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <StrategyBlock
                title="The person (locked for every segment)"
                icon={User}
                rows={Object.entries(strategy.character || {})}
              />
              <StrategyBlock
                title="The scene (locked for every segment)"
                icon={MapPin}
                rows={Object.entries(strategy.scene || {})}
              />
              <StrategyBlock
                title="Performance"
                icon={Film}
                rows={Object.entries(strategy.performance || {})}
              />
            </div>
            <div className="space-y-1">
              <span className="eyebrow">Segments planned</span>
              <ol className="space-y-1 text-sm">
                {(strategy.segments || []).map((s) => (
                  <li key={s.index}>
                    <span className="font-medium">{s.role}</span> ({s.seconds}s) — {s.goal}
                  </li>
                ))}
              </ol>
            </div>
            {strategy.continuity_contract?.must_not_change?.length > 0 && (
              <div className="space-y-1">
                <span className="eyebrow">Locked across the whole video</span>
                <ul className="list-disc space-y-0.5 pl-4 text-sm">
                  {strategy.continuity_contract.must_not_change.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2. Hook + 3. Extend */}
      {hasStrategy && (
        <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
          <Button
            variant="secondary"
            onClick={handleGenerateHook}
            disabled={Boolean(busy) || Boolean(inFlightId) || blocked}
          >
            {busy === "hook" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {segments.length ? "Regenerate the hook" : "Generate the 3–4s hook"}
          </Button>

          {segments.length === 0 && !inFlightId && (
            <p className="text-xs text-muted-foreground">
              The hook is its own short job, so you can judge the concept in four seconds
              before spending on a full video.
            </p>
          )}

          <div className="space-y-2">
            {segments.map((segment) => {
              const inFlight = segment.status === "submitted" || segment.status === "generating";
              const url = segment.r2_url || segment.video_url;
              return (
                <div
                  key={segment.id}
                  className="space-y-2 rounded-xl border border-[color:var(--hairline)] p-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="eyebrow">Segment {segment.segment_index}</span>
                    {segment.segment_index === 0 && <Badge variant="outline" className="text-[11px]">hook</Badge>}
                    <StatusBadge status={segment.status} />
                    {segment.approved && <Badge variant="indigo" className="text-[11px]">approved</Badge>}
                    {segment.duration && (
                      <Badge variant="outline" className="text-[11px]">
                        <Clock className="mr-1 h-2.5 w-2.5" />{segment.duration}s
                      </Badge>
                    )}
                    {segment.trim_to_seconds > 0 && (
                      <Badge variant="outline" className="text-[11px]">
                        trimmed to {segment.trim_to_seconds}s
                      </Badge>
                    )}
                    {money(segment.cost_usd) && (
                      <Badge variant="secondary" className="text-[11px]">{money(segment.cost_usd)}</Badge>
                    )}
                  </div>

                  {segment.status === "completed" && url && (
                    <video
                      src={mediaUrl(url)}
                      controls
                      playsInline
                      className="w-full max-w-[220px] rounded-lg border border-[color:var(--hairline)]"
                    />
                  )}

                  <ContinuityNote continuity={segment.continuity} />

                  {segment.status === "failed" && (
                    <p className="text-xs text-destructive">{segment.error}</p>
                  )}
                  {inFlight && (
                    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" /> Working — this page checks back on its own.
                    </p>
                  )}

                  {segment.status === "completed" && (
                    <div className="flex flex-wrap gap-2">
                      {!segment.approved && (
                        <Button
                          variant="brand"
                          size="sm"
                          onClick={() => handleApprove(segment.id)}
                          disabled={Boolean(busy)}
                        >
                          {busy === `approve-${segment.id}` ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Check className="h-3.5 w-3.5" />
                          )}
                          Approve this segment
                        </Button>
                      )}
                      {segment.approved && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <label
                            htmlFor={`extend-by-${segment.id}`}
                            className="sr-only"
                          >
                            How much to add for this extension
                          </label>
                          <select
                            id={`extend-by-${segment.id}`}
                            value={extendBy}
                            onChange={(e) => setExtendBy(Number(e.target.value))}
                            disabled={Boolean(busy) || Boolean(inFlightId)}
                            className="rounded-lg border border-[color:var(--hairline)] bg-transparent px-2 py-1.5 text-xs"
                          >
                            {EXTEND_CHOICES.map((n) => {
                              const p = resolveLength(n);
                              return (
                                <option key={n} value={n}>
                                  +{n}s{p.trimTo ? ` (trimmed from ${p.render}s)` : ""}
                                </option>
                              );
                            })}
                            {targetTotal > 0 && remainingToTarget > 0 && (
                              <option value="target">
                                {`Fill to target (+${remainingToTarget}s)`}
                              </option>
                            )}
                          </select>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() =>
                              handleExtend(
                                segment.id,
                                extendBy === "target" ? remainingToTarget : Number(extendBy)
                              )
                            }
                            disabled={Boolean(busy) || Boolean(inFlightId)}
                          >
                            {busy === `extend-${segment.id}` ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <RefreshCw className="h-3.5 w-3.5" />
                            )}
                            {extendIntent ? "Extend" : "Extend (optional)"}
                          </Button>
                        </div>
                      )}
                      {url && (
                        <Button variant="ghost" size="sm" asChild>
                          <a href={mediaUrl(url)} download>
                            <Download className="h-3.5 w-3.5" /> This segment
                          </a>
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Running total. Only shown when a full video is actually planned, so
          "just the hook for now" does not present a target that was never
          chosen. Counts delivered length, so a trimmed hook counts what it
          really is. */}
      {extendIntent && completedSegments.length > 0 && targetTotal > 0 && (
        <div className="space-y-1 border-t border-[color:var(--hairline)] pt-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium">
              {runningTotal}s of {targetTotal}s
            </span>
            {reachesTarget ? (
              <span className="text-[color:var(--brand-indigo)]">Target reached</span>
            ) : (
              <span className="text-muted-foreground">
                {remainingToTarget}s to go
              </span>
            )}
          </div>
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-[color:var(--indigo-8)]"
            role="progressbar"
            aria-valuenow={Math.min(runningTotal, targetTotal)}
            aria-valuemin={0}
            aria-valuemax={targetTotal}
            aria-label="Video length so far"
          >
            <div
              className="h-full rounded-full bg-[color:var(--brand-indigo)]"
              style={{ width: `${Math.min(100, (runningTotal / targetTotal) * 100)}%` }}
            />
          </div>
          {plannedCoverage > 0 && remainingToTarget > 0 && (
            <p className="text-xs text-muted-foreground">
              The strategy plans {plannedCoverage} more segment
              {plannedCoverage === 1 ? "" : "s"}. At +{extendBy === "target" ? remainingToTarget : extendBy}s
              {plannedCoverage * (extendBy === "target" ? remainingToTarget : extendBy) < remainingToTarget
                ? ` that reaches about ${plannedCoverage * (extendBy === "target" ? remainingToTarget : extendBy)}s, so you may need to rebuild the strategy for the full ${targetTotal}s.`
                : " that covers the rest of your target."}
            </p>
          )}
        </div>
      )}

      {/* 4. Assemble */}
      {approvedSegments.length > 0 && (
        <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
          <Button
            variant="brand"
            onClick={() => handleAssemble(tip.id)}
            disabled={!canAssemble || Boolean(busy)}
          >
            {busy === "assemble" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Scissors className="h-4 w-4" />
            )}
            Join the approved segments
          </Button>
          <p className="text-xs text-muted-foreground">
            {approvedSegments.length} approved segment(s). Unapproved or still-generating
            segments are left out and reported, never silently dropped.
          </p>

          {assembled && (
            <div className="space-y-2 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-3">
              <span className="eyebrow flex items-center gap-1.5">
                <Clapperboard className="h-3 w-3" /> One continuous video
              </span>
              <video
                src={mediaUrl(assembled.r2_url)}
                controls
                playsInline
                className="w-full max-w-[280px] rounded-lg"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="secondary" size="sm" asChild>
                  <a href={mediaUrl(assembled.r2_url)} download>
                    <Download className="h-3.5 w-3.5" /> Download the full video
                  </a>
                </Button>
                <Badge variant="outline" className="text-[11px]">
                  {assembled.segment_count} segment(s) joined
                </Badge>
              </div>
              {assembled.skipped?.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                  {assembled.skipped.map((s, i) => (
                    <li key={i}>Skipped {s.id?.slice(0, 8)} — {s.reason}</li>
                  ))}
                </ul>
              )}
              {assembled.storage_error && (
                <p className="text-xs text-muted-foreground">{assembled.storage_error}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default HookContinuityPanel;
