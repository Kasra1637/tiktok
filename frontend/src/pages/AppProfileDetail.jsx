import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import {
  Briefcase, Loader2, AlertTriangle, ArrowLeft, Sparkles, Target,
  ShieldAlert, Lightbulb, ChevronRight, Video, Trash2, RefreshCw,
} from "lucide-react";

/** Read an array-or-empty field into a clean list. */
function list(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === "string" && value.trim()) {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
    } catch {
      return [];
    }
  }
  return [];
}

function ListBlock({ label, items, tone = "default" }) {
  if (!items.length) return null;
  const toneClass =
    tone === "banned"
      ? "border-[color:var(--hairline-strong)] bg-secondary/30"
      : tone === "review"
        ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
        : "border-[color:var(--hairline)] bg-secondary/20";
  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <span className="eyebrow block">{label}</span>
      <ul className="mt-2 space-y-1.5 text-sm text-foreground/90">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[color:var(--brand-indigo)]" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({ label, value }) {
  if (!value) return null;
  return (
    <div>
      <span className="eyebrow block">{label}</span>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{value}</p>
    </div>
  );
}

function ClaimPanel({ profile }) {
  const approved = list(profile.claims_approved);
  const review = list(profile.claims_review);
  const banned = list(profile.claims_banned);
  if (!approved.length && !review.length && !banned.length) return null;
  return (
    <div className="space-y-3" data-testid="claim-guardrails">
      <span className="eyebrow block">Claim guardrails</span>
      <p className="text-xs text-muted-foreground">The plan checks these phrases before rendering. Review each claim for accuracy before publishing; an automated check is not a guarantee.</p>
      <ListBlock label="Approved — safe to use" items={approved} />
      <ListBlock label="Needs review — verify first" items={review} tone="review" />
      <ListBlock label="Never use" items={banned} tone="banned" />
    </div>
  );
}

