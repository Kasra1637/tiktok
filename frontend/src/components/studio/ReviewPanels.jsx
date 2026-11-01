import { useEffect, useState } from "react";
import { Button } from "../ui/button";
import { CONTROL_CLASS } from "../formControls";
import { api, getErrorMessage } from "../../lib/api";

const PLAN_PHASES = ["Writing the hook…", "Writing the script…", "Placing the shots…", "Adding the demo note…"];

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * What changed on Review and what it means downstream.
 *
 * Read-only explanatory panel: which edits are still unsaved, whether the
 * downstream strategy needs rebuilding, and whether the newest rendered clip
 * still reflects the current plan and strategy. It never edits, rebuilds, or
 * renders anything itself — the existing Save, Rebuild, and Generate controls
 * keep their confirmations and gates, and nothing here triggers a paid render.
 *
 * Honest about missing history. There is no plan-history table, so "what
 * changed" is derived only from unsaved edits against the saved plan — never
 * fabricated from a previous snapshot. The clip comparison reads the newest
 * generation's recorded script/strategy versions; when the record carries no
 * versions (or no finished clip exists) it says so instead of guessing.
 */
const REVIEW_EDIT_LABELS = {
  hook_line: "Hook line",
  script: "Script",
  demo_brief: "Demo note",
  camera_setup: "Camera setup",
  visual_direction: "Visual direction",
  voice_direction: "Voice direction",
  tone: "Tone",
  beat_timeline: "Shot timeline",
};

export function ReviewRevisionsPanel({ project, edits, hasEdits, onGoToHookStory }) {
  const scriptVersion = Number(project?.script_version) || 0;
  const strategy = project?.strategy || {};
  const hasStrategy = Boolean(strategy?.hook_line);
  const strategyVersion = Number(project?.strategy_version) || 0;
  const strategyScriptVersion = Number(project?.strategy_script_version) || 0;
  const staleStrategy = hasStrategy && project?.strategy_is_current === false;
  const angleStale =
    hasStrategy &&
    String(strategy?.content_angle_id || "") !== String(project?.content_angle_id || "");

  const [clip, setClip] = useState(null);
  const [clipLoaded, setClipLoaded] = useState(false);
  const [clipError, setClipError] = useState(null);
  const [clipCheck, setClipCheck] = useState(0);
  const projectId = project?.id;
  useEffect(() => {
    let cancelled = false;
    if (!projectId || !scriptVersion) {
      setClip(null);
      setClipLoaded(false);
      return undefined;
    }
    setClipLoaded(false);
    api
      .getGenerations({ studio_project_id: projectId, limit: 1 })
      .then((data) => {
        if (cancelled) return;
        setClip(data?.generations?.[0] || null);
        setClipError(null);
        setClipLoaded(true);
      })
      .catch((err) => {
        // A failed check is not an empty shelf: naming it stops the panel
        // from inviting a duplicate paid render for a clip that exists.
        if (cancelled) return;
        setClip(null);
        setClipError(getErrorMessage(err));
        setClipLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, scriptVersion, clipCheck]);

  if (!scriptVersion) return null;

  const editedLabels = Object.keys(edits || {}).map(
    (key) => REVIEW_EDIT_LABELS[key] || humanize(key)
  );

  // A strategy row without a recorded version is missing history, not proof
  // of a match: the server numbers every build, so v0 means the record
  // predates the versioning rather than that it matches the current plan.
  const strategyUnversioned = hasStrategy && !strategyVersion;

  const clipIsCurrent =
    clipLoaded &&
    clip &&
    clip.status === "completed" &&
    typeof clip.script_version === "number" &&
    typeof clip.strategy_version === "number" &&
    clip.script_version === scriptVersion &&
    clip.strategy_version === strategyVersion;
  const clipIsStale =
    clipLoaded &&
    clip &&
    clip.status === "completed" &&
    typeof clip.script_version === "number" &&
    typeof clip.strategy_version === "number" &&
    (clip.script_version !== scriptVersion || clip.strategy_version !== strategyVersion);
  const clipUnversioned =
    clipLoaded &&
    clip &&
    clip.status === "completed" &&
    (typeof clip.script_version !== "number" || typeof clip.strategy_version !== "number");

  // One status line: the saved-plan state plus the single next thing to do.
  // Priority is unchanged — unsaved edits first (the render gate refuses
  // them), then strategy staleness (a paid render built from the wrong
  // words), then clip staleness.
  const planState =
    `Plan v${scriptVersion} · ` +
    ((project?.hook_line || project?.script) ? "has words." : "empty.");
  let status;
  if (hasEdits) {
    status =
      `${planState} Unsaved edits in: ${editedLabels.join(", ")}. ` +
      "Save below first — rendering needs the saved plan.";
  } else if (!hasStrategy) {
    status = `${planState} No strategy yet — build it below before rendering.`;
  } else if (strategyUnversioned) {
    status =
      `${planState} Strategy exists but its version was not recorded — ` +
      "rebuild it below before rendering.";
  } else if (staleStrategy) {
    status =
      `${planState} Strategy v${strategyVersion} was built from plan v${strategyScriptVersion}. ` +
      "Rebuild the strategy before rendering, or the clip follows the older plan.";
  } else if (angleStale) {
    status =
      `${planState} Strategy was built for a different audience angle. ` +
      "Rebuild it for the current angle before rendering.";
  } else if (!clipLoaded) {
    status = `${planState} Strategy v${strategyVersion} matches. Checking for rendered clips…`;
  } else if (clipIsStale) {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      `Rendered clip reflects plan v${clip.script_version} and strategy v${clip.strategy_version} — ` +
      "re-render below.";
  } else if (clipUnversioned) {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      "Rendered clip's versions were not recorded — re-render if you edited since.";
  } else if (clip && clip.status !== "completed") {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      `Latest render is ${clip.status || "not finished"} — finish or retry it below.`;
  } else if (clipIsCurrent) {
    status =
      `${planState} Strategy v${strategyVersion} matches · rendered clip is current.`;
  } else if (clipError) {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      `Could not check for rendered clips (${clipError}) — check again below.`;
  } else {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      "No rendered clip yet — render below when ready.";
  }

  return (
    <div
      className="inset-panel space-y-4"
      data-testid="review-revisions"
    >
      <span className="eyebrow block">Revisions &amp; consequences</span>
      <p className="text-base" data-testid="revisions-status">
        {status}
      </p>
      {clipError && clipLoaded && (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setClipError(null);
            setClipLoaded(false);
            setClipCheck((k) => k + 1);
          }}
          data-testid="clip-recheck"
        >
          Check again
        </Button>
      )}
      {onGoToHookStory && (
        <Button variant="secondary" size="sm" onClick={onGoToHookStory}>
          Review strategy below
        </Button>
      )}
    </div>
  );
}

