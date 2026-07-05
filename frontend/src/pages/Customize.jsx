import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Input } from "../components/ui/input";
import { Skeleton } from "../components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import GenerationProgress from "../components/GenerationProgress";
import JsonSpecPanel from "../components/JsonSpecPanel";
import Stepper from "../components/Stepper";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { ArrowLeft, Upload, Sparkles, ImageIcon, AlertTriangle, RotateCcw, X, Lock, Palette, Check, ArrowRight } from "lucide-react";
import { toast } from "sonner";

const ENVIRONMENT_PRESETS = ["Cozy bedroom", "Modern living room", "Outdoor park", "Coffee shop", "Home office", "Kitchen"];
const BACKGROUND_PRESETS = ["Warm afternoon light", "Neon city night", "Minimalist white studio", "Bookshelf backdrop", "Beach sunset"];
const CLOTHING_PRESETS = ["Casual streetwear", "Business casual", "Athletic wear", "Cozy hoodie", "Elegant evening outfit"];

const CUSTOMIZE_STAGES = ["Uploading your photo", "Preparing generation spec", "Generating your customized preview(s)"];

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
            aria-pressed={value === p}
            className={`rounded-full px-3 py-1.5 text-xs font-medium border transition-colors hover:-translate-y-[1px] active:translate-y-0 active:scale-95 ${
              value === p
                ? "bg-[color:var(--brand-teal)] text-white border-transparent"
                : "bg-white border-border hover:border-[color:rgba(99,102,241,0.45)]"
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
  const [mode, setMode] = useState("preserve"); // "preserve" | "custom"
  const [selectedFrames, setSelectedFrames] = useState([]);
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
        setSelectedFrames([a.key_hook_frame_index]);
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

  const toggleFrame = (idx) => {
    setSelectedFrames((prev) => {
      if (prev.includes(idx)) return prev.filter((i) => i !== idx);
      if (prev.length >= 3) {
        toast.info("You can generate up to 3 images at a time.");
        return prev;
      }
      return [...prev, idx];
    });
  };

  const handleGenerate = async () => {
    if (!photoFile) {
      toast.error("Please upload a photo first.");
      return;
    }
    if (selectedFrames.length === 0) {
      toast.error("Select at least one frame to generate.");
      return;
    }
    setGenerating(true);
    setGenError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("person_photo", photoFile);
      formData.append("mode", mode);
      formData.append("frame_indices", JSON.stringify(selectedFrames));
      if (mode === "custom") {
        formData.append("environment", environment);
        formData.append("background", background);
        formData.append("clothing", clothing);
        formData.append("custom_instructions", customInstructions);
      }
      const data = await api.customize(videoId, formData);
      setResult(data);
      toast.success("Customized preview(s) generated!");
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
    return (
      <div className="space-y-6" data-testid="customize-loading">
        <Stepper current="swap" />
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-full max-w-2xl" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
          <Card className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-5 h-fit">
            <Skeleton className="h-40 w-full rounded-2xl" />
            <div className="flex gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="w-16 h-20 rounded-lg shrink-0" />
              ))}
            </div>
            <Skeleton className="h-10 w-full rounded-xl" />
          </Card>
          <Skeleton className="h-80 rounded-2xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Stepper current="swap" />
      <Button
        variant="ghost"
        onClick={() => navigate(`/analysis/${videoId}`)}
        className="gap-1.5 -ml-2"
        data-testid="back-to-analysis-button"
      >
        <ArrowLeft className="h-4 w-4" /> Back to analysis
      </Button>

      <div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight">Face swap this hook</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl">
          Upload your photo and we'll swap it into the hook moment. By default we keep the pose, gesture, environment,
          background, and clothing exactly as the original — only the face/character changes.
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
                  className="absolute top-2 right-2 rounded-full bg-black/70 text-white p-1 transition-colors transition-transform hover:bg-black/85 hover:scale-105 active:scale-95"
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

          <div className="space-y-2">
            <label className="text-sm font-medium">Frames to generate ({selectedFrames.length}/3)</label>
            <p className="text-xs text-muted-foreground">Pick up to 3 frames from the hook to face-swap.</p>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {analysis.frames.map((f) => {
                const isSelected = selectedFrames.includes(f.index);
                return (
                  <button
                    key={f.index}
                    type="button"
                    onClick={() => toggleFrame(f.index)}
                    data-testid={`select-frame-${f.index}`}
                    className={`group relative shrink-0 w-16 h-20 rounded-lg overflow-hidden border-2 transition-colors hover:-translate-y-[1px] active:translate-y-0 ${
                      isSelected ? "border-[color:var(--brand-teal)]" : "border-border hover:border-[color:rgba(99,102,241,0.45)]"
                    }`}
                  >
                    <img src={mediaUrl(f.media_url)} alt={`Frame ${f.index}`} className="w-full h-full object-cover" />
                    {isSelected && (
                      <span className="absolute top-1 right-1 rounded-full bg-[color:var(--brand-teal)] text-white p-0.5">
                        <Check className="h-2.5 w-2.5" />
                      </span>
                    )}
                    {f.index === analysis.key_hook_frame_index && (
                      <span className="absolute bottom-1 left-1 rounded-full bg-[color:var(--brand-coral)] text-white text-[8px] px-1">
                        Hook
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2 rounded-2xl border border-border p-3 bg-white/40">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setMode("preserve")}
                data-testid="mode-preserve-button"
                aria-pressed={mode === "preserve"}
                className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold border transition-colors hover:-translate-y-[1px] active:translate-y-0 active:scale-[0.98] ${
                  mode === "preserve"
                    ? "bg-[color:var(--brand-teal)] text-white border-transparent"
                    : "bg-white border-border text-muted-foreground hover:border-[color:rgba(99,102,241,0.45)]"
                }`}
              >
                <Lock className="h-3.5 w-3.5" /> Keep Original (Recommended)
              </button>
              <button
                type="button"
                onClick={() => setMode("custom")}
                data-testid="mode-custom-button"
                aria-pressed={mode === "custom"}
                className={`flex-1 flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold border transition-colors hover:-translate-y-[1px] active:translate-y-0 active:scale-[0.98] ${
                  mode === "custom"
                    ? "bg-[color:var(--brand-coral)] text-white border-transparent"
                    : "bg-white border-border text-muted-foreground hover:border-[color:rgba(244,63,94,0.4)]"
                }`}
              >
                <Palette className="h-3.5 w-3.5" /> Customize Scene
              </button>
            </div>
            {mode === "preserve" ? (
              <p className="text-xs text-muted-foreground pt-1">
                Placement, pose, gesture, environment, background, and clothing stay exactly as in the original video —
                only the face/character is swapped.
              </p>
            ) : (
              <div className="space-y-4 pt-2">
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
                    placeholder="e.g. add a golden retriever in the background..."
                    className="min-h-[70px]"
                    data-testid="custom-instructions-textarea"
                  />
                </div>
              </div>
            )}
          </div>

          <Button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white"
            data-testid="generate-preview-button"
          >
            <Sparkles className="h-4 w-4" /> {generating ? "Generating..." : "Generate Preview"}
          </Button>
        </Card>

        <div className="space-y-6">
          {!result && !generating && (
            <Card className="overflow-hidden rounded-2xl border-border" data-testid="reference-frame-preview">
              <div className="px-4 py-2 text-xs font-medium text-muted-foreground border-b border-border">
                Selected reference frame(s)
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-3">
                {selectedFrames.map((idx) => {
                  const f = analysis.frames.find((fr) => fr.index === idx);
                  return f ? (
                    <img
                      key={idx}
                      src={mediaUrl(f.media_url)}
                      alt={`Reference frame ${idx}`}
                      className="w-full object-contain bg-black/5 rounded-lg max-h-[380px]"
                    />
                  ) : null;
                })}
              </div>
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
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4" data-testid="generated-images-gallery">
                {result.generated_images.map((img) => (
                  <Card key={img.id} className="overflow-hidden rounded-2xl border-[color:var(--brand-teal)]" data-testid="generated-preview-image">
                    <div className="px-4 py-2 text-xs font-medium text-[color:var(--brand-teal-dark)] border-b border-border">
                      Frame {img.frame_index} • {img.timestamp_seconds}s
                    </div>
                    <img
                      src={mediaUrl(img.image_url)}
                      alt="Generated customized preview"
                      className="w-full object-contain bg-black/5 max-h-[420px]"
                    />
                    <div className="p-3">
                      <a href={mediaUrl(img.image_url)} download target="_blank" rel="noreferrer">
                        <Button variant="secondary" size="sm" className="w-full gap-1.5 rounded-lg">
                          Download
                        </Button>
                      </a>
                    </div>
                  </Card>
                ))}
              </div>
              <JsonSpecPanel spec={result.generation_spec} />
              <Button
                onClick={() => navigate(`/generate-video/${result.id}`)}
                className="w-full gap-2 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
                data-testid="continue-to-video-button"
              >
                Continue to Generate Video <ArrowRight className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
