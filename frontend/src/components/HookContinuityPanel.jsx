import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { api, getErrorMessage, mediaUrl } from "../lib/api";
import {
  DEFAULT_HOOK,
  readExtendIntent,
  resolveLength as resolveLengthFor,
  resolveExtendLock as resolveExtendLockFor,
  plannedCoverage as plannedCoverageFor,
} from "../lib/videoLength";
import {
  Loader2, Clapperboard, AlertTriangle, Download, RefreshCw, Check,
  Info, Clock, MapPin, Film, Scissors, ShieldQuestion,
  Sparkles, Play, Link2,
} from "lucide-react";

/**
 * The app-specific influencer workflow, end to end.
 *
 *   strategy -> hook (locked length) -> approve -> extend -> assemble
 *
 * The order is the product. The hook is generated on its own so the concept
 * can be judged in seconds, approving it is what unlocks extensions, and
 * only approved segments are joined into the final file. An extension always
 * continues the approved take rather than re-imagining it, and the panel says
 * plainly what the provider was actually given so a continuity gap is never
 * something the founder has to infer from a prompt.
 */

const POLL_INTERVAL_MS = 6000;

// Hook lengths, extend lengths and their rules live in ../lib/videoLength so
// they can be asserted directly. That file was extracted after this panel
// shipped an `extend_intent === 0` that could never read "off" and a
// `Number("target")` that turned "fill to target" into a silent 5s request —
// neither of which any build step or backend test could see.

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

/**
 * Turn a machine key into something readable.
 *
 * The strategy comes back from the model with snake_case keys, and they were
 * being printed verbatim: "facial_features", "body_appearance", "color_palette".
 * That reads as a debug dump rather than a plan the founder is meant to act on.
 *
 * `ACRONYMS` covers the cases where a plain title-case is wrong, and
 * `STRATEGY_LABELS` covers the ones that need real words rather than a
 * mechanical transform.
 */
const STRATEGY_LABELS = {
  camera_angle: "Camera angle",
  visual_style: "Visual style",
  age_range: "Age range",
  color_palette: "Colour palette",
  hair_style: "Hair style",
  body_appearance: "Body and posture",
  facial_features: "Face",
  facial_expression: "Expression",
  styling_details: "Styling details",
  voice_delivery: "Voice delivery",
  character_positioning: "Position in frame",
};

const ACRONYMS = {
  ai: "AI",
  api: "API",
  fps: "FPS",
  hd: "HD",
  us: "US",
  uk: "UK",
  url: "URL",
  vlog: "Vlog",
  cta: "CTA",
};