/**
 * One profile-aware dropdown for a Review-step direction field.
 *
 * The options come from the profile's category group (no free typing), and
 * picking only fills the draft — saving still runs the normal claim check
 * and the strategy still needs a rebuild, exactly as with typed notes.
 */
export function DirectionSelect({
  id,
  testId,
  label,
  value,
  onPick,
  options,
  placeholder,
  disabled,
  // Fresh-list generation for this dropdown alone. When provided, a small
  // action beside the label spends one text model call for four new options
  // grounded in the profile and the selected angle — the static category
  // list repeats itself across videos, and a founder who has seen all four
  // has nowhere else to go. { onRefresh, refreshing, refreshTestId }.
  refresh = null,
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-semibold">{label}</label>
        {refresh && (
          <button
            type="button"
            onClick={refresh.onRefresh}
            disabled={disabled || refresh.refreshing}
            data-testid={refresh.refreshTestId}
            className="shrink-0 text-xs text-muted-foreground underline disabled:opacity-50"
          >
            {refresh.refreshing ? "Finding new options…" : "New options"}
          </button>
        )}
      </div>
      <select
        id={id}
        data-testid={testId}
        className={CONTROL_CLASS}
        value={value}
        disabled={disabled || !options}
        onChange={(e) => onPick(e.target.value)}
      >
        <option value="">{options ? placeholder : "Loading options…"}</option>
        {(options || []).map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </div>
  );
}

/**
 * Live narration while the plan writes. The artifact arrives whole, so there
 * is nothing honest to count — but its sections are known up front (hook,
 * script, shots, demo note), and naming the current one beats a static line
 * that never moves. Unmounts with its branch, so a failure can never strand
 * it beside the error; the interval dies with the component.
 */
export function PlanPhaseLine() {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % PLAN_PHASES.length);
    }, 1800);
    return () => clearInterval(timer);
  }, []);
  return (
    <span role="status" data-testid="plan-progress">
      {PLAN_PHASES[index]}
    </span>
  );
}
