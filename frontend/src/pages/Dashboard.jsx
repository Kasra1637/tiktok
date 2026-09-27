import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import {
  LayoutDashboard, Loader2, AlertTriangle, ArrowRight, Briefcase,
  LayoutTemplate, Clapperboard, DollarSign, CheckCircle2, TrendingUp,
} from "lucide-react";

function money(value) {
  if (value === null || value === undefined) return null;
  return `$${Number(value).toFixed(2)}`;
}

function Stat({ icon: Icon, label, value, hint, tone = "default" }) {
  const toneClass =
    tone === "good" ? "text-[color:var(--brand-indigo)]" :
    tone === "bad" ? "text-destructive" : "";
  return (
    <div className="surface rounded-2xl p-4">
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      <p className={`mt-1.5 font-display text-2xl font-bold ${toneClass}`}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function ActionRow({ to, icon: Icon, title, description, count, tone }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] p-3 transition-colors hover:border-[color:var(--indigo-35)]"
    >
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
          tone === "warn"
            ? "border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-[color:var(--brand-indigo)]"
            : "border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <span className="text-sm font-medium">{title}</span>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {count > 0 && <Badge variant="indigo" className="shrink-0">{count}</Badge>}
      <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
    </Link>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .getDashboard()
      .then(setData)
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading dashboard...
      </p>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Could not load the dashboard</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const t = data?.totals || {};
  const successRate = t.success_rate;
  const spent = money(t.total_usd);
  const unapproved = data?.profiles_awaiting_approval || [];
  const drafts = data?.pending_template_drafts || [];
  const failures = data?.recent_failures || [];

  return (
    <div className="space-y-6">
      <PageHeader
        icon={LayoutDashboard}
        title="Dashboard"
        description="Where everything stands, and what needs you next."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          icon={Clapperboard}
          label="Videos created"
          value={t.videos_created ?? 0}
          hint={`${t.completed ?? 0} completed · ${t.failed ?? 0} failed`}
        />
        <Stat
          icon={CheckCircle2}
          label="Success rate"
          value={successRate == null ? "—" : `${Math.round(successRate * 100)}%`}
          hint="In-flight jobs are excluded"
          tone={successRate != null && successRate < 0.5 ? "bad" : "good"}
        />
        <Stat
          icon={DollarSign}
          label="Spend"
          value={spent || "$0.00"}
          hint={
            t.unpriced_runs
              ? `${t.unpriced_runs} run(s) unpriced`
              : "All runs priced"
          }
        />
        <Stat
          icon={TrendingUp}
          label="Avg generation"
          value={t.avg_generation_seconds != null ? `${t.avg_generation_seconds}s` : "—"}
        />
      </div>

      {(unapproved.length > 0 || drafts.length > 0) && (
        <div className="space-y-2">
          <h2 className="font-display text-base font-semibold">Needs your review</h2>
          {unapproved.map((p) => (
            <ActionRow
              key={`p-${p.id}`}
              to="/brand"
              icon={Briefcase}
              tone="warn"
              title={`${p.brand_name || "Untitled app"} is not approved yet`}
              description="Content angles and video plans need an approved profile."
              count={1}
            />
          ))}
          {drafts.map((d) => (
            <ActionRow
              key={`d-${d.id}`}
              to="/research"
              icon={LayoutTemplate}
              tone="warn"
              title={`Unpublished template draft: ${d.name}`}
              description="From trend research. Publish it to use it in a video."
              count={1}
            />
          ))}
        </div>
      )}

      <div className="space-y-2">
        <h2 className="font-display text-base font-semibold">Next steps</h2>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <ActionRow
            to="/create"
            icon={Clapperboard}
            title="Create a video"
            description="Guided wizard from profile to MP4"
          />
          <ActionRow
            to="/app-profiles"
            icon={Briefcase}
            title="App Profiles"
            description="Research and approve an app"
            count={(data?.profiles || []).length}
          />
          <ActionRow
            to="/templates"
            icon={LayoutTemplate}
            title="Hook Templates"
            description="Curated reusable structures"
          />
          <ActionRow
            to="/history"
            icon={Clapperboard}
            title="Generation History"
            description="Review, vary, and download"
          />
        </div>
      </div>

      {failures.length > 0 && (
        <div className="space-y-2">
          <h2 className="font-display text-base font-semibold">Recent failures</h2>
          {failures.map((f) => (
            <div
              key={f.id}
              className="flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-sm"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
              <span className="min-w-0 flex-1 truncate text-xs">{f.error}</span>
              {f.retryable && <Badge variant="outline" className="shrink-0 text-[11px]">retryable</Badge>}
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Videos are generated here and posted by hand. This tool never publishes to any
        platform and never asks for platform credentials.
      </p>
    </div>
  );
}
