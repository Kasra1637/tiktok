import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { rememberCurrentAppId } from "../lib/currentApp";
import { useTourEligibility } from "../components/onboarding/OnboardingProvider";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "../components/ui/dropdown-menu";
import PageHeader from "../components/PageHeader";
import { SectionCard, GroupLabel } from "../components/SectionCard";
import { ListenButton } from "../components/ListenButton";
import { SectionGroup } from "../components/profileUi";
import { AppPicker } from "../components/AppPicker";
import { Disclosure } from "../components/Disclosure";
import { Skeleton } from "../components/ui/skeleton";
import PageFrame from "../components/PageFrame";
import { api, getErrorMessage } from "../lib/api";
import { BUSY_ETA_SECONDS } from "../lib/busyEta";
import { Sparkles, Briefcase, Save, CircleCheck as CheckCircle2, TriangleAlert as AlertTriangle, ArrowRight, Smartphone, RefreshCw, BadgeCheck, Package, Layers, Compass, Users } from "lucide-react";
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
  };
}

/* Labelled form field wrapper. The label is the shared GroupLabel eyebrow —
   the same 12/600 uppercase muted label the angles page uses for its own
   fields — so a form row reads like a detail row. Hint stays 12/18 muted.
   `listen` puts a speaker on the label row for the field's current text. */
function Field({ label, hint, listen, children }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <GroupLabel as="label">{label}</GroupLabel>
        {listen && (
          <ListenButton
            id={listen.id}
            label={listen.label || label}
            getBlocks={listen.getBlocks}
            testId={listen.testId}
            className="h-7 w-7"
          />
        )}
      </div>
      {children}
      {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
    </div>
  );
}

/* Every collapsible bar in the App Profile Details card. Same ids, order and
   single-open behaviour as the App Profile page's SectionGroups, so the two
   pages read as one surface. Summaries are derived from the live form below. */
const GROUP_IDS = ["basics", "does", "direction", "audience"];

/**
 * Map a save/approve failure to the group holding the offending field, so
 * the error opens its section instead of hiding inside a collapsed one.
 * Returns null when the message names nothing mappable — guessing wrong is
 * worse than leaving the founder's place.
 */
function groupForSaveError(message) {
  const text = (message || "").toLowerCase();
  if (/audience|segment|differentiation|ideal customer/.test(text)) return "audience";
  if (/featur|outcome|statement|problems solved|use case|\buse it for\b/.test(text)) return "does";
  if (/proof|objection|must not show|usage moment|direction|scene/.test(text)) return "direction";
  if (/name|description|categor|niche|platform|tone/.test(text)) return "basics";
  return null;
}

