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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import { Input } from "../components/ui/input";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import { sentenceCase } from "../lib/copyCase";
import { Briefcase, Loader as Loader2, TriangleAlert as AlertTriangle, ArrowLeft, Sparkles, Target, ShieldAlert, Lightbulb, Trash as Trash2, RefreshCw, MoveHorizontal as MoreHorizontal, Pencil } from "lucide-react";

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
            <span>{sentenceCase(item)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * A list rendered as wrapping chips rather than one long column of bullets.
 *
 * The research fields this page shows are mostly short phrases, and a stacked
 * bullet list gave every one of them a full card width with the text hugging
 * the left edge — the page read as a tall strip of empty space. Chips let a
 * list use the horizontal room it is given: two or three phrases per row, the
 * card shrinking to fit its content instead of stretching to fill the grid.
 */
function ChipList({ label, items, tone = "default" }) {
  if (!items.length) return null;
  const labelClass =
    tone === "enforced"
      ? "text-[color:var(--destructive,oklch(0.65_0.2_25))]"
      : "text-foreground";
  const chipClass =
    tone === "enforced"
      ? "border-red-500/30 bg-red-500/10 text-foreground/90"
      : "border-[color:var(--hairline)] bg-secondary/40 text-foreground/90";
  return (
    <div>
      <span className={`eyebrow block ${labelClass}`}>{label}</span>
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <li
            key={i}
            className={`rounded-full border px-2.5 py-1 text-xs leading-5 ${chipClass}`}
          >
            {sentenceCase(item)}
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
      <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">{sentenceCase(value)}</p>
    </div>
  );
}

/**
 * One bordered information card. Every info block on this page gets its own
 * border and breathing room so the cards read as separate, organized units
 * instead of one long undifferentiated column.
 */
function SectionCard({ testid, eyebrow, children }) {
  return (
    <div className="surface space-y-3 rounded-2xl" {...(testid ? { "data-testid": testid } : {})}>
      {eyebrow && <span className="eyebrow block">{eyebrow}</span>}
      {children}
    </div>
  );
}

function ClaimPanel({ profile }) {
  const approved = list(profile.claims_approved);
  const review = list(profile.claims_review);
  const banned = list(profile.claims_banned);
  if (!approved.length && !review.length && !banned.length) return null;
  return (
    <SectionCard testid="claim-guardrails" eyebrow="Claim guardrails">
      <p className="text-xs text-muted-foreground">The plan checks these phrases before rendering. Review each claim for accuracy before publishing; an automated check is not a guarantee.</p>
      <ListBlock label="Approved — safe to use" items={approved} />
      <ListBlock label="Needs review — verify first" items={review} tone="review" />
      <ListBlock label="Never use" items={banned} tone="banned" />
    </SectionCard>
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
      // Angles are regenerated too but managed in Create Video now, so the
      // notice names where they went rather than a section that is gone.
      setNotice(
        src.length > 0
          ? `Refreshed research (${readSrc} of ${src.length} sources read) and approval. Audience angles were regenerated for use in Create Video.`
          : "Refreshed research and approval. Audience angles were regenerated for use in Create Video."
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRegeneratingEverything(false);
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

  // Section visibility is computed up front so an empty research field leaves
  // no hollow bordered card behind: ChipList and Field render null when they
  // have nothing to show, and a SectionCard around nothing would be a box
  // with a title and no body.
  const basics = [profile?.app_category || profile?.niche, list(profile?.platforms).join(", "), profile?.tone_voice];
  const coreFeatures = list(profile?.core_features);
  const useCases = list(profile?.primary_use_cases);
  const problems = list(profile?.problems_solved);
  const outcomes = list(profile?.desired_outcomes);
  const mustNotShow = list(profile?.must_not_show);
  const usageMoments = list(profile?.usage_moments);
  const competitors = list(profile?.competitors);

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
        description={profile?.brand_description ? sentenceCase(profile.brand_description) : undefined}
        actions={
          <div className="flex items-center gap-2">
            {approved ? (
              <Badge variant="indigo" className="px-3 py-1">Approved</Badge>
            ) : (
              <Badge variant="secondary" className="px-3 py-1">Draft — needs review</Badge>
            )}
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" aria-label="More actions">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <Link to="/brand" className="flex items-center gap-2">
                    <Pencil className="h-3.5 w-3.5" /> Edit profile
                  </Link>
                </DropdownMenuItem>
                {approved && (
                  <DropdownMenuItem
                    onClick={handleRegenerateEverything}
                    disabled={regeneratingEverything}
                    className="flex items-center gap-2"
                  >
                    {regeneratingEverything ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    Refresh research &amp; angles
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem
                  onClick={openConfirm}
                  className="flex items-center gap-2 text-destructive focus:text-destructive"
                  data-testid="delete-profile-button"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete profile
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
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

      {/* Two columns on desktop: the research facts span the wide column and
          the lighter panels (results, audiences, guardrails) take the rail.
          One full-width column was the whole defect this page shipped with —
          every card stretched past any text it held. */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {basics.some(Boolean) ? (
            <SectionCard testid="profile-facts" eyebrow="Product facts">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Field label="Category" value={basics[0]} />
                <Field label="Platforms" value={basics[1]} />
                <Field label="Tone / voice" value={basics[2]} />
              </div>
            </SectionCard>
          ) : null}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {coreFeatures.length > 0 ? (
              <SectionCard>
                <ChipList label="Core features" items={coreFeatures} />
              </SectionCard>
            ) : null}
            {useCases.length > 0 ? (
              <SectionCard>
                <ChipList label="Primary use cases" items={useCases} />
              </SectionCard>
            ) : null}
            {problems.length > 0 ? (
              <SectionCard>
                <ChipList label="Problems solved" items={problems} />
              </SectionCard>
            ) : null}
            {outcomes.length > 0 ? (
              <SectionCard>
                <ChipList label="Desired outcomes" items={outcomes} />
              </SectionCard>
            ) : null}
          </div>
          {profile?.differentiation || profile?.known_limitations || profile?.proof_moment ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {profile?.differentiation ? (
                <SectionCard>
                  <Field label="Differentiators" value={profile.differentiation} />
                </SectionCard>
              ) : null}
              {profile?.known_limitations ? (
                <SectionCard>
                  <Field label="Known limitations" value={profile.known_limitations} />
                </SectionCard>
              ) : null}
              {profile?.proof_moment ? (
                <SectionCard>
                  <Field label="The proof moment" value={profile.proof_moment} />
                </SectionCard>
              ) : null}
            </div>
          ) : null}
          {mustNotShow.length > 0 || usageMoments.length > 0 || competitors.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {/* Labelled as enforced because it is: this list is attached to
                  every video prompt, so it is an instruction to the model rather
                  than context it may use or ignore. The wording matters — the old
                  label promised the same enforcement over a field that had none. */}
              {mustNotShow.length > 0 ? (
                <SectionCard>
                  <ChipList
                    label="Never show in the video (enforced)"
                    items={mustNotShow}
                    tone="enforced"
                  />
                </SectionCard>
              ) : null}
              {usageMoments.length > 0 ? (
                <SectionCard>
                  <ChipList label="When the app is reached for" items={usageMoments} />
                </SectionCard>
              ) : null}
              {competitors.length > 0 ? (
                <SectionCard>
                  <ChipList label="Competitor apps" items={competitors} />
                </SectionCard>
              ) : null}
            </div>
          ) : null}
            {Array.isArray(profile?.outcome_statements) && profile.outcome_statements.length > 0 && (
              <SectionCard eyebrow="Feature-to-outcome statements">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {profile.outcome_statements.map((s, i) => (
                  <div
                    key={`${s.outcome}-${i}`}
                    className="rounded-xl border border-[color:var(--hairline)] p-3 text-sm"
                  >
                    <p className="font-medium">{sentenceCase(s.outcome)}</p>
                    {s.who_feels_it && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Who feels it: {sentenceCase(s.who_feels_it)}
                      </p>
                    )}
                    {s.from_feature && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        From: {sentenceCase(s.from_feature)}
                      </p>
                    )}
                    {s.how_it_helps && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        How it helps: {sentenceCase(s.how_it_helps)}
                      </p>
                    )}
                  </div>
                ))}
                </div>
              </SectionCard>
            )}
            {Array.isArray(profile?.viewer_objections) && profile.viewer_objections.length > 0 && (
              <SectionCard eyebrow="Why they would not download">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {profile.viewer_objections.map((o, i) => (
                  <div
                    key={`${o.objection}-${i}`}
                    className="rounded-xl border border-[color:var(--hairline)] p-3 text-sm"
                  >
                    <p className="font-medium">{sentenceCase(o.objection)}</p>
                    {o.what_they_do_now && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Does now: {sentenceCase(o.what_they_do_now)}
                      </p>
                    )}
                    {o.honest_answer && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Answer: {sentenceCase(o.honest_answer)}
                      </p>
                    )}
                  </div>
                ))}
                </div>
              </SectionCard>
            )}
        </div>

        {/* The rail: lighter panels sharing one column. */}
        <div className="space-y-4">

          <SectionCard testid="content-angles">
            <span className="eyebrow flex items-center gap-1.5">
              <Target className="h-3 w-3" /> Content angles
            </span>
            {angles.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No audience angles yet. Generate them in Create Video or refresh this profile's research.
              </p>
            ) : (
              <div className="space-y-2">
                {angles.map((a) => (
                  <div key={a.id} className="rounded-lg border border-[color:var(--hairline)] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{sentenceCase(a.label)}</span>
                      <Badge variant="secondary" className="text-[11px]">
                        {a.kind ? a.kind.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "Angle"}
                      </Badge>
                    </div>
                    {a.user_problem && (
                      <p className="mt-1 text-xs text-muted-foreground">{sentenceCase(a.user_problem)}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

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
                  Across {whatWorks.videos} recorded videos. View counts are only directional —
                  they do not prove that one template is better.
                </p>
                <dl className="space-y-1.5 text-sm">
                  {(whatWorks.top || []).map((row) => (
                    <div key={row.template_id} className="flex items-baseline justify-between gap-3">
                      <dt className="min-w-0 truncate">{row.template_id}</dt>
                      <dd className="shrink-0 text-muted-foreground">
                        {row.views.toLocaleString()} views · save rate {Math.round(row.save_rate * 100)}%
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
