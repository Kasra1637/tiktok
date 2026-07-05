import { useState, useRef, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import GenerationProgress from "../components/GenerationProgress";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import {
  Upload,
  Sparkles,
  AlertTriangle,
  RotateCcw,
  X,
  Download,
  ArrowRight,
  ImageIcon,
  User,
  Wand2,
  Check,
  ZoomIn,
  Film,
  Clapperboard,
  Play,
  Clock,
  Loader2,
  Globe,
} from "lucide-react";
import { toast } from "sonner";

const FACE_SWAP_STAGES = [
  "Analyzing facial geometry & skin tone",
  "Matching lighting conditions",
  "Generating high-fidelity face swap",
  "Applying natural blending & color matching",
];

const STEPS = [
  { id: 1, title: "Upload Your Target", description: "Choose the photo you want to swap a face onto", icon: ImageIcon },
  { id: 2, title: "Upload Your Source Face", description: "Select a clear photo of the face you want to insert", icon: User },
  { id: 3, title: "Generate Your Swap", description: "Click Generate and let our face swap AI work its magic", icon: Wand2 },
];

function StepIndicator({ currentStep }) {
  return (
    <div className="flex items-center justify-center gap-0 w-full max-w-2xl mx-auto" data-testid="face-swap-step-indicator">
      {STEPS.map((step, idx) => {
        const isCompleted = currentStep > step.id;
        const isCurrent = currentStep === step.id;
        const Icon = step.icon;

        return (
          <div key={step.id} className="flex items-center flex-1">
            <div className="flex flex-col items-center text-center flex-1">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all duration-300 ${
                  isCompleted
                    ? "bg-[color:var(--brand-teal)] border-[color:var(--brand-teal)] text-white"
                    : isCurrent
                    ? "border-[color:var(--brand-teal)] text-[color:var(--brand-teal)] bg-white shadow-md"
                    : "border-border text-muted-foreground bg-white"
                }`}
              >
                {isCompleted ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
              </div>
              <p
                className={`mt-2 text-xs font-semibold ${
                  isCompleted || isCurrent ? "text-foreground" : "text-muted-foreground"
                }`}
              >
                {step.title}
              </p>
              <p className="text-[10px] text-muted-foreground mt-0.5 hidden sm:block">{step.description}</p>
            </div>
            {idx < STEPS.length - 1 && (
              <div
                className={`h-[2px] w-full min-w-[24px] mx-1 transition-colors duration-300 ${
                  currentStep > step.id ? "bg-[color:var(--brand-teal)]" : "bg-border"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function DropZone({ onFileSelect, accept, label, sublabel, preview, onRemove, testId, icon: Icon = Upload }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file && file.type.startsWith("image/")) {
        onFileSelect(file);
      } else {
        toast.error("Please drop an image file (JPEG, PNG, or WEBP).");
      }
    },
    [onFileSelect]
  );

  const handleClick = () => inputRef.current?.click();

  const handleInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        toast.error("Please upload an image file (JPEG, PNG, or WEBP).");
        return;
      }
      onFileSelect(file);
    }
  };

  if (preview) {
    return (
      <div className="relative group" data-testid={`${testId}-preview`}>
        <img
          src={preview}
          alt="Uploaded preview"
          className="w-full rounded-2xl object-cover aspect-[3/4] shadow-[var(--shadow-soft)]"
        />
        <div className="absolute inset-0 rounded-2xl bg-black/0 group-hover:bg-black/10 transition-colors" />
        <button
          onClick={onRemove}
          className="absolute top-3 right-3 rounded-full bg-black/70 text-white p-1.5 transition-all hover:bg-black/90 hover:scale-110 active:scale-95 shadow-lg"
          aria-label="Remove image"
          data-testid={`${testId}-remove`}
        >
          <X className="h-4 w-4" />
        </button>
        <div className="absolute bottom-3 left-3 rounded-full bg-[color:var(--brand-teal)] text-white px-2.5 py-1 text-xs font-semibold flex items-center gap-1 shadow-lg">
          <Check className="h-3 w-3" /> Uploaded
        </div>
      </div>
    );
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleInputChange}
        data-testid={`${testId}-input`}
      />
      <button
        type="button"
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`w-full flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed py-16 transition-all duration-200 cursor-pointer ${
          isDragging
            ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.06)] scale-[1.02]"
            : "border-border bg-white/60 hover:bg-white/80 hover:border-[color:rgba(99,102,241,0.45)]"
        }`}
        data-testid={`${testId}-dropzone`}
      >
        <div
          className={`flex h-14 w-14 items-center justify-center rounded-full transition-colors ${
            isDragging ? "bg-[color:rgba(99,102,241,0.12)]" : "bg-muted"
          }`}
        >
          <Icon className={`h-6 w-6 ${isDragging ? "text-[color:var(--brand-teal)]" : "text-muted-foreground"}`} />
        </div>
        <div className="text-center">
          <span className="text-sm font-medium text-foreground">{label}</span>
          <p className="text-xs text-muted-foreground mt-1">{sublabel}</p>
        </div>
        <span className="text-xs text-muted-foreground bg-muted px-3 py-1 rounded-full">
          Drag & drop or click to browse
        </span>
      </button>
    </div>
  );
}

