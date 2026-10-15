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
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "../components/ui/dropdown-menu";
import { Input } from "../components/ui/input";
import { Skeleton } from "../components/ui/skeleton";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import { sentenceCase } from "../lib/copyCase";
import { ProfileCard, ProfileField, InfoChipList, InfoListBlock, CardGrid, StatementCard, SectionGroup } from "../components/profileUi";
import { api, getErrorMessage } from "../lib/api";
import { rememberCurrentAppId } from "../lib/currentApp";
import {
  Briefcase, Loader2, AlertTriangle, ArrowLeft,
  Lightbulb, Trash2, RefreshCw, ClipboardCheck,
  Layers, Target, Megaphone, MessagesSquare, Users,
  Info, Sparkles, Compass, Ban, CircleAlert, Trophy,
  BadgeCheck, Star, ListChecks, Clock, ShieldCheck, MessageCircleQuestion,
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

/* Shared card language: one background, 1px hairline, radius 16, px-4 py-3
   padding and 8px gaps — the Content Angles rows' tokens, so this page reads
   like the angle list on Create Video. Research phrases render as
   wrapping chips so lists use their horizontal room instead of stretching
   one phrase per row down a tall strip of empty space. */

function ClaimPanel({ profile }) {
  const approved = list(profile.claims_approved);
  const review = list(profile.claims_review);
  const banned = list(profile.claims_banned);
  if (!approved.length && !review.length && !banned.length) return null;
  return (
    <ProfileCard testid="claim-guardrails" eyebrow="Claim guardrails" icon={ShieldCheck}>
      {/* The "Needs review · N" badge that sat here was the same tier the list
          below already names, said again one line above it — and this group's
          bar counts what is to review as well. It also read "Needs review · 0"
          on a profile with nothing to check. The tiers are the headings. */}
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
function destroyedBy(drafts, angles) {
  const items = [];
  const videos = drafts.length;
  if (videos > 0) {
    items.push(`${videos} video draft${videos === 1 ? "" : "s"}`);
  }
  if (angles.length > 0) {
    items.push(`${angles.length} content angle${angles.length === 1 ? "" : "s"}`);
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
  // Re-research into a pending proposal (approval owed) and research-into-
  // a-new-draft: the BrandSetup sticky bar and research form own these for
  // the editor, and this page mirrors them next to the delete control so a
  // founder reading the approved profile never has to leave it to act.
  const [refreshing, setRefreshing] = useState(false);
  const [approving, setApproving] = useState(false);
  const [researchingNew, setResearchingNew] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [drafts, setDrafts] = useState([]);
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
      const [p, a, d] = await Promise.all([
        api.getAppProfile(profileId),
        api.getContentAngles(profileId).catch(() => ({ angles: [] })),
        // A profile is reusable for as many videos as you want, so the page
        // shows the drafts already built on it. Scoped by brand_profile_id, and
        // the backend filters on the caller's user_id too.
        api.getStudioProjects({ brand_profile_id: profileId }).catch(() => ({ projects: [] })),
      ]);
      setProfile(p);
      setAngles(a.angles || []);
      setDrafts(d.projects || []);
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
    // Liveness the founder keeps while scrolled away: the button spinner only
    // reads where it is. Dismissed on settle — the notice below carries the
    // result, so this toast must never outlive the call.
    const toastId = toast.loading("Refreshing research and angles…");
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
      toast.dismiss(toastId);
      setRegeneratingEverything(false);
    }
  };

  // Refresh from sources: re-read the store listings into a pending
  // proposal. The approved profile is unchanged until the proposal is
  // approved — the opposite of Refresh research & angles above, which
  // applies immediately. Only for researched profiles: a hand-typed one
  // has no sources to re-read, and a draft has no approval to owe.
  const handleRefreshFromSources = async () => {
    setRefreshing(true);
    setError(null);
    const toastId = toast.loading("Re-reading the store listings…");
    try {
      const saved = await api.refreshAppProfile(profileId);
      setProfile(saved);
      setNotice("Re-research complete — review the proposal below, then approve to apply it.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      toast.dismiss(toastId);
      setRefreshing(false);
    }
  };

  // Approve the pending proposal in place: the proposal belongs to this
  // approved page, so the founder reviews it where the diff will land
  // rather than being sent to the editor for one click.
  const handleApprovePending = async () => {
    setApproving(true);
    setError(null);
    try {
      const saved = await api.approveAppProfile(profileId, true);
      setProfile(saved);
      const a = await api.getContentAngles(profileId).catch(() => ({ angles: [] }));
      setAngles(a.angles || []);
      setNotice("Proposal applied — profile and angles are current.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setApproving(false);
    }
  };

  // Research into a new draft: re-run research for this app's store URLs
  // as a separate draft profile. The current profile is untouched, and the
  // editor opens on the new draft (it is the most recently created row, so
  // getActiveBrand returns it). Needs a store listing on file — research
  // with no URL is the toast BrandSetup shows, so the button stays disabled
  // with that reason instead.
  const handleResearchNewDraft = async () => {
    const appstoreUrl = (profile?.appstore_url || "").trim();
    const playUrl = (profile?.play_url || "").trim();
    if (!appstoreUrl && !playUrl) return;
    setResearchingNew(true);
    setError(null);
    const toastId = toast.loading("Researching a new draft…");
    try {
      const created = await api.researchAppProfile({
        ...(appstoreUrl ? { appstore_url: appstoreUrl } : {}),
        ...(playUrl ? { play_url: playUrl } : {}),
      });
      if (created?.id) rememberCurrentAppId(created.id);
      toast.success("New research draft ready — review it, then approve it.", { id: toastId });
      navigate("/brand");
    } catch (err) {
      toast.error(getErrorMessage(err), { id: toastId });
      setError(getErrorMessage(err));
    } finally {
      setResearchingNew(false);
    }
  };

  // What the founder has to type to arm the delete. Falls back to "Untitled
  // app" because brand_name is optional on a researched draft — and without
  // the fallback an unnamed profile would match an empty string, leaving the
  // confirm button permanently enabled. The app name is deliberately absent
  // from the page masthead; this is the one place it still has to appear, since
  // the founder types it to confirm they are deleting that app and not another.
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
    // Same frame as the loaded page and Create Video's own loading state:
    // skeleton blocks shaped like the header and the group cards, so nothing
    // reflows when the profile arrives. Never a bare spinner line.
    return (
      <PageFrame className="space-y-6">
        <div className="flex items-start gap-3" aria-label="Loading profile" data-testid="profile-loading">
          <Skeleton className="h-10 w-10 shrink-0 rounded-xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-3 w-full" />
          </div>
        </div>
        <div className="space-y-4">
          <Skeleton className="h-14 w-full rounded-2xl" />
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-40 w-full rounded-2xl" />
        </div>
      </PageFrame>
    );
  }

  if (error && !profile) {
    return (
      <PageFrame className="space-y-6">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load this profile</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </PageFrame>
    );
  }

  const approved = profile?.status === "approved";
  // Researched means re-researchable: last_research_at is written only by
  // the research INSERT and the refresh UPDATE, never by analyze-url or a
  // hand-typed create.
  const researched = Boolean(profile?.last_research_at);
  const hasStoreUrl = Boolean(
    (profile?.appstore_url || "").trim() || (profile?.play_url || "").trim()
  );
  const pendingProposal = profile?.pending_research;

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
    <PageFrame className="space-y-6">
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
        /* The section, not the app. Every other masthead in the app names its
           page — Asset Library, Demo + CTA, Generation History — and the app
           name was the one place a page title carried the user's data instead.
           It also read twice on screen: the back link above already says
           "App Profile". The name still appears where it is actionable, in
           the delete confirmation the founder has to type it. */
        title="App Profile"
        description={profile?.brand_description ? sentenceCase(profile.brand_description) : undefined}
        actions={
          <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-3">
            {/* Brand hierarchy: status badge, primary edit, research dropdown, delete */}
            {approved ? (
              <Badge className="border-green-500/25 bg-green-500/10 px-3 py-1 font-semibold text-green-300 transition-none">Approved</Badge>
            ) : (
              <Badge variant="secondary" className="px-3 py-1 transition-none">Draft — needs review</Badge>
            )}
            <Button variant="secondary" size="sm" asChild>
              <Link to="/brand">Edit</Link>
            </Button>
            {approved && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={regeneratingEverything || refreshing || researchingNew}
                    className="gap-1.5"
                    data-testid="research-menu-button"
                  >
                    {regeneratingEverything || refreshing || researchingNew ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5" />
                    )}
                    Research
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-[220px]">
                  <DropdownMenuLabel className="text-xs">Research actions</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={handleRegenerateEverything}
                    disabled={regeneratingEverything || refreshing || researchingNew}
                    className="text-sm"
                  >
                    {regeneratingEverything ? (
                      <> <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> Refreshing… </> 
                    ) : (
                      <> <RefreshCw className="h-3.5 w-3.5 mr-2" /> Refresh research & angles </>
                    )}
                    <span className="ml-auto text-xs text-muted-foreground">Applies immediately</span>
                  </DropdownMenuItem>
                  {researched && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={handleRefreshFromSources}
                        disabled={refreshing || regeneratingEverything || researchingNew}
                        className="text-sm"
                        data-testid="refresh-sources-button"
                      >
                        {refreshing ? (
                          <> <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> Re-researching… </>
                        ) : (
                          <> <RefreshCw className="h-3.5 w-3.5 mr-2" /> Refresh from sources </>
                        )}
                        <span className="ml-auto text-xs text-muted-foreground">Needs re-approval</span>
                      </DropdownMenuItem>
                    </>
                  )}
                  {hasStoreUrl && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={handleResearchNewDraft}
                        disabled={researchingNew || regeneratingEverything || refreshing}
                        className="text-sm"
                        data-testid="research-new-draft-button"
                      >
                        {researchingNew ? (
                          <> <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> Researching… </>
                        ) : (
                          <> <Sparkles className="h-3.5 w-3.5 mr-2" /> Research into new draft </>
                        )}
                        <span className="ml-auto text-xs text-muted-foreground">Creates separate draft</span>
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {/* Deletes the profile and everything scoped to it: content angles,
                studio projects, generations, assets and their recorded
                results. Type-to-confirm because the blast radius is every
                finished video, not one regenerable row. */}
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
      {/* A refreshed proposal waits: the approved profile is unchanged
          until the founder applies it. Same contract as the editor's
          pending-refresh alert, reviewed here where the diff will land. */}
      {pendingProposal && (
        <Alert data-testid="pending-proposal-alert">
          <RefreshCw className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>A refreshed proposal is waiting</AlertTitle>
          <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <span className="text-muted-foreground">
              Re-research found updates. Your approved profile is unchanged — approving applies the proposal.
            </span>
            <Button
              variant="secondary"
              size="sm"
              className="shrink-0"
              onClick={handleApprovePending}
              disabled={approving}
              data-testid="approve-pending-button"
            >
              {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BadgeCheck className="h-3.5 w-3.5" />}
              {approving ? "Approving..." : "Review & approve"}
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {!approved && (
        <Alert>
          <ClipboardCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>Review &amp; approve before generating</AlertTitle>
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
      <div className="min-w-0 space-y-4">
        {hasEssentials && (
        <SectionGroup id="essentials" label="Essentials" icon={Layers} summary={essentialsSummary} open={openGroup === "essentials"} onToggle={toggleGroup}>
        {basics.some(Boolean) ? (
          <ProfileCard testid="profile-facts" eyebrow="Product facts" icon={Info}>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_2fr]">
              <ProfileField label="Category" value={basics[0]} />
              <ProfileField label="Platforms" value={basics[1]} />
              <ProfileField label="Tone / voice" value={basics[2]} />
            </div>
          </ProfileCard>
        ) : null}
        {/* The card's heading is the title. Passing the same string again as
            the list's own label printed it twice, one line apart — the label
            is omitted wherever the heading already says it, and kept only
            where the two genuinely differ (Never show, Product facts). */}
        {coreFeatures.length > 0 || useCases.length > 0 ? (
          <CardGrid className="md:grid-cols-2">
            {coreFeatures.length > 0 ? (
              <ProfileCard eyebrow="Core features" icon={Sparkles}>
                <InfoChipList items={coreFeatures} />
              </ProfileCard>
            ) : null}
            {useCases.length > 0 ? (
              <ProfileCard eyebrow="Primary use cases" icon={Compass}>
                <InfoChipList items={useCases} />
              </ProfileCard>
            ) : null}
          </CardGrid>
        ) : null}
        {/* Labelled as enforced because it is: this list is attached to
            every video prompt, so it is an instruction to the model rather
            than context it may use or ignore. The wording matters — the old
            label promised the same enforcement over a field that had none. */}
        {mustNotShow.length > 0 ? (
          <ProfileCard eyebrow="Never show in the video (enforced)" icon={Ban} tone="enforced">
            <InfoChipList
              items={mustNotShow}
              tone="enforced"
            />
          </ProfileCard>
        ) : null}
        </SectionGroup>
        )}
        {hasProblems && (
        <SectionGroup id="problems" label="Problems & outcomes" icon={Target} summary={problemsSummary} open={openGroup === "problems"} onToggle={toggleGroup}>
          <CardGrid className="md:grid-cols-2">
            {problems.length > 0 ? (
              <ProfileCard eyebrow="Problems solved" icon={CircleAlert}>
                <InfoChipList items={problems} />
              </ProfileCard>
            ) : null}
            {outcomes.length > 0 ? (
              <ProfileCard eyebrow="Desired outcomes" icon={Trophy}>
                <InfoChipList items={outcomes} />
              </ProfileCard>
            ) : null}
          </CardGrid>
        </SectionGroup>
        )}
        {hasMessaging && (
        <SectionGroup id="messaging" label="Messaging" icon={Megaphone} summary={messagingSummary} open={openGroup === "messaging"} onToggle={toggleGroup}>
        {profile?.differentiation || profile?.known_limitations || profile?.proof_moment ? (
          <div className="grid grid-cols-1 items-stretch gap-2 md:grid-cols-2">
            {profile?.differentiation ? (
              <div className="h-full md:row-span-2">
                <ProfileCard eyebrow="Differentiators" icon={BadgeCheck}>
                  <ProfileField value={profile.differentiation} />
                </ProfileCard>
              </div>
            ) : null}
            {profile?.known_limitations || profile?.proof_moment ? (
              <div className="flex h-full min-w-0 flex-col gap-2">
                {profile?.known_limitations ? (
                    <ProfileCard eyebrow="Known limitations" icon={AlertTriangle}>
                    <ProfileField value={profile.known_limitations} />
                  </ProfileCard>
                ) : null}
                {profile?.proof_moment ? (
                    <ProfileCard eyebrow="The proof moment" icon={Star}>
                    <ProfileField value={profile.proof_moment} />
                  </ProfileCard>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
          {Array.isArray(profile?.outcome_statements) && profile.outcome_statements.length > 0 && (
            <ProfileCard eyebrow="Feature-to-outcome statements" icon={ListChecks}>
              <div className="grid grid-cols-1 items-stretch gap-2 md:grid-cols-2">
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
        <SectionGroup id="context" label="Context & objections" icon={MessagesSquare} summary={contextSummary} open={openGroup === "context"} onToggle={toggleGroup}>
        {usageMoments.length > 0 ? (
          <ProfileCard eyebrow="When the app is reached for" icon={Clock}>
            <InfoChipList items={usageMoments} />
          </ProfileCard>
        ) : null}
          {Array.isArray(profile?.viewer_objections) && profile.viewer_objections.length > 0 && (
            <ProfileCard eyebrow="Why they would not download" icon={MessageCircleQuestion}>
              <div className="grid grid-cols-1 items-stretch gap-2 md:grid-cols-2">
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
        {/* The delete dialog counts drafts, angles and photos from the data
            above; recorded-results history lived here once and is gone with
            the manual-results loop. */}
        {hasAudience && (
        <SectionGroup id="audience" label="Audience & guardrails" icon={Users} summary={audienceSummary} open={openGroup === "audience"} onToggle={toggleGroup}>
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
              {formatList(destroyedBy(drafts, angles))}. Your
              provider call log is kept.
            </DialogDescription>
          </DialogHeader>

          <label className="block text-sm font-semibold" htmlFor="delete-confirm-name">
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
