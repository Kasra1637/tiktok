import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { rememberCurrentAppId } from "../lib/currentApp";
import { cn } from "../lib/utils";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import PageHeader from "../components/PageHeader";
import { SectionCard, GroupLabel } from "../components/SectionCard";
import { SectionGroup } from "../components/profileUi";
import { AppPicker } from "../components/AppPicker";
import { Skeleton } from "../components/ui/skeleton";
import PageFrame, { PAGE_WIDTH_CLASS } from "../components/PageFrame";
import { api, getErrorMessage } from "../lib/api";
import { Sparkles, Briefcase, Loader as Loader2, Save, CircleCheck as CheckCircle2, TriangleAlert as AlertTriangle, ArrowRight, Smartphone, RefreshCw, BadgeCheck, Package, Layers, Compass, Users, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

const EMPTY_FORM = {
  brand_name: "",
  brand_description: "",
  niche: "",
  app_category: "",
  platforms: "",
  core_features: "",
  primary_use_cases: "",
  problems_solved: "",
  must_not_show: "",
  usage_moments: "",
  proof_moment: "",
  viewer_objections: "",
  desired_outcomes: "",
  outcome_statements: "",
  target_audience: "",
  ideal_customer_profile: "",
  icp_segments: "",
  differentiation: "",
  tone_voice: "",
  claims_approved: "",
  claims_review: "",
  claims_banned: "",
};

function productsToText(products) {
  if (Array.isArray(products)) return products.join(", ");
  return products || "";
}

function textToProducts(text) {
  return (text || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * viewer_objections round-trips as three lines per objection.
 *
 * A comma-separated line would break the moment an objection contains one,
 * which is most of them -- "it's just another subscription, I already pay for
 * three". The three-line form also keeps the fields visually distinct, which
 * matters because an objection without a current alternative is not usable.
 */
const OBJECTION_LINES = 3;

function objectionsToText(objections) {
  if (!Array.isArray(objections)) return objections || "";
  return objections
    .map((o) => [o?.objection, o?.what_they_do_now, o?.honest_answer].join("\n"))
    .join("\n\n");
}

function textToObjections(text) {
  const blocks = (text || "").split(/\n\s*\n/);
  const out = [];
  for (const block of blocks) {
    const lines = block.split("\n").map((l) => l.trim());
    // Trailing empties dropped so an objection answered on two lines still
    // saves, rather than requiring the founder to pad a blank third line.
    while (lines.length && !lines[lines.length - 1]) lines.pop();
    if (lines.length < OBJECTION_LINES) continue;
    out.push({
      objection: lines[0],
      what_they_do_now: lines[1],
      honest_answer: lines.slice(2).join(" ").trim(),
    });
  }
  return out;
}

/**
 * outcome_statements round-trips as four lines per statement.
 *
 * Same blank-line-separated block form as objections: the outcome, who feels
 * it, the source feature named verbatim, and how it helps in benefit terms.
 * Four lines are required because an outcome without its source feature is
 * exactly the unlinked benefit phrasing the flat outcomes list already
 * carries — the link is the field.
 */
const OUTCOME_LINES = 4;

function outcomesToText(statements) {
  if (!Array.isArray(statements)) return statements || "";
  return statements
    .map((s) => [s?.outcome, s?.who_feels_it, s?.from_feature, s?.how_it_helps].join("\n"))
    .join("\n\n");
}

function textToOutcomes(text) {
  const blocks = (text || "").split(/\n\s*\n/);
  const out = [];
  for (const block of blocks) {
    const lines = block.split("\n").map((l) => l.trim());
    while (lines.length && !lines[lines.length - 1]) lines.pop();
    if (lines.length < OUTCOME_LINES) continue;
    out.push({
      outcome: lines[0],
      who_feels_it: lines[1],
      from_feature: lines[2],
      how_it_helps: lines.slice(3).join(" ").trim(),
    });
  }
  return out;
}

/** One list item per line — for entries that themselves contain commas. */
function linesToText(items) {
  if (Array.isArray(items)) return items.join("\n");
  return items || "";
}

function textToLines(text) {
  return (text || "")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Read a profile row (lists arrive parsed) into the text-based form state. */
function profileToForm(data) {
  return {
    brand_name: data.brand_name || "",
    brand_description: data.brand_description || "",
    niche: data.niche || "",
    app_category: data.app_category || "",
    platforms: productsToText(data.platforms),
    core_features: productsToText(data.core_features),
    primary_use_cases: productsToText(data.primary_use_cases),
    problems_solved: productsToText(data.problems_solved),
    must_not_show: productsToText(data.must_not_show),
    usage_moments: productsToText(data.usage_moments),
    proof_moment: data.proof_moment || "",
    viewer_objections: objectionsToText(data.viewer_objections),
    desired_outcomes: productsToText(data.desired_outcomes),
    outcome_statements: outcomesToText(data.outcome_statements),
    target_audience: data.target_audience || "",
    ideal_customer_profile: data.ideal_customer_profile || "",
    icp_segments: linesToText(data.icp_segments),
    differentiation: data.differentiation || "",
    tone_voice: data.tone_voice || "",
    claims_approved: productsToText(data.claims_approved),
    claims_review: productsToText(data.claims_review),
    claims_banned: productsToText(data.claims_banned),
  };
}

/* Labelled form field wrapper. The label is the shared GroupLabel eyebrow —
   the same 12/600 uppercase muted label the angles page uses for its own
   fields — so a form row reads like a detail row. Hint stays 12/18 muted. */
function Field({ label, hint, children }) {
  return (
    <div className="space-y-2">
      <GroupLabel as="label">{label}</GroupLabel>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/* Every collapsible bar in the App Profile Details card. Same ids, order and
   single-open behaviour as the App Profile page's SectionGroups, so the two
   pages read as one surface. Summaries are derived from the live form below. */
const GROUP_IDS = ["basics", "does", "direction", "audience", "claims"];

/**
 * Map a save/approve failure to the group holding the offending field, so
 * the error opens its section instead of hiding inside a collapsed one.
 * Returns null when the message names nothing mappable — guessing wrong is
 * worse than leaving the founder's place.
 */
function groupForSaveError(message) {
  const text = (message || "").toLowerCase();
  if (/claim/.test(text)) return "claims";
  if (/audience|segment|differentiation|ideal customer/.test(text)) return "audience";
  if (/featur|outcome|statement|problems solved|use case|\buse it for\b/.test(text)) return "does";
  if (/proof|objection|must not show|usage moment|direction|scene/.test(text)) return "direction";
  if (/name|description|categor|niche|platform|tone/.test(text)) return "basics";
  return null;
}

export default function BrandSetup() {
  const navigate = useNavigate();

  const [appstoreUrl, setAppstoreUrl] = useState("");
  const [playUrl, setPlayUrl] = useState("");
  const [supportUrls, setSupportUrls] = useState("");
  const [notes, setNotes] = useState("");
  const [researching, setResearching] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  const [brand, setBrand] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [loadingActive, setLoadingActive] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  // Accordion-exclusive groups, mirroring the App Profile page: at most one
  // bar open, Basics open by default, persisted per profile so an editing
  // position survives reloads and profile switches.
  const brandId = brand?.id;
  const [openGroup, setOpenGroup] = useState("basics");
  useEffect(() => {
    if (!brandId) return;
    try {
      const raw = localStorage.getItem(`brand-groups:${brandId}`);
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
  }, [brandId]);
  const toggleGroup = useCallback((id, open) => {
    const next = open ? id : null;
    setOpenGroup(next);
    try {
      if (brandId) localStorage.setItem(`brand-groups:${brandId}`, JSON.stringify(next));
    } catch {
      // Private-mode writes fail silently; the toggle still works in memory.
    }
  }, [brandId]);
  // The details card only exists once research has produced a profile, so the
  // scroll target below is a ref rather than a query: it is either mounted or
  // it is not, and nothing else on the page answers to this name.
  const manualCardRef = useRef(null);

  const applyProfile = (data) => {
    setBrand(data);
    setForm(profileToForm(data));
    setAppstoreUrl(data.appstore_url || "");
    setPlayUrl(data.play_url || "");
    setSupportUrls(productsToText(data.support_urls));
    setNotes(data.notes || "");
    // Every route into this page ends here — first load, the picker, research,
    // save, approve — so this is the one place worth recording which app is
    // being worked on. A page that needs a profile but is not handed one, such
    // as the standalone Asset Library, can then open on the same app.
    rememberCurrentAppId(data.id);
  };

  const refreshProfilesList = () => {
    api
      .getAppProfiles()
      .then((data) => setProfiles(data.profiles || []))
      .catch(() => setProfiles([]));
  };

  useEffect(() => {
    api
      .getActiveBrand()
      .then((data) => {
        applyProfile(data);
      })
      .catch(() => {
        // No brand profile yet — that's fine, form stays empty.
        setBrand(null);
      })
      .finally(() => setLoadingActive(false));
    refreshProfilesList();
  }, []);

  const handleSelectProfile = (id) => {
    if (!id) return;
    api
      .getAppProfile(id)
      .then((data) => {
        applyProfile(data);
        refreshProfilesList();
      })
      .catch((err) => toast.error(getErrorMessage(err)));
  };

  const handleResearchApp = async (e) => {
    e.preventDefault();
    if (!appstoreUrl.trim() && !playUrl.trim()) {
      toast.error("Enter your app's App Store URL, Google Play URL, or both.");
      return;
    }
    setResearching(true);
    setAnalyzeError(null);
    try {
      const data = await api.researchAppProfile({
        appstore_url: appstoreUrl.trim() || undefined,
        play_url: playUrl.trim() || undefined,
        support_urls: textToProducts(supportUrls),
        notes: notes.trim() || undefined,
      });
      applyProfile(data);
      refreshProfilesList();
      toast.success("App research complete — review the draft profile, then approve it.");
      // The details card only renders once a profile exists. Scroll it into
      // view now that research just created one, so the founder lands on the
      // draft instead of staring at the form they just submitted.
      requestAnimationFrame(() => {
        manualCardRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
      });
    } catch (err) {
      setAnalyzeError(getErrorMessage(err));
    } finally {
      setResearching(false);
    }
  };

  const handleFieldChange = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
  };

  const handleSave = async () => {
    // A brand with no name is useless to every downstream generator, so this is
    // the one field we insist on. Everything else can be filled in later.
    if (!form.brand_name.trim()) {
      // The name lives in Basics — open it so the empty field is visible
      // rather than the error pointing at a closed section.
      toggleGroup("basics", true);
      toast.error("Please enter a brand name before saving.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        appstore_url: appstoreUrl.trim() || undefined,
        play_url: playUrl.trim() || undefined,
        support_urls: textToProducts(supportUrls),
        notes: notes.trim(),
        brand_name: form.brand_name,
        brand_description: form.brand_description,
        niche: form.niche,
        app_category: form.app_category,
        platforms: textToProducts(form.platforms),
        core_features: textToProducts(form.core_features),
        primary_use_cases: textToProducts(form.primary_use_cases),
        problems_solved: textToProducts(form.problems_solved),
        must_not_show: textToProducts(form.must_not_show),
        usage_moments: textToProducts(form.usage_moments),
        proof_moment: form.proof_moment,
        viewer_objections: textToObjections(form.viewer_objections),
        desired_outcomes: textToProducts(form.desired_outcomes),
        outcome_statements: textToOutcomes(form.outcome_statements),
        target_audience: form.target_audience,
        ideal_customer_profile: form.ideal_customer_profile,
        icp_segments: textToLines(form.icp_segments),
        differentiation: form.differentiation,
        tone_voice: form.tone_voice,
        claims_approved: textToProducts(form.claims_approved),
        claims_review: textToProducts(form.claims_review),
        claims_banned: textToProducts(form.claims_banned),
      };
      // Update in place when a profile already exists, otherwise create one from
      // the manual fields — research is optional, not a prerequisite.
      const saved = brand?.id
        ? await api.updateAppProfile(brand.id, payload)
        : await api.createBrand(payload);
      applyProfile(saved);
      refreshProfilesList();
      toast.success("App Profile saved!");
    } catch (err) {
      const group = groupForSaveError(getErrorMessage(err));
      if (group) toggleGroup(group, true);
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async (applyPending = true) => {
    if (!brand?.id) return;
    setApproving(true);
    try {
      const saved = await api.approveAppProfile(brand.id, applyPending);
      applyProfile(saved);
      refreshProfilesList();
      toast.success("App Profile approved — ready for video generation.");
    } catch (err) {
      // Approval gaps name profile fields (description, features, outcomes),
      // so the same mapping opens the section holding the gap.
      const group = groupForSaveError(getErrorMessage(err));
      if (group) toggleGroup(group, true);
      toast.error(getErrorMessage(err));
    } finally {
      setApproving(false);
    }
  };

  const handleRefresh = async () => {
    if (!brand?.id) return;
    setRefreshing(true);
    try {
      const saved = await api.refreshAppProfile(brand.id);
      applyProfile(saved);
      toast.success("Re-research complete — review the proposal, then approve to apply it.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setRefreshing(false);
    }
  };

  const status = brand?.status || "draft";
  // Did research build this profile, rather than the founder typing it?
  //
  // `last_research_at` is written by exactly one path on the server: the
  // /app-profiles/research INSERT, and the /refresh UPDATE that re-runs it.
  // Both analyze-url and a hand-typed create leave it null. That makes it the
  // honest signal for "there is a generated draft here worth reviewing", rather
  // than inferring it from a non-empty field the founder may have typed.
  const researchedProfile = Boolean(brand?.last_research_at);
  const pendingProposal = brand?.pending_research;
  // What the last research run actually read. Rides on the refresh response
  // (and vanishes on the next load/save, which is correct — it describes
  // that run, not the profile). Shown in the pending alert so a partial run
  // is visible instead of silently thin.
  const researchSources = Array.isArray(brand?.research_sources)
    ? brand.research_sources
    : [];
  const sourcesRead = researchSources.filter((s) => s && s.ok).length;
  const sourcesFailed = researchSources
    .filter((s) => s && !s.ok && s.label)
    .map((s) => s.label);

  /* One-line summaries for the collapsible bars, read from the live form so
     a collapsed section still says what it holds. */
  const basicsSummary = [form.brand_name.trim(), form.app_category.trim()]
    .filter(Boolean).join(" · ") || "Name, category, platforms";
  const featureCount = textToProducts(form.core_features).length;
  const statementCount = textToOutcomes(form.outcome_statements).length;
  const doesSummary = (featureCount || statementCount)
    ? `${featureCount} feature${featureCount === 1 ? "" : "s"} · ${statementCount} pitch statement${statementCount === 1 ? "" : "s"}`
    : "Features, use cases, pitch";
  const momentCount = textToProducts(form.usage_moments).length;
  const directionSummary = form.proof_moment.trim()
    || (momentCount ? `${momentCount} usage moment${momentCount === 1 ? "" : "s"}` : "")
    || "Scenes, proof, objections";
  const audienceSummary = form.target_audience.trim() || "Who it's for";
  const approvedCount = textToProducts(form.claims_approved).length;
  const reviewCount = textToProducts(form.claims_review).length;
  const bannedCount = textToProducts(form.claims_banned).length;
  const claimsSummary = (approvedCount || reviewCount || bannedCount)
    ? `${approvedCount} approved · ${reviewCount} to review · ${bannedCount} never`
    : "No guardrails set";

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={Briefcase}
        title="App Profile"
        description="Research a mobile app from its store listing, review the draft for accuracy, then approve the app."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {profiles.length > 1 && (
              <AppPicker
                profiles={profiles}
                value={brand?.id}
                onChange={handleSelectProfile}
                showStatus
                testId="app-profile-picker"
              />
            )}
            {brand?.id ? (
              <Badge variant={status === "approved" ? "indigo" : "secondary"} className="px-3 py-1">
                {status === "approved" ? (
                  <><BadgeCheck className="h-3 w-3" /> Approved{brand.version > 1 ? ` · v${brand.version}` : ""}</>
                ) : (
                  <><AlertTriangle className="h-3 w-3" /> Draft — needs review</>
                )}
              </Badge>
            ) : null}
            {/* The App Profiles list used to be the only route to
                /app-profiles/:id, which is where content angles, template
                recommendations and the per-app "Videos from this app" list
                live. With the list gone this is the one way in, so those
                features stay reachable instead of becoming URL-only. */}
            {brand?.id && (
              <Badge variant="secondary" className="shrink-0 px-3 py-1" title={researchedProfile ? "Built by store research; your edits apply on top" : "Typed by hand, never researched"}>
                {researchedProfile ? "Researched + edits" : "Manually entered"}
              </Badge>
            )}
            {brand?.id && (
              <Button variant="secondary" size="sm" asChild>
                <Link to={`/app-profiles/${brand.id}`}>Content angles</Link>
              </Button>
            )}
          </div>
        }
      />

      {/* ---------- App research (store listings) ----------
          Profiles are created from App Store and Google Play URLs only. The
          details card below renders once research returns a profile.

          A SectionCard like every Create Video step: 32px tile + 16px
          heading + one-line description, surface padding from `.surface`.
          The testid stays on the form itself, because the suite submits
          through it. */}
      <SectionCard
        title="Research a mobile app"
        icon={Smartphone}
        description="App Store and Google Play URLs only — the draft appears below for review."
      >
          <form onSubmit={handleResearchApp} className="flex min-w-0 flex-col gap-2" data-testid="app-research-card" aria-label="Research a mobile app">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Input
                value={appstoreUrl}
                onChange={(e) => setAppstoreUrl(e.target.value)}
                placeholder="Apple App Store URL"
                data-testid="appstore-url-input"
              />
              <Input
                value={playUrl}
                onChange={(e) => setPlayUrl(e.target.value)}
                placeholder="Google Play URL"
                data-testid="play-url-input"
              />
            </div>
            <Input
              value={supportUrls}
              onChange={(e) => setSupportUrls(e.target.value)}
              placeholder="Supporting URLs, comma-separated (optional)"
              data-testid="support-urls-input"
            />
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Founder notes: positioning, pricing, constraints (optional)"
              className="min-h-[60px]"
              data-testid="app-notes-input"
            />
            <Button
              type="submit"
              disabled={researching}
              variant="brand"
              className="w-full sm:w-auto"
              data-testid="research-app-button"
            >
              {researching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {researching ? "Researching..." : brand?.id ? "Research into a new draft" : "Research app"}
            </Button>
          </form>
      </SectionCard>

      {brand?.id && pendingProposal && (
        <Alert data-testid="pending-refresh-alert">
          <RefreshCw className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>A refreshed proposal is waiting</AlertTitle>
          <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <span className="text-muted-foreground">
              Re-research found updates. Your approved profile is unchanged — approving applies the proposal.
              {researchSources.length > 0 && (
                <>
                  {" "}Read {sourcesRead} of {researchSources.length} source
                  {researchSources.length === 1 ? "" : "s"}
                  {sourcesFailed.length > 0 && ` · failed: ${sourcesFailed.join(", ")}`}.
                </>
              )}
            </span>
            <Button
              variant="secondary"
              size="sm"
              className="shrink-0"
              onClick={() => handleApprove(true)}
              disabled={approving}
              data-testid="approve-pending-button"
            >
              {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BadgeCheck className="h-3.5 w-3.5" />}
              Review &amp; approve
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {analyzeError && (
        <Alert variant="destructive" data-testid="brand-analyze-error-alert">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not analyze this URL</AlertTitle>
          <AlertDescription>{analyzeError}</AlertDescription>
        </Alert>
      )}

      {/* ---------- Manual details ----------
          Rendered only once a profile exists — research creates it, and the
          research handler scrolls it into view at that point. Before that
          there is no draft to correct, so the page is just the research card.
          (A legacy hand-typed profile picked from storage still opens here.)

          No outer box and no card header of its own: like the angles page,
          the groups are bare siblings under the page header in a space-y-2
          stack. The provenance badge moved up into the PageHeader actions.
          The "App Profile Details" display heading went with the box — the
          PageHeader title already says it. */}
      {brand?.id && (
      <div ref={manualCardRef} className="min-w-0 space-y-4" data-testid="brand-manual-card">
        {loadingActive ? (
          <div className="surface surface-flush space-y-2 rounded-2xl px-4 py-3 md:px-6" aria-label="Loading your app profile">
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-10 w-2/3 rounded-xl" />
          </div>
        ) : (
          <>
            <div className="space-y-4">
              {/* ── Basics ── */}
              <SectionGroup id="basics" label="Basics" icon={Package} summary={basicsSummary} open={openGroup === "basics"} onToggle={toggleGroup}>
              <div className="space-y-2">
                <Field label="App name">
                  <Input
                    value={form.brand_name}
                    onChange={handleFieldChange("brand_name")}
                    placeholder="For example: Voxel — Voice Journaling App"
                    data-testid="brand-name-field"
                  />
                </Field>

                <Field label="Description">
                  <Textarea
                    value={form.brand_description}
                    onChange={handleFieldChange("brand_description")}
                    placeholder="What does the app do?"
                    className="min-h-[90px]"
                    data-testid="brand-description-field"
                  />
                </Field>

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Field label="App category">
                    <Input
                      value={form.app_category}
                      onChange={handleFieldChange("app_category")}
                      placeholder="For example: Health & Fitness"
                      data-testid="app-category-field"
                    />
                  </Field>
                  <Field label="Niche">
                    <Input
                      value={form.niche}
                      onChange={handleFieldChange("niche")}
                      placeholder="For example: Fitness supplements"
                      data-testid="brand-niche-field"
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Field label="Platforms" hint="Comma-separated.">
                    <Input
                      value={form.platforms}
                      onChange={handleFieldChange("platforms")}
                      placeholder="For example: iOS, Android"
                      data-testid="app-platforms-field"
                    />
                  </Field>
                  <Field label="Tone / voice">
                    <Input
                      value={form.tone_voice}
                      onChange={handleFieldChange("tone_voice")}
                      placeholder="For example: Playful, high-energy, no-nonsense"
                      data-testid="brand-tone-field"
                    />
                  </Field>
                </div>
              </div>
              </SectionGroup>

              {/* ── What the app does ── */}
              <SectionGroup id="does" label="What the app does" icon={Layers} summary={doesSummary} open={openGroup === "does"} onToggle={toggleGroup}>
              <div className="space-y-2">
                <Field label="Core features" hint="Comma-separated — only features the app really has.">
                  <Input
                    value={form.core_features}
                    onChange={handleFieldChange("core_features")}
                    placeholder="Comma-separated, for example: Voice journaling, Reminders"
                    data-testid="app-features-field"
                  />
                </Field>

                <Field label="Primary use cases" hint="Comma-separated.">
                  <Input
                    value={form.primary_use_cases}
                    onChange={handleFieldChange("primary_use_cases")}
                    placeholder="Comma-separated, for example: Evening reflection, Habit tracking"
                    data-testid="app-usecases-field"
                  />
                </Field>

                <Field label="Problems solved" hint="Comma-separated.">
                  <Input
                    value={form.problems_solved}
                    onChange={handleFieldChange("problems_solved")}
                    placeholder="Comma-separated, for example: Forgetting to journal, Blank-page friction"
                    data-testid="app-problems-field"
                  />
                </Field>

                <Field label="Desired outcomes" hint="Comma-separated.">
                  <Input
                    value={form.desired_outcomes}
                    onChange={handleFieldChange("desired_outcomes")}
                    placeholder="Comma-separated, for example: Consistent journaling habit"
                    data-testid="app-outcomes-field"
                  />
                </Field>

                {/* The pitch material. Four lines per statement, separated by a
                    blank line — outcome / who feels it / source feature named
                    verbatim / how it helps in benefit terms. The link is the
                    field: without the source feature the video can only list
                    features, and approval requires at least one statement. */}
                <Field
                  label="Feature-to-outcome statements"
                  hint="Four lines per statement, blank line between: the benefit / who feels it / the feature it comes from / how it helps. These become the video's pitch."
                >
                  <Textarea
                    value={form.outcome_statements}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, outcome_statements: e.target.value }))
                    }
                    placeholder={
                      "Fall asleep without checking your phone\nNight-time scrollers\nSleep timer\nThe wind-down starts itself so there is no reason to pick the phone back up\n\n" +
                      "Wake up knowing what matters today\nOverloaded planners\nMorning brief\nOne glance replaces the whole list-scroll"
                    }
                    className="min-h-[140px]"
                    data-testid="app-outcome-statements-field"
                  />
                </Field>
              </div>
              </SectionGroup>

              {/* ── Video direction ── */}
              <SectionGroup id="direction" label="Video direction" icon={Compass} summary={directionSummary} open={openGroup === "direction"} onToggle={toggleGroup}>
              <div className="space-y-2">
                {/* These two exist because the strategy asks for a scene and a
                    demonstration, and no profile field supplied either. The model
                    was inventing a kitchen at 7am for every app and then being
                    told to "show it in use" with nothing saying what that is. */}
                <Field
                  label="When is the app reached for?"
                  hint="Concrete moments, not categories — these set the scene the video is shot in."
                >
                  <Textarea
                    value={productsToText(form.usage_moments)}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, usage_moments: e.target.value }))
                    }
                    placeholder={"One per line, for example:\nEnd of a night shift\n7am before the house wakes up\nPayday"}
                    className="min-h-[80px]"
                    data-testid="app-usage-moments-field"
                  />
                </Field>

                <Field
                  label="The proof moment"
                  hint="One moment the camera can film that makes the main claim believable."
                >
                  <Input
                    value={form.proof_moment}
                    onChange={handleFieldChange("proof_moment")}
                    placeholder="For example: The envelope splits the moment the transfer lands"
                    data-testid="app-proof-moment-field"
                  />
                </Field>

                {/* Enforced, not advisory: this list is attached to every video
                    prompt, so a detail here is an instruction to the model
                    rather than background it can use or ignore. known_limitations
                    is the advisory sibling and stays readable-only below. */}
                <Field
                  label="Never show in the video"
                  hint="One per line. Attached to every render — use it for things a camera could actually depict."
                >
                  <Textarea
                    value={productsToText(form.must_not_show)}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, must_not_show: e.target.value }))
                    }
                    placeholder={"One per line, for example:\nA hospital corridor\nA competitor's app icon\nAnyone under 18"}
                    className="min-h-[80px]"
                    data-testid="app-must-not-show-field"
                  />
                </Field>

                {/* The arc's material. Three lines per objection, separated by a
                    blank line — the "does now" line is what makes an objection
                    answerable rather than just a complaint to acknowledge. */}
                <Field
                  label="Why they would not download"
                  hint="Three lines per objection, blank line between: the objection / what they use now / your honest answer. These become the video's argument."
                >
                  <Textarea
                    value={form.viewer_objections}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, viewer_objections: e.target.value }))
                    }
                    placeholder={
                      "It is just another subscription\nThree other habit trackers I already pay for\nOne that costs nothing and works offline\n\n" +
                      "I do not have time to set it up\nI abandon anything that takes a setup call\nIt logs the first task in under a second"
                    }
                    className="min-h-[140px]"
                    data-testid="app-viewer-objections-field"
                  />
                </Field>
              </div>
              </SectionGroup>

              {/* ── Audience ── */}
              <SectionGroup id="audience" label="Audience" icon={Users} summary={audienceSummary} open={openGroup === "audience"} onToggle={toggleGroup}>
              <div className="space-y-2">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Field label="Target audience">
                    <Input
                      value={form.target_audience}
                      onChange={handleFieldChange("target_audience")}
                      placeholder="For example: Busy professionals 25-40"
                      data-testid="brand-audience-field"
                    />
                  </Field>
                </div>

                <Field label="Ideal Customer">
                  <Textarea
                    value={form.ideal_customer_profile}
                    onChange={handleFieldChange("ideal_customer_profile")}
                    placeholder="Demographics, interests, pain points..."
                    className="min-h-[80px]"
                    data-testid="brand-ideal-customer-field"
                  />
                </Field>

                <Field label="Audience segments" hint="One segment per line.">
                  <Textarea
                    value={form.icp_segments}
                    onChange={handleFieldChange("icp_segments")}
                    placeholder={"One per line, for example:\nBusy parents — 2-minute evening check-ins"}
                    className="min-h-[80px]"
                    data-testid="app-icp-segments-field"
                  />
                </Field>

                <Field label="What Sets You Apart">
                  <Textarea
                    value={form.differentiation}
                    onChange={handleFieldChange("differentiation")}
                    placeholder="Unique strengths, selling propositions, signature angles..."
                    className="min-h-[80px]"
                    data-testid="brand-differentiation-field"
                  />
                </Field>
              </div>
              </SectionGroup>

              {/* ── Claim guardrails ── */}
              <SectionGroup id="claims" label="Claim guardrails" icon={ShieldAlert} summary={claimsSummary} open={openGroup === "claims"} onToggle={toggleGroup}>
              <div className="space-y-2">
                <Field label="Approved claims" hint="Comma-separated — factual claims safe for promos.">
                  <Input
                    value={form.claims_approved}
                    onChange={handleFieldChange("claims_approved")}
                    placeholder="Comma-separated"
                    data-testid="app-claims-approved-field"
                  />
                </Field>

                <Field label="Claims needing review" hint="Comma-separated — verify before use.">
                  <Input
                    value={form.claims_review}
                    onChange={handleFieldChange("claims_review")}
                    placeholder="Comma-separated"
                    data-testid="app-claims-review-field"
                  />
                </Field>

                <Field label="Banned claims" hint="Comma-separated — promos must never make these.">
                  <Input
                    value={form.claims_banned}
                    onChange={handleFieldChange("claims_banned")}
                    placeholder="Comma-separated, for example: Guaranteed results, Fake reviews"
                    data-testid="app-claims-banned-field"
                  />
                </Field>
              </div>
              </SectionGroup>
            </div>

            {/* The manual path's own Save. Rendered only when research has not
                run, because the sticky bar owns saving for a researched profile
                and two Saves would leave the founder choosing between them for
                no reason. Without this the gate would silently remove the only
                way to store a hand-typed profile. */}
            {!researchedProfile && (
              <Button
                onClick={handleSave}
                disabled={saving}
                variant="accent"
                className="w-full sm:w-auto"
                data-testid="save-manual-profile-button"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {saving ? "Saving..." : brand?.id ? "Save App Profile" : "Create App Profile"}
              </Button>
            )}

            {brand?.id && (
              <Alert className="border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)]">
                <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                <AlertTitle>Ready for the template studio</AlertTitle>
                <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <span className="text-muted-foreground">
            {status === "approved"
              ? "This approved profile is ready to select in Create Video."
              : "Save and approve this profile before using it in Create Video."}
          </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="shrink-0"
                    onClick={() => navigate("/create")}
                    data-testid="find-video-to-remix-button"
                  >
                    Open the studio <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </AlertDescription>
              </Alert>
            )}
          </>
        )}
      </div>
      )}

      {/* ---------- Sticky action bar ----------
          Only for a profile research generated. "Save" and "Review complete"
          are review affordances over a machine-written draft, so before
          research runs there is nothing to review and the bar would be two
          buttons over an empty form.

          A hand-typed profile therefore has no sticky bar, which would leave it
          unsaveable — so the manual card carries its own Save below. The two
          never show at once: two Saves on one page is the ambiguity this gate
          was meant to remove. */}
      {researchedProfile && (
        <div className="sticky bottom-0 z-10 border-t border-[color:var(--hairline)] bg-background/80 py-4 backdrop-blur-sm">
          <div className={cn(PAGE_WIDTH_CLASS.default, "flex items-center gap-3")}>
            <Button
              onClick={handleSave}
              disabled={saving}
              variant="accent"
              data-testid="save-brand-button"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? "Saving..." : "Save App Profile"}
            </Button>

            {status !== "approved" && (
              <Button
                onClick={() => handleApprove(true)}
                disabled={approving}
                variant="brand"
                data-testid="approve-profile-button"
              >
                {approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
                {approving ? "Approving..." : "Review complete — approve profile"}
              </Button>
            )}

            {status === "approved" && (
              <Button
                onClick={handleRefresh}
                disabled={refreshing}
                variant="secondary"
                data-testid="refresh-profile-button"
              >
                {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                {refreshing ? "Re-researching..." : "Refresh from sources (needs re-approval)"}
              </Button>
            )}
          </div>
        </div>
      )}
    </PageFrame>
  );
}
