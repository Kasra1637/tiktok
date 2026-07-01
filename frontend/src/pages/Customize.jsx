import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Input } from "../components/ui/input";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import GenerationProgress from "../components/GenerationProgress";
import SideBySideCompare from "../components/SideBySideCompare";
import JsonSpecPanel from "../components/JsonSpecPanel";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { ArrowLeft, Upload, Sparkles, ImageIcon, AlertTriangle, RotateCcw, X } from "lucide-react";
import { toast } from "sonner";

const ENVIRONMENT_PRESETS = ["Cozy bedroom", "Modern living room", "Outdoor park", "Coffee shop", "Home office", "Kitchen"];
const BACKGROUND_PRESETS = ["Warm afternoon light", "Neon city night", "Minimalist white studio", "Bookshelf backdrop", "Beach sunset"];
const CLOTHING_PRESETS = ["Casual streetwear", "Business casual", "Athletic wear", "Cozy hoodie", "Elegant evening outfit"];

const CUSTOMIZE_STAGES = ["Uploading your photo", "Preparing generation spec", "Generating your customized preview"];

function ChipGroup({ label, presets, value, onChange, testIdPrefix }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            data-testid={`${testIdPrefix}-${p.toLowerCase().replace(/\s+/g, "-")}`}
            className={`rounded-full px-3 py-1.5 text-xs font-medium border transition-colors ${
              value === p
                ? "bg-[color:var(--brand-teal)] text-white border-transparent"
                : "bg-white border-border hover:border-[color:rgba(13,148,136,0.45)]"
            }`}
          >
            {p}
          </button>
        ))}
      </div>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`Custom ${label.toLowerCase()}...`}
        data-testid={`${testIdPrefix}-input`}
      />
    </div>
  );
}