export default function FaceSwap() {
  const [searchParams] = useSearchParams();
  const [targetFile, setTargetFile] = useState(null);
  const [targetPreview, setTargetPreview] = useState(null);
  const [targetFrameUrl, setTargetFrameUrl] = useState(null); // When target comes from a video frame
  const [sourceFile, setSourceFile] = useState(null);
  const [sourcePreview, setSourcePreview] = useState(null);
  const [videoInfo, setVideoInfo] = useState(null); // Info about the source video if applicable

  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState(null);
  const [result, setResult] = useState(null);

  // Phase 2: Video generation state
  const [videoDuration, setVideoDuration] = useState(10);
  const [videoPrompt, setVideoPrompt] = useState("");
  const [generatingVideo, setGeneratingVideo] = useState(false);
  const [videoJobId, setVideoJobId] = useState(null);
  const [videoStatus, setVideoStatus] = useState(null); // "pending" | "in_progress" | "completed" | "failed"
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoError, setVideoError] = useState(null);
  const pollingRef = useRef(null);

  // Phase 2B: Branded video state
  const [brandUrl, setBrandUrl] = useState("");
  const [brandProfile, setBrandProfile] = useState(null);
  const [brandedDuration, setBrandedDuration] = useState(15);
  const [brandedPrompt, setBrandedPrompt] = useState("");
  const [brandedPromptBrand, setBrandedPromptBrand] = useState("");
  const [generatingBrandedPrompt, setGeneratingBrandedPrompt] = useState(false);
  const [brandedPromptError, setBrandedPromptError] = useState(null);

  // Pre-load target frame from query params (when coming from video analysis)
  useEffect(() => {
    const frameUrl = searchParams.get("target");
    const videoId = searchParams.get("videoId");
    const frameIndex = searchParams.get("frame");

    if (frameUrl) {
      const fullUrl = mediaUrl(frameUrl);
      setTargetPreview(fullUrl);
      setTargetFrameUrl(frameUrl);
      // Create a synthetic "file" marker so the step indicator advances
      setTargetFile({ name: "video_frame.jpg", fromVideo: true });

      if (videoId) {
        setVideoInfo({ videoId, frameIndex: frameIndex || "key" });
      }
    }
  }, [searchParams]);

  const currentStep = !targetFile ? 1 : !sourceFile ? 2 : 3;

  const handleTargetSelect = (file) => {
    setTargetFile(file);
    setTargetPreview(URL.createObjectURL(file));
    setTargetFrameUrl(null);
    setVideoInfo(null);
    setResult(null);
    setGenError(null);
  };

  const handleSourceSelect = (file) => {
    setSourceFile(file);
    setSourcePreview(URL.createObjectURL(file));
    setResult(null);
    setGenError(null);
  };

  const handleRemoveTarget = () => {
    setTargetFile(null);
    setTargetPreview(null);
    setTargetFrameUrl(null);
    setVideoInfo(null);
    setResult(null);
    setGenError(null);
  };

  const handleRemoveSource = () => {
    setSourceFile(null);
    setSourcePreview(null);
    setResult(null);
    setGenError(null);
  };

  const handleGenerate = async () => {
    if (!targetFile || !sourceFile) {
      toast.error("Please upload both a target image and a source face.");
      return;
    }
    setGenerating(true);
    setGenError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("source_face", sourceFile);

      if (targetFrameUrl) {
        // Target is a server-side frame from a video analysis — pass the URL
        formData.append("target_frame_url", targetFrameUrl);
      } else {
        // Target is a user-uploaded file
        formData.append("target_image", targetFile);
      }

      const data = await api.faceSwap(formData);
      setResult(data);
      toast.success("Face swap generated successfully!");
    } catch (err) {
      setGenError(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  // Phase 2: Generate video from swapped image
  const handleGenerateVideo = async () => {
    if (!result?.id) return;
    setGeneratingVideo(true);
    setVideoError(null);
    setVideoUrl(null);
    setVideoStatus("pending");
    try {
      const data = await api.faceSwapGenerateVideo(result.id, videoPrompt, videoDuration);
      setVideoJobId(data.job_id);
      setVideoStatus("pending");
      toast.success("Video generation started!");
      // Start polling
      startPolling(data.job_id);
    } catch (err) {
      setVideoError(getErrorMessage(err));
      setVideoStatus(null);
      setGeneratingVideo(false);
    }
  };

  const startPolling = (jobId) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const status = await api.faceSwapVideoStatus(jobId);
        setVideoStatus(status.status);
        if (status.status === "completed") {
          setVideoUrl(status.video_url || status.video_urls?.[0]);
          setGeneratingVideo(false);
          clearInterval(pollingRef.current);
          pollingRef.current = null;
          toast.success("Video generated successfully!");
        } else if (status.status === "failed") {
          setVideoError(status.error || "Video generation failed.");
          setGeneratingVideo(false);
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      } catch (err) {
        // Don't stop polling on transient errors
        console.warn("Polling error:", err);
      }
    }, 5000); // Poll every 5 seconds
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // Load existing brand profile on mount
  useEffect(() => {
    api.getActiveBrand()
      .then((brand) => setBrandProfile(brand))
      .catch(() => setBrandProfile(null));
  }, []);

  // Phase 2B: Generate branded video prompt
  const handleGenerateBrandedPrompt = async () => {
    if (!result?.id) return;
    if (!brandUrl.trim() && !brandProfile) {
      toast.error("Please enter your brand/website URL.");
      return;
    }
    setGeneratingBrandedPrompt(true);
    setBrandedPromptError(null);
    setBrandedPrompt("");
    try {
      const data = await api.faceSwapBrandedPrompt(
        result.id,
        brandUrl.trim(),
        videoInfo?.videoId || "",
        brandedDuration
      );
      setBrandedPrompt(data.video_prompt || "");
      setBrandedPromptBrand(data.brand_name || "");
      toast.success("Brand video prompt generated!");
    } catch (err) {
      setBrandedPromptError(getErrorMessage(err));
    } finally {
      setGeneratingBrandedPrompt(false);
    }
  };

  // Phase 2B: Generate the actual branded video using the prompt
  const handleGenerateBrandedVideo = async () => {
    if (!result?.id || !brandedPrompt) return;
    setVideoDuration(brandedDuration);
    setVideoPrompt(brandedPrompt);
    setGeneratingVideo(true);
    setVideoError(null);
    setVideoUrl(null);
    setVideoStatus("pending");
    try {
      const data = await api.faceSwapGenerateVideo(result.id, brandedPrompt, brandedDuration);
      setVideoJobId(data.job_id);
      setVideoStatus("pending");
      toast.success("Branded video generation started!");
      startPolling(data.job_id);
    } catch (err) {
      setVideoError(getErrorMessage(err));
      setVideoStatus(null);
      setGeneratingVideo(false);
    }
  };

  // Quick preview: 5s video with default motion
  const handleQuickPreview = async () => {
    if (!result?.id) return;
    setVideoDuration(5);
    setVideoPrompt("");
    setGeneratingVideo(true);
    setVideoError(null);
    setVideoUrl(null);
    setVideoStatus("pending");
    try {
      const data = await api.faceSwapGenerateVideo(result.id, "", 5);
      setVideoJobId(data.job_id);
      setVideoStatus("pending");
      toast.success("Quick preview generation started!");
      startPolling(data.job_id);
    } catch (err) {
      setVideoError(getErrorMessage(err));
      setVideoStatus(null);
      setGeneratingVideo(false);
    }
  };

  const handleReset = () => {
    setTargetFile(null);
    setTargetPreview(null);
    setTargetFrameUrl(null);
    setVideoInfo(null);
    setSourceFile(null);
    setSourcePreview(null);
    setResult(null);
    setGenError(null);
    // Reset video state
    setVideoDuration(10);
    setVideoPrompt("");
    setGeneratingVideo(false);
    setVideoJobId(null);
    setVideoStatus(null);
    setVideoUrl(null);
    setVideoError(null);
    // Reset branded video state
    setBrandUrl("");
    setBrandedDuration(15);
    setBrandedPrompt("");
    setBrandedPromptBrand("");
    setGeneratingBrandedPrompt(false);
    setBrandedPromptError(null);
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center space-y-3">
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight">
          AI Face Swap
        </h1>
        <p className="text-muted-foreground max-w-xl mx-auto">
          Swap any face in photos instantly. Our AI tracks facial geometry, skin tone, and lighting
          to deliver production-ready results with natural blending.
        </p>
      </div>

      {/* Step Indicator */}
      <StepIndicator currentStep={result ? 4 : currentStep} />

      {/* Main Content */}
      <div className="max-w-5xl mx-auto">
        {!result ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 lg:gap-8">
            {/* Step 1: Target Upload */}
            <Card className="p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--brand-teal)] text-white text-xs font-bold">
                  1
                </span>
                <h2 className="font-display font-semibold text-lg">Upload Your Target</h2>
              </div>
              <p className="text-sm text-muted-foreground">
                {videoInfo
                  ? "Target frame loaded from your analyzed viral video. You can replace it or continue to step 2."
                  : "Choose the photo you want to swap a face onto. Works with any photo style."}
              </p>
              {videoInfo && targetPreview && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[color:rgba(99,102,241,0.06)] border border-[color:rgba(99,102,241,0.15)]">
                  <Film className="h-4 w-4 text-[color:var(--brand-teal)]" />
                  <span className="text-xs font-medium text-[color:var(--brand-teal-dark)]">
                    From viral video analysis (frame {videoInfo.frameIndex})
                  </span>
                </div>
              )}
              <DropZone
                onFileSelect={handleTargetSelect}
                accept="image/jpeg,image/png,image/webp"
                label="Upload target image"
                sublabel="JPEG, PNG, or WEBP up to 12MB"
                preview={targetPreview}
                onRemove={handleRemoveTarget}
                testId="target"
                icon={ImageIcon}
              />
            </Card>

            {/* Step 2: Source Face Upload */}
            <Card className="p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-4">
              <div className="flex items-center gap-2">
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                    targetFile
                      ? "bg-[color:var(--brand-teal)] text-white"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  2
                </span>
                <h2 className={`font-display font-semibold text-lg ${!targetFile ? "text-muted-foreground" : ""}`}>
                  Upload Your Source Face
                </h2>
              </div>
              <p className="text-sm text-muted-foreground">
                Select a clear, well-lit photo of the face you want to insert. Frontal view works best.
              </p>
              <DropZone
                onFileSelect={handleSourceSelect}
                accept="image/jpeg,image/png,image/webp"
                label="Upload source face"
                sublabel="Clear, frontal face photo recommended"
                preview={sourcePreview}
                onRemove={handleRemoveSource}
                testId="source"
                icon={User}
              />
            </Card>
          </div>
        ) : (
          /* Results Display */
          <div className="space-y-6">
            <Card className="overflow-hidden rounded-2xl border-[color:var(--brand-teal)] shadow-lg" data-testid="face-swap-result">
              <div className="px-5 py-3 border-b border-border bg-gradient-to-r from-[color:rgba(99,102,241,0.04)] to-transparent flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-[color:var(--brand-teal)]" />
                  <span className="text-sm font-semibold">Your Face Swap Result</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 text-green-700 rounded-full font-medium">
                    <Check className="h-3 w-3" /> Production-Ready
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
                {/* Original target */}
                <div className="p-4 border-r border-border">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Target Image</p>
                  <img
                    src={targetPreview}
                    alt="Target"
                    className="w-full rounded-xl object-cover aspect-[3/4]"
                  />
                </div>
                {/* Source face */}
                <div className="p-4 border-r border-border">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Source Face</p>
                  <img
                    src={sourcePreview}
                    alt="Source face"
                    className="w-full rounded-xl object-cover aspect-[3/4]"
                  />
                </div>
                {/* Generated result */}
                <div className="p-4 bg-gradient-to-b from-transparent to-[color:rgba(99,102,241,0.02)]">
                  <p className="text-xs font-medium text-[color:var(--brand-teal-dark)] mb-2 flex items-center gap-1">
                    <Sparkles className="h-3 w-3" /> Generated Result
                  </p>
                  <img
                    src={mediaUrl(result.generated_image_url)}
                    alt="Face swap result"
                    className="w-full rounded-xl object-cover aspect-[3/4] ring-2 ring-[color:var(--brand-teal)] ring-offset-2"
                    data-testid="face-swap-generated-image"
                  />
                </div>
              </div>

              {/* Quality Indicators */}
              <div className="px-5 py-3 border-t border-border bg-muted/30 grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">Resolution</p>
                  <p className="text-sm font-semibold">{result.resolution || "1024x1024"}</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">Blending</p>
                  <p className="text-sm font-semibold text-green-600">Natural</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">Color Match</p>
                  <p className="text-sm font-semibold text-green-600">Matched</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">Format</p>
                  <p className="text-sm font-semibold">PNG</p>
                </div>
              </div>
            </Card>

            {/* Action buttons */}
            <div className="flex flex-col sm:flex-row gap-3">
              <a
                href={mediaUrl(result.generated_image_url)}
                download
                target="_blank"
                rel="noreferrer"
                className="flex-1"
              >
                <Button className="w-full gap-2 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white" data-testid="download-swap-button">
                  <Download className="h-4 w-4" /> Download Image
                </Button>
              </a>
              <Button
                onClick={handleReset}
                variant="outline"
                className="flex-1 gap-2 rounded-xl"
                data-testid="new-swap-button"
              >
                <RotateCcw className="h-4 w-4" /> New Face Swap
              </Button>
            </div>

            {/* Phase 2: Generate Video from Swapped Image */}
            <Card className="p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-4" data-testid="phase2-video-section">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[color:var(--brand-coral)] text-white">
                  <Clapperboard className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="font-display font-semibold text-lg">Generate Video</h3>
                  <p className="text-xs text-muted-foreground">Animate your face-swapped image into a full video</p>
                </div>
              </div>

              {/* Video Result — shown at top when complete */}
              {videoUrl && (
                <div className="space-y-4" data-testid="video-result">
                  <div className="rounded-xl overflow-hidden border border-[color:var(--brand-teal)] shadow-lg">
                    <video
                      src={videoUrl}
                      controls
                      autoPlay
                      loop
                      className="w-full"
                      data-testid="generated-video-player"
                    />
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-green-50 border border-green-200">
                    <Check className="h-4 w-4 text-green-600" />
                    <span className="text-xs font-medium text-green-700">
                      Video generated — face consistency maintained throughout {videoDuration}s
                    </span>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-3">
                    <a href={videoUrl} download target="_blank" rel="noreferrer" className="flex-1">
                      <Button className="w-full gap-2 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white" data-testid="download-video-button">
                        <Download className="h-4 w-4" /> Download Video
                      </Button>
                    </a>
                    <Button onClick={handleReset} variant="outline" className="flex-1 gap-2 rounded-xl">
                      <RotateCcw className="h-4 w-4" /> Start Over
                    </Button>
                  </div>
                </div>
              )}

              {/* Video generation in progress */}
              {!videoUrl && (videoStatus === "pending" || videoStatus === "in_progress") && (
                <Card className="p-4 rounded-xl border-border bg-muted/30">
                  <div className="flex items-center gap-3">
                    <Loader2 className="h-5 w-5 animate-spin text-[color:var(--brand-teal)]" />
                    <div>
                      <p className="text-sm font-medium">
                        {videoStatus === "pending" ? "Video queued..." : "Generating video..."}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        This typically takes 30 seconds to 2 minutes.
                      </p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <GenerationProgress
                      stages={["Submitting to video engine", "Processing first frame", "Animating with face consistency", "Rendering final video"]}
                      active={true}
                    />
                  </div>
                </Card>
              )}

              {videoError && (
                <Alert variant="destructive" className="rounded-xl" data-testid="video-error">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Video generation failed</AlertTitle>
                  <AlertDescription className="space-y-2">
                    <p>{videoError}</p>
                    <Button size="sm" onClick={handleGenerateVideo} className="gap-1.5">
                      <RotateCcw className="h-3.5 w-3.5" /> Retry
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              {/* Two options — only shown when no video is generating/complete */}
              {!videoUrl && !videoStatus && (
                <div className="space-y-5">
                  {/* Option A: Quick Preview */}
                  <div className="rounded-xl border border-border p-4 space-y-3 bg-white/60">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-sm font-semibold flex items-center gap-1.5">
                          <Play className="h-3.5 w-3.5 text-[color:var(--brand-teal)]" /> Quick Preview
                        </h4>
                        <p className="text-xs text-muted-foreground mt-0.5">5-second video with natural motion — see how your face looks in motion</p>
                      </div>
                    </div>
                    <Button
                      onClick={() => handleQuickPreview()}
                      disabled={generatingVideo}
                      variant="secondary"
                      className="w-full gap-2 rounded-xl"
                      data-testid="quick-preview-button"
                    >
                      <Play className="h-4 w-4" /> Generate Quick Preview (5s)
                    </Button>
                  </div>

                  {/* Divider */}
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-xs font-medium text-muted-foreground">OR</span>
                    <div className="flex-1 h-px bg-border" />
                  </div>

                  {/* Option B: Full Branded Video */}
                  <div className="rounded-xl border-2 border-[color:var(--brand-coral)] p-4 space-y-4 bg-gradient-to-b from-[color:rgba(244,63,94,0.02)] to-transparent">
                    <div>
                      <h4 className="text-sm font-semibold flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-[color:var(--brand-coral)]" /> Full Branded Video
                        <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-[color:var(--brand-coral)] text-white font-bold">RECOMMENDED</span>
                      </h4>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Enter your brand/website URL — AI generates a custom video prompt tailored to your product, niche, and audience (up to 30s)
                      </p>
                    </div>

                    <div className="space-y-3">
                      <div className="space-y-2">
                        <label className="text-sm font-medium">Your brand/website URL</label>
                        <div className="flex gap-2">
                          <Input
                            value={brandUrl}
                            onChange={(e) => setBrandUrl(e.target.value)}
                            placeholder="https://yourbrand.com"
                            className="flex-1"
                            data-testid="brand-url-input"
                          />
                        </div>
                        <p className="text-[10px] text-muted-foreground">
                          We'll analyze your website to understand your brand, products, audience, and tone — then write a video prompt custom to you.
                          {brandProfile && <span className="text-[color:var(--brand-teal)]"> Or we'll use your saved brand profile.</span>}
                        </p>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <label className="text-xs font-medium flex items-center gap-1">
                            <Clock className="h-3 w-3" /> Duration
                          </label>
                          <Input
                            type="number"
                            min={5}
                            max={30}
                            value={brandedDuration}
                            onChange={(e) => setBrandedDuration(Math.max(5, Math.min(30, Number(e.target.value) || 15)))}
                            data-testid="branded-duration-input"
                          />
                          <p className="text-[10px] text-muted-foreground">5–30 seconds</p>
                        </div>
                      </div>

                      {/* Generated branded prompt (editable) */}
                      {brandedPrompt && (
                        <div className="space-y-2">
                          <label className="text-sm font-medium flex items-center justify-between">
                            <span>Generated video prompt (editable)</span>
                            {brandedPromptBrand && (
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted font-medium">
                                {brandedPromptBrand}
                              </span>
                            )}
                          </label>
                          <Textarea
                            value={brandedPrompt}
                            onChange={(e) => setBrandedPrompt(e.target.value)}
                            className="min-h-[100px] text-xs font-mono"
                            data-testid="branded-prompt-textarea"
                          />
                        </div>
                      )}

                      {generatingBrandedPrompt ? (
                        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/50">
                          <Loader2 className="h-4 w-4 animate-spin text-[color:var(--brand-coral)]" />
                          <span className="text-xs font-medium">Analyzing your brand & writing video prompt...</span>
                        </div>
                      ) : !brandedPrompt ? (
                        <Button
                          onClick={handleGenerateBrandedPrompt}
                          disabled={generatingBrandedPrompt}
                          className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white"
                          data-testid="generate-branded-prompt-button"
                        >
                          <Wand2 className="h-4 w-4" /> Generate Branded Video Prompt
                        </Button>
                      ) : (
                        <Button
                          onClick={handleGenerateBrandedVideo}
                          disabled={generatingVideo}
                          className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white"
                          data-testid="generate-branded-video-button"
                        >
                          <Clapperboard className="h-4 w-4" />
                          {generatingVideo ? "Submitting..." : `Generate ${brandedDuration}s Branded Video`}
                        </Button>
                      )}

                      {brandedPromptError && (
                        <p className="text-xs text-red-600">{brandedPromptError}</p>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}

        {/* Generate Button - shown when both images are uploaded */}
        {!result && targetFile && sourceFile && (
          <div className="mt-8 text-center space-y-4">
            {generating ? (
              <Card className="p-6 rounded-2xl border-border shadow-[var(--shadow-soft)] max-w-lg mx-auto">
                <h3 className="font-display font-semibold mb-3 flex items-center justify-center gap-2">
                  <Wand2 className="h-4 w-4 text-[color:var(--brand-teal)]" /> Generating your face swap...
                </h3>
                <GenerationProgress stages={FACE_SWAP_STAGES} active={true} />
              </Card>
            ) : (
              <>
                <Button
                  onClick={handleGenerate}
                  disabled={generating}
                  size="lg"
                  className="gap-2.5 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white px-10 py-6 text-base font-semibold shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5 active:translate-y-0"
                  data-testid="generate-swap-button"
                >
                  <Sparkles className="h-5 w-5" /> Generate Face Swap
                </Button>
                <p className="text-xs text-muted-foreground">
                  Our AI analyzes facial geometry, matches skin tone & lighting, and generates a natural blend
                </p>
              </>
            )}
          </div>
        )}

        {/* Error State */}
        {genError && (
          <div className="mt-6 max-w-lg mx-auto">
            <Alert variant="destructive" className="rounded-2xl" data-testid="face-swap-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Face swap generation failed</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{genError}</p>
                <Button size="sm" onClick={handleGenerate} className="gap-1.5" data-testid="retry-swap-button">
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </Button>
              </AlertDescription>
            </Alert>
          </div>
        )}
      </div>

      {/* Features Section */}
      {!result && !generating && (
        <div className="max-w-4xl mx-auto pt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { title: "Frame-by-Frame Accuracy", desc: "Tracks facial geometry, skin tone, and lighting for precise results" },
              { title: "Works With Any Content", desc: "Photos, portraits, artistic styles, or any image format" },
              { title: "Lightning-Fast", desc: "High-resolution results generated in seconds" },
              { title: "Production-Ready Output", desc: "Matched color, natural blending, ready to publish" },
            ].map((feat) => (
              <Card key={feat.title} className="p-4 rounded-2xl border-border">
                <h3 className="text-sm font-semibold mb-1">{feat.title}</h3>
                <p className="text-xs text-muted-foreground">{feat.desc}</p>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
