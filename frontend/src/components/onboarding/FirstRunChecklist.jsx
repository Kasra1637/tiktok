import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, ChevronRight, HelpCircle, ListChecks, X } from "lucide-react";
import { SectionCard } from "../SectionCard";
import { useOptionalOnboarding } from "./OnboardingProvider";
import { dismissFirstRun, shouldShowChecklist } from "../../lib/onboarding/firstRun";

/**
 * First-run wayfinding: the golden path is Create Video, then Demo + CTA,
 * then Export — but the sidebar lists six destinations with no order, and
 * each page's spotlight tour only explains the page you are already on.
 * This card is step zero: it carries the founder across pages, and each
 * step offers the existing tour for that page rather than re-explaining it.
 *
 * Shows until the first Demo + CTA export is saved to History (see
 * exportFlow's saveExport) or until dismissed — never again after either.
 * Steps are doors, not progress tracking: the app cannot know a render
 * finished from here, so nothing pretends to tick itself off.
 */
const STEPS = [
  {
    key: "create",
    title: "Create your Hook + Story",
    body: "Pick an app, an angle and a template, then render the clip.",
    to: "/create",
    tourId: "create",
  },
  {
    key: "demo-cta",
    title: "Style it in Demo + CTA",
    body: "Open the finished render, add your demo and your close.",
    to: "/demo-cta",
    tourId: "demo-cta",
  },
  {
    key: "export",
    title: "Export the TikTok",
    body: "One fixed MP4 in the Demo + CTA player row, saved to History.",
    to: "/demo-cta",
    tourId: "demo-cta",
  },
];

function storage() {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function FirstRunChecklist() {
  // Nullable on purpose: the render-smoke suite mounts components without
  // the provider, and a card that crashed there would take its whole page
  // down in the harness while working fine in the app. Without a provider
  // the steps are still doors — they just lose the tour shortcut.
  const onboarding = useOptionalOnboarding();
  const [visible, setVisible] = useState(() => shouldShowChecklist(storage()));
  if (!visible) return null;

  const dismiss = () => {
    dismissFirstRun(storage());
    setVisible(false);
  };

  return (
    <SectionCard
      title="Your first export in 3 steps"
      icon={ListChecks}
      description="The path through the studio — each step links to its page, with its tour one click away."
      data-testid="first-run-checklist"
      actions={
        <button
          type="button"
          onClick={dismiss}
          title="Dismiss this guide"
          aria-label="Dismiss this guide"
          data-testid="first-run-dismiss"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[color:var(--indigo-8)] hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      }
    >
      <ol className="space-y-2">
        {STEPS.map((step, i) => (
          <li
            key={step.key}
            data-testid={`first-run-step-${step.key}`}
            className="flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2.5"
          >
            <span
              aria-hidden="true"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[color:var(--indigo-35)] font-mono text-xs font-semibold text-[color:var(--brand-indigo)]"
            >
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{step.title}</p>
              <p className="truncate text-xs text-muted-foreground">{step.body}</p>
            </div>
            {onboarding && (
            <button
              type="button"
              onClick={() => onboarding.startTour(step.tourId)}
              title={`Show me around ${step.title}`}
              aria-label={`Show me around ${step.title}`}
              data-testid={`first-run-tour-${step.key}`}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[color:var(--indigo-8)] hover:text-[color:var(--brand-indigo)]"
            >
              <HelpCircle className="h-4 w-4" />
            </button>
            )}
            <Link
              to={step.to}
              aria-label={`Go to ${step.title}`}
              data-testid={`first-run-go-${step.key}`}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[color:var(--indigo-8)] hover:text-foreground"
            >
              <ChevronRight className="h-4 w-4" />
            </Link>
          </li>
        ))}
      </ol>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" />
        Done after your first export saves to History — this card never returns.
      </p>
    </SectionCard>
  );
}

export default FirstRunChecklist;
