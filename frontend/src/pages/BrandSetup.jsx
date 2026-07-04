import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import { api, getErrorMessage } from "../lib/api";
import { Globe, Sparkles, Briefcase, Loader2, Save, CheckCircle2, AlertTriangle, ArrowRight } from "lucide-react";
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
    setSaving(true);
    try {
      let saved;
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
      if (brand?.id) {
        saved = await api.updateBrand(brand.id, payload);
      } else {
        // No brand profile exists yet and no URL was analyzed — create one via manual entry
        // by first requiring a URL analysis is not possible, so guide the user instead.
        toast.error("Please analyze a website URL first to create your brand profile, then you can edit it here.");
        setSaving(false);
        return;
      }
      setBrand(saved);
      toast.success("Brand profile saved!");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Briefcase className="h-6 w-6 text-[color:var(--brand-teal)]" /> Your Brand
        </h1>
        <p className="text-muted-foreground mt-1 max-w-2xl">
          The Content Remixer uses this brand profile to adapt any viral hook — from our discovery feed or a
          pasted URL — into a script tailored to your niche, products, and tone.
        </p>
      </div>

      <Card className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-3" data-testid="brand-url-card">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-[color:var(--brand-teal)]" />
          <h3 className="font-display font-semibold">Enter your website URL</h3>
        </div>
        <p className="text-xs text-muted-foreground">
          We'll read your website and automatically extract your brand name, description, niche, products/services,
          target audience, and tone of voice.
        </p>
        <form onSubmit={handleAnalyzeUrl} className="flex flex-col sm:flex-row gap-2">
          <Input
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
            placeholder="https://yourbrand.com"
            data-testid="brand-url-input"
            className="flex-1"
          />
          <Button
            type="submit"
            disabled={analyzing}
            className="gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#EA580C] text-white shrink-0"
            data-testid="analyze-brand-url-button"
          >
            {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {analyzing ? "Analyzing..." : "Analyze My Brand"}
          </Button>
        </form>

        {analyzeError && (
          <Alert variant="destructive" className="rounded-2xl" data-testid="brand-analyze-error-alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Could not analyze this URL</AlertTitle>
            <AlertDescription>{analyzeError}</AlertDescription>
          </Alert>
        )}
      </Card>

      <Card className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-4" data-testid="brand-manual-card">
        <div className="flex items-center justify-between">
          <h3 className="font-display font-semibold">Your Brand</h3>
          {brand?.id && (
            <Badge variant="secondary" className="rounded-full text-[10px]">
              {brand.website_url ? "From website + edits" : "Manually entered"}
            </Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          What do you create or offer? Tell us about your brand, channel, products, services, niche, or industry.
        </p>

        {loadingActive ? (
          <p className="text-sm text-muted-foreground">Loading your brand profile...</p>
        ) : !brand ? (
          <Alert className="rounded-2xl" data-testid="no-brand-profile-alert">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>No brand profile yet</AlertTitle>
            <AlertDescription>
              Analyze your website URL above to create your brand profile. Once created, you can edit any field
              manually right here.
            </AlertDescription>
          </Alert>
        ) : (
          <>
            <div className="space-y-2">
              <label className="text-sm font-medium">Brand name</label>
              <Input
                value={form.brand_name}
                onChange={handleFieldChange("brand_name")}
                placeholder="e.g. Voxel — Voice Journaling App"
                data-testid="brand-name-field"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Brand description</label>
              <Textarea
                value={form.brand_description}
                onChange={handleFieldChange("brand_description")}
                placeholder="What do you create or offer? Tell us about your brand, channel, products, services, niche, or industry."
                className="min-h-[90px]"
                data-testid="brand-description-field"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Niche / Industry</label>
                <Input
                  value={form.niche}
                  onChange={handleFieldChange("niche")}
                  placeholder="e.g. Fitness supplements"
                  data-testid="brand-niche-field"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Target audience</label>
                <Input
                  value={form.target_audience}
                  onChange={handleFieldChange("target_audience")}
                  placeholder="e.g. Busy professionals 25-40"
                  data-testid="brand-audience-field"
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Products / services (comma-separated)</label>
              <Input
                value={form.products_services}
                onChange={handleFieldChange("products_services")}
                placeholder="e.g. Protein powder, pre-workout, recovery gummies"
                data-testid="brand-products-field"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Who are you trying to reach?</label>
              <p className="text-xs text-muted-foreground">
                Describe your ideal customers or viewers — their demographics, interests, pain points, and
                where they spend time online.
              </p>
              <Textarea
                value={form.ideal_customer_profile}
                onChange={handleFieldChange("ideal_customer_profile")}
                placeholder="e.g. Women 22-35 interested in home workouts, struggling to stay consistent with fitness routines while juggling work — mostly active on TikTok and Instagram Reels in the evenings."
                className="min-h-[100px]"
                data-testid="brand-ideal-customer-field"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">What Sets You Apart</label>
              <p className="text-xs text-muted-foreground">
                What makes you different from others in your space? What are your standout strengths, selling
                propositions, or signature angles?
              </p>
              <Textarea
                value={form.differentiation}
                onChange={handleFieldChange("differentiation")}
                placeholder="e.g. Only supplement brand with third-party lab-tested batches published publicly, same-day shipping, and a no-BS ingredient list with zero fillers."
                className="min-h-[100px]"
                data-testid="brand-differentiation-field"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Tone / voice</label>
              <Input
                value={form.tone_voice}
                onChange={handleFieldChange("tone_voice")}
                placeholder="e.g. Playful, high-energy, no-nonsense"
                data-testid="brand-tone-field"
              />
            </div>

            <Button
              onClick={handleSave}
              disabled={saving}
              className="w-full gap-2 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
              data-testid="save-brand-button"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? "Saving..." : "Save Brand Profile"}
            </Button>

            <Alert className="rounded-2xl border-[color:var(--brand-teal)] bg-[color:rgba(13,148,136,0.06)]">
              <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-teal)]" />
              <AlertTitle>Ready for the Content Remixer</AlertTitle>
              <AlertDescription className="flex flex-col sm:flex-row sm:items-center gap-2 justify-between">
                <span>
                  This profile will auto-fill and inform brand-adapted scripts anywhere you generate a video.
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  className="gap-1.5 rounded-lg shrink-0"
                  onClick={() => navigate("/")}
                  data-testid="find-video-to-remix-button"
                >
                  Find a video to remix <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </AlertDescription>
            </Alert>
          </>
        )}
      </Card>
    </div>
  );
}
