import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { rememberCurrentAppId } from "../lib/currentApp";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import { Globe, Sparkles, Briefcase, Loader2, Save, CheckCircle2, AlertTriangle, ArrowRight, Wand2, Smartphone, RefreshCw, BadgeCheck } from "lucide-react";
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
  desired_outcomes: "",
  competitors: "",
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
    desired_outcomes: productsToText(data.desired_outcomes),
    competitors: productsToText(data.competitors),
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

/** Labelled form field wrapper — keeps every input in this page aligned. */
function Field({ label, hint, children }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default function BrandSetup() {
  const navigate = useNavigate();

  const [websiteUrl, setWebsiteUrl] = useState("");
  const [appstoreUrl, setAppstoreUrl] = useState("");
  const [playUrl, setPlayUrl] = useState("");
  const [supportUrls, setSupportUrls] = useState("");
  const [notes, setNotes] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [researching, setResearching] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  const [brand, setBrand] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [loadingActive, setLoadingActive] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const applyProfile = (data) => {
    setBrand(data);
    setForm(profileToForm(data));
    setWebsiteUrl(data.website_url || "");
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

  const handleAnalyzeUrl = async (e) => {
    e.preventDefault();
    if (!websiteUrl.trim()) {
      toast.error("Please enter a website URL first.");
      return;
    }
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const data = await api.analyzeBrandUrl(websiteUrl.trim());
      applyProfile(data);
      refreshProfilesList();
      toast.success("We analyzed your website and pre-filled your brand profile below!");
    } catch (err) {
      setAnalyzeError(getErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleResearchApp = async (e) => {
    e.preventDefault();
    if (!websiteUrl.trim() && !appstoreUrl.trim() && !playUrl.trim() && !supportUrls.trim()) {
      toast.error("Enter at least one URL: website, App Store, Google Play, or a support page.");
      return;
    }
    setResearching(true);
    setAnalyzeError(null);
    try {
      const data = await api.researchAppProfile({
        website_url: websiteUrl.trim() || undefined,
        appstore_url: appstoreUrl.trim() || undefined,
        play_url: playUrl.trim() || undefined,
        support_urls: textToProducts(supportUrls),
        notes: notes.trim() || undefined,
      });
      applyProfile(data);
      refreshProfilesList();
      toast.success("App research complete — review the draft profile, then approve it.");
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
      toast.error("Please enter a brand name before saving.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        website_url: websiteUrl.trim() || undefined,
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
        desired_outcomes: textToProducts(form.desired_outcomes),
        competitors: textToProducts(form.competitors),
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
  const pendingProposal = brand?.pending_research;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        icon={Briefcase}
        title="Your app"
        description="Research a mobile app, review the draft profile, then approve it — approved profiles power video scripts."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {profiles.length > 1 && (
              <select
                value={brand?.id || ""}
                onChange={(e) => handleSelectProfile(e.target.value)}
                className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-1.5 text-xs font-medium"
                data-testid="app-profile-picker"
                aria-label="Select App Profile"
              >
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.brand_name || "Untitled app"} ({p.status || "draft"})
                  </option>
                ))}
              </select>
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
              <Button variant="secondary" size="sm" asChild>
                <Link to={`/app-profiles/${brand.id}`}>Content angles</Link>
              </Button>
            )}
          </div>
        }
      />

      {/* ---------- Autofill from website ---------- */}
      <div className="border-gradient relative rounded-2xl p-[1px]">
        <div className="surface-solid relative overflow-hidden rounded-2xl p-5">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background: "radial-gradient(500px circle at 100% 0%, rgba(99,102,241,0.10), transparent 60%)",
            }}
          />
          <form onSubmit={handleAnalyzeUrl} className="relative space-y-3" data-testid="brand-url-card">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                <Wand2 className="h-[18px] w-[18px]" />
              </span>
              <div className="min-w-0">
                <h2 className="font-display text-base font-semibold">Autofill from your website</h2>
                <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                  AI reads your site and extracts your name, niche, audience, and tone &mdash; so you
                  don&apos;t fill out the form below from scratch.
                </p>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <Globe className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  placeholder="https://yourbrand.com"
                  data-testid="brand-url-input"
                  className="pl-10"
                />
              </div>
              <Button
                type="submit"
                disabled={analyzing}
                variant="brand"
                className="shrink-0"
                data-testid="analyze-brand-url-button"
              >
                {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {analyzing ? "Analyzing..." : "Analyze"}
              </Button>
            </div>
          </form>
        </div>
      </div>

      {/* ---------- App research (website + store listings) ---------- */}
      <div className="border-gradient relative rounded-2xl p-[1px]">
        <div className="surface-solid relative overflow-hidden rounded-2xl p-5">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background: "radial-gradient(500px circle at 0% 0%, rgba(99,102,241,0.10), transparent 60%)",
            }}
          />
          <form onSubmit={handleResearchApp} className="relative space-y-3" data-testid="app-research-card">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                <Smartphone className="h-[18px] w-[18px]" />
              </span>
              <div className="min-w-0">
                <h2 className="font-display text-base font-semibold">Research a mobile app</h2>
                <p className="mt-0.5 text-sm leading-relaxed text-muted-foreground">
                  AI reads the website plus the App Store and Google Play listings and drafts a full
                  App Profile — features, audiences, claims, and video themes. Review it below, then approve.
                </p>
              </div>
            </div>
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
        </div>
      </div>

      {brand?.id && pendingProposal && (
        <Alert data-testid="pending-refresh-alert">
          <RefreshCw className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>A refreshed proposal is waiting</AlertTitle>
          <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <span className="text-muted-foreground">
              Re-research found updates. Your approved profile is unchanged — approving applies the proposal.
            </span>
            <Button
              variant="secondary"
              size="sm"
              className="shrink-0 gap-1.5"
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

      {/* ---------- Manual details ---------- */}
      <div className="surface space-y-5 rounded-2xl p-5 md:p-6" data-testid="brand-manual-card">
        <div className="flex items-center justify-between gap-3">
          <div>
            <span className="eyebrow block">Profile</span>
            <h2 className="font-display text-base font-semibold">App Profile Details</h2>
          </div>
          {brand?.id && (
            <Badge variant="secondary" className="shrink-0 text-xs">
              {brand.website_url ? "From website + edits" : "Manually entered"}
            </Badge>
          )}
        </div>

        {loadingActive ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading your brand profile...
          </p>
        ) : (
          <>
            {!brand && (
              <Alert data-testid="no-brand-profile-alert">
                <AlertTriangle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                <AlertTitle>No App Profile yet</AlertTitle>
                <AlertDescription>
                  Research an app above to fill this in automatically, or just type the
                  details in below and hit Save — no URLs required.
                </AlertDescription>
              </Alert>
            )}

            <div className="space-y-5">
              <Field label="App name">
                <Input
                  value={form.brand_name}
                  onChange={handleFieldChange("brand_name")}
                  placeholder="e.g. Voxel — Voice Journaling App"
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

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <Field label="App category">
                  <Input
                    value={form.app_category}
                    onChange={handleFieldChange("app_category")}
                    placeholder="e.g. Health & Fitness"
                    data-testid="app-category-field"
                  />
                </Field>
                <Field label="Niche">
                  <Input
                    value={form.niche}
                    onChange={handleFieldChange("niche")}
                    placeholder="e.g. Fitness supplements"
                    data-testid="brand-niche-field"
                  />
                </Field>
              </div>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <Field label="Platforms" hint="Comma-separated.">
                  <Input
                    value={form.platforms}
                    onChange={handleFieldChange("platforms")}
                    placeholder="e.g. iOS, Android"
                    data-testid="app-platforms-field"
                  />
                </Field>
              </div>

              <Field label="Core features" hint="Comma-separated — only features the app really has.">
                <Input
                  value={form.core_features}
                  onChange={handleFieldChange("core_features")}
                  placeholder="Comma-separated, e.g. Voice journaling, Reminders"
                  data-testid="app-features-field"
                />
              </Field>

              <Field label="Primary use cases" hint="Comma-separated.">
                <Input
                  value={form.primary_use_cases}
                  onChange={handleFieldChange("primary_use_cases")}
                  placeholder="Comma-separated, e.g. Evening reflection, Habit tracking"
                  data-testid="app-usecases-field"
                />
              </Field>

              <Field label="Problems solved" hint="Comma-separated.">
                <Input
                  value={form.problems_solved}
                  onChange={handleFieldChange("problems_solved")}
                  placeholder="Comma-separated, e.g. Forgetting to journal, Blank-page friction"
                  data-testid="app-problems-field"
                />
              </Field>

              <Field label="Desired outcomes" hint="Comma-separated.">
                <Input
                  value={form.desired_outcomes}
                  onChange={handleFieldChange("desired_outcomes")}
                  placeholder="Comma-separated, e.g. Consistent journaling habit"
                  data-testid="app-outcomes-field"
                />
              </Field>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <Field label="Competitor apps" hint="Comma-separated.">
                  <Input
                    value={form.competitors}
                    onChange={handleFieldChange("competitors")}
                    placeholder="e.g. Day One, Journey"
                    data-testid="app-competitors-field"
                  />
                </Field>
                <Field label="Target audience">
                  <Input
                    value={form.target_audience}
                    onChange={handleFieldChange("target_audience")}
                    placeholder="e.g. Busy professionals 25-40"
                    data-testid="brand-audience-field"
                  />
                </Field>
              </div>

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
                  placeholder={"One per line, e.g.\nA hospital corridor\nA competitor's app icon\nAnyone under 18"}
                  className="min-h-[80px]"
                  data-testid="app-must-not-show-field"
                />
              </Field>

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
                  placeholder={"One per line, e.g.\nBusy parents — 2-minute evening check-ins"}
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

              <Field label="Tone / voice">
                <Input
                  value={form.tone_voice}
                  onChange={handleFieldChange("tone_voice")}
                  placeholder="e.g. Playful, high-energy, no-nonsense"
                  data-testid="brand-tone-field"
                />
              </Field>

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
                  placeholder="Comma-separated, e.g. Guaranteed results, Fake reviews"
                  data-testid="app-claims-banned-field"
                />
              </Field>
            </div>

            <Button
              onClick={handleSave}
              disabled={saving}
              variant="accent"
              size="lg"
              className="w-full"
              data-testid="save-brand-button"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? "Saving..." : brand?.id ? "Save App Profile" : "Create App Profile"}
            </Button>

            {brand?.id && status !== "approved" && (
              <Button
                onClick={() => handleApprove(true)}
                disabled={approving}
                variant="brand"
                size="lg"
                className="w-full"
                data-testid="approve-profile-button"
              >
                {approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}
                {approving ? "Approving..." : "Review complete — approve profile"}
              </Button>
            )}

            {brand?.id && status === "approved" && (
              <Button
                onClick={handleRefresh}
                disabled={refreshing}
                variant="secondary"
                size="lg"
                className="w-full gap-1.5"
                data-testid="refresh-profile-button"
              >
                {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                {refreshing ? "Re-researching..." : "Refresh from sources (needs re-approval)"}
              </Button>
            )}

            {brand?.id && (
              <Alert className="border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)]">
                <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                <AlertTitle>Ready for the template studio</AlertTitle>
                <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                  <span className="text-muted-foreground">
                    This profile can inform App Profiles and template-based scripts anywhere you generate a video.
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="shrink-0 gap-1.5"
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
    </div>
  );
}
