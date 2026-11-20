import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Briefcase,
  Clapperboard,
  Compass,
  History as HistoryIcon,
  Images,
  Layers,
  LayoutDashboard,
  Smartphone,
  TrendingUp,
} from "lucide-react";
import PageFrame from "../components/PageFrame";
import PageHeader from "../components/PageHeader";
import { SectionHeading } from "../components/SectionCard";
import { IconTile } from "../components/IconTile";
import { StatusBadge } from "../components/StatusBadge";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { api, mediaUrl } from "../lib/api";
import { draftHref, readRecentDraft } from "../lib/recentDraft";
import { CREATE_ACTION, pickDashboardAction } from "../lib/dashboardNextAction";

/**
 * The Dashboard: a routing home, not a report (ADR 0208).
 *
 * The dashboard this replaces restated what Generation History already
 * shows — totals, failed generations, a Retry button — and then linked
 * out to pages already in the sidebar. This one carries no numbers and
 * no retries: one state-aware next action, the seven destinations as
 * visual cards, and the newest renders as pictures. Its whole job is
 * to put the founder one click from the right workflow.
 *
 * Everything visual is the app's existing design system: PageFrame /
 * PageHeader framing, .surface and .surface-compact cards, IconTile,
 * StatusBadge, the accent Button, the sidebar's own icons and hint
 * lines for the destinations, and the one rise-and-settle entrance.
 */

// The seven destinations, in the order a founder works through them.
// Icons and hints are the sidebar's own (Sidebar.jsx NAV_ITEMS), so a
// card here and its link there can never describe the same place two
// ways; the sidebar stays the owner of that vocabulary.
const DESTINATIONS = [
  { to: "/create", label: "Create Video", icon: Clapperboard, testId: "dashboard-card-create", hint: "Plan, review, render" },
  { to: "/stories", label: "Stories", icon: Layers, testId: "dashboard-card-stories", hint: "Short clips, posted as stories" },
  { to: "/demo-cta", label: "Demo + CTA", icon: Smartphone, testId: "dashboard-card-demo-cta", hint: "Style clips, join, export" },
  { to: "/history", label: "History", icon: HistoryIcon, testId: "dashboard-card-history", hint: "Renders, exports, results" },
  { to: "/assets", label: "Asset Library", icon: Images, testId: "dashboard-card-assets", hint: "Presenter photos by app" },
  { to: "/analytics", label: "Analytics", icon: TrendingUp, testId: "dashboard-card-analytics", hint: "Results, verdicts, learnings" },
  { to: "/brand", label: "App Profile", icon: Briefcase, testId: "dashboard-card-brand", hint: "Research, review, approve" },
];

// The hero's glyph is the destination's own icon, so the next action
// and the grid card for the same place wear the same face.
const ACTION_ICONS = {
  profile: Briefcase,
  draft: Clapperboard,
  rendering: HistoryIcon,
  finish: Smartphone,
  create: Clapperboard,
};

/** A render's name, in the same words Analytics gives it. */
function clipName(row) {
  return row.hook_line || `${row.segment_role === "demo_cta" ? "Demo + CTA export" : "Render"} · ${row.id.slice(0, 8)}`;
}

function NextActionHero({ action }) {
  const Icon = ACTION_ICONS[action.kind] || Clapperboard;
  return (
    <section className="surface card-enter" data-testid="dashboard-next-action">
      <div className="flex flex-wrap items-center gap-4">
        <IconTile icon={Icon} size="page" />
        <div className="min-w-0 flex-1 space-y-1">
          <h2 className="font-display text-base font-semibold tracking-tight">{action.title}</h2>
          <p className="text-sm text-muted-foreground">{action.body}</p>
        </div>
        <Button variant="accent" asChild>
          <Link to={action.to} data-testid="dashboard-next-action-link">
            {action.cta}
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </Button>
      </div>
    </section>
  );
}

function HeroLoading() {
  return (
    <div className="surface" role="status" aria-label="Loading your next step" data-testid="dashboard-loading">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10 rounded-xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-4 w-2/3" />
        </div>
        <Skeleton className="h-11 w-40 rounded-xl" />
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  );
}