function strategyLabel(key) {
  if (STRATEGY_LABELS[key]) return STRATEGY_LABELS[key];
  return String(key)
    .split("_")
    .filter(Boolean)
    .map((word) => ACRONYMS[word.toLowerCase()] || word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * A titled group of label/value rows.
 *
 * The label sits on its own line above the value rather than beside it. Side by
 * side, `shrink-0` on the label plus a long value forced the value column to
 * wrap into a ragged narrow strip, which is what made this block hard to scan.
 * Stacked, every value gets the full column width regardless of key length.
 */
function StrategyBlock({ title, icon: Icon, rows, description }) {
  const filled = rows.filter(([, value]) => String(value || "").trim());
  if (!filled.length) return null;
  return (
    <div className="space-y-2">
      <div className="space-y-0.5">
        <span className="eyebrow flex items-center gap-1.5">
          <Icon className="h-3 w-3" /> {title}
        </span>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <dl className="space-y-2">
        {filled.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs font-medium text-muted-foreground">
              {strategyLabel(label)}
            </dt>
            <dd className="mt-0.5 text-sm leading-snug">{String(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * Collapse a long run of same-role segments into one readable line.
 *
 * A typical plan is 7-8 identical "continuation (1s)" lines, which is a wall of
 * near-duplicate text that hides the two lines that actually matter — the hook
 * and the CTA. Runs of the same role and length collapse to "2-8. Continuation
 * (1s each)"; anything that stands alone keeps its own line, so a plan with one
 * continuation does not gain a range for no reason.
 *
 * A collapsed run reports the summed duration and the COUNT of goals rather than
 * the first goal it happens to encounter. Printing one goal out of seven would
 * read as though that was all the run did, which is exactly the kind of quiet
 * misreading this collapse exists to prevent.
 */
function collapseSegments(segments) {
  const runs = [];
  segments.forEach((s, i) => {
    const last = runs[runs.length - 1];
    const seconds = Number(s.seconds) || 0;
    if (last && last.role === s.role && last.seconds === seconds) {
      last.end = i;
      last.total += seconds;
      if (s.goal) last.goalCount += 1;
      return;
    }
    runs.push({
      role: s.role,
      seconds,
      total: seconds,
      start: i,
      end: i,
      goal: s.goal,
      goalCount: s.goal ? 1 : 0,
    });
  });
  return runs;
}

function segmentRange(run) {
  // 1-based, and a collapsed run reads "2-8" rather than "2–8" so it stays
  // unambiguous when copied out of the page.
  const from = run.start + 1;
  const to = run.end + 1;
  return from === to ? `${from}` : `${from}-${to}`;
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
  // Hook length: computed, recommended, locked.
  //
  // The strategy plans segment 0 at N seconds, and that number — resolved
  // against the provider floor/ceiling — is what renders. There is no
  // selector because there is no choice to make: any other length would no
  // longer be the planned hook. Nothing is displayed before a strategy
  // exists; the saved value below only seeds the computation the hook
  // submit and button label need once the plan is there. resolveLength()
  // mirrors the backend's resolve_length() so the delivered number is honest
  // BEFORE the render is paid for — the backend still decides, and its plan
  // is what the response reports.
  // -------------------------------------------------------------------------
  const capability = models?.models?.find((m) => m.key === selectedModel);
  const floor = capability?.min_duration ?? 4;
  const ceiling = capability?.max_duration ?? 30;

  const resolveLength = (target) => resolveLengthFor(target, capability);

  const savedHook = Number(project?.hook_seconds || 0);
  const plannedHook = Number(strategy?.segments?.[0]?.seconds) || 0;
  const lockedHook = plannedHook || savedHook || DEFAULT_HOOK;
  const lengthPlan = resolveLength(lockedHook);
  const hookDelivered = lengthPlan.trimTo || lengthPlan.render;
  // Read as a boolean. The previous `=== 0` never read "off" because the API
  // returns a real boolean and `false === 0` is false.
  const extendIntent = readExtendIntent(project);

  // Declared intent to extend the hook into a full video.
  //
  // Set on the Audience & goal step, where the total length is chosen, and
  // persisted with the project. Read-only here: it gates the running total and
  // the extend button's label, so a hook-only video never presents a target
  // that was never chosen. Deliberately NOT load-bearing — it changes what this
  // panel shows, never what gets rendered, so changing it after a strategy
  // exists cannot invalidate that strategy and force a paid rebuild. The hook is
  // the opening of a video either way, and extending is always available.

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
  // null when the strategy predates coverage reporting, so we say nothing
  // rather than claiming "0 remaining".
  const plannedCoverage = plannedCoverageFor(segments, strategy);
  // The locked extension for a segment: the next uncovered planned beat's
  // seconds, resolved against the provider floor/ceiling. Computed per
  // segment because each extension continues a different point in the plan.
  const extendLockFor = (segmentIndex) => resolveExtendLockFor(
    Number(strategy?.segments?.[Number(segmentIndex) + 1]?.seconds) || 0,
    remainingToTarget,
    capability
  );

  const handleGenerateStrategy = () =>
    run("strategy", async () => {
      // No hook length is sent: the server resolves the template default,
      // the strategy plans segment 0 from it, and the lock displays the
      // plan. Sending our own number here would let a stale saved value
      // override the template the founder actually picked.
      const updated = await api.generateStrategy(projectId, {});
      onProjectChange?.(updated);
      setNotice(
        `Strategy v${updated.strategy_version} built from this app's profile. Review the hook and the locked person, then generate the hook.`
      );
    });

  const handleGenerateHook = () =>
    run("hook", async () => {
      const created = await api.generateHook(projectId, {
        model: selectedModel || undefined,
        duration_seconds: lockedHook,
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

      {/* Hook length. Shown only once a strategy exists: the length is
          computed from the plan, not chosen before it. The planned hook beat
          is N seconds and nothing else would be the planned hook, so there is
          no selector. Separate from the project's "total video length"
          because it is a different axis: this is the first segment of it. */}
      {hasStrategy && (
      <div className="space-y-1.5">
        <span className="text-sm font-medium">Hook length</span>
        <p className="rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm">
          {hookDelivered}s — recommended for this plan
        </p>
        {lengthPlan.trimTo ? (
          <p className="text-xs text-muted-foreground">
            {capability?.name || "This provider"} cannot render under {floor}s, so the hook
            is generated at {lengthPlan.render}s and cut down to {lengthPlan.trimTo}s. The
            total video length is unchanged — this is only the opening segment.
          </p>
        ) : (
          <p className="text-xs text-muted-foreground">
            The opening {hookDelivered}s of the video. The total length is set on the
            Audience &amp; goal step.
          </p>
        )}
      </div>
      )}

      {/* Declared intent lives on the Audience & goal step now, because it
          decides whether a total length is a real choice. It is still READ
          here: it gates the running total below and the extend button's label. */}

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
            {/* There is no "person" block, and deliberately so. It used to sit
                here above "The scene" listing the model's guess at the founder's
                face, hair, age and wardrobe, under the heading "locked for every
                segment" — while the actual photograph sat in the project's
                assets. It read as a description of the person they uploaded, and
                it was invented. The on-camera person is now copied from the
                character reference image and nothing is written about them.
                Scene and performance remain: they are plan-level and conflict
                with nothing. Both take the full width, since the scene block is
                the only one of its kind left in this row. */}
            <StrategyBlock
              title="The scene"
              description="Locked for every segment."
              icon={MapPin}
              rows={Object.entries(strategy.scene || {})}
            />
            <div className="border-t border-[color:var(--indigo-35)] pt-3">
              <StrategyBlock
                title="Performance"
                icon={Film}
                rows={Object.entries(strategy.performance || {})}
              />
            </div>
            <div className="space-y-1.5">
              <span className="eyebrow">Segments planned</span>
              <ol className="space-y-1.5 text-sm">
                {collapseSegments(strategy.segments || []).map((run) => {
                  const collapsed = run.start !== run.end;
                  return (
                    <li key={`${run.start}-${run.role}`} className="flex gap-2">
                      <span className="w-8 shrink-0 font-mono text-xs text-muted-foreground">
                        {segmentRange(run)}
                      </span>
                      <span className="min-w-0">
                        <span className="font-medium capitalize">{run.role}</span>{" "}
                        <span className="text-muted-foreground">
                          {collapsed
                            ? `x${run.end - run.start + 1}, ${run.total}s total`
                            : `${run.seconds}s`}
                        </span>
                        {!collapsed && run.goal && (
                          <>
                            {" — "}
                            {run.goal}
                          </>
                        )}
                        {collapsed && run.goalCount > 0 && (
                          <span className="block text-xs text-muted-foreground">
                            {run.goalCount} {run.goalCount === 1 ? "beat covers" : "beats cover"}{" "}
                            {run.goalCount === 1 ? "its goal" : "their goals"}
                            {run.goal ? `, starting with "${run.goal}"` : ""}.
                          </span>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ol>
              <p className="text-xs text-muted-foreground">
                The hook and the CTA are the two segments that carry the video. The
                continuations between them hold the same person and scene in place
                while the point lands.
              </p>
            </div>
            {/* Restates the fields above in the model's own words, so it is
                deliberately the quietest block here: it is the contract, not new
                information. */}
            {strategy.continuity_contract?.must_not_change?.length > 0 && (
              <details className="space-y-1.5 border-t border-[color:var(--indigo-35)] pt-3">
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                  Continuity contract ({strategy.continuity_contract.must_not_change.length} locked
                  {strategy.continuity_contract.must_not_change.length === 1 ? "" : "s"})
                </summary>
                <ul className="list-disc space-y-0.5 pl-4 text-sm">
                  {strategy.continuity_contract.must_not_change.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </details>
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
            {segments.length ? "Regenerate the hook" : `Generate the ${hookDelivered}s hook`}
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
                      {segment.approved && (() => {
                        // Extension length is computed, recommended, locked:
                        // the next uncovered planned beat, resolved so the
                        // delivered number is honest. No selector, because any
                        // other length would no longer be the planned beat.
                        const lock = extendLockFor(segment.segment_index);
                        return (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-xs text-muted-foreground">
                            {lock ? (
                              <>+{lock.seconds}s — recommended{lock.trimTo ? ` (renders at ${lock.render}s, cut down)` : ""}</>
                            ) : remainingToTarget > ceiling ? (
                              <>Needs {remainingToTarget}s — more than one pass. Extend in two steps.</>
                            ) : (
                              <>The plan has no further beats for this segment.</>
                            )}
                          </span>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              if (!lock) {
                                setNotice(
                                  "That needs more than one pass on this model. Extend in two " +
                                    "steps, or pick a shorter length."
                                );
                                return;
                              }
                              handleExtend(segment.id, lock.seconds);
                            }}
                            disabled={
                              Boolean(busy) ||
                              Boolean(inFlightId) ||
                              !lock
                            }
                          >
                            {busy === `extend-${segment.id}` ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <RefreshCw className="h-3.5 w-3.5" />
                            )}
                            {extendIntent ? "Extend" : "Extend (optional)"}
                          </Button>
                        </div>
                        );
                      })()}
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
          {plannedCoverage !== null && remainingToTarget > 0 && (() => {
            // Warns BEFORE the founder spends: a plan is finite, and a founder
            // extending by 3s could exhaust it before reaching the target.
            const per = resolveExtendRequest(extendBy, remainingToTarget, capability);
            const each = per ? per.seconds : 0;
            const reachable = each * plannedCoverage;
            return (
              <p className="text-xs text-muted-foreground">
                {`The strategy plans ${plannedCoverage} more segment${plannedCoverage === 1 ? "" : "s"}. `}
                {!each
                  ? "Choose a length to see whether that covers the rest of your target."
                  : reachable < remainingToTarget
                    ? `At +${each}s that reaches about ${reachable}s, so you may need to rebuild the strategy for the full ${targetTotal}s.`
                    : `At +${each}s that covers the rest of your target.`}
              </p>
            );
          })()}
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
