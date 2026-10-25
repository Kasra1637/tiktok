import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
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
  const navigate = useNavigate();
  const { pathname } = useLocation();
  // A tour shortcut must land on its page first: opening the Demo + CTA
  // tour while still on Create spotlights nothing and skips itself shut,
  // which reads as a dead button. Navigate, then open the tour once the
  // new page has rendered. Already there: just open it.
  const goTour = (step) => {
    if (!onboarding) return;
    if (pathname === step.to) {
      onboarding.startTour(step.tourId);
      return;
    }
    navigate(step.to);
    setTimeout(() => onboarding.startTour(step.tourId), 150);
  };
  const [visible, setVisible] = useState(() => shouldShowChecklist(storage()));
  // "You are here" nudge: clicking the row for the page already on screen
  // cannot navigate, so the row answers with a single ring pulse instead of
  // reading dead. Holds the pinged step key and clears itself after the
  // animation lands, so every click replays it.
  const [ping, setPing] = useState(null);
  const pingTimer = useRef(null);
  useEffect(() => () => {
    if (pingTimer.current) clearTimeout(pingTimer.current);
  }, []);
  if (!visible) return null;

  const pingRow = (key) => {
    if (pingTimer.current) clearTimeout(pingTimer.current);
    setPing(key);
    pingTimer.current = setTimeout(() => setPing(null), 900);
  };

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
            className={`flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2.5${ping === step.key ? " first-run-ping" : ""}`}
          >
            <span
              aria-hidden="true"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[color:var(--indigo-35)] font-mono text-xs font-semibold text-[color:var(--brand-indigo)]"
            >
              {i + 1}
            </span>
            {/* The whole bar is the door: text and chevron share one link so
                a click anywhere on the row (not just the 32px chevron)
                navigates. Hover answers with the same indigo wash the five
                Demo + CTA group headers use — one hover language, not two.
                The tour shortcut stays a separate button beside it — a button
                inside a link is invalid markup and would make "show me
                around" navigate away instead. Already on that page (row 1,
                since this card lives on /create), the link would be a no-op,
                so the row plays its "you are here" pulse instead. */}
            <Link
              to={step.to}
              aria-label={pathname === step.to ? `You are already on ${step.title}` : `Go to ${step.title}`}
              data-testid={`first-run-go-${step.key}`}
              className="focus-ring flex min-w-0 flex-1 items-center gap-3 rounded-lg px-1 py-0.5 text-left transition duration-150 hover:bg-[color:var(--indigo-6)]"
              onClick={(event) => {
                // Same-page navigation is a no-op: the founder is already
                // where this step points (the card lives on /create, so row
                // 1 always is), and a click that only re-links reads dead.
                // The pulse names where they are; the tour shortcut beside
                // the row stays the way to get guided.
                if (pathname !== step.to) return;
                event.preventDefault();
                pingRow(step.key);
              }}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{step.title}</span>
                <span className="block truncate text-xs text-muted-foreground">{step.body}</span>
              </span>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            </Link>
            {onboarding && (
            <button
              type="button"
              onClick={() => goTour(step)}
              title={`Show me around ${step.title}`}
              aria-label={`Show me around ${step.title}`}
              data-testid={`first-run-tour-${step.key}`}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[color:var(--indigo-8)] hover:text-[color:var(--brand-indigo)]"
            >
              <HelpCircle className="h-4 w-4" />
            </button>
            )}
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
