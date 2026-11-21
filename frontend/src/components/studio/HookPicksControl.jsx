import { Focus, HelpCircle, MessagesSquare } from "lucide-react";
import { AppSelect } from "../AppSelect";
import { CONTROL_CLASS } from "../formControls";
import { GroupLabel } from "../SectionCard";

/**
 * The founder's steering picks for the Hook + CTA hook (ADR 0247),
 * standing in the Hook card above the generate action: a focus, a
 * tone, and a shape. Three small choices, each with the app's own
 * choice as its default — an untouched set of picks generates
 * exactly the hook this page has always generated.
 *
 * FOCUS is one of the app profile's own outcome lines — the list
 * below is the whole vocabulary, built from the profile the same
 * way the backend builds it (`profile_outcome_lines` in
 * ai_service.py: the evidenced outcome statements first, then the
 * flat desired outcomes they do not already say). It is NOT the
 * retired angle picker: no angle is created, stored or scored —
 * the pick names which of the app's outcomes the hook leads with,
 * and the backend proves membership again when the pick saves and
 * when the hook is written, so a line the profile no longer
 * carries steers nothing (and reads here as the app's choice).
 *
 * TONE is a closed set of three — plain, warm, bold — riding the
 * project's tone column; SHAPE is the app's choice, a question, or
 * a statement: Kasra's framing of a good hook — it names a feeling
 * or a pain point fast, as a quick question or a bold statement,
 * and holds the answer back for the demo.
 *
 * The picks are the project's, saved through the same draft PATCH
 * as every other pick on the page; this control only reports
 * choices. Changing a pick never regenerates on its own
 * (click-to-generate only): when a hook is already on file the
 * stale note says the line predates the picks and names the
 * remedy — the one hook button, Suggest a clearer hook, which the
 * founder presses themselves (ADR 0249's unified control).
 */

export function profileOutcomeLines(profile) {
  const lines = [];
  const seen = new Set();
  const add = (text) => {
    const line = String(text || "").split(/\s+/).join(" ").trim();
    if (line && !seen.has(line)) {
      seen.add(line);
      lines.push(line);
    }
  };
  for (const entry of profile?.outcome_statements || []) {
    add(typeof entry === "string" ? entry : entry?.outcome);
  }
  const desired = profile?.desired_outcomes;
  if (Array.isArray(desired)) {
    for (const entry of desired) add(entry);
  } else if (desired) {
    add(desired);
  }
  return lines;
}

const TONE_OPTIONS = [
  { value: "", label: "App's choice" },
  { value: "plain", label: "Plain" },
  { value: "warm", label: "Warm" },
  { value: "bold", label: "Bold" },
];

const SHAPE_OPTIONS = [
  { value: "auto", label: "App's choice" },
  { value: "question", label: "Question" },
  { value: "statement", label: "Statement" },
];

function PickPills({ options, current, onChange, disabled, testId, ariaLabel }) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value || "auto"}
          type="button"
          aria-pressed={current === option.value}
          disabled={disabled}
          onClick={() => onChange?.(option.value)}
          data-testid={`${testId}-${option.value || "auto"}`}
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            current === option.value
              ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-[color:var(--brand-indigo)]"
              : "border-[color:var(--hairline)] text-muted-foreground"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export default function HookPicksControl({
  focusOptions = [],
  focus = "",
  onFocusChange,
  tone = "",
  onToneChange,
  shape = "auto",
  onShapeChange,
  stale = false,
  disabled = false,
  testId = "hook-picks",
}) {
  const toneValue = TONE_OPTIONS.some((option) => option.value === tone) ? tone : "";
  const shapeValue = SHAPE_OPTIONS.some((option) => option.value === shape) ? shape : "auto";
  // A saved focus the profile no longer carries steers nothing on
  // the backend; here it reads as what it now is — the app's choice.
  const focusValue = focusOptions.includes(focus) ? focus : "";
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <GroupLabel icon={Focus}>Focus</GroupLabel>
        <AppSelect
          id="hook-cta-hook-focus"
          testId={`${testId}-focus`}
          block
          value={focusValue}
          onChange={(value) => onFocusChange?.(value)}
          disabled={disabled}
          className={CONTROL_CLASS}
          options={[
            { value: "", label: "Let the app choose" },
            ...focusOptions.map((line) => ({ value: line, label: line })),
          ]}
        />
        <p className="text-sm text-muted-foreground">
          The outcome the hook leads with — one of your app&rsquo;s own outcomes.
        </p>
      </div>

      <div className="space-y-2">
        <GroupLabel icon={MessagesSquare}>Tone</GroupLabel>
        <PickPills
          options={TONE_OPTIONS}
          current={toneValue}
          onChange={onToneChange}
          disabled={disabled}
          testId={`${testId}-tone`}
          ariaLabel="Hook tone"
        />
      </div>

      <div className="space-y-2">
        <GroupLabel icon={HelpCircle}>Shape</GroupLabel>
        <PickPills
          options={SHAPE_OPTIONS}
          current={shapeValue}
          onChange={onShapeChange}
          disabled={disabled}
          testId={`${testId}-shape`}
          ariaLabel="Hook shape"
        />
        <p className="text-sm text-muted-foreground">
          Ask the pain point as a question, or name it as a statement — the answer
          stays withheld either way, for the demo.
        </p>
      </div>

      {stale && (
        <p role="status" className="text-sm text-muted-foreground" data-testid={`${testId}-stale-note`}>
          The line on file was written before these picks — suggest a clearer hook to
          write it with them.
        </p>
      )}
    </div>
  );
}