function AngleCard({ angle, onDelete, busy }) {
  return (
    <div className="surface rounded-2xl">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-display text-sm font-semibold">{angle.label || angle.kind}</h4>
          <Badge variant="secondary" className="mt-1 text-[11px]">
            {String(angle.kind || "").replace(/_/g, " ")}
          </Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete(angle.id)}
          disabled={busy}
          aria-label={`Delete ${angle.label || "angle"}`}
        >
          Delete
        </Button>
      </div>

      <dl className="mt-3 space-y-2 text-sm">
        {angle.target_audience && (
          <div>
            <dt className="eyebrow">Audience</dt>
            <dd className="text-foreground/90">{angle.target_audience}</dd>
          </div>
        )}
        {angle.user_problem && (
          <div>
            <dt className="eyebrow">Problem</dt>
            <dd className="text-foreground/90">{angle.user_problem}</dd>
          </div>
        )}
        {angle.hook_promise && (
          <div>
            <dt className="eyebrow">Hook promise</dt>
            <dd className="text-foreground/90">{angle.hook_promise}</dd>
          </div>
        )}
        {angle.app_feature && (
          <div>
            <dt className="eyebrow">Feature shown</dt>
            <dd className="text-foreground/90">{angle.app_feature}</dd>
          </div>
        )}
        {angle.desired_emotion && (
          <div>
            <dt className="eyebrow">Desired emotion</dt>
            <dd className="text-foreground/90">{angle.desired_emotion}</dd>
          </div>
        )}
      </dl>

      {list(angle.claims_to_respect).length > 0 && (
        <div className="mt-3 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-3">
          <span className="eyebrow block">Respect these claims</span>
          <ul className="mt-1.5 space-y-1 text-sm text-foreground/90">
            {list(angle.claims_to_respect).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Join a list the way a sentence does: "a", "a and b", "a, b and c".
 *
 * Written out rather than assembled with inline conditionals because the
 * punctuation has to stay correct at every count — including none. Spreading
 * ternaries through JSX produced "removes the profile and everything built on
 * it: every uploaded photo", which reads as though photos were the only thing
 * lost.
 */
function formatList(items) {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/**
 * Everything a delete of this profile takes with it, named from the data the
 * page has already loaded rather than described in the abstract.
 *
 * The counts are the point. "Deletes your profile and its data" gives a founder
 * no way to tell a profile they forgot about from one that made six videos, and
 * the videos are the part they cannot get back.
 */
function destroyedBy(drafts, angles, whatWorks) {
  const items = [];
  const videos = drafts.length;
  if (videos > 0) {
    items.push(`${videos} video draft${videos === 1 ? "" : "s"}`);
  }
  if (angles.length > 0) {
    items.push(`${angles.length} content angle${angles.length === 1 ? "" : "s"}`);
  }
  const recorded = whatWorks?.videos || 0;
  if (recorded > 0) {
    items.push(
      `history from ${recorded} recorded video${recorded === 1 ? "" : "s"}`
    );
  }
  items.push("every uploaded photo");
  return items;
}

export default function AppProfileDetail() {
  const { profileId } = useParams();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [angles, setAngles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [regeneratingEverything, setRegeneratingEverything] = useState(false);
  // Angles only, no re-research: offered while there are none, where the
  // heavier "Refresh research & angles" would be the only route otherwise.
  const [generatingAngles, setGeneratingAngles] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [whatWorks, setWhatWorks] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [typedName, setTypedName] = useState("");
  const [deleteError, setDeleteError] = useState(null);
  const [deletingProfile, setDeletingProfile] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, a, d, w] = await Promise.all([
        api.getAppProfile(profileId),
        api.getContentAngles(profileId).catch(() => ({ angles: [] })),
        // A profile is reusable for as many videos as you want, so the page
        // shows the drafts already built on it. Scoped by brand_profile_id, and
        // the backend filters on the caller's user_id too.
        api.getStudioProjects({ brand_profile_id: profileId }).catch(() => ({ projects: [] })),
        // Aggregate only, and manual entries only. A missing signal is the
        // expected case for a new profile, so it is not an error.
        api.getProfileWhatWorks(profileId).catch(() => null),
      ]);
      setProfile(p);
      setAngles(a.angles || []);
      setDrafts(d.projects || []);
      setWhatWorks(w);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const handleRegenerateEverything = async () => {
    setRegeneratingEverything(true);
    setError(null);
    try {
      const updated = await api.regenerateEverything(profileId);
      setProfile(updated);
      // Reload angles after regeneration
      const a = await api.getContentAngles(profileId).catch(() => ({ angles: [] }));
      setAngles(a.angles || []);
      const src = Array.isArray(updated?.research_sources) ? updated.research_sources : [];
      const readSrc = src.filter((s) => s && s.ok).length;
      setNotice(
        src.length > 0
          ? `Refreshed research (${readSrc} of ${src.length} sources read), approval, and audience angles.`
          : "Refreshed research, approval, and audience angles."
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRegeneratingEverything(false);
    }
  };

  const handleGenerateAngles = async () => {
    setGeneratingAngles(true);
    setError(null);
    try {
      const data = await api.generateContentAngles(profileId);
      setAngles(data.angles || []);
      setNotice(`Generated ${data.angles?.length || 0} audience angles.`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setGeneratingAngles(false);
    }
  };

  const handleDeleteAngle = async (angleId) => {
    setDeleting(true);
    try {
      await api.deleteContentAngle(profileId, angleId);
      setAngles((prev) => prev.filter((a) => a.id !== angleId));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  // What the founder has to type to arm the delete. Falls back to the same
  // "Untitled app" the header shows, because brand_name is optional on a
  // researched draft — and without the fallback an unnamed profile would match
  // an empty string, leaving the confirm button permanently enabled.
  const deletableName = profile?.brand_name?.trim() || "Untitled app";
  const canDelete = typedName.trim() === deletableName && !deletingProfile;

  const openConfirm = () => {
    setTypedName("");
    setDeleteError(null);
    setConfirmOpen(true);
  };

  const handleDeleteProfile = async () => {
    if (!canDelete) return;
    setDeletingProfile(true);
    setDeleteError(null);
    try {
      const res = await api.deleteAppProfile(profileId);
      // There is no profile list page any more, so the App Profile list is the only
      // landing. The toast is mounted globally, so it survives the navigation.
      const removed = res?.generations_removed || 0;
      toast.success(
        removed
          ? `Deleted ${deletableName} and ${removed} video${removed === 1 ? "" : "s"}`
          : `Deleted ${deletableName}`
      );
      navigate("/brand");
    } catch (err) {
      // Deliberately not the page-level setError: that renders at the top of
      // the page, behind this dialog, so a 409 would look like the button
      // simply stopped working.
      setDeleteError(getErrorMessage(err));
      setDeletingProfile(false);
    }
  };

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading profile...
      </p>
    );
  }

  if (error && !profile) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Could not load this profile</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const approved = profile?.status === "approved";

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        {/* Was "All profiles" -> /app-profiles. There is no list page any
            more, and the editor is where an app is created, approved and
            switched between, so that is the honest way back. */}
        <Link to="/brand">
          <ArrowLeft className="h-3.5 w-3.5" /> App Profile
        </Link>
      </Button>

      <div data-testid="app-profile-header">
      <PageHeader
        icon={Briefcase}
        title={profile?.brand_name || "Untitled app"}
        description={profile?.brand_description || undefined}
        actions={
          <div className="flex items-center gap-2">
            {approved ? (
              <Badge variant="indigo" className="px-3 py-1">Approved</Badge>
            ) : (
              <Badge variant="secondary" className="px-3 py-1">Draft — needs review</Badge>
            )}
            <Button variant="secondary" size="sm" asChild>
              <Link to="/brand">Edit</Link>
            </Button>
            {/* Deletes the profile and everything scoped to it: content angles,
                studio projects, generations, assets and their recorded
                results. The endpoint and the api client both already existed
                and nothing called them; this is the control that reaches them.
                Type-to-confirm rather than window.confirm because the blast
                radius is every finished video, not one regenerable row. */}
            <Button
              variant="ghost"
              size="sm"
              onClick={openConfirm}
              aria-label="Delete app profile"
              title="Delete this app profile and everything built on it"
              data-testid="delete-profile-button"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
            {/* An App Profile is not consumed by making a video: the same
                approved profile backs every video, and the studio reuses its
                angles, assets and templates. This is the way back in, on the
                page where someone is looking at the app itself. */}
            <Button variant="brand" size="sm" asChild>
              <Link
                to={`/create?profile=${encodeURIComponent(profileId)}`}
                onClick={(e) => {
                  if (!approved) {
                    e.preventDefault();
                    setNotice("Approve this profile first — the studio only accepts approved apps.");
                  }
                }}
              >
                <Sparkles className="h-3.5 w-3.5" />
                Create Video
              </Link>
            </Button>
            {approved && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleRegenerateEverything}
                disabled={regeneratingEverything}
                title="Re-research this app, apply the refreshed profile, and regenerate its audience angles"
              >
                {regeneratingEverything ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                Refresh research &amp; angles
              </Button>
            )}
          </div>
        }
      />
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert>
          <Lightbulb className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {!approved && (
        <Alert>
          <ShieldAlert className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>Review and approve before generating</AlertTitle>
          <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <span className="text-muted-foreground">
              Content angles and template recommendations need an approved, verified profile.
            </span>
            <Button variant="secondary" size="sm" className="shrink-0" asChild>
              <Link to="/brand">Open profile editor</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="surface space-y-4 rounded-2xl" data-testid="profile-facts">
            <span className="eyebrow block">Product facts</span>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Category" value={profile?.app_category || profile?.niche} />
              <Field label="Platforms" value={list(profile?.platforms).join(", ")} />
              <Field label="Tone / voice" value={profile?.tone_voice} />
            </div>
            <ListBlock label="Core features" items={list(profile?.core_features)} />
            <ListBlock label="Primary use cases" items={list(profile?.primary_use_cases)} />
            <ListBlock label="Problems solved" items={list(profile?.problems_solved)} />
            <ListBlock label="Desired outcomes" items={list(profile?.desired_outcomes)} />
            {Array.isArray(profile?.outcome_statements) && profile.outcome_statements.length > 0 && (
              <div className="space-y-2">
                <span className="eyebrow block">Feature-to-outcome statements</span>
                {profile.outcome_statements.map((s, i) => (
                  <div
                    key={`${s.outcome}-${i}`}
                    className="rounded-xl border border-[color:var(--hairline)] p-3 text-sm"
                  >
                    <p className="font-medium">{s.outcome}</p>
                    {s.who_feels_it && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Who feels it: {s.who_feels_it}
                      </p>
                    )}
                    {s.from_feature && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        From: {s.from_feature}
                      </p>
                    )}
                    {s.how_it_helps && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        How it helps: {s.how_it_helps}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
            <ListBlock label="Competitor apps" items={list(profile?.competitors)} />
            <Field label="Differentiators" value={profile?.differentiation} />
            <Field label="Known limitations" value={profile?.known_limitations} />
            {/* Labelled as enforced because it is: this list is attached to
                every video prompt, so it is an instruction to the model rather
                than context it may use or ignore. The wording matters — the old
                label promised the same enforcement over a field that had none. */}
            <ListBlock
              label="Never show in the video (enforced)"
              items={list(profile?.must_not_show)}
            />
            <ListBlock label="When the app is reached for" items={list(profile?.usage_moments)} />
            <Field label="The proof moment" value={profile?.proof_moment} />
            {Array.isArray(profile?.viewer_objections) && profile.viewer_objections.length > 0 && (
              <div className="space-y-2">
                <span className="eyebrow block">Why they would not download</span>
                {profile.viewer_objections.map((o, i) => (
                  <div
                    key={`${o.objection}-${i}`}
                    className="rounded-xl border border-[color:var(--hairline)] p-3 text-sm"
                  >
                    <p className="font-medium">{o.objection}</p>
                    {o.what_they_do_now && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Does now: {o.what_they_do_now}
                      </p>
                    )}
                    {o.honest_answer && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Answer: {o.honest_answer}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* The only part of the profile that improves with use. Everything
              above was scraped once from the URL; this is the founder's own
              numbers on their own videos, and the next strategy prompt reads
              it. Aggregate per template, so it is evidence of what carried
              views rather than a ranking of hooks. */}
          <div className="surface space-y-3 rounded-2xl" data-testid="what-works">
            <span className="eyebrow flex items-center gap-1.5">
              <Target className="h-3 w-3" /> What has worked here
            </span>
            {!whatWorks || !whatWorks.has_signal ? (
              <p className="text-sm text-muted-foreground">
                Nothing recorded yet. Add view numbers to a finished video and the next strategy
                will know which of this app&apos;s openings actually carried them.
              </p>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">
                  Across {whatWorks.videos} recorded video(s). View counts only — not proof that one
                  template is better.
                </p>
                <dl className="space-y-1.5 text-sm">
                  {(whatWorks.top || []).map((row) => (
                    <div key={row.template_id} className="flex items-baseline justify-between gap-3">
                      <dt className="min-w-0 truncate">{row.template_id}</dt>
                      <dd className="shrink-0 text-muted-foreground">
                        {row.views.toLocaleString()} views · save {Math.round(row.save_rate * 100)}%
                      </dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </div>

          <div className="surface space-y-4 rounded-2xl">
            <span className="eyebrow block">Audiences</span>
            <Field label="Primary audience" value={profile?.target_audience} />
            <Field label="Ideal customer" value={profile?.ideal_customer_profile} />
            <ListBlock label="Segments" items={list(profile?.icp_segments)} />
          </div>

          <ClaimPanel profile={profile || {}} />
        </div>

        <div className="space-y-4">
          <div className="surface space-y-3 rounded-2xl" data-testid="app-profile-videos">
            <div className="flex items-center justify-between gap-2">
              <span className="eyebrow flex items-center gap-1.5">
                <Video className="h-3 w-3" />
                Videos from this app
              </span>
              <span className="text-xs text-muted-foreground">
                {drafts.length ? `${drafts.length} draft${drafts.length === 1 ? "" : "s"}` : ""}
              </span>
            </div>

            {drafts.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {approved
                  ? "No video drafts yet. Start a new video with this profile, or use it again for another video whenever you like."
                  : "Review and approve this profile before starting a video. You can reuse it for as many videos as you need."}
              </p>
            ) : (
              <div className="space-y-2">
                {drafts.map((d) => (
                  <Link
                    key={d.id}
                    to={`/create?profile=${encodeURIComponent(profileId)}&project=${encodeURIComponent(d.id)}`}
                    className="block rounded-xl border border-[color:var(--hairline)] p-3 transition-colors hover:border-[color:var(--indigo-35)]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">
                        {d.hook_line || d.objective || "Untitled draft"}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {d.script_version > 0
                        ? "Script plan ready — resume in Create Video"
                        : "Setup started — choose a goal, template, and presenter photo"}
                    </p>
                  </Link>
                ))}
                <p className="pt-1 text-xs text-muted-foreground">
                  Each draft is separate. Start another video without changing this profile or its other drafts.
                </p>
              </div>
            )}
          </div>

          <div className="surface space-y-3 rounded-2xl" data-testid="app-profile-angles">
            <span className="eyebrow flex items-center gap-1.5">
              <Target className="h-3 w-3" />
              Audience angles
            </span>
            <p className="text-xs text-muted-foreground">Optional audience-and-problem starting points. Choose one in Create Video to focus template suggestions, or skip it for a broader match.</p>

            {angles.length === 0 ? (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {approved
                    ? "No audience angles yet. Generate them from this approved profile, or use Refresh research & angles above for a full re-research."
                    : "Approve this profile to create suggested audience angles for the video workflow."}
                </p>
                {approved && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="gap-1.5"
                    onClick={handleGenerateAngles}
                    disabled={generatingAngles}
                    data-testid="generate-angles-button"
                  >
                    {generatingAngles ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5" />
                    )}
                    {generatingAngles ? "Generating…" : "Generate audience angles"}
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {angles.map((a) => (
                  <AngleCard
                    key={a.id}
                    angle={a}
                    onDelete={handleDeleteAngle}
                    busy={deleting}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <Dialog
        open={confirmOpen}
        onOpenChange={(open) => {
          setConfirmOpen(open);
          if (!open) {
            setTypedName("");
            setDeleteError(null);
          }
        }}
      >
        <DialogContent data-testid="delete-profile-dialog">
          <DialogHeader>
            <DialogTitle>Delete {deletableName}?</DialogTitle>
            <DialogDescription>
              This cannot be undone. It removes {deletableName} and
              everything built on it:{" "}
              {formatList(destroyedBy(drafts, angles, whatWorks))}. Your
              provider call log is kept.
            </DialogDescription>
          </DialogHeader>

          <label className="block text-sm font-medium" htmlFor="delete-confirm-name">
            Type <span className="font-semibold">{deletableName}</span> to confirm
          </label>
          <Input
            id="delete-confirm-name"
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            placeholder={deletableName}
            autoComplete="off"
            data-testid="delete-confirm-input"
          />

          {deleteError && (
            <Alert variant="destructive" data-testid="delete-profile-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{deleteError}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setConfirmOpen(false)}
              disabled={deletingProfile}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteProfile}
              disabled={!canDelete}
              data-testid="delete-profile-confirm"
            >
              {deletingProfile && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Delete permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
