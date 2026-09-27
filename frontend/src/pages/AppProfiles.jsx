import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage } from "../lib/api";
import { Briefcase, Loader2, AlertTriangle, ExternalLink, Plus, ArrowRight } from "lucide-react";

function StatusBadge({ status }) {
  if (status === "approved") {
    return <Badge variant="indigo" className="text-xs">Approved</Badge>;
  }
  return <Badge variant="secondary" className="text-xs">Draft — needs review</Badge>;
}

function PlatformChips({ row }) {
  const stores = [
    row.website_url && { label: "Web", href: row.website_url },
    row.appstore_url && { label: "App Store", href: row.appstore_url },
    row.play_url && { label: "Google Play", href: row.play_url },
  ].filter(Boolean);
  if (!stores.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {stores.map((s) => (
        <a
          key={s.label}
          href={s.href}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1 rounded-full border border-[color:var(--hairline)] px-2 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:border-[color:var(--indigo-35)] hover:text-[color:var(--brand-indigo)]"
        >
          {s.label}
          <ExternalLink className="h-2.5 w-2.5" />
        </a>
      ))}
    </div>
  );
}

export default function AppProfiles() {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .getAppProfiles()
      .then((data) => setProfiles(data.profiles || []))
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  const approved = profiles.filter((p) => p.status === "approved").length;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Briefcase}
        title="App Profiles"
        description="Each profile holds the verified facts about one mobile app: features, pricing, audiences, and the claims a promo may or may not make."
        actions={
          <Button variant="brand" asChild>
            <Link to="/brand">
              <Plus className="h-4 w-4" /> New profile
            </Link>
          </Button>
        }
      />

      {profiles.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {profiles.length} profile{profiles.length === 1 ? "" : "s"} · {approved} approved
        </p>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load profiles</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading profiles...
        </p>
      ) : profiles.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No App Profiles yet"
          description="Research a mobile app from its website and store listings to generate your first profile."
          action={
            <Button variant="brand" asChild>
              <Link to="/brand">
                Research an app <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {profiles.map((p) => (
            <Link
              key={p.id}
              to={`/app-profiles/${p.id}`}
              className="surface group flex flex-col gap-3 rounded-2xl p-5 transition-colors hover:border-[color:var(--indigo-35)]"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-display truncate text-base font-semibold">
                    {p.brand_name || "Untitled app"}
                  </h3>
                  <p className="mt-0.5 text-sm text-muted-foreground">
                    {p.app_category || p.niche || "Category not set"}
                  </p>
                </div>
                <StatusBadge status={p.status} />
              </div>

              <PlatformChips row={p} />

              <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
                <span>
                  {p.version > 1 ? `Version ${p.version}` : "Version 1"}
                  {p.approved_at ? " · approved" : ""}
                </span>
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