function RecentTile({ row, index, posterFailed, onPosterError }) {
  const posterUrl = row.poster_url && !posterFailed.has(row.id) ? mediaUrl(row.poster_url) : null;
  return (
    <Link
      to="/history"
      data-testid={`dashboard-recent-${row.id}`}
      className="surface-compact surface-interactive card-enter group block w-40 shrink-0 sm:w-44"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <span className="flex flex-col gap-3">
        <span className="relative block aspect-[9/16] overflow-hidden rounded-xl bg-secondary/20">
          {posterUrl ? (
            <img
              src={posterUrl}
              alt=""
              className="absolute inset-0 h-full w-full object-cover"
              onError={() => onPosterError(row.id)}
            />
          ) : (
            <span className="flex h-full items-center justify-center">
              <IconTile icon={Clapperboard} size="section" />
            </span>
          )}
        </span>
        <span className="space-y-2">
          <span className="block truncate text-sm font-semibold">{clipName(row)}</span>
          <StatusBadge status={row.status} />
        </span>
      </span>
    </Link>
  );
}

export default function Dashboard() {
  const [draft] = useState(() => readRecentDraft());
  const [state, setState] = useState({ loading: true, failed: false, profilesCount: 0, generations: [] });
  const [posterFailed, setPosterFailed] = useState(() => new Set());

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([api.getAppProfiles(), api.getGenerationHistory({ limit: 12 })]).then(
      ([profilesRes, historyRes]) => {
        if (cancelled) return;
        setState({
          loading: false,
          failed: profilesRes.status === "rejected" || historyRes.status === "rejected",
          profilesCount:
            profilesRes.status === "fulfilled" ? (profilesRes.value.profiles || []).length : 0,
          generations:
            historyRes.status === "fulfilled" ? historyRes.value.generations || [] : [],
        });
      }
    );
    return () => {
      cancelled = true;
    };
  }, []);

  // A navigation hub must never dead-end: when either read fails the
  // hero falls back to the one action that is always true, and the
  // grid below still routes everywhere.
  const action = state.failed
    ? CREATE_ACTION
    : pickDashboardAction({
        profilesCount: state.profilesCount,
        draft,
        draftLink: draftHref(draft),
        generations: state.generations,
      });
  const recent = state.generations.slice(0, 5);

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={LayoutDashboard}
        title="Dashboard"
        description="One next step up top, and every workflow one click away."
        data-testid="dashboard-header"
      />

      {state.loading ? <HeroLoading /> : <NextActionHero action={action} />}

      <section className="space-y-4">
        <SectionHeading icon={Compass}>Where to next</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DESTINATIONS.map((destination, index) => {
            const Icon = destination.icon;
            return (
              <Link
                key={destination.to}
                to={destination.to}
                data-testid={destination.testId}
                className="surface-compact surface-interactive card-enter group flex items-center gap-4"
                style={{ animationDelay: `${index * 60}ms` }}
              >
                <IconTile icon={Icon} size="section" />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-base font-semibold">{destination.label}</span>
                  <span className="truncate text-sm text-muted-foreground">{destination.hint}</span>
                </span>
                <ArrowRight
                  aria-hidden="true"
                  className="ml-auto h-4 w-4 shrink-0 text-muted-foreground transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-[color:var(--brand-indigo)]"
                />
              </Link>
            );
          })}
        </div>
      </section>

      {!state.loading && recent.length > 0 && (
        <section className="space-y-4">
          <SectionHeading icon={HistoryIcon}>Recent renders</SectionHeading>
          <div className="flex flex-wrap gap-4">
            {recent.map((row, index) => (
              <RecentTile
                key={row.id}
                row={row}
                index={index}
                posterFailed={posterFailed}
                onPosterError={(id) =>
                  setPosterFailed((current) => new Set(current).add(id))
                }
              />
            ))}
          </div>
        </section>
      )}
    </PageFrame>
  );
}