export default function Customize() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [video, setVideo] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(null);
  const [environment, setEnvironment] = useState("Cozy bedroom");
  const [background, setBackground] = useState("Warm afternoon light");
  const [clothing, setClothing] = useState("Casual streetwear");
  const [customInstructions, setCustomInstructions] = useState("");

  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    Promise.all([api.getVideo(videoId), api.getAnalysis(videoId)])
      .then(([v, a]) => {
        setVideo(v);
        setAnalysis(a);
      })
      .catch((err) => setLoadError(getErrorMessage(err)));
  }, [videoId]);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload an image file (JPEG, PNG, or WEBP).");
      return;
    }
    setPhotoFile(file);
    setPhotoPreview(URL.createObjectURL(file));
  };

  const handleGenerate = async () => {
    if (!photoFile) {
      toast.error("Please upload a photo first.");
      return;
    }
    setGenerating(true);
    setGenError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("person_photo", photoFile);
      formData.append("environment", environment);
      formData.append("background", background);
      formData.append("clothing", clothing);
      formData.append("custom_instructions", customInstructions);
      const data = await api.customize(videoId, formData);
      setResult(data);
      toast.success("Customized preview generated!");
    } catch (err) {
      setGenError(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  if (loadError) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Alert variant="destructive" className="rounded-2xl">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Could not load this hook</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
        <Button onClick={() => navigate("/")} className="gap-1.5">
          <ArrowLeft className="h-4 w-4" /> Back to feed
        </Button>
      </div>
    );
  }

  if (!video || !analysis) {
    return <p className="text-muted-foreground">Loading...</p>;
  }

  const referenceFrame =
    analysis.frames?.find((f) => f.index === analysis.key_hook_frame_index) || analysis.frames?.[0];

  return (
    <div className="space-y-6">
      <Button
        variant="ghost"
        onClick={() => navigate(`/analysis/${videoId}`)}
        className="gap-1.5 -ml-2"
        data-testid="back-to-analysis-button"
      >
        <ArrowLeft className="h-4 w-4" /> Back to analysis
      </Button>

      <div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight">Customize this hook</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl">
          Upload your photo and we'll swap it into the hook moment while preserving the expression and gesture that
          made it work.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
        <Card className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-5 h-fit">
          <div className="space-y-2">
            <label className="text-sm font-medium">Your photo</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={handleFileChange}
              data-testid="photo-upload-input"
            />
            {photoPreview ? (
              <div className="relative">
                <img src={photoPreview} alt="Uploaded preview" className="w-full rounded-xl object-cover aspect-square" />
                <button
                  onClick={() => {
                    setPhotoFile(null);
                    setPhotoPreview(null);
                  }}
                  className="absolute top-2 right-2 rounded-full bg-black/70 text-white p-1"
                  data-testid="remove-photo-button"
                  aria-label="Remove photo"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-full flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border bg-white/60 hover:bg-white/80 py-10 transition-colors"
                data-testid="photo-upload-dropzone"
              >
                <Upload className="h-6 w-6 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Click to upload a photo</span>
                <span className="text-xs text-muted-foreground">JPEG, PNG, or WEBP</span>
              </button>
            )}
          </div>

          <ChipGroup
            label="Environment"
            presets={ENVIRONMENT_PRESETS}
            value={environment}
            onChange={setEnvironment}
            testIdPrefix="environment-preset"
          />
          <ChipGroup
            label="Background / Lighting"
            presets={BACKGROUND_PRESETS}
            value={background}
            onChange={setBackground}
            testIdPrefix="background-preset"
          />
          <ChipGroup
            label="Clothing"
            presets={CLOTHING_PRESETS}
            value={clothing}
            onChange={setClothing}
            testIdPrefix="clothing-preset"
          />

          <div className="space-y-2">
            <label className="text-sm font-medium">Additional instructions (optional)</label>
            <Textarea
              value={customInstructions}
              onChange={(e) => setCustomInstructions(e.target.value)}
              placeholder="e.g. add a golden retriever in the background, keep hair color natural..."
              className="min-h-[90px]"
              data-testid="custom-instructions-textarea"
            />
          </div>

          <Button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#EA580C] text-white"
            data-testid="generate-preview-button"
          >
            <Sparkles className="h-4 w-4" /> {generating ? "Generating..." : "Generate Preview"}
          </Button>
        </Card>

        <div className="space-y-6">
          {!result && !generating && (
            <Card className="overflow-hidden rounded-2xl border-border" data-testid="reference-frame-preview">
              <div className="px-4 py-2 text-xs font-medium text-muted-foreground border-b border-border">
                Reference hook frame (what we'll preserve)
              </div>
              {referenceFrame && (
                <img
                  src={mediaUrl(referenceFrame.media_url)}
                  alt="Reference hook frame"
                  className="w-full object-contain bg-black/5 max-h-[480px]"
                />
              )}
            </Card>
          )}

          {generating && (
            <Card className="p-6 rounded-2xl border-border shadow-[var(--shadow-soft)]">
              <h3 className="font-display font-semibold mb-3 flex items-center gap-2">
                <ImageIcon className="h-4 w-4" /> Generating your customized preview...
              </h3>
              <GenerationProgress stages={CUSTOMIZE_STAGES} active={true} />
            </Card>
          )}

          {genError && (
            <Alert variant="destructive" className="rounded-2xl" data-testid="customize-error-alert">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Preview generation failed</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{genError}</p>
                <Button size="sm" onClick={handleGenerate} className="gap-1.5" data-testid="retry-generate-button">
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {result && (
            <>
              <SideBySideCompare originalUrl={result.reference_frame_url} generatedUrl={result.generated_image_url} />
              <div className="flex gap-2">
                <a href={mediaUrl(result.generated_image_url)} download target="_blank" rel="noreferrer">
                  <Button variant="secondary" className="gap-1.5 rounded-xl" data-testid="download-preview-button">
                    Download Preview
                  </Button>
                </a>
              </div>
              <JsonSpecPanel spec={result.generation_spec} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
