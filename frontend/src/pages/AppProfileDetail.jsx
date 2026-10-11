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
import PageFrame from "../components/PageFrame";
import { sentenceCase } from "../lib/copyCase";
import { ProfileCard, ProfileField, InfoChipList, InfoListBlock, CardGrid, StatementCard, SectionGroup } from "../components/profileUi";
import { api, getErrorMessage } from "../lib/api";
import {
  Briefcase, Loader2, AlertTriangle, ArrowLeft,
  ShieldAlert, Lightbulb, Trash2, RefreshCw, ClipboardCheck, Info, Package, Layers,
  ListChecks, Ban, CircleCheck, Flag, Zap, Eye, GitBranch,
  Clock, ThumbsDown,
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

/* Shared card language (Step 1): one background, 1px hairline, radius 16,
   padding 20, 16px card gaps, 12px item gaps. Research phrases render as
   wrapping chips so lists use their horizontal room instead of stretching
   one phrase per row down a tall strip of empty space. */

function ClaimPanel({ profile }) {
  const approved = list(profile.claims_approved);
  const review = list(profile.claims_review);
  const banned = list(profile.claims_banned);
  if (!approved.length && !review.length && !banned.length) return null;
  return (
    <ProfileCard testid="claim-guardrails" eyebrow="Claim guardrails" icon={ShieldAlert}>
      <div>
        <Badge variant="indigo" className="px-3 py-1 font-medium">
          Needs review · {review.length}
        </Badge>
      </div>
      <p className="text-xs leading-[18px] text-muted-foreground">The plan checks these phrases before rendering. Review each claim for accuracy before publishing; an automated check is not a guarantee.</p>
      <InfoListBlock label="Approved — safe to use" items={approved} tone="approved" />
      <InfoListBlock label="Needs review — verify first" items={review} tone="review" />
      <InfoListBlock label="Never use" items={banned} tone="banned" />
    </ProfileCard>
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

/* Every collapsible bar on this page. The accordion keeps at most one of
   these open; persisted state stores the open id (or null). */
const GROUP_IDS = ["essentials", "problems", "messaging", "context", "audience"];

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
  // Accordion-exclusive groups (per group, never per card, so row heights
  // stay equal): at most one bar open, Essentials open by default. The open
  // bar's id (or null) persists per profile so a reading position survives
  // reloads. A legacy object-shaped value degrades to its first open bar.
  const [openGroup, setOpenGroup] = useState("essentials");
  useEffect(() => {
    try {
      const raw = localStorage.getItem(`profile-groups:${profileId}`);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed === "string") {
        if (GROUP_IDS.includes(parsed)) setOpenGroup(parsed);
      } else if (parsed && typeof parsed === "object") {
        setOpenGroup(GROUP_IDS.find((id) => parsed[id]) || null);
      }
    } catch {
      // A stale or foreign value leaves everything collapsed.
    }
  }, [profileId]);
  const toggleGroup = useCallback((id, open) => {
    const next = open ? id : null;
    setOpenGroup(next);
    try {
      localStorage.setItem(`profile-groups:${profileId}`, JSON.stringify(next));
    } catch {
      // Private-mode writes fail silently; the toggle still works in memory.
    }
  }, [profileId]);

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
  // no hollow bordered card behind: InfoChipList and ProfileField render null
  // when they have nothing to show, and a ProfileCard around nothing would be
  // a box with a title and no body.
  const basics = [profile?.app_category || profile?.niche, list(profile?.platforms).join(", "), profile?.tone_voice];
  const coreFeatures = list(profile?.core_features);
  const useCases = list(profile?.primary_use_cases);
  const problems = list(profile?.problems_solved);
  const outcomes = list(profile?.desired_outcomes);
  const mustNotShow = list(profile?.must_not_show);
  const usageMoments = list(profile?.usage_moments);
  const outcomeCount = Array.isArray(profile?.outcome_statements) ? profile.outcome_statements.length : 0;
  const objectionCount = Array.isArray(profile?.viewer_objections) ? profile.viewer_objections.length : 0;
  const claimApproved = list(profile?.claims_approved);
  const claimReview = list(profile?.claims_review);
  const claimBanned = list(profile?.claims_banned);
  // The group holds Claim Guardrails only now, so it renders when there is
  // at least one claim to show.
  const hasAudience = claimApproved.length + claimReview.length + claimBanned.length > 0;

  // Group visibility mirrors the cards: an empty group leaves no header
  // behind. Summaries are computed from the data, never hand-written.
  const hasEssentials = basics.some(Boolean) || coreFeatures.length > 0 || useCases.length > 0 || mustNotShow.length > 0;
  const hasProblems = problems.length > 0 || outcomes.length > 0;
  const hasMessaging = Boolean(profile?.differentiation || profile?.known_limitations || profile?.proof_moment) || outcomeCount > 0;
  const hasContext = usageMoments.length > 0 || objectionCount > 0;
  const joinSummary = (parts) => parts.filter(Boolean).join(" · ");
  const essentialsSummary = joinSummary([
    coreFeatures.length > 0 && `${coreFeatures.length} feature${coreFeatures.length === 1 ? "" : "s"}`,
    useCases.length > 0 && `${useCases.length} use case${useCases.length === 1 ? "" : "s"}`,
    mustNotShow.length > 0 && `${mustNotShow.length} never-show`,
  ]);
  const problemsSummary = joinSummary([
    problems.length > 0 && `${problems.length} problem${problems.length === 1 ? "" : "s"}`,
    outcomes.length > 0 && `${outcomes.length} outcome${outcomes.length === 1 ? "" : "s"}`,
  ]);
  const messagingSummary = joinSummary([
    profile?.differentiation && "differentiators",
    outcomeCount > 0 && `${outcomeCount} statement${outcomeCount === 1 ? "" : "s"}`,
  ]);
  const contextSummary = joinSummary([
    usageMoments.length > 0 && `${usageMoments.length} moment${usageMoments.length === 1 ? "" : "s"}`,
    objectionCount > 0 && `${objectionCount} objection${objectionCount === 1 ? "" : "s"}`,
  ]);
  const audienceSummary = joinSummary([
    claimApproved.length > 0 && `${claimApproved.length} approved`,
    claimReview.length > 0 && `${claimReview.length} to review`,
  ]);

return (
    <PageFrame width="narrow" className="space-y-6">
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
          <div className="flex flex-wrap items-center justify-end gap-2">
            {/* Brand hierarchy, left to right: semantic status badge, secondary
                edits, destructive icon. Wraps under the title on narrow screens
                instead of squeezing. Create Video starts from the sidebar —
                this header only manages the profile. */}
            {approved ? (
              <Badge className="border-green-500/25 bg-green-500/10 px-3 py-1 font-medium text-green-300 transition-none">Approved</Badge>
            ) : (
              <Badge variant="secondary" className="px-3 py-1 transition-none">Draft — needs review</Badge>
            )}
            <Button variant="secondary" size="sm" asChild>
              <Link to="/brand">Edit</Link>
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
                Refresh research & angles
              </Button>
            )}
            {/* Deletes the profile and everything scoped to it: content angles,
                studio projects, generations, assets and their recorded
                results. The endpoint and the api client both already existed
                and nothing called them; this is the control that reaches them.
                Type-to-confirm rather than window.confirm because the blast
                radius is every finished video, not one regenerable row. */}
            <Button
              variant="ghost"
              size="icon"
              onClick={openConfirm}
              aria-label="Delete app profile"
              title="Delete this app profile and everything built on it"
              data-testid="delete-profile-button"
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
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
          <ClipboardCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" />
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

      {/* Section groups: Essentials, Problems & Outcomes, Messaging,
          Context & Objections, Audience & guardrails. Directly under header,
          no gap above. Accordion-exclusive with persisted single-open state;
          Essentials open by default, the rest collapsed; no bulk
          expand/collapse. */}
      <div className="min-w-0 space-y-3">
        {hasEssentials && (
        <SectionGroup id="essentials" label="Essentials" summary={essentialsSummary} open={openGroup === "essentials"} onToggle={toggleGroup}>
        {basics.some(Boolean) ? (
          <ProfileCard testid="profile-facts" eyebrow="Product facts" icon={Package}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_1fr_2fr]">
              <ProfileField label="Category" value={basics[0]} />
              <ProfileField label="Platforms" value={basics[1]} />
              <ProfileField label="Tone / voice" value={basics[2]} />
            </div>
          </ProfileCard>
        ) : null}
        {coreFeatures.length > 0 || useCases.length > 0 ? (
          <CardGrid className="md:grid-cols-2">
            {coreFeatures.length > 0 ? (
              <ProfileCard eyebrow="Core features" icon={Layers}>
                <InfoChipList label="Core features" items={coreFeatures} />
              </ProfileCard>
            ) : null}
            {useCases.length > 0 ? (
              <ProfileCard eyebrow="Primary use cases" icon={ListChecks}>
                <InfoChipList label="Primary use cases" items={useCases} />
              </ProfileCard>
            ) : null}
          </CardGrid>
        ) : null}
        {/* Labelled as enforced because it is: this list is attached to
            every video prompt, so it is an instruction to the model rather
            than context it may use or ignore. The wording matters — the old
            label promised the same enforcement over a field that had none. */}
        {mustNotShow.length > 0 ? (
          <ProfileCard eyebrow="Never show in the video (enforced)" tone="enforced" icon={Ban}>
            <InfoChipList
              items={mustNotShow}
              tone="enforced"
            />
          </ProfileCard>
        ) : null}
        </SectionGroup>
        )}
        {hasProblems && (
        <SectionGroup id="problems" label="Problems & outcomes" summary={problemsSummary} open={openGroup === "problems"} onToggle={toggleGroup}>
          <CardGrid className="md:grid-cols-2">
            {problems.length > 0 ? (
              <ProfileCard eyebrow="Problems solved" icon={CircleCheck}>
                <InfoChipList label="Problems solved" items={problems} />
              </ProfileCard>
            ) : null}
            {outcomes.length > 0 ? (
              <ProfileCard eyebrow="Desired outcomes" icon={Flag}>
                <InfoChipList label="Desired outcomes" items={outcomes} />
              </ProfileCard>
            ) : null}
          </CardGrid>
        </SectionGroup>
        )}
        {hasMessaging && (
        <SectionGroup id="messaging" label="Messaging" summary={messagingSummary} open={openGroup === "messaging"} onToggle={toggleGroup}>
        {profile?.differentiation || profile?.known_limitations || profile?.proof_moment ? (
          <div className="grid grid-cols-1 items-stretch gap-4 md:grid-cols-2">
            {profile?.differentiation ? (
              <div className="h-full md:row-span-2">
                <ProfileCard eyebrow="Differentiators" icon={Zap}>
                  <ProfileField label="Differentiators" value={profile.differentiation} />
                </ProfileCard>
              </div>
            ) : null}
            {profile?.known_limitations || profile?.proof_moment ? (
              <div className="flex h-full min-w-0 flex-col gap-4">
                {profile?.known_limitations ? (
                    <ProfileCard eyebrow="Known limitations" icon={Info}>
                    <ProfileField label="Known limitations" value={profile.known_limitations} />
                  </ProfileCard>
                ) : null}
                {profile?.proof_moment ? (
                    <ProfileCard eyebrow="The proof moment" icon={Eye}>
                    <ProfileField label="The proof moment" value={profile.proof_moment} />
                  </ProfileCard>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
          {Array.isArray(profile?.outcome_statements) && profile.outcome_statements.length > 0 && (
            <ProfileCard eyebrow="Feature-to-outcome statements" icon={GitBranch}>
              <div className="grid grid-cols-1 items-stretch gap-4 md:grid-cols-2">
              {profile.outcome_statements.map((s, i) => (
                <StatementCard
                  key={`${s.outcome}-${i}`}
                  title={s.outcome}
                  spanFull={profile.outcome_statements.length % 2 === 1 && i === profile.outcome_statements.length - 1}
                  rows={[
                    s.who_feels_it && `Who feels it: ${s.who_feels_it}`,
                    s.from_feature && `From: ${s.from_feature}`,
                    s.how_it_helps && `How it helps: ${s.how_it_helps}`,
                  ]}
                />
              ))}
              </div>
            </ProfileCard>
          )}
        </SectionGroup>
        )}
        {hasContext && (
        <SectionGroup id="context" label="Context & objections" summary={contextSummary} open={openGroup === "context"} onToggle={toggleGroup}>
        {usageMoments.length > 0 ? (
          <ProfileCard eyebrow="When the app is reached for" icon={Clock}>
            <InfoChipList label="When the app is reached for" items={usageMoments} />
          </ProfileCard>
        ) : null}
          {Array.isArray(profile?.viewer_objections) && profile.viewer_objections.length > 0 && (
            <ProfileCard eyebrow="Why they would not download" icon={ThumbsDown}>
              <div className="grid grid-cols-1 items-stretch gap-4 md:grid-cols-2">
              {profile.viewer_objections.map((o, i) => (
                <StatementCard
                  key={`${o.objection}-${i}`}
                  title={o.objection}
                  spanFull={profile.viewer_objections.length % 2 === 1 && i === profile.viewer_objections.length - 1}
                  rows={[
                    o.what_they_do_now && `Does now: ${o.what_they_do_now}`,
                    o.honest_answer && `Answer: ${o.honest_answer}`,
                  ]}
                />
              ))}
              </div>
            </ProfileCard>
          )}
        </SectionGroup>
        )}
        {/* What Has Worked Here and the supporting row are gone: recorded
            results belong on Analytics. The whatWorks fetch stays — the
            delete dialog counts recorded videos from it. */}
        {hasAudience && (
        <SectionGroup id="audience" label="Audience & guardrails" summary={audienceSummary} open={openGroup === "audience"} onToggle={toggleGroup}>
          <ClaimPanel profile={profile || {}} />
        </SectionGroup>
        )}
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
    </PageFrame>
  );
}
