import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import { Globe, Sparkles, Briefcase, Loader2, Save, CheckCircle2, AlertTriangle, ArrowRight, Wand2 } from "lucide-react";
import { toast } from "sonner";

const EMPTY_FORM = {
  brand_name: "",
  brand_description: "",
  niche: "",
  products_services: "",
  target_audience: "",
  ideal_customer_profile: "",
  differentiation: "",
  tone_voice: "",
};

function productsToText(products) {
  if (Array.isArray(products)) return products.join(", ");
  return products || "";
}

function textToProducts(text) {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Labelled form field wrapper — keeps every input in this page aligned. */
function Field({ label, hint, children }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default function BrandSetup() {
  const navigate = useNavigate();

  const [websiteUrl, setWebsiteUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  const [brand, setBrand] = useState(null);
  const [loadingActive, setLoadingActive] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getActiveBrand()
      .then((data) => {
        setBrand(data);
        setForm({
          brand_name: data.brand_name || "",
          brand_description: data.brand_description || "",
          niche: data.niche || "",
          products_services: productsToText(data.products_services),
          target_audience: data.target_audience || "",
          ideal_customer_profile: data.ideal_customer_profile || "",
          differentiation: data.differentiation || "",
          tone_voice: data.tone_voice || "",
        });
        setWebsiteUrl(data.website_url || "");
      })
      .catch(() => {
        // No brand profile yet — that's fine, form stays empty.
        setBrand(null);
      })
      .finally(() => setLoadingActive(false));
  }, []);

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
      setBrand(data);
      setForm({
        brand_name: data.brand_name || "",
        brand_description: data.brand_description || "",
        niche: data.niche || "",
        products_services: productsToText(data.products_services),
        target_audience: data.target_audience || "",
        ideal_customer_profile: data.ideal_customer_profile || "",
        differentiation: data.differentiation || "",
        tone_voice: data.tone_voice || "",
      });
      toast.success("We analyzed your website and pre-filled your brand profile below!");
    } catch (err) {
      setAnalyzeError(getErrorMessage(err));
    } finally {
      setAnalyzing(false);
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
        brand_name: form.brand_name,
        brand_description: form.brand_description,
        niche: form.niche,
        products_services: textToProducts(form.products_services),
        target_audience: form.target_audience,
        ideal_customer_profile: form.ideal_customer_profile,
        differentiation: form.differentiation,
        tone_voice: form.tone_voice,
      };
      // Update in place when a profile already exists, otherwise create one from
      // the manual fields — analysing a website is optional, not a prerequisite.
      const saved = brand?.id
        ? await api.updateBrand(brand.id, payload)
        : await api.createBrand(payload);
      setBrand(saved);
      toast.success("Brand profile saved!");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        icon={Briefcase}
        title="Your Brand"
        description="This profile powers brand-adapted scripts across the Content Remixer."
        actions={
          brand?.id ? (
            <Badge variant="indigo" className="px-3 py-1">
              <CheckCircle2 className="h-3 w-3" /> Profile active
            </Badge>
          ) : null
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
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-teal)]">
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
            <h2 className="font-display text-base font-semibold">Brand Details</h2>
          </div>
          {brand?.id && (
            <Badge variant="secondary" className="shrink-0 text-[10px]">
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
                <AlertTriangle className="h-4 w-4 text-[color:var(--brand-teal)]" />
                <AlertTitle>No brand profile yet</AlertTitle>
                <AlertDescription>
                  Analyze your website above to fill this in automatically, or just type your
                  details in below and hit Save — a website isn&apos;t required.
                </AlertDescription>
              </Alert>
            )}

            <div className="space-y-5">
              <Field label="Brand name">
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
                  placeholder="What do you create or offer?"
                  className="min-h-[90px]"
                  data-testid="brand-description-field"
                />
              </Field>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <Field label="Niche">
                  <Input
                    value={form.niche}
                    onChange={handleFieldChange("niche")}
                    placeholder="e.g. Fitness supplements"
                    data-testid="brand-niche-field"
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

              <Field label="Products / services" hint="Comma-separated — each becomes a separate entry.">
                <Input
                  value={form.products_services}
                  onChange={handleFieldChange("products_services")}
                  placeholder="Comma-separated, e.g. Protein powder, pre-workout"
                  data-testid="brand-products-field"
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
              {saving ? "Saving..." : brand?.id ? "Save Brand Profile" : "Create Brand Profile"}
            </Button>

            {brand?.id && (
              <Alert className="border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)]">
                <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-teal)]" />
                <AlertTitle>Ready for the Content Remixer</AlertTitle>
                <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                  <span className="text-muted-foreground">
                    This profile will auto-fill and inform brand-adapted scripts anywhere you generate a video.
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="shrink-0 gap-1.5"
                    onClick={() => navigate("/discover")}
                    data-testid="find-video-to-remix-button"
                  >
                    Find a video to remix <ArrowRight className="h-3.5 w-3.5" />
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
