import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage } from "../lib/api";
import { Briefcase, Loader2, AlertTriangle, ExternalLink, Plus, ArrowRight, Trash2, Video } from "lucide-react";

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
    /* z-10 keeps the store links clickable above the stretched card link. */
    <div className="relative z-10 flex flex-wrap gap-1.5">
      {stores.map((s) => (
        <a
          key={s.label}
          href={s.href}
          target="_blank"
          rel="noreferrer"
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
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    api
      .getAppProfiles()
      .then((data) => setProfiles(data.profiles || []))
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(profile) {
    const name = profile.brand_name || "Untitled app";
    if (
      !window.confirm(
        `Delete "${name}"? This permanently removes the profile, its assets, projects, generations, and history. This can't be undone.`,
      )
    ) {
      return;
    }
    setDeletingId(profile.id);
    setError(null);
    try {
      await api.deleteAppProfile(profile.id);
      setProfiles((prev) => prev.filter((row) => row.id !== profile.id));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDeletingId(null);
    }
  }

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
          <AlertTitle>Something went wrong</AlertTitle>
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
          {profiles.map((p) => {
            const name = p.brand_name || "Untitled app";
            const deleting = deletingId === p.id;
            return (
              /* Stretched-link card: the Link overlays the whole card so any
                 click navigates, while interactive children (store chips,
                 Delete) sit above it with z-10. Keeps the DOM valid — no
                 button nested inside an anchor. */
              <div
                key={p.id}
                className="surface group relative flex flex-col gap-3 rounded-2xl p-5 transition-colors hover:border-[color:var(--indigo-35)]"
              >
                <Link
                  to={`/app-profiles/${p.id}`}
                  className="absolute inset-0 rounded-2xl"
                  aria-label={`Open ${name}`}
                />

                <div className="pointer-events-none relative z-10 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-display truncate text-base font-semibold">{name}</h3>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {p.app_category || p.niche || "Category not set"}
                    </p>
                  </div>
                  <StatusBadge status={p.status} />
                </div>

                <PlatformChips row={p} />

                <div className="pointer-events-none relative z-10 flex items-center justify-between pt-1 text-xs text-muted-foreground">
                  <span>
                    {p.version > 1 ? `Version ${p.version}` : "Version 1"}
                    {p.approved_at ? " · approved" : ""}
                  </span>
                  <div className="flex items-center gap-2">
                    {/* An app is a reusable starting point, not a one-shot
                        input. This is why a built profile doesn't feel spent. */}
                    {p.status === "approved" && (
                      <Button
                        variant="secondary"
                        size="sm"
                        asChild
                        className="pointer-events-auto h-7 gap-1.5 rounded-lg px-2 text-xs"
                        data-testid={`new-video-${p.id}`}
                      >
                        <Link
                          to={`/create?profile=${encodeURIComponent(p.id)}`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Video className="h-3.5 w-3.5" />
                          New video
                        </Link>
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={deleting}
                      onClick={() => handleDelete(p)}
                      data-testid={`delete-profile-${p.id}`}
                      className="pointer-events-auto h-7 gap-1.5 rounded-lg px-2 text-xs text-muted-foreground hover:text-destructive"
                    >
                      {deleting ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                      Delete
                    </Button>
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