export default function BrandSetup() {
  const navigate = useNavigate();

  const [websiteUrl, setWebsiteUrl] = useState("");
  const [appstoreUrl, setAppstoreUrl] = useState("");
  const [playUrl, setPlayUrl] = useState("");
  const [supportUrls, setSupportUrls] = useState("");
  const [notes, setNotes] = useState("");
  const [researching, setResearching] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  const [brand, setBrand] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [loadingActive, setLoadingActive] = useState(true);
  useTourEligibility("brand", !loadingActive && !brand && profiles.length === 0 && !analyzeError && !researching);
  const [form, setForm] = useState(EMPTY_FORM);

  // Split a comma- or newline-separated field into speakable values.
  const spokenList = (key) =>
    String(form[key] || "")
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
  const listenField = (key, label) => ({
    id: `brand-${key}`,
    label,
    testId: `listen-brand-${key}`,
    getBlocks: () => [{ label, values: spokenList(key) }],
  });
  const listenParagraph = (key, label) => ({
    id: `brand-${key}`,
    label,
    testId: `listen-brand-${key}`,
    getBlocks: () => [{ label, values: [form[key]] }],
  });
  const listenBasics = () => [
    { label: "App name", values: [form.brand_name] },
    { label: "Description", values: [form.brand_description] },
    { label: "App category", values: [form.app_category] },
    { label: "Niche", values: [form.niche] },
    { label: "Platforms", values: spokenList("platforms") },
    { label: "Tone and voice", values: [form.tone_voice] },
  ];
  const listenDoes = () => [
    { label: "Core features", values: spokenList("core_features") },
    { label: "Primary use cases", values: spokenList("primary_use_cases") },
    { label: "Problems solved", values: spokenList("problems_solved") },
    { label: "Desired outcomes", values: spokenList("desired_outcomes") },
    { label: "Feature-to-outcome statements", values: [form.outcome_statements] },
  ];
  const listenDirection = () => [
    { label: "When is the app reached for", values: spokenList("usage_moments") },
    { label: "The proof moment", values: [form.proof_moment] },
    { label: "Never show in the video", values: spokenList("must_not_show") },
    { label: "Why they would not download", values: [form.viewer_objections] },
  ];
  const listenAudience = () => [
    { label: "Target audience", values: [form.target_audience] },
    { label: "Ideal Customer", values: [form.ideal_customer_profile] },
    { label: "Audience segments", values: spokenList("icp_segments") },
    { label: "What Sets You Apart", values: [form.differentiation] },
  ];
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

  // A missing picker is a missing way to switch apps, so its failure names
  // itself with its own retry rather than collapsing to no options.
  const [profilesError, setProfilesError] = useState(null);
  const refreshProfilesList = useCallback(() => {
    setProfilesError(null);
    api
      .getAppProfiles()
      .then((data) => setProfiles(data.profiles || []))
      .catch((err) => {
        setProfiles([]);
        setProfilesError(getErrorMessage(err));
      });
  }, []);

  // A 404 means no brand profile yet — that's fine, the form stays empty.
  // Anything else is a failed load, and it names itself with a retry.
  const [loadError, setLoadError] = useState(null);
  const loadBrand = useCallback(() => {
    setLoadError(null);
    setLoadingActive(true);
    api
      .getActiveBrand()
      .then((data) => {
        applyProfile(data);
      })
      .catch((err) => {
        if (err?.response?.status === 404) {
          setBrand(null);
        } else {
          setLoadError(getErrorMessage(err));
        }
      })
      .finally(() => setLoadingActive(false));
  }, []);

  useEffect(() => {
    loadBrand();
    refreshProfilesList();
  }, [loadBrand, refreshProfilesList]);

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

  /**
   * One research run, shared by the card's submit and the Research menu's
   * "Research into new draft" item — both send the URLs in this box and land
   * on whatever the server returns.
   *
   * With a profile already open the server stores a separate draft rather than
   * updating it, so the toast names which happened. The menu's "Creates
   * separate draft" caption is off screen by then, and a fork reported as an
   * ordinary re-research is exactly the surprise this page must not hand over.
   */
  const runResearch = async () => {
    const forking = Boolean(brand?.id);
    if (!websiteUrl.trim() && !appstoreUrl.trim() && !playUrl.trim()) {
      toast.error("Enter your app's website, App Store URL, Google Play URL, or a combination.");
      return;
    }
    setResearching(true);
    setAnalyzeError(null);
    const toastId = toast.loading("Researching your app pages…");
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
      toast.success(
        forking
          ? "New draft researched from these URLs — your other profile is untouched."
          : "App research complete — review the draft profile, then approve it.",
        { id: toastId }
      );
      // The details card only renders once a profile exists. Scroll it into
      // view now that research just created one, so the founder lands on the
      // draft instead of staring at the form they just submitted.
      requestAnimationFrame(() => {
        manualCardRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
      });
    } catch (err) {
      setAnalyzeError(getErrorMessage(err));
      toast.error(getErrorMessage(err), { id: toastId });
    } finally {
      setResearching(false);
    }
  };

  const handleResearchApp = async (e) => {
    e.preventDefault();
    await runResearch();
  };

  const handleFieldChange = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
  };

  // One payload builder for both save paths below: the manual Save and the
  // autosave send the same row, so an autosaved profile is never a thinner
  // record than a manually saved one.
  const buildPayload = () => ({
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
  });

  // The write itself, shared: update in place when a profile already exists,
  // otherwise create one from the hand-typed fields — research is optional,
  // not a prerequisite.
  const persistProfile = async () => {
    const payload = buildPayload();
    return brand?.id
      ? api.updateAppProfile(brand.id, payload)
      : api.createBrand(payload);
  };

  // What the inputs look like as one string, and what a server row looks
  // like as the same string. When the two agree there is nothing to save:
  // research, refresh, profile switches and manual saves all land through
  // applyProfile, so the form matching the row is the baseline syncing
  // itself without scheduling a redundant write.
  const liveSignature = () =>
    JSON.stringify({ form, websiteUrl, appstoreUrl, playUrl, supportUrls, notes });
  const signatureForRow = (row) =>
    JSON.stringify({
      form: profileToForm(row),
      websiteUrl: row.website_url || "",
      appstoreUrl: row.appstore_url || "",
      playUrl: row.play_url || "",
      supportUrls: productsToText(row.support_urls),
      notes: row.notes || "",
    });

  // Autosave mirrors the Review step's rhythm (save ~1s after the last
  // change through the same path as the manual button), because this form
  // is the same shape of risk: 20+ fields behind one Save press, so an
  // unpressed button reads as lost work. Silent saves never touch `saving`
  // — locking the form on every debounced keystroke would interrupt the
  // typing they follow — and the manual Save stays for an explicit save.
  // Editing never changes approval status server-side, so autosaving an
  // approved profile stores the edit without yanking its approval; the
  // founder still re-approves explicitly, exactly as after a manual Save.
  const [autosaving, setAutosaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");
  const brandRef = useRef(null);
  brandRef.current = brand;
  const liveRef = useRef(null);
  liveRef.current = { form, websiteUrl, appstoreUrl, playUrl, supportUrls, notes };
  const lastSavedRef = useRef(null);
  const saveProfileRef = useRef(null);
  const saveProfile = async ({ silent = false } = {}) => {
    if (silent) {
      // A profile cannot be created without a name, and nagging about it on
      // every keystroke would punish typing the name last. The manual Save
      // still validates with a toast; autosave simply waits for a name.
      if (!form.brand_name.trim()) return;
      if (autosaving || saving || researching || approving || refreshing) return;
    } else {
      setSaving(true);
    }
    const sentBrandId = brand?.id || null;
    const sentSignature = liveSignature();
    if (silent) {
      setAutosaving(true);
      setSaveStatus("Saving…");
    }
    try {
      const saved = await persistProfile();
      // A profile switch (or a research run replacing the row) mid-flight:
      // the result belongs to a screen the founder already left.
      if ((brandRef.current?.id || null) !== sentBrandId) {
        refreshProfilesList();
        return;
      }
      const latest = JSON.stringify(liveRef.current);
      if (silent && latest !== sentSignature) {
        // Typed during the flight: keep the keystrokes, never clobber them
        // with the older response. The id is still worth keeping (a create
        // just minted it); the chained save below stores the newer text.
        setBrand(saved);
        refreshProfilesList();
      } else {
        applyProfile(saved);
        refreshProfilesList();
        lastSavedRef.current = signatureForRow(saved);
        if (silent) setSaveStatus("All changes saved");
      }
    } catch (err) {
      const message = getErrorMessage(err);
      if (silent) {
        setSaveStatus(`Could not autosave: ${message}`);
      } else {
        const group = groupForSaveError(message);
        if (group) toggleGroup(group, true);
        toast.error(message);
      }
    } finally {
      if (silent) {
        setAutosaving(false);
        // A change that landed mid-flight still owes a save now that the
        // flag is clear. Compared against what this flight sent, not the
        // baseline: a normalization gap between the typed text and the
        // stored row must never read as a new edit, or this chains
        // forever. Failures do not chain — the status names the failure
        // and the next keystroke retries — so a dead server cannot spin
        // this into a loop either.
        if (JSON.stringify(liveRef.current) !== sentSignature) {
          saveProfileRef.current?.({ silent: true });
        }
      } else {
        setSaving(false);
        setSaveStatus("");
      }
    }
  };
  saveProfileRef.current = (options) => saveProfile(options);
  // Save ~1s after the last change, never during a research/refresh flight
  // or a manual save: the same button the founder would press, without
  // being asked. The baseline syncs itself whenever the form matches the
  // loaded row, so research, refreshes and profile switches never schedule
  // a redundant write.
  const formSignature = liveSignature();
  useEffect(() => {
    if (saving || researching || approving || refreshing || autosaving) return undefined;
    const row = brandRef.current;
    if (formSignature === lastSavedRef.current) return undefined;
    if (row && formSignature === signatureForRow(row)) {
      lastSavedRef.current = formSignature;
      return undefined;
    }
    if (!row && !liveRef.current.form.brand_name.trim()) return undefined;
    setSaveStatus("");
    const timer = setTimeout(() => {
      saveProfileRef.current?.({ silent: true });
    }, 1000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the signature
    // is the inputs; the saver rides a ref so scheduling never re-fires.
  }, [formSignature, saving, researching, approving, refreshing, autosaving, brand?.id]);

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
      const saved = await persistProfile();
      applyProfile(saved);
      refreshProfilesList();
      toast.success("App Profile saved!");
    } catch (err) {
      const group = groupForSaveError(getErrorMessage(err));
      if (group) toggleGroup(group, true);
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
      setSaveStatus("");
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
    const toastId = toast.loading("Re-reading your app pages…");
    try {
      const saved = await api.refreshAppProfile(brand.id);
      applyProfile(saved);
      toast.success("Re-research complete — review the proposal, then approve to apply it.", { id: toastId });
    } catch (err) {
      toast.error(getErrorMessage(err), { id: toastId });
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

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={Briefcase}
        title="App Profile"
        description="Review and approve app details before creating videos."
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
            {profilesError && (
              <span role="alert" className="flex items-center gap-1 text-sm text-destructive">
                {profilesError}{" "}
                <button type="button" className="underline" onClick={refreshProfilesList} data-testid="profiles-retry">
                  Try again
                </button>
              </span>
            )}
            {brand?.id ? (
              <Badge variant={status === "approved" ? "indigo" : "secondary"} className="px-3 py-1">
                {status === "approved" ? (
                  <><BadgeCheck className="h-3 w-3" /> Ready for video{brand.version > 1 ? ` · v${brand.version}` : ""}</>
                ) : (
                  <><AlertTriangle className="h-3 w-3" /> Draft — blocked for video</>
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
                <Link to={`/app-profiles/${brand.id}`}>Review app facts</Link>
              </Button>
            )}
          </div>
        }
      />

      {/* ---------- App research (public pages) ----------
          Profiles are created from the website, App Store and Google Play URLs.
          The website often carries the positioning the stores omit, so leaving
          it out builds the first draft without it. The details card below
          renders once research returns a profile.

          A SectionCard like every Create Video step: 32px tile + 16px
          heading + one-line description, surface padding from `.surface`.
          The testid stays on the form itself, because the suite submits
          through it. */}
      <SectionCard
        className="page-content-enter"
        title="Research a mobile app"
        icon={Smartphone}
        description="Website, App Store and Google Play URLs — the draft appears below for review."
      >
          <form onSubmit={handleResearchApp} className="flex min-w-0 flex-col gap-2" data-testid="app-research-card" aria-label="Research a mobile app">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Input
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                placeholder="Website URL (carries your positioning)"
                data-testid="website-url-input"
              />
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
            <Disclosure
              summary="More context (optional)"
              detailsClassName="group rounded-lg border border-[color:var(--hairline)] px-3 py-2"
              summaryClassName="flex cursor-pointer items-center justify-between gap-2 text-sm text-muted-foreground transition-colors group-hover:text-foreground [&::-webkit-details-marker]:hidden"
            >
              <div className="flex min-w-0 flex-col gap-2 pt-2">
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
              </div>
            </Disclosure>
            {/* One row of short actions, not a sentence per action.

                Research is the submit while no machine draft exists: it is the
                only way to create one, and a hand-typed profile keeps it. Once
                research has produced a draft, re-running it is an occasional
                move with a consequence attached — "needs re-approval",
                "creates separate draft" — so both re-runs collapse behind one
                Research menu that states the consequence beside the item, the
                shape the App Profile page's header already uses. Three wide
                labels read as a paragraph in one row, and two of them were
                Signal Coral at once; the palette reserves coral for the single
                commit action of a screen, which here is Approve while the
                profile is still a draft.

                Save and Approve sit in this row, beside the research controls —
                the sticky bottom bar is gone, so review actions live where the
                draft is made rather than pinned to the viewport. Gated exactly
                as the bar was: only a researched profile has review
                affordances, so a hand-typed one keeps its single manual Save
                further down. type="button" on each: inside this form an untyped
                button submits research.

                A hairline above the row separates the fields from the actions:
                at the form's own 8px rhythm the buttons read as one more field,
                which is what made the row look crowded into the notes box. */}
            <div className="flex flex-col gap-2 border-t border-[color:var(--hairline)] pt-4 sm:flex-row sm:flex-wrap sm:items-center">
              {!researchedProfile && (
                <Button
                  type="submit"
                  disabled={researching}
                  busy={researching}
                  etaSeconds={BUSY_ETA_SECONDS.research}
                  variant="secondary"
                  className="w-full sm:w-auto"
                  data-testid="research-app-button"
                >
                  <Sparkles className="h-4 w-4" />
                  {researching ? "Researching" : "Research app for video"}
                </Button>
              )}
              {researchedProfile && (
                <Button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  busy={saving}
                  variant="accent"
                  className="w-full sm:w-auto"
                  data-testid="save-brand-button"
                >
                  <Save className="h-4 w-4" />
                  {saving ? "Saving" : "Save profile"}
                </Button>
              )}
              {researchedProfile && status !== "approved" && (
                <Button
                  type="button"
                  onClick={() => handleApprove(true)}
                  disabled={approving}
                  busy={approving}
                  variant="accent"
                  className="w-full sm:w-auto"
                  data-testid="approve-profile-button"
                >
                  <BadgeCheck className="h-4 w-4" />
                  {approving ? "Approving" : "Approve for video"}
                </Button>
              )}
              {/* Refresh from sources is offered only on an approved profile: a
                  draft owes no approval, and re-reading the listings into a
                  proposal for one would have nothing to compare against. */}
              {researchedProfile && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="secondary"
                      className="w-full sm:w-auto"
                      disabled={researching || refreshing}
                      busy={researching || refreshing}
                      etaSeconds={BUSY_ETA_SECONDS.research}
                      title="Re-run research from these listings: read them into a proposal, or fork a separate draft"
                      data-testid="research-menu-button"
                    >
                      <Sparkles className="h-4 w-4" />
                      Research
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="min-w-[240px]">
                    <DropdownMenuLabel className="text-xs">Research actions</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    {status === "approved" && (
                      <DropdownMenuItem
                        onClick={handleRefresh}
                        disabled={refreshing || researching}
                        className="text-sm"
                        data-testid="refresh-profile-button"
                      >
                        <RefreshCw className="mr-2 h-3.5 w-3.5" />
                        Refresh from sources
                        <span className="ml-auto text-xs text-muted-foreground">Needs re-approval</span>
                      </DropdownMenuItem>
                    )}
                    {/* The run the card's submit used to make, landing as a
                        separate draft row: forking never touches this profile,
                        which is the part worth reading before choosing it. */}
                    <DropdownMenuItem
                      onClick={runResearch}
                      disabled={researching || refreshing}
                      className="text-sm"
                      data-testid="research-new-draft-button"
                    >
                      <Sparkles className="mr-2 h-3.5 w-3.5" />
                      Research into new draft
                      <span className="ml-auto text-xs text-muted-foreground">Creates separate draft</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
            {/* Autosave status for the researched path, same rhythm as the
                Review step's draft line: silent saves narrate here so an
                unpressed Save never reads as lost work. Conditioned on the
                path like the Save buttons are, so the testid stays unique. */}
            {researchedProfile && saveStatus && (
              <p role="status" data-testid="brand-autosave-status" className="pt-2 text-sm text-muted-foreground">
                {saveStatus}
              </p>
            )}
          </form>
      </SectionCard>

      {brand?.id && pendingProposal && (
        <Alert variant="warning" data-testid="pending-refresh-alert">
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
              busy={approving}
              data-testid="approve-pending-button"
            >
              <BadgeCheck className="h-3.5 w-3.5" />
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

      {loadError && (
        <Alert variant="destructive" data-testid="brand-load-error">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load your app profile</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>{loadError}</span>
            <Button variant="secondary" size="sm" onClick={() => loadBrand()} data-testid="brand-load-retry">
              Try again
            </Button>
          </AlertDescription>
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
      <div ref={manualCardRef} className={`min-w-0 space-y-4${loadingActive ? "" : " page-content-enter"}`} data-testid="brand-manual-card">
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
              <SectionGroup id="basics" label="Basics" icon={Package} summary={basicsSummary} open={openGroup === "basics"} onToggle={toggleGroup} listen={{ id: "brand-basics", label: "Basics", getBlocks: listenBasics }}>
              <div className="space-y-2">
                <Field label="App name" listen={listenParagraph("brand_name", "App name")}>
                  <Input
                    value={form.brand_name}
                    onChange={handleFieldChange("brand_name")}
                    placeholder="For example: Voxel — Voice Journaling App"
                    data-testid="brand-name-field"
                  />
                </Field>

                <Field label="Description" listen={listenParagraph("brand_description", "Description")}>
                  <Textarea
                    value={form.brand_description}
                    onChange={handleFieldChange("brand_description")}
                    placeholder="What does the app do?"
                    className="min-h-[90px]"
                    data-testid="brand-description-field"
                  />
                </Field>

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Field label="App category" listen={listenParagraph("app_category", "App category")}>
                    <Input
                      value={form.app_category}
                      onChange={handleFieldChange("app_category")}
                      placeholder="For example: Health & Fitness"
                      data-testid="app-category-field"
                    />
                  </Field>
                  <Field label="Niche" listen={listenParagraph("niche", "Niche")}>
                    <Input
                      value={form.niche}
                      onChange={handleFieldChange("niche")}
                      placeholder="For example: Fitness supplements"
                      data-testid="brand-niche-field"
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Field label="Platforms" hint="Comma-separated." listen={listenField("platforms", "Platforms")}>
                    <Input
                      value={form.platforms}
                      onChange={handleFieldChange("platforms")}
                      placeholder="For example: iOS, Android"
                      data-testid="app-platforms-field"
                    />
                  </Field>
                  <Field label="Tone / voice" listen={listenParagraph("tone_voice", "Tone / voice")}>
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
              <SectionGroup id="does" label="What the app does" icon={Layers} summary={doesSummary} open={openGroup === "does"} onToggle={toggleGroup} listen={{ id: "brand-does", label: "What the app does", getBlocks: listenDoes }}>
              <div className="space-y-2">
                <Field label="Core features" hint="Comma-separated — only features the app really has." listen={listenField("core_features", "Core features")}>
                  <Input
                    value={form.core_features}
                    onChange={handleFieldChange("core_features")}
                    placeholder="Comma-separated, for example: Voice journaling, Reminders"
                    data-testid="app-features-field"
                  />
                </Field>

                <Field label="Primary use cases" hint="Comma-separated." listen={listenField("primary_use_cases", "Primary use cases")}>
                  <Input
                    value={form.primary_use_cases}
                    onChange={handleFieldChange("primary_use_cases")}
                    placeholder="Comma-separated, for example: Evening reflection, Habit tracking"
                    data-testid="app-usecases-field"
                  />
                </Field>

                <Field label="Problems solved" hint="Comma-separated." listen={listenField("problems_solved", "Problems solved")}>
                  <Input
                    value={form.problems_solved}
                    onChange={handleFieldChange("problems_solved")}
                    placeholder="Comma-separated, for example: Forgetting to journal, Blank-page friction"
                    data-testid="app-problems-field"
                  />
                </Field>

                <Field label="Desired outcomes" hint="Comma-separated." listen={listenField("desired_outcomes", "Desired outcomes")}>
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
                  listen={listenParagraph("outcome_statements", "Feature-to-outcome statements")}
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
              <SectionGroup id="direction" label="Video direction" icon={Compass} summary={directionSummary} open={openGroup === "direction"} onToggle={toggleGroup} listen={{ id: "brand-direction", label: "Video direction", getBlocks: listenDirection }}>
              <div className="space-y-2">
                {/* These two exist because the strategy asks for a scene and a
                    demonstration, and no profile field supplied either. The model
                    was inventing a kitchen at 7am for every app and then being
                    told to "show it in use" with nothing saying what that is. */}
                <Field
                  label="When is the app reached for?"
                  hint="Concrete moments, not categories — these set the scene the video is shot in."
                  listen={listenField("usage_moments", "When the app is reached for")}
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
                  listen={listenParagraph("proof_moment", "The proof moment")}
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
                  listen={listenField("must_not_show", "Never show in the video")}
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
                  listen={listenParagraph("viewer_objections", "Why they would not download")}
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
              <SectionGroup id="audience" label="Audience" icon={Users} summary={audienceSummary} open={openGroup === "audience"} onToggle={toggleGroup} listen={{ id: "brand-audience", label: "Audience", getBlocks: listenAudience }}>
              <div className="space-y-2">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <Field label="Target audience" listen={listenParagraph("target_audience", "Target audience")}>
                    <Input
                      value={form.target_audience}
                      onChange={handleFieldChange("target_audience")}
                      placeholder="For example: Busy professionals 25-40"
                      data-testid="brand-audience-field"
                    />
                  </Field>
                </div>

                <Field label="Ideal Customer" listen={listenParagraph("ideal_customer_profile", "Ideal Customer")}>
                  <Textarea
                    value={form.ideal_customer_profile}
                    onChange={handleFieldChange("ideal_customer_profile")}
                    placeholder="Demographics, interests, pain points..."
                    className="min-h-[80px]"
                    data-testid="brand-ideal-customer-field"
                  />
                </Field>

                <Field label="Audience segments" hint="One segment per line." listen={listenField("icp_segments", "Audience segments")}>
                  <Textarea
                    value={form.icp_segments}
                    onChange={handleFieldChange("icp_segments")}
                    placeholder={"One per line, for example:\nBusy parents — 2-minute evening check-ins"}
                    className="min-h-[80px]"
                    data-testid="app-icp-segments-field"
                  />
                </Field>

                <Field label="What Sets You Apart" listen={listenParagraph("differentiation", "What Sets You Apart")}>
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

            </div>

            {/* The manual path's own Save, then the Ready alert directly below
                it. The pair sits in its own stack with a 21px gap: the wizard
                CTA sits 21px above its panel edge (20px inset gutter + 1px
                border), so this is the same distance without the panel. The
                parent stays space-y-4, so the groups above keep their 16px. */}
            <div className="space-y-[21px]">
            {/* The manual path's own Save. Rendered only when research has not
                run, because the research row above owns saving for a researched
                profile and two Saves would leave the founder choosing between
                them for no reason. Without this the gate would silently remove
                the only way to store a hand-typed profile. */}
            {!researchedProfile && (
              <>
                <Button
                  onClick={handleSave}
                  disabled={saving}
                  busy={saving}
                  variant="accent"
                  className="w-full sm:w-auto"
                  data-testid="save-manual-profile-button"
                >
                  <Save className="h-4 w-4" />
                  {saving ? "Saving" : brand?.id ? "Save App Profile" : "Create App Profile"}
                </Button>
                {/* Autosave status for the hand-typed path — see the research
                    form above for why it narrates here. */}
                {saveStatus && (
                  <p role="status" data-testid="brand-autosave-status" className="text-sm text-muted-foreground">
                    {saveStatus}
                  </p>
                )}
              </>
            )}

            {brand?.id && (
              <Alert variant="warning">
                <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                <AlertTitle>{status === "approved" ? "Ready for Create Video" : "Approval needed before Create Video"}</AlertTitle>
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
                    onClick={status === "approved"
                      ? () => navigate(`/create?profile=${encodeURIComponent(brand.id)}`)
                      : () => handleApprove(false)}
                    disabled={approving || saving}
                    busy={approving}
                    data-testid="find-video-to-remix-button"
                  >
                    {approving ? "Approving" : status === "approved" ? "Create Video" : "Approve saved profile"} <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </AlertDescription>
              </Alert>
            )}
            </div>
          </>
        )}
      </div>
      )}

    </PageFrame>
  );
}
